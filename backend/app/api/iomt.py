"""Authenticated, explicitly simulated IoMT telemetry."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from ..core.auth import verified_user
from ..core.config import settings
from ..core.database import get_db
from ..ml.iomt_anomaly import iomt_engine
from ..models import TelemetryEvent, User

router = APIRouter(prefix="/iomt", tags=["IoMT Telemetry"])


class TelemetryInspectRequest(BaseModel):
    heart_rate_bpm: int = Field(ge=0, le=300)
    spo2_percentage: int = Field(ge=0, le=100)
    systolic_bp: int = Field(ge=0, le=300)
    diastolic_bp: int = Field(ge=0, le=200)
    body_temp_celsius: float = Field(ge=20, le=50)
    blood_glucose_mgdl: int = Field(ge=0, le=1000)
    packet_jitter_ms: float = Field(ge=0, le=10000)
    checksum_error_rate: float = Field(ge=0, le=1)


@router.get("/stream")
def stream(mode: str = Query("normal", pattern="^(normal|clinical_emergency|sensor_tampering|mitm_attack)$"),
           user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    if mode != "normal" and not settings.DEMO_MODE:
        raise HTTPException(status_code=404, detail="Simulated anomaly modes are disabled")
    packet = iomt_engine.generate_live_packet(patient_id=f"account:{user.email}", mode=mode)
    security = packet.get("security_status", {})
    db.add(TelemetryEvent(patient_email=user.email, classification=security.get("classification", "UNKNOWN"),
                          threat_level=security.get("threat_level", "UNKNOWN"), measurements=packet,
                          is_simulated=True))
    db.commit()
    packet["capability"] = {"source": "SIMULATED", "clinical_device_connected": False}
    return packet


@router.post("/inspect")
def inspect(req: TelemetryInspectRequest, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    packet = {"patient_id": f"account:{user.email}", **req.model_dump()}
    analysis = iomt_engine.analyze_telemetry(packet)
    db.add(TelemetryEvent(patient_email=user.email, classification=analysis.get("classification", "UNKNOWN"),
                          threat_level=analysis.get("threat_level", "UNKNOWN"), measurements=packet,
                          is_simulated=True))
    db.commit()
    return {"telemetry": packet, "ai_evaluation": analysis,
            "capability": {"source": "CLIENT_SUBMITTED_DEMO_VALUES", "clinical_device_connected": False}}
