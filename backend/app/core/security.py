"""Password hashing, standards-based JWTs, client identity, and persistent login throttling."""

import base64
import hashlib
import hmac
import ipaddress
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from .config import settings
from ..models import LoginAttempt, Session, User


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    iterations = 600_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, rounds, salt, expected = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(rounds))
        return hmac.compare_digest(actual, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False


def privacy_hash(value: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), value.strip().lower().encode(), hashlib.sha256).hexdigest()


def client_ip(request: Request) -> str:
    direct = request.client.host if request.client else "unknown"
    if settings.TRUST_PROXY_HEADERS and direct in settings.TRUSTED_PROXIES:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return direct


def recent_attempt_count(db: DbSession, ip_hash: str, email_hash: str) -> int:
    since = datetime.now(timezone.utc) - timedelta(minutes=5)
    return int(db.scalar(select(func.count()).select_from(LoginAttempt).where(
        LoginAttempt.occurred_at >= since,
        (LoginAttempt.ip_hash == ip_hash) | (LoginAttempt.email_hash == email_hash),
    )) or 0)


def record_attempt(db: DbSession, ip_hash: str, email_hash: str, succeeded: bool) -> None:
    db.add(LoginAttempt(ip_hash=ip_hash, email_hash=email_hash, succeeded=succeeded))


def issue_session(db: DbSession, user: User, ip: str) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    session = Session(id=str(uuid4()), user_email=user.email, expires_at=expires, client_ip_hash=privacy_hash(ip))
    db.add(session)
    token = jwt.encode(
        {"sub": user.email, "jti": session.id, "iat": now, "nbf": now, "exp": expires,
         "iss": settings.JWT_ISSUER, "aud": settings.JWT_AUDIENCE},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, expires


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM],
                          issuer=settings.JWT_ISSUER, audience=settings.JWT_AUDIENCE,
                          options={"require": ["sub", "jti", "iat", "nbf", "exp", "iss", "aud"]})
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Session is invalid or expired") from exc


class SecurityManager:
    hash_password = staticmethod(hash_password)
    verify_password = staticmethod(verify_password)


security_manager = SecurityManager()
