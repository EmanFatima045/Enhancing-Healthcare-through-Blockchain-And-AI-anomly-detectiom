"""Server-derived application event-window features."""
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from ..models import AuditEvent, LoginAttempt

def _entropy(value: str) -> float:
    if not value: return 0.0
    counts=Counter(value); total=len(value); return -sum((n/total)*math.log2(n/total) for n in counts.values())

def application_features(db, ip_hash: str, email_hash: str, user_agent: str, payload_size: int, user_email: str|None=None) -> dict:
    now=datetime.now(timezone.utc); five=now-timedelta(minutes=5); hour=now-timedelta(hours=1)
    failed=int(db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.ip_hash==ip_hash,LoginAttempt.email_hash==email_hash,LoginAttempt.succeeded.is_(False),LoginAttempt.occurred_at>=five)) or 0)
    attempts=int(db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.ip_hash==ip_hash,LoginAttempt.occurred_at>=five)) or 0)
    record_count=int(db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.actor_email==user_email,AuditEvent.action=="ENCRYPTED_ENVELOPE_DELIVERED",AuditEvent.created_at>=hour)) or 0) if user_email else 0
    return {"failed_attempts_last_5min":failed,"time_since_last_login_sec":300.0,"ip_reputation_score":0.0,"user_agent_entropy":_entropy(user_agent),"request_rate_per_sec":attempts/300.0,"geo_velocity_kmh":0.0,"payload_size_bytes":payload_size,"record_access_count_1hr":record_count,"is_abnormal_hour":int(now.hour<6)}
