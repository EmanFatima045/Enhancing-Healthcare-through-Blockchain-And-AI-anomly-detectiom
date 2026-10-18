"""Versioned encrypted records and recipient-specific key delivery."""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session as DbSession

from ..core.auth import verified_user
from ..core.database import get_db
from ..core.envelopes import KeyEnvelope, RecordEnvelope, canonical_bytes
from ..models import (AuditEvent, ConsentProjection, EncryptedEnvelope, MedicalRecord,
                      RecordVersion, User, UserKey)
from ..services.ciphertext_storage import ciphertext_storage
from ..services.blockchain_service import BlockchainUnavailable, blockchain_service
from ..services.outbox import enqueue

router = APIRouter(prefix="/records", tags=["Medical Records & Consent"])


class RecipientEnvelope(BaseModel):
    recipient_email: str = Field(min_length=5, max_length=254)
    envelope: KeyEnvelope


class RecordUploadRequest(BaseModel):
    record_id: str = Field(pattern=r"^REC-[A-F0-9]{32}$")
    title: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9 _-]+$")
    envelope: RecordEnvelope
    key_envelopes: list[RecipientEnvelope] = Field(min_length=1, max_length=101)


class VersionUploadRequest(BaseModel):
    envelope: RecordEnvelope
    key_envelopes: list[RecipientEnvelope] = Field(min_length=1, max_length=101)


class AddKeyEnvelopeRequest(BaseModel):
    recipient_email: str = Field(min_length=5, max_length=254)
    envelope: KeyEnvelope


class GrantConsentRequest(BaseModel):
    practitioner_email: str = Field(min_length=5, max_length=254)
    category: str = Field(min_length=2, max_length=64)
    access_level: Literal["ReadOnly", "ReadAndWrite"] = "ReadOnly"
    duration_hours: int = Field(ge=1, le=24 * 365)


class RevokeConsentRequest(BaseModel):
    practitioner_email: str = Field(min_length=5, max_length=254)
    category: str = Field(min_length=2, max_length=64)


def metadata(record: MedicalRecord) -> dict:
    return {"record_id": record.id, "title": record.title, "category": record.category,
            "envelope_digest": record.data_hash, "storage_status": record.storage_kind,
            "cid": record.cid, "is_archived": record.is_archived, "created_at": record.created_at}


def active_consent(db: DbSession, record: MedicalRecord, user: User) -> ConsentProjection | None:
    now = datetime.now(timezone.utc)
    base = (ConsentProjection.patient_email == record.patient_email,
            ConsentProjection.practitioner_email == user.email,
            ConsentProjection.status == "CONFIRMED",
            ConsentProjection.valid_until > now)
    exact = db.scalar(select(ConsentProjection).where(*base, ConsentProjection.category == record.category)
                      .order_by(ConsentProjection.created_at.desc()).limit(1))
    projection = exact or db.scalar(select(ConsentProjection).where(*base, ConsentProjection.category == "ALL")
                                    .order_by(ConsentProjection.created_at.desc()).limit(1))
    if projection and projection.source == "CHAIN":
        patient = db.get(User, record.patient_email)
        if not patient or not patient.wallet_address or not user.wallet_address: return None
        try:
            active, level = blockchain_service.resolve_consent(patient.wallet_address, user.wallet_address, record.category)
        except BlockchainUnavailable:
            return None
        required = 1
        if not active or level < required: return None
    return projection


def can_read(db: DbSession, record: MedicalRecord, user: User) -> bool:
    return record.patient_email == user.email or (user.role == "Doctor" and active_consent(db, record, user) is not None)


def validate_key_envelope(db: DbSession, item: RecipientEnvelope, record_id: str, version: int) -> tuple[User, UserKey]:
    email = item.recipient_email.strip().lower()
    if item.envelope.record_id != record_id or item.envelope.record_version != version:
        raise HTTPException(status_code=422, detail="Key envelope record identifier/version mismatch")
    recipient = db.get(User, email)
    if not recipient or not recipient.is_active or not recipient.is_verified:
        raise HTTPException(status_code=422, detail=f"Verified recipient not found: {email}")
    key = db.scalar(select(UserKey).where(UserKey.user_email == email,
                                         UserKey.version == item.envelope.recipient_key_version))
    if not key or not key.is_active:
        raise HTTPException(status_code=422, detail=f"Recipient RSA key version not found: {email}")
    if recipient.role not in ("Patient", "Doctor"):
        raise HTTPException(status_code=422, detail="Only patient and doctor recipient keys are supported")
    return recipient, key


def persist_version(db: DbSession, record: MedicalRecord, version_number: int,
                    envelope: RecordEnvelope, recipients: list[RecipientEnvelope], actor: User) -> RecordVersion:
    if envelope.aad.record_id != record.id or envelope.aad.record_version != version_number:
        raise HTTPException(status_code=422, detail="Record envelope AAD identifier/version mismatch")
    if envelope.key_version != version_number:
        raise HTTPException(status_code=422, detail="A fresh data-key version is required for every record version")
    normalized = {item.recipient_email.strip().lower(): item for item in recipients}
    if actor.email not in normalized:
        raise HTTPException(status_code=422, detail="The patient must have a recipient key envelope")
    active_recipients = set(db.scalars(select(ConsentProjection.practitioner_email).where(
        ConsentProjection.patient_email == actor.email,
        or_(ConsentProjection.category == record.category, ConsentProjection.category == "ALL"),
        ConsentProjection.status == "CONFIRMED",
        ConsentProjection.valid_until > datetime.now(timezone.utc),
    )))
    missing = active_recipients - set(normalized)
    if missing:
        raise HTTPException(status_code=422, detail="New versions require envelopes for every active consent recipient")
    version = RecordVersion(record=record, version=version_number,
                            ciphertext_b64=envelope.ciphertext_b64, nonce_b64=envelope.nonce_b64,
                            data_hash=envelope.digest.removeprefix("sha256:"), envelope_json=envelope.model_dump(mode="json"),
                            envelope_digest=envelope.digest, key_version=envelope.key_version, created_by=actor.email)
    db.add(version); db.flush()
    for email, item in normalized.items():
        _, key = validate_key_envelope(db, item, record.id, version_number)
        db.add(EncryptedEnvelope(record_version_id=version.id, recipient_email=email,
                                 wrapped_key=item.envelope.wrapped_key_b64, algorithm=item.envelope.wrapping,
                                 recipient_key_version=key.version, envelope_json=item.envelope.model_dump(mode="json"),
                                 envelope_digest=item.envelope.digest))
    return version


@router.post("/upload", status_code=201)
def upload_record(req: RecordUploadRequest,
                  idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
                  user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    if user.role != "Patient":
        raise HTTPException(status_code=403, detail="Patients may upload records only to their own account")
    existing = db.get(MedicalRecord, req.record_id)
    if existing:
        if existing.patient_email == user.email and idempotency_key:
            return {"message": "Existing encrypted record returned", "record": metadata(existing)}
        raise HTTPException(status_code=409, detail="Record identifier already exists")
    record = MedicalRecord(id=req.record_id, patient_email=user.email, owner_wallet=user.wallet_address,
                           title=req.title, category=req.category,
                           data_hash=req.envelope.digest, storage_kind="LOCAL", cid=None)
    db.add(record)
    persist_version(db, record, 1, req.envelope, req.key_envelopes, user)
    remote = ciphertext_storage.store(record.id, canonical_bytes(req.envelope.model_dump(mode="json")))
    record.storage_kind, record.cid = remote["status"], remote["cid"]
    db.add(AuditEvent(actor_email=user.email, action="RECORD_VERSION_CREATED", resource_type="record",
                      resource_id=record.id, outcome="SUCCESS", metadata_json={"version": 1, "envelope_digest": req.envelope.digest}))
    if user.wallet_address:
        enqueue(db, "RECORD_ANCHOR", f"record-anchor:{record.id}:1", {"record_id": record.id, "patient_wallet": user.wallet_address, "envelope_digest": req.envelope.digest, "storage": record.storage_kind, "category": record.category})
    db.commit()
    return {"message": "Authenticated encrypted envelope stored.", "record": metadata(record),
            "remote_storage_error": remote["error"]}


@router.post("/{record_id}/versions", status_code=201)
def add_version(record_id: str, req: VersionUploadRequest, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    record = db.get(MedicalRecord, record_id)
    if not record or record.patient_email != user.email:
        raise HTTPException(status_code=404, detail="Owned record not found")
    next_version = int(db.scalar(select(func.max(RecordVersion.version)).where(RecordVersion.record_id == record.id)) or 0) + 1
    persist_version(db, record, next_version, req.envelope, req.key_envelopes, user)
    remote = ciphertext_storage.store(record.id, canonical_bytes(req.envelope.model_dump(mode="json")))
    record.data_hash, record.storage_kind, record.cid = req.envelope.digest, remote["status"], remote["cid"]
    db.add(AuditEvent(actor_email=user.email, action="RECORD_VERSION_CREATED", resource_type="record",
                      resource_id=record.id, outcome="SUCCESS", metadata_json={"version": next_version, "envelope_digest": req.envelope.digest}))
    db.commit()
    return {"record": metadata(record), "version": next_version, "remote_storage_error": remote["error"]}


@router.get("/mine")
def my_records(offset: int = 0, limit: int = 50, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    limit = min(max(limit, 1), 100)
    items = db.scalars(select(MedicalRecord).where(MedicalRecord.patient_email == user.email)
                       .order_by(MedicalRecord.created_at.desc()).offset(max(offset, 0)).limit(limit)).all()
    return {"items": [metadata(item) for item in items], "offset": max(offset, 0), "limit": limit}


@router.get("/accessible")
def accessible_records(offset: int = 0, limit: int = 50, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    if user.role != "Doctor":
        raise HTTPException(status_code=403, detail="Verified doctor role required")
    records = db.scalars(select(MedicalRecord).order_by(MedicalRecord.created_at.desc())).all()
    visible = [record for record in records if active_consent(db, record, user)]
    return {"items": [metadata(record) for record in visible[max(offset, 0):max(offset, 0) + min(max(limit, 1), 100)]]}


@router.get("/view/{record_id}")
def view_record(record_id: str, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    record = db.get(MedicalRecord, record_id)
    if not record or not can_read(db, record, user):
        raise HTTPException(status_code=404, detail="Authorized record not found")
    return metadata(record)


@router.get("/{record_id}/envelope")
def get_envelope(record_id: str, version: int | None = None,
                 user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    record = db.get(MedicalRecord, record_id)
    if not record or not can_read(db, record, user):
        raise HTTPException(status_code=404, detail="Authorized record not found")
    query = select(RecordVersion).where(RecordVersion.record_id == record.id)
    query = query.where(RecordVersion.version == version) if version else query.order_by(RecordVersion.version.desc()).limit(1)
    record_version = db.scalar(query)
    if not record_version or not record_version.envelope_json:
        raise HTTPException(status_code=409, detail="Legacy record has no complete versioned envelope")
    key_envelope = db.scalar(select(EncryptedEnvelope).where(
        EncryptedEnvelope.record_version_id == record_version.id,
        EncryptedEnvelope.recipient_email == user.email,
    ))
    if not key_envelope or not key_envelope.envelope_json:
        raise HTTPException(status_code=403, detail="No RSA-wrapped data key is available for this account and version")
    # Re-validate persisted data before delivery.
    encrypted = RecordEnvelope.model_validate(record_version.envelope_json)
    wrapped = KeyEnvelope.model_validate(key_envelope.envelope_json)
    db.add(AuditEvent(actor_email=user.email, action="ENCRYPTED_ENVELOPE_DELIVERED", resource_type="record",
                      resource_id=record.id, outcome="SUCCESS", metadata_json={"version": record_version.version}))
    db.commit()
    return {"record": metadata(record), "record_version": record_version.version,
            "envelope": encrypted.model_dump(mode="json"), "key_envelope": wrapped.model_dump(mode="json"),
            "plaintext": None, "decryption_performed": False}


@router.post("/{record_id}/versions/{version}/key-envelopes", status_code=201)
def add_key_envelope(record_id: str, version: int, req: AddKeyEnvelopeRequest,
                     user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    record = db.get(MedicalRecord, record_id)
    if not record or record.patient_email != user.email:
        raise HTTPException(status_code=404, detail="Owned record not found")
    record_version = db.scalar(select(RecordVersion).where(RecordVersion.record_id == record_id, RecordVersion.version == version))
    if not record_version:
        raise HTTPException(status_code=404, detail="Record version not found")
    recipient = RecipientEnvelope(recipient_email=req.recipient_email, envelope=req.envelope)
    validate_key_envelope(db, recipient, record_id, version)
    email = req.recipient_email.strip().lower()
    existing = db.scalar(select(EncryptedEnvelope).where(EncryptedEnvelope.record_version_id == record_version.id,
                                                          EncryptedEnvelope.recipient_email == email))
    if existing:
        raise HTTPException(status_code=409, detail="A key envelope already exists for this recipient and version")
    db.add(EncryptedEnvelope(record_version_id=record_version.id, recipient_email=email,
                             wrapped_key=req.envelope.wrapped_key_b64, algorithm=req.envelope.wrapping,
                             recipient_key_version=req.envelope.recipient_key_version,
                             envelope_json=req.envelope.model_dump(mode="json"), envelope_digest=req.envelope.digest))
    db.add(AuditEvent(actor_email=user.email, action="RECIPIENT_KEY_ENVELOPE_CREATED", resource_type="record",
                      resource_id=record.id, outcome="SUCCESS", metadata_json={"version": version, "recipient": email}))
    db.commit()
    return {"status": "STORED_OFF_CHAIN", "recipient_email": email, "version": version}


@router.post("/consent/grant")
def grant_consent(req: GrantConsentRequest, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    raise HTTPException(status_code=410, detail="Use /blockchain/consent/prepare and submit the patient-signed MetaMask transaction")


@router.post("/consent/revoke")
def revoke_consent(req: RevokeConsentRequest, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    raise HTTPException(status_code=410, detail="Use /blockchain/consent/revoke/prepare and submit the patient-signed MetaMask transaction")


@router.post("/break-glass")
def break_glass(_: dict, user: User = Depends(verified_user)):
    if user.role != "Doctor":
        raise HTTPException(status_code=403, detail="Only a verified doctor may request emergency access")
    raise HTTPException(status_code=503, detail="Emergency decryption is unavailable; no key escrow or recovery service is configured")
