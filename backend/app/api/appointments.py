"""Persistent, authenticated appointment requests."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..core.auth import verified_user
from ..core.database import get_db
from ..models import Appointment, AuditEvent, User

router = APIRouter(prefix="/appointments", tags=["Appointments"])


class AppointmentRequest(BaseModel):
    service: str = Field(min_length=2, max_length=100)
    practitioner: str | None = Field(default=None, max_length=100)
    preferred_date: date
    preferred_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    patient_name: str | None = Field(default=None, max_length=120)
    phone: str = Field(min_length=6, max_length=30)
    notes: str | None = Field(default=None, max_length=1000)


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
    db.add(AuditEvent(actor_email=user.email, action="APPOINTMENT_REQUESTED", resource_type="appointment",
                      resource_id=item.id, outcome="PENDING", metadata_json={"service": req.service}))
    db.commit()
    return output(item)


@router.get("/mine")
def list_my_appointments(offset: int = 0, limit: int = 50,
                         user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    limit = min(max(limit, 1), 100)
    items = db.scalars(select(Appointment).where(Appointment.patient_email == user.email)
                       .order_by(Appointment.created_at.desc()).offset(max(offset, 0)).limit(limit)).all()
    return [output(item) for item in items]


@router.post("/{appointment_id}/cancel-request")
def request_cancellation(appointment_id: str, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    item = db.get(Appointment, appointment_id)
    if not item or item.patient_email != user.email:
        raise HTTPException(status_code=404, detail="Appointment request not found")
    item.status = "cancellation requested"
    db.add(AuditEvent(actor_email=user.email, action="APPOINTMENT_CANCELLATION_REQUESTED",
                      resource_type="appointment", resource_id=item.id, outcome="PENDING", metadata_json={}))
    db.commit()
    return output(item)
