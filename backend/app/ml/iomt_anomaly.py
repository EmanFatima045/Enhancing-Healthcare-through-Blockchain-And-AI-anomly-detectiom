"""Synthetic IoMT source with separate network, signal-quality, and physiology rule channels."""
import random,time
class IoMTMonitor:
    def generate_live_packet(self,patient_id="PATIENT_001",mode="normal"):
        values={"normal":(72,98,120,80,36.8,95,6,.001),"clinical_emergency":(170,82,200,115,39.4,300,10,.003),"sensor_tampering":(0,100,280,165,44.2,600,240,.65),"mitm_attack":(90,96,135,88,37.,100,180,.35)}[mode]
        keys=["heart_rate_bpm","spo2_percentage","systolic_bp","diastolic_bp","body_temp_celsius","blood_glucose_mgdl","packet_jitter_ms","checksum_error_rate"]
        packet={"device_id":f"IoMT-BEDSIDE-{patient_id}","patient_id":patient_id,"timestamp":time.time(),**dict(zip(keys,values))};packet["security_status"]=self.analyze_telemetry(packet);return packet
    def analyze_telemetry(self,packet):
        hr,spo2,temp,jitter,errors=packet["heart_rate_bpm"],packet["spo2_percentage"],packet["body_temp_celsius"],packet["packet_jitter_ms"],packet["checksum_error_rate"]
        cyber=[]
        if errors>.15:cyber.append("HIGH_CHECKSUM_ERROR_RATE")
        if jitter>100:cyber.append("HIGH_NETWORK_JITTER")
        signal=[]
        if spo2>100 or hr==0 or temp<32 or temp>43:signal.append("PHYSIOLOGICALLY_IMPLAUSIBLE_VALUE")
        clinical=[]
        if hr>140 or hr<50:clinical.append("HEART_RATE_OUTSIDE_RULE_RANGE")
        if spo2<90:clinical.append("LOW_SPO2_RULE_ALERT")
        if temp>38.5:clinical.append("HIGH_TEMPERATURE_RULE_ALERT")
        return {"classification":"NETWORK_ALERT" if cyber else "NETWORK_BASELINE","is_alert":bool(cyber or signal or clinical),"threat_level":"HIGH" if cyber else "REVIEW" if signal or clinical else "LOW","network_security":{"source":"iomt_network_rules","alert":bool(cyber),"reason_codes":cyber,"enforced_action":"QUARANTINE_NETWORK_COPY_PRESERVE_READING" if cyber else "ALLOW"},"signal_quality":{"status":"UNCERTAIN" if signal else "ACCEPTABLE_BY_RULES","reason_codes":signal,"uncertainty":"No calibrated signal-quality model is installed"},"physiology":{"status":"CLINICAL_REVIEW" if clinical else "NO_RULE_ALERT","reason_codes":clinical,"disclaimer":"Rule output is not a diagnosis"},"action":"PRESERVE_AND_ROUTE_FOR_REVIEW" if cyber or signal else "CLINICAL_ALERT" if clinical else "NONE"}
iomt_engine=IoMTMonitor()
