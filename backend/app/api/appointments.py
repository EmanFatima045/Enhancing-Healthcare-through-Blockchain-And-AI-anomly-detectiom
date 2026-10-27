"""Persistent, authenticated appointment requests."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..core.auth import require_roles, verified_user
from ..core.database import get_db
from ..models import Appointment, AuditEvent, User
from ..services.outbox import enqueue

router = APIRouter(prefix="/appointments", tags=["Appointments"])


class AppointmentRequest(BaseModel):
    service: str = Field(min_length=2, max_length=100)
    practitioner: str | None = Field(default=None, max_length=100)
    preferred_date: date
    preferred_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    patient_name: str | None = Field(default=None, max_length=120)
    phone: str = Field(min_length=6, max_length=30)
    notes: str | None = Field(default=None, max_length=1000)


class AppointmentDecision(BaseModel):
    status: str = Field(pattern=r"^(under review|confirmed|declined|rescheduled|cancelled)$")
    practitioner: str | None = Field(default=None, max_length=100)
    preferred_date: date | None = None
    preferred_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    staff_note: str | None = Field(default=None, max_length=1000)


def output(item: Appointment) -> dict:
    return {"id": item.id, "service": item.service, "practitioner": item.practitioner,
            "preferred_date": item.preferred_date, "preferred_time": item.preferred_time,
            "patient_name": item.patient_name, "phone": item.phone, "notes": item.notes,
            "status": item.status, "confirmed": item.status == "confirmed", "created_at": item.created_at}


@router.post("", status_code=201)
def create_appointment(req: AppointmentRequest,
                       idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
                       user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    if req.preferred_date < date.today():
        raise HTTPException(status_code=400, detail="Preferred date cannot be in the past")
    if idempotency_key:
        if len(idempotency_key) > 128:
            raise HTTPException(status_code=400, detail="Idempotency-Key is too long")
        existing = db.scalar(select(Appointment).where(Appointment.idempotency_key == idempotency_key,
                                                       Appointment.patient_email == user.email))
        if existing:
            return output(existing)
    item = Appointment(patient_email=user.email, patient_name=user.name, service=req.service,
                       practitioner=req.practitioner, preferred_date=req.preferred_date,
                       preferred_time=req.preferred_time, phone=req.phone, notes=req.notes,
                       idempotency_key=idempotency_key)
    db.add(item)
    db.flush()
    db.add(AuditEvent(actor_email=user.email, action="APPOINTMENT_REQUESTED", resource_type="appointment",
                      resource_id=item.id, outcome="PENDING", metadata_json={"service": req.service}))
    enqueue(db, "NOTIFICATION", f"appointment:{item.id}:requested",
            {"recipient": "local-care-team", "kind": "APPOINTMENT_REQUESTED", "appointment_id": item.id,
             "patient_email": user.email})
    db.commit()
    return output(item)


@router.get("/mine")
def list_my_appointments(offset: int = 0, limit: int = 50,
                         user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    limit = min(max(limit, 1), 100)
    items = db.scalars(select(Appointment).where(Appointment.patient_email == user.email)
                       .order_by(Appointment.created_at.desc()).offset(max(offset, 0)).limit(limit)).all()
    return [output(item) for item in items]


@router.get("/manage")
def list_manageable_appointments(offset: int = 0, limit: int = 50,
                                  status: str | None = None,
                                  user: User = Depends(require_roles("HospitalAdmin", "Doctor", "Nurse")),
                                  db: DbSession = Depends(get_db)):
    limit = min(max(limit, 1), 100)
    query = select(Appointment).order_by(Appointment.created_at.desc())
    if status:
        query = query.where(Appointment.status == status)
    items = db.scalars(query.offset(max(offset, 0)).limit(limit)).all()
    return [output(item) for item in items]


@router.patch("/{appointment_id}")
def decide_appointment(appointment_id: str, decision: AppointmentDecision,
                       user: User = Depends(require_roles("HospitalAdmin", "Doctor", "Nurse")),
                       db: DbSession = Depends(get_db)):
    item = db.get(Appointment, appointment_id)
    if not item:
        raise HTTPException(status_code=404, detail="Appointment request not found")
    if decision.preferred_date and decision.preferred_date < date.today():
        raise HTTPException(status_code=400, detail="Appointment date cannot be in the past")
    if decision.status in {"confirmed", "rescheduled"} and not (decision.preferred_date or item.preferred_date):
        raise HTTPException(status_code=400, detail="A date is required for a confirmed appointment")
    previous_status = item.status
    item.status = decision.status
    if decision.practitioner is not None:
        item.practitioner = decision.practitioner
    if decision.preferred_date is not None:
        item.preferred_date = decision.preferred_date
    if decision.preferred_time is not None:
        item.preferred_time = decision.preferred_time
    metadata = {"previous_status": previous_status, "new_status": item.status}
    if decision.staff_note:
        metadata["staff_note"] = decision.staff_note
    enqueue(db, "NOTIFICATION", f"appointment:{item.id}:status:{item.status}",
            {"recipient": item.patient_email, "kind": "APPOINTMENT_STATUS_CHANGED", "appointment_id": item.id,
             "status": item.status})
    db.add(AuditEvent(actor_email=user.email, action="APPOINTMENT_STATUS_CHANGED",
                      resource_type="appointment", resource_id=item.id, outcome="SUCCESS",
                      metadata_json=metadata))
    db.commit()
    return output(item)


@router.post("/{appointment_id}/cancel-request")
def request_cancellation(appointment_id: str, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    item = db.get(Appointment, appointment_id)
    if not item or item.patient_email != user.email:
        raise HTTPException(status_code=404, detail="Appointment request not found")
    item.status = "cancellation requested"
    db.add(AuditEvent(actor_email=user.email, action="APPOINTMENT_CANCELLATION_REQUESTED",
                      resource_type="appointment", resource_id=item.id, outcome="PENDING", metadata_json={}))
    enqueue(db, "NOTIFICATION", f"appointment:{item.id}:cancellation-requested",
            {"recipient": "local-care-team", "kind": "APPOINTMENT_CANCELLATION_REQUESTED", "appointment_id": item.id})
    db.commit()
    return output(item)
