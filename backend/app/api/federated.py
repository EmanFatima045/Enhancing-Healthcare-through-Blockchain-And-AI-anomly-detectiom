"""Restricted and explicitly simulated federated-learning demonstration."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..core.auth import require_roles
from ..core.config import settings
from ..core.database import get_db
from ..ml.federated_learning import fed_coordinator
from ..models import FederatedRound, User

router = APIRouter(prefix="/federated", tags=["Federated Learning"])


class TriggerRoundRequest(BaseModel):
    epochs: int = Field(default=3, ge=1, le=20)


@router.get("/status")
def status(_: User = Depends(require_roles("SecurityAuditor", "HospitalAdmin")), db: DbSession = Depends(get_db)):
    rounds = db.scalar(select(func.count()).select_from(FederatedRound)) or 0
    return {"mode": "SIMULATED", "real_hospitals_connected": 0, "privacy_guarantee": None,
            "persisted_simulation_rounds": rounds, "demo_mode": settings.DEMO_MODE}


@router.post("/train-round")
def train(req: TriggerRoundRequest, user: User = Depends(require_roles("SecurityAuditor", "HospitalAdmin")),
          db: DbSession = Depends(get_db)):
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=404, detail="Federated simulation is disabled")
    result = fed_coordinator.run_federated_round(epochs=req.epochs)
    next_round = (db.scalar(select(func.max(FederatedRound.round_number))) or 0) + 1
    result["round"] = next_round
    result["mode"] = "SIMULATED"
    result["privacy_guarantee"] = None
    result["real_hospitals_connected"] = 0
    db.add(FederatedRound(round_number=next_round, status="SIMULATED", metrics=result, created_by=user.email))
    db.commit()
    return {"message": "Simulated FedAvg round completed; no external hospital participated.", "result": result}
