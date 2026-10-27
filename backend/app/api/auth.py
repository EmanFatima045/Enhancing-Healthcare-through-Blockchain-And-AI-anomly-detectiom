"""Authentication, revocable sessions, and administrator-managed staff accounts."""

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from ..core.auth import current_user, require_roles
from ..core.database import get_db
from ..core.security import (client_ip, decode_token, hash_password, issue_session,
                             privacy_hash, recent_attempt_count, record_attempt, verify_password)
from ..core.crypto import validate_rsa_public_key
from ..core.config import settings
from ..ml.application_detection import ids_engine
from ..ml.features import application_features
from ..models import AuditEvent, PasswordResetToken, Session, User, UserKey
from ..services.outbox import enqueue

router = APIRouter(prefix="/auth", tags=["Authentication"])
EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, min_length=6, max_length=30)
    role: Literal["Patient"] = "Patient"

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL.fullmatch(value):
            raise ValueError("Enter a valid email address")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class StaffRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    name: str = Field(min_length=2, max_length=120)
    role: Literal["Doctor", "HospitalAdmin", "SecurityAuditor"]
    phone: str | None = Field(default=None, max_length=30)
    wallet_address: str | None = Field(default=None, pattern=r"^0x[a-fA-F0-9]{40}$")


class PublicKeyRequest(BaseModel):
    algorithm: Literal["RSA-OAEP-SHA-256"] = "RSA-OAEP-SHA-256"
    public_key_spki_b64: str = Field(min_length=512, max_length=2048)


class ProfileUpdateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, min_length=6, max_length=30)

    @field_validator("name")
    @classmethod
    def normalized_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Name must contain at least two non-space characters")
        return value

    @field_validator("phone")
    @classmethod
    def normalized_phone(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        if value is not None and len(value) < 6:
            raise ValueError("Phone number is too short")
        return value


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=10, max_length=128)


def public_user(user: User) -> dict:
    return {"email": user.email, "name": user.name, "role": user.role, "phone": user.phone,
            "wallet_address": user.wallet_address, "is_verified": user.is_verified}


@router.post("/register", status_code=201)
def register(req: RegisterRequest, db: DbSession = Depends(get_db)):
    user = User(email=req.email, name=req.name.strip(), phone=req.phone, password_hash=hash_password(req.password),
                role="Patient", is_verified=True)
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Account with this email already exists") from exc
    db.add(AuditEvent(actor_email=req.email, action="PATIENT_REGISTERED", resource_type="user",
                      resource_id=req.email, outcome="SUCCESS", metadata_json={}))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Account with this email already exists") from exc
    return {"message": "Patient account created", "user": public_user(user)}


@router.post("/login")
def login(req: LoginRequest, request: Request, db: DbSession = Depends(get_db)):
    email = req.email.strip().lower()
    ip = client_ip(request)
    ip_digest, email_digest = privacy_hash(ip), privacy_hash(email)
    attempts = recent_attempt_count(db, ip_digest, email_digest)
    if not settings.TESTING and attempts >= 10:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again after five minutes.", headers={"Retry-After": "300"})

    features = application_features(db, ip_digest, email_digest, request.headers.get("user-agent", ""), len(req.password), email)
    preliminary = ids_engine.predict(features, enforced_action="PENDING_POLICY")
    if not settings.TESTING and preliminary["suggested_action"] == "DENY":
        record_attempt(db, ip_digest, email_digest, False); db.commit()
        raise HTTPException(status_code=429, detail={"message":"Request denied by local abuse policy","detection":{**preliminary,"enforced_action":"DENY"}}, headers={"Retry-After":"300"})
    verdict = {**preliminary, "enforced_action": "THROTTLE" if preliminary["suggested_action"] == "THROTTLE" else "ALLOW"}
    user = db.get(User, email)
    valid = bool(user and user.is_active and verify_password(req.password, user.password_hash))
    record_attempt(db, ip_digest, email_digest, valid)
    if not valid:
        db.commit()
        raise HTTPException(status_code=401, detail={"message": "Invalid email or password", "ai_threat_evaluation": verdict})
    if not user.is_verified:
        db.commit()
        raise HTTPException(status_code=403, detail="Account is pending administrator verification")

    token, expires = issue_session(db, user, ip)
    db.add(AuditEvent(actor_email=user.email, action="LOGIN", resource_type="session", outcome="SUCCESS",
                      metadata_json={"ip_hash": ip_digest}))
    db.commit()
    return {"access_token": token, "token_type": "bearer", "expires_at": expires,
            "user": public_user(user), "ai_ids_verdict": verdict}


@router.post("/logout", status_code=204)
def logout(authorization: Annotated[str | None, Header()] = None, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    claims = decode_token((authorization or "")[7:])
    session = db.get(Session, claims["jti"])
    if session:
        from ..models import utcnow
        session.revoked_at = utcnow()
    db.add(AuditEvent(actor_email=user.email, action="LOGOUT", resource_type="session",
                      resource_id=claims["jti"], outcome="SUCCESS", metadata_json={}))
    db.commit()


@router.get("/me")
def get_current_user(user: User = Depends(current_user)):
    return public_user(user)


@router.patch("/me")
def update_current_user(req: ProfileUpdateRequest, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    user.name = req.name.strip()
    user.phone = req.phone.strip() if req.phone else None
    db.add(AuditEvent(actor_email=user.email, action="PROFILE_UPDATED", resource_type="user",
                      resource_id=user.email, outcome="SUCCESS", metadata_json={"fields": ["name", "phone"]}))
    db.commit()
    return public_user(user)


@router.post("/password-reset/request", status_code=202)
def request_password_reset(req: PasswordResetRequest, db: DbSession = Depends(get_db)):
    email = req.email.strip().lower()
    user = db.get(User, email)
    # Always return the same response to prevent account enumeration.
    if user and user.is_active:
        now = datetime.now(timezone.utc)
        raw_token = secrets.token_urlsafe(48)
        item = PasswordResetToken(user_email=email, token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
                                  expires_at=now + timedelta(minutes=30))
        db.add(item)
        db.flush()
        enqueue(db, "NOTIFICATION", f"password-reset:{item.id}",
                {"recipient": email, "kind": "PASSWORD_RESET", "reset_token": raw_token,
                 "expires_at": item.expires_at.isoformat()})
        db.add(AuditEvent(actor_email=email, action="PASSWORD_RESET_REQUESTED", resource_type="user",
                          resource_id=email, outcome="QUEUED", metadata_json={}))
        db.commit()
    return {"message": "If the account exists, password recovery instructions have been queued."}


@router.post("/password-reset/confirm")
def confirm_password_reset(req: PasswordResetConfirm, db: DbSession = Depends(get_db)):
    token_hash = hashlib.sha256(req.token.encode()).hexdigest()
    item = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    now = datetime.now(timezone.utc)
    expires = item.expires_at.replace(tzinfo=timezone.utc) if item and item.expires_at.tzinfo is None else item.expires_at if item else now
    if not item or item.used_at or expires <= now:
        raise HTTPException(status_code=400, detail="Reset token is invalid or expired")
    user = db.get(User, item.user_email)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Reset token is invalid or expired")
    user.password_hash = hash_password(req.password)
    item.used_at = now
    for session in db.scalars(select(Session).where(Session.user_email == user.email, Session.revoked_at.is_(None))):
        session.revoked_at = now
    db.add(AuditEvent(actor_email=user.email, action="PASSWORD_RESET_COMPLETED", resource_type="user",
                      resource_id=user.email, outcome="SUCCESS", metadata_json={}))
    db.commit()
    return {"message": "Password reset completed. Please sign in again."}


@router.get("/users")
def list_users(offset: int = 0, limit: int = 50,
               _: User = Depends(require_roles("HospitalAdmin")), db: DbSession = Depends(get_db)):
    limit = min(max(limit, 1), 100)
    users = db.scalars(select(User).order_by(User.created_at.desc()).offset(max(offset, 0)).limit(limit)).all()
    return {"items": [public_user(user) for user in users], "offset": max(offset, 0), "limit": limit}


@router.post("/staff", status_code=201)
def create_staff(req: StaffRequest, admin: User = Depends(require_roles("HospitalAdmin")), db: DbSession = Depends(get_db)):
    email = req.email.strip().lower()
    user = User(email=email, name=req.name.strip(), phone=req.phone, password_hash=hash_password(req.password),
                role=req.role, wallet_address=req.wallet_address, public_key=None, is_verified=False)
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Staff account or wallet already exists") from exc
    db.add(AuditEvent(actor_email=admin.email, action="STAFF_CREATED", resource_type="user",
                      resource_id=email, outcome="PENDING_APPROVAL", metadata_json={"role": req.role}))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Staff account or wallet already exists") from exc
    return public_user(user)


@router.post("/staff/{email}/approve")
def approve_staff(email: str, admin: User = Depends(require_roles("HospitalAdmin")), db: DbSession = Depends(get_db)):
    user = db.get(User, email.strip().lower())
    if not user or user.role == "Patient":
        raise HTTPException(status_code=404, detail="Pending staff account not found")
    user.is_verified = True
    db.add(AuditEvent(actor_email=admin.email, action="STAFF_APPROVED", resource_type="user",
                      resource_id=user.email, outcome="SUCCESS", metadata_json={"role": user.role}))
    if user.wallet_address:
        enqueue(db, "STAFF_REGISTER", f"staff-register:{user.email}:{user.wallet_address.lower()}",
                {"wallet": user.wallet_address, "role": user.role})
    db.commit()
    return public_user(user)


@router.post("/staff/{email}/suspend")
def suspend_staff(email: str, admin: User = Depends(require_roles("HospitalAdmin")), db: DbSession = Depends(get_db)):
    user = db.get(User, email.strip().lower())
    if not user or user.role == "Patient" or user.email == admin.email:
        raise HTTPException(status_code=404, detail="Suspendable staff account not found")
    user.is_active = False
    db.add(AuditEvent(actor_email=admin.email, action="STAFF_SUSPENDED", resource_type="user",
                      resource_id=user.email, outcome="SUCCESS", metadata_json={"role": user.role}))
    db.commit()
    return public_user(user)


def public_key_output(key: UserKey) -> dict:
    return {"version": key.version, "algorithm": key.algorithm,
            "public_key_spki_b64": key.public_key_spki_b64,
            "fingerprint_sha256": key.fingerprint_sha256, "key_size": key.key_size,
            "created_at": key.created_at}


@router.post("/keys", status_code=201)
def register_public_key(req: PublicKeyRequest, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    try:
        fingerprint, key_size = validate_rsa_public_key(req.public_key_spki_b64)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    existing = db.scalar(select(UserKey).where(UserKey.fingerprint_sha256 == fingerprint))
    if existing:
        if existing.user_email != user.email:
            raise HTTPException(status_code=409, detail="This public key belongs to another account")
        return public_key_output(existing)
    for key in db.scalars(select(UserKey).where(UserKey.user_email == user.email, UserKey.is_active.is_(True))):
        key.is_active = False
    version = int(db.scalar(select(func.max(UserKey.version)).where(UserKey.user_email == user.email)) or 0) + 1
    key = UserKey(user_email=user.email, version=version, public_key_spki_b64=req.public_key_spki_b64,
                  fingerprint_sha256=fingerprint, key_size=key_size, is_active=True)
    db.add(key)
    db.add(AuditEvent(actor_email=user.email, action="RSA_PUBLIC_KEY_REGISTERED", resource_type="user_key",
                      resource_id=key.id, outcome="SUCCESS", metadata_json={"version": version, "fingerprint": fingerprint}))
    db.commit()
    return public_key_output(key)


@router.get("/keys/me")
def my_public_key(user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    key = db.scalar(select(UserKey).where(UserKey.user_email == user.email, UserKey.is_active.is_(True)))
    if not key:
        raise HTTPException(status_code=404, detail="No active RSA decryption key is registered")
    return public_key_output(key)


@router.get("/recipients")
def recipients(role: Literal["Doctor"] = "Doctor", user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    rows = db.execute(select(User, UserKey).join(UserKey, UserKey.user_email == User.email).where(
        User.role == role, User.is_verified.is_(True), User.is_active.is_(True), UserKey.is_active.is_(True)
    ).order_by(User.name)).all()
    return {"items": [{"email": recipient.email, "name": recipient.name, "role": recipient.role,
                        "key": public_key_output(key)} for recipient, key in rows]}

@router.get("/emergency-escrow-key")
def emergency_escrow_key(user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    if not settings.EMERGENCY_ESCROW_EMAIL: raise HTTPException(404, "Emergency escrow is not configured")
    escrow = db.get(User, settings.EMERGENCY_ESCROW_EMAIL)
    key = db.scalar(select(UserKey).where(UserKey.user_email == settings.EMERGENCY_ESCROW_EMAIL, UserKey.is_active.is_(True)))
    if not escrow or not escrow.is_active or not key: raise HTTPException(503, "Emergency escrow public key is unavailable")
    return {"email": escrow.email, "key": public_key_output(key), "trust_boundary": "The institution can unwrap emergency data keys using its separately stored escrow private key."}


# Backward-compatible import name for older modules while they migrate.
require_user = current_user
