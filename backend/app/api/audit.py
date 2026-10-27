"""Scoped audit-history views for patients, staff, and security administrators."""

from fastapi import APIRouter, Depends
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session as DbSession

from ..core.auth import verified_user
from ..core.database import get_db
from ..models import AuditEvent, MedicalRecord, User

router = APIRouter(prefix="/audit", tags=["Audit History"])


def event_output(item: AuditEvent) -> dict:
    return {
        "id": item.id,
        "timestamp": item.created_at,
        "actor_email": item.actor_email,
        "action": item.action,
        "resource_type": item.resource_type,
        "resource_id": item.resource_id,
        "outcome": item.outcome,
        "metadata": item.metadata_json,
    }


@router.get("/events")
def list_events(offset: int = 0, limit: int = 50,
                user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    limit = min(max(limit, 1), 100)
    if user.role in ("HospitalAdmin", "SecurityAuditor"):
        query = select(AuditEvent)
    else:
        record_ids = select(MedicalRecord.id).where(MedicalRecord.patient_email == user.email)
        query = select(AuditEvent).where(or_(
            AuditEvent.actor_email == user.email,
            and_(AuditEvent.resource_type == "record", AuditEvent.resource_id.in_(record_ids)),
        ))
    items = db.scalars(query.order_by(AuditEvent.created_at.desc())
                       .offset(max(offset, 0)).limit(limit)).all()
    return {"items": [event_output(item) for item in items], "offset": max(offset, 0), "limit": limit}
