"""Runtime application-event detection. Never trains on import."""
import json, time
from pathlib import Path
from typing import Any
import joblib, numpy as np
from ..core.config import settings

FEATURES = ["failed_attempts_last_5min","time_since_last_login_sec","ip_reputation_score","user_agent_entropy","request_rate_per_sec","geo_velocity_kmh","payload_size_bytes","record_access_count_1hr","is_abnormal_hour"]
LABELS = {0:"Normal Access",1:"Brute-Force Attack",2:"Credential Stuffing",3:"Unauthorized EMR Exfiltration"}

class ApplicationDetector:
    def __init__(self):
        self.mode="RULES"; self.bundle=None; self.report=None; root=Path(settings.MODEL_ARTIFACT_DIR)
        try:
            manifest=json.loads((root/"manifest.json").read_text("utf-8")); self.bundle=joblib.load(root/manifest["artifact"]); self.report=json.loads((root/manifest["report"]).read_text("utf-8")); self.mode="MODEL"
        except Exception: pass

    def predict(self, features: dict[str,Any], event_source="server_event_window", enforced_action: str|None=None) -> dict[str,Any]:
        vector=np.array([[float(features[name]) for name in FEATURES]]); reasons=[]
        if self.mode=="MODEL":
            probabilities=self.bundle["classifier"].predict_proba(vector)[0]; classes=self.bundle["classifier"].classes_; attack_probability=float(sum(p for p,c in zip(probabilities,classes) if int(c)!=0)); label=int(classes[int(np.argmax(probabilities))]); novelty=float(-self.bundle["isolation"].decision_function(vector)[0]); threshold=float(self.bundle["threshold"]); score=attack_probability
            if novelty>=self.bundle["novelty_threshold"]: reasons.append("NOVELTY_SCORE_ABOVE_VALIDATION_THRESHOLD")
            if score>=threshold: reasons.append("ATTACK_SCORE_ABOVE_VALIDATION_THRESHOLD")
        else:
            f=features; score=min(1.0,max(f["failed_attempts_last_5min"]/10,f["request_rate_per_sec"]/50,f["record_access_count_1hr"]/100,f["ip_reputation_score"])); threshold=.65; novelty=None
            if f["failed_attempts_last_5min"]>=6: reasons.append("REPEATED_LOGIN_FAILURES")
            if f["request_rate_per_sec"]>=20: reasons.append("HIGH_REQUEST_RATE")
            if f["record_access_count_1hr"]>=50: reasons.append("HIGH_RECORD_ACCESS_VOLUME")
            label=1 if f["failed_attempts_last_5min"]>=6 else 3 if f["record_access_count_1hr"]>=50 else 0
        suggested="DENY" if score>=.9 else "THROTTLE" if score>=threshold else "ALLOW"
        return {"model_version":self.bundle.get("model_version") if self.bundle else "rules-v1","schema_version":"application-security-v1","event_source":event_source,"mode":self.mode,"predicted_class":label,"attack_type":LABELS[label],"score":round(score,6),"score_meaning":"higher means greater model-estimated attack risk" if self.mode=="MODEL" else "higher means greater deterministic rule risk","threshold":threshold,"novelty_score":None if novelty is None else round(novelty,6),"reason_codes":reasons or ["NO_THRESHOLD_EXCEEDED"],"suggested_action":suggested,"enforced_action":enforced_action or "OBSERVE_ONLY","is_threat":score>=threshold,"severity":"CRITICAL" if score>=.9 else "HIGH" if score>=threshold else "LOW"}

    def get_benchmark_metrics(self):
        return self.report or {"evaluation_status":"UNAVAILABLE_RULES_MODE","warning":"No exported held-out evaluation artifact is installed."}

ids_engine=ApplicationDetector()
