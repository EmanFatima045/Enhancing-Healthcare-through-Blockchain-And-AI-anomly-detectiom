"""Server-derived application event detection and explicitly synthetic scenarios."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession
from ..core.auth import require_roles
from ..core.config import settings
from ..core.database import get_db
from ..core.security import client_ip, privacy_hash
from ..ml.application_detection import ids_engine
from ..ml.features import application_features
from ..models import Incident, User
from ..services.outbox import enqueue

router=APIRouter(prefix="/security",tags=["Application Security Detection"])
class SimulateAttackRequest(BaseModel):
    attack_scenario:str=Field(pattern=r"^(brute_force|credential_stuffing|exfiltration|ddos_burst)$"); intensity:int=Field(default=5,ge=1,le=10)

def incident_output(item): return {"id":item.id,"timestamp":item.created_at,"attack_type":item.kind,"severity":item.severity,"source":item.source,"details":item.details,"is_simulated":item.is_simulated,"ip_hash":item.ip_hash}

@router.post("/evaluate")
def evaluate(request:Request,user:User=Depends(require_roles("SecurityAuditor","HospitalAdmin")),db:DbSession=Depends(get_db)):
    ip=privacy_hash(client_ip(request)); features=application_features(db,ip,privacy_hash(user.email),request.headers.get("user-agent",""),int(request.headers.get("content-length") or 0),user.email)
    analysis=ids_engine.predict(features,event_source="server_event_window",enforced_action="OBSERVE_ONLY")
    if analysis["is_threat"]:
        item=Incident(kind=analysis["attack_type"],severity=analysis["severity"],source="APPLICATION_EVENT_DETECTION",ip_hash=ip,details=analysis,is_simulated=False);db.add(item);db.flush();enqueue(db,"INCIDENT_ATTESTATION",f"incident-attestation:{item.id}",{"incident_id":item.id});db.commit()
    return analysis

@router.post("/simulate-attack")
def simulate(req:SimulateAttackRequest,_:User=Depends(require_roles("SecurityAuditor","HospitalAdmin")),db:DbSession=Depends(get_db)):
    if not settings.DEMO_MODE: raise HTTPException(404,"Attack simulation is disabled")
    scenarios={"brute_force":[25,.4,.92,1.4,48.,0,350,0,1],"credential_stuffing":[8,2.5,.96,4.8,12,1850,750,2,1],"exfiltration":[0,15,.65,3.1,30,150,85000,350,1],"ddos_burst":[40,.1,.99,.8,95,0,200,0,1]}
    keys=["failed_attempts_last_5min","time_since_last_login_sec","ip_reputation_score","user_agent_entropy","request_rate_per_sec","geo_velocity_kmh","payload_size_bytes","record_access_count_1hr","is_abnormal_hour"]
    analysis=ids_engine.predict(dict(zip(keys,scenarios[req.attack_scenario])),event_source="synthetic_scenario",enforced_action="OBSERVE_ONLY")
    item=Incident(kind=analysis["attack_type"],severity=analysis["severity"],source="DEMO_SIMULATION",details={"scenario":req.attack_scenario,"analysis":analysis},is_simulated=True);db.add(item);db.commit()
    return {"scenario":req.attack_scenario,"simulation":True,"detection":analysis,"incident":incident_output(item)}

@router.get("/threat-feed")
def feed(offset:int=0,limit:int=50,_:User=Depends(require_roles("SecurityAuditor","HospitalAdmin")),db:DbSession=Depends(get_db)):
    limit=min(max(limit,1),100);items=db.scalars(select(Incident).order_by(Incident.created_at.desc()).offset(max(offset,0)).limit(limit)).all();total=db.scalar(select(func.count()).select_from(Incident)) or 0
    return {"total":total,"items":[incident_output(x) for x in items],"detector_mode":ids_engine.mode}

@router.get("/metrics")
def metrics(_:User=Depends(require_roles("SecurityAuditor","HospitalAdmin"))): return {"application_event_detection":ids_engine.get_benchmark_metrics(),"iomt_network_benchmark":"NOT_RUN","physiological_signal_quality":"RULES_ONLY_SEPARATE_CHANNEL"}
