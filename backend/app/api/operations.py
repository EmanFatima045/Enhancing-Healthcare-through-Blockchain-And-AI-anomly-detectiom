"""Restricted operational views for the durable outbox and worker health."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..core.auth import verified_user
from ..core.database import get_db
from ..models import OutboxJob, User

router = APIRouter(prefix="/operations", tags=["Operations"])


@router.get("/outbox")
def outbox_status(user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    """Return queue health without exposing job payloads or secrets."""
    if user.role not in ("HospitalAdmin", "SecurityAuditor"):
        raise HTTPException(status_code=403, detail="Operations access is restricted")
    counts = dict(db.execute(select(OutboxJob.status, func.count()).group_by(OutboxJob.status)).all())
    recent = db.scalars(select(OutboxJob).order_by(OutboxJob.created_at.desc()).limit(20)).all()
    return {
        "counts": counts,
        "recent": [{"id": job.id, "topic": job.topic, "status": job.status,
                    "attempts": job.attempts, "created_at": job.created_at} for job in recent],
    }
