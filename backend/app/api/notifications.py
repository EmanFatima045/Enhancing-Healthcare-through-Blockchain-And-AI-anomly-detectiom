"""Authenticated notification inbox for the local delivery sink."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..core.auth import verified_user
from ..core.database import get_db
from ..models import NotificationDelivery, User

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/mine")
def list_notifications(offset: int = 0, limit: int = 50,
                       user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    limit = min(max(limit, 1), 100)
    items = db.scalars(select(NotificationDelivery).where(NotificationDelivery.recipient == user.email)
                       .order_by(NotificationDelivery.created_at.desc()).offset(max(offset, 0)).limit(limit)).all()
    return {"items": [{"id": item.id, "channel": item.channel, "status": item.status,
                       "payload": item.payload_json, "created_at": item.created_at,
                       "delivered_at": item.delivered_at} for item in items]}
