"""Authorization dependencies that always consult current persistent state."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session as DbSession

from .database import get_db
from .security import decode_token
from ..models import Session, User


Db = Annotated[DbSession, Depends(get_db)]


def current_user(authorization: Annotated[str | None, Header()] = None, db: DbSession = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    claims = decode_token(authorization[7:])
    session = db.get(Session, claims["jti"])
    user = db.get(User, claims["sub"])
    now = datetime.now(timezone.utc)
    expiry = session.expires_at if session else now
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if not session or session.revoked_at or expiry <= now or not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Session is invalid or expired")
    return user


def verified_user(user: User = Depends(current_user)) -> User:
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Account verification is required")
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(verified_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="This role is not authorized")
        return user
    return dependency
