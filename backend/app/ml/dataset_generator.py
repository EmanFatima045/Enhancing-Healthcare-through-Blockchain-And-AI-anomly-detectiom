"""
HealerPlus 2.0 - Synthetic Healthcare Security Dataset Generator
Generates high-fidelity datasets simulating:
1. Authentication & Network Traffic (Normal logins, Brute-force attacks, Credential Stuffing, Impossible Travel, Unauthorized EMR scraping).
2. IoMT Vital Signs Stream (Normal telemetry vs Sensor Spoofing / Tampering / Acute cardiac anomalies).
"""

import csv
import math
import os
import random
import time

DATASETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../datasets"))

def generate_healthcare_ids_dataset(num_samples: int = 2500) -> str:
    """
    Generates a healthcare intrusion detection dataset with feature engineering:
    - failed_attempts_last_5min: Count of recent failed logins
    - time_since_last_login_sec: Delta seconds between login events
    - ip_reputation_score: 0.0 (clean) to 1.0 (malicious/TOR/proxy)
    - user_agent_entropy: Entropy score of browser user agent string
    - request_rate_per_sec: Velocity of API requests
    - geo_velocity_kmh: Speed required between subsequent logins from different IPs
    - payload_size_bytes: Size of request payload (anomalous payload may indicate injection/exfiltration)
    - record_access_count_1hr: Volume of EMRs queried
    - label: 0 (Normal / Benign), 1 (Brute-Force), 2 (Credential Stuffing), 3 (Data Exfiltration / Tampering)
    """
    os.makedirs(DATASETS_DIR, exist_ok=True)
    file_path = os.path.join(DATASETS_DIR, "healthcare_ids_dataset.csv")

    headers = [
        "failed_attempts_last_5min",
        "time_since_last_login_sec",
        "ip_reputation_score",
        "user_agent_entropy",
        "request_rate_per_sec",
        "geo_velocity_kmh",
        "payload_size_bytes",
        "record_access_count_1hr",
        "is_abnormal_hour",
        "label"
    ]

    with open(file_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for _ in range(num_samples):
            # 65% Normal Traffic, 15% Brute-force, 10% Credential Stuffing, 10% Exfiltration
            p = random.random()

            if p < 0.65:
                # Normal Benign Access
                failed_attempts = random.choice([0, 0, 0, 1, 2])
                time_since_login = random.uniform(300, 86400)
                ip_rep = random.uniform(0.0, 0.2)
                ua_entropy = random.uniform(2.5, 4.2)
                req_rate = random.uniform(0.1, 2.5)
                geo_vel = random.uniform(0.0, 60.0) # Normal travel speed
                payload_sz = random.randint(200, 4000)
                rec_access = random.randint(1, 15)
                abnormal_hr = 1 if random.random() < 0.1 else 0
                label = 0 # Benign

            elif p < 0.80:
                # Brute-Force Attack
                failed_attempts = random.randint(8, 60)
                time_since_login = random.uniform(0.1, 5.0)
                ip_rep = random.uniform(0.5, 0.95)
                ua_entropy = random.uniform(1.0, 2.8)
                req_rate = random.uniform(10.0, 80.0)
                geo_vel = random.uniform(0.0, 100.0)
                payload_sz = random.randint(150, 600)
                rec_access = random.randint(0, 2)
                abnormal_hr = 1 if random.random() < 0.6 else 0
                label = 1 # Brute Force

            elif p < 0.90:
                # Credential Stuffing (Distributed IPs, Moderate Rate)
                failed_attempts = random.randint(3, 15)
                time_since_login = random.uniform(1.0, 20.0)
                ip_rep = random.uniform(0.6, 0.99)
                ua_entropy = random.uniform(3.8, 5.0)
                req_rate = random.uniform(3.0, 15.0)
                geo_vel = random.uniform(800.0, 2500.0) # Impossible travel velocity
                payload_sz = random.randint(300, 1200)
                rec_access = random.randint(1, 5)
                abnormal_hr = 1 if random.random() < 0.5 else 0
                label = 2 # Credential Stuffing

            else:
                # Data Exfiltration / Unauthorized EMR Scraping
                failed_attempts = random.choice([0, 1])
                time_since_login = random.uniform(10.0, 200.0)
                ip_rep = random.uniform(0.2, 0.8)
                ua_entropy = random.uniform(2.0, 4.0)
                req_rate = random.uniform(8.0, 40.0)
                geo_vel = random.uniform(0.0, 300.0)
                payload_sz = random.randint(15000, 120000) # Heavy payload extraction
                rec_access = random.randint(80, 500) # Massive record querying
                abnormal_hr = 1 if random.random() < 0.8 else 0
                label = 3 # Exfiltration

            writer.writerow([
                failed_attempts,
                round(time_since_login, 2),
                round(ip_rep, 3),
                round(ua_entropy, 3),
                round(req_rate, 2),
                round(geo_vel, 2),
                payload_sz,
                rec_access,
                abnormal_hr,
                label
            ])

    return file_path


def generate_iomt_telemetry_dataset(num_samples: int = 1500) -> str:
    """
    Generates IoMT physiological dataset:
    - heart_rate_bpm: 40 - 200 bpm
    - spo2_percentage: 75% - 100%
    - systolic_bp: 70 - 220 mmHg
    - diastolic_bp: 40 - 130 mmHg
    - body_temp_celsius: 35.0 - 41.5 C
    - blood_glucose_mgdl: 50 - 380 mg/dL
    - packet_jitter_ms: Network timing jitter (high jitter indicates MITM/sensor spoofing)
    - checksum_error_rate: 0.0 to 1.0
    - label: 0 (Normal), 1 (Clinical Emergency/Tachycardia/Hypoxia), 2 (Sensor Tampering/Spoofing Attack)
    """
    os.makedirs(DATASETS_DIR, exist_ok=True)
    file_path = os.path.join(DATASETS_DIR, "iomt_telemetry_dataset.csv")

    headers = [
        "heart_rate_bpm",
        "spo2_percentage",
        "systolic_bp",
        "diastolic_bp",
        "body_temp_celsius",
        "blood_glucose_mgdl",
        "packet_jitter_ms",
        "checksum_error_rate",
        "label"
    ]

    with open(file_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for _ in range(num_samples):
            p = random.random()

            if p < 0.70:
                # Normal Telemetry
                hr = random.randint(62, 95)
                spo2 = random.randint(96, 100)
                sys_bp = random.randint(110, 128)
                dia_bp = random.randint(72, 84)
                temp = round(random.uniform(36.4, 37.2), 1)
                glucose = random.randint(80, 125)
                jitter = round(random.uniform(1.0, 15.0), 2)
                chk_err = round(random.uniform(0.0, 0.02), 3)
                label = 0

            elif p < 0.85:
                # Clinical Emergency (Cardiac / Hypoxia / Hyperglycemia)
                anomaly_type = random.choice(["cardiac", "hypoxia", "septic"])
                if anomaly_type == "cardiac":
                    hr = random.randint(140, 195) # Severe tachycardia
                    spo2 = random.randint(90, 96)
                    sys_bp = random.randint(160, 210)
                    dia_bp = random.randint(98, 120)
                elif anomaly_type == "hypoxia":
                    hr = random.randint(110, 140)
                    spo2 = random.randint(76, 88) # Severe desaturation
                    sys_bp = random.randint(90, 115)
                    dia_bp = random.randint(60, 75)
                else:
                    hr = random.randint(115, 150)
                    spo2 = random.randint(91, 95)
                    sys_bp = random.randint(80, 100)
                    dia_bp = random.randint(50, 65)

                temp = round(random.uniform(37.8, 40.5), 1)
                glucose = random.randint(180, 360)
                jitter = round(random.uniform(2.0, 20.0), 2)
                chk_err = round(random.uniform(0.0, 0.03), 3)
                label = 1 # Clinical Anomaly

            else:
                # Sensor Tampering / Biometric Spoofing Attack
                hr = random.choice([0, 240, random.randint(190, 220)]) # Impossible spikes
                spo2 = random.choice([40, 105, random.randint(60, 70)])
                sys_bp = random.randint(220, 280)
                dia_bp = random.randint(130, 160)
                temp = round(random.uniform(31.0, 44.0), 1)
                glucose = random.randint(20, 500)
                jitter = round(random.uniform(85.0, 350.0), 2) # Severe network MITM jitter
                chk_err = round(random.uniform(0.15, 0.85), 3) # Corrupted packets
                label = 2 # Tampering / Spoofing Attack

            writer.writerow([
                hr,
                spo2,
                sys_bp,
                dia_bp,
                temp,
                glucose,
                jitter,
                chk_err,
                label
            ])

    return file_path

if __name__ == "__main__":
    p1 = generate_healthcare_ids_dataset()
    p2 = generate_iomt_telemetry_dataset()
    print(f"Generated IDS Dataset at: {p1}")
    print(f"Generated IoMT Dataset at: {p2}")
