import base64
import hashlib
import os
import tempfile
import json
from pathlib import Path
from uuid import uuid4

os.environ["HEALER_ENV"] = "test"
os.environ["HEALER_SECRET_KEY"] = "test-only-secret-key-with-at-least-32-characters"
os.environ["DATABASE_URL"] = f"sqlite:///{(Path(tempfile.gettempdir()) / f'healerplus-{uuid4().hex}.db').as_posix()}"

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.core.security import hash_password
from backend.app.main import app
from backend.app.models import OutboxJob, User
from backend.app.services.outbox import process_jobs
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from eth_account import Account
from eth_account.messages import encode_defunct


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def crypto_material(record_id: str, email: str):
    private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    public = private.public_key()
    spki = public.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    key = AESGCM.generate_key(bit_length=256); nonce = os.urandom(12)
    aad = {"format": "healerplus.record-aad", "record_id": record_id, "record_version": 1}
    ciphertext = AESGCM(key).encrypt(nonce, b"authenticated clinical payload", canonical(aad))
    unsigned = {"format": "healerplus.record-envelope", "version": 1, "cipher": "AES-256-GCM", "key_version": 1,
                "nonce_b64": base64.b64encode(nonce).decode(), "ciphertext_b64": base64.b64encode(ciphertext).decode(), "aad": aad}
    envelope = {**unsigned, "digest": "sha256:" + hashlib.sha256(canonical(unsigned)).hexdigest()}
    wrapped = public.encrypt(key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    key_unsigned = {"format": "healerplus.key-envelope", "version": 1, "wrapping": "RSA-OAEP-SHA-256",
                    "record_id": record_id, "record_version": 1, "recipient_key_version": 1,
                    "wrapped_key_b64": base64.b64encode(wrapped).decode()}
    key_envelope = {**key_unsigned, "digest": "sha256:" + hashlib.sha256(canonical(key_unsigned)).hexdigest()}
    return base64.b64encode(spki).decode(), private, key, envelope, {"recipient_email": email, "envelope": key_envelope}


def recipient_material(record_id: str, email: str, data_key: bytes):
    private = rsa.generate_private_key(public_exponent=65537, key_size=3072); public = private.public_key()
    spki = public.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    wrapped = public.encrypt(data_key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    unsigned = {"format": "healerplus.key-envelope", "version": 1, "wrapping": "RSA-OAEP-SHA-256",
                "record_id": record_id, "record_version": 1, "recipient_key_version": 1,
                "wrapped_key_b64": base64.b64encode(wrapped).decode()}
    return base64.b64encode(spki).decode(), {**unsigned, "digest": "sha256:" + hashlib.sha256(canonical(unsigned)).hexdigest()}


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_local_acceptance_flow():
    with TestClient(app) as client:
        email = f"patient-{uuid4().hex[:8]}@example.test"
        created = client.post("/api/v1/auth/register", json={
            "email": email, "password": "StrongPass!123", "name": "Test Patient",
            "phone": "+1-202-555-0199", "role": "Patient",
        })
        assert created.status_code == 201
        assert created.json()["user"]["role"] == "Patient"

        login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass!123"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = auth(token)

        assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
        assert client.get("/api/v1/iomt/stream").status_code == 401
        telemetry = client.get("/api/v1/iomt/stream", headers=headers)
        assert telemetry.status_code == 200
        assert telemetry.json()["capability"]["source"] == "SIMULATED"

        appointment = client.post("/api/v1/appointments", headers={**headers, "Idempotency-Key": "appt-1"}, json={
            "service": "primary-care", "preferred_date": "2099-01-01", "preferred_time": "10:30",
            "patient_name": "Spoofed Name", "phone": "+1-202-555-0199", "notes": "Demo only",
        })
        assert appointment.status_code == 201
        assert appointment.json()["patient_name"] == "Test Patient"
        assert len(client.get("/api/v1/appointments/mine", headers=headers).json()) == 1

        record_id = f"REC-{uuid4().hex.upper()}"
        spki, _, data_key, envelope_payload, recipient = crypto_material(record_id, email)
        registered_key = client.post("/api/v1/auth/keys", headers=headers, json={
            "algorithm": "RSA-OAEP-SHA-256", "public_key_spki_b64": spki,
        })
        assert registered_key.status_code == 201
        record = client.post("/api/v1/records/upload", headers=headers, json={
            "record_id": record_id, "title": "Encrypted demo", "category": "General",
            "envelope": envelope_payload, "key_envelopes": [recipient],
        })
        assert record.status_code == 201
        assert record.json()["record"]["storage_status"] == "LOCAL"
        envelope = client.get(f"/api/v1/records/{record_id}/envelope", headers=headers)
        assert envelope.status_code == 200
        assert envelope.json()["decryption_performed"] is False
        assert envelope.json()["envelope"] == envelope_payload

        doctor_email = f"doctor-{uuid4().hex[:8]}@example.test"
        with SessionLocal() as db:
            db.add(User(email=doctor_email, name="Consent Doctor", password_hash=hash_password("DoctorPass!123"),
                        role="Doctor", is_verified=True, is_active=True)); db.commit()
        doctor_login = client.post("/api/v1/auth/login", json={"email": doctor_email, "password": "DoctorPass!123"})
        doctor_headers = auth(doctor_login.json()["access_token"])
        doctor_spki, doctor_envelope = recipient_material(record_id, doctor_email, data_key)
        assert client.post("/api/v1/auth/keys", headers=doctor_headers, json={"public_key_spki_b64": doctor_spki}).status_code == 201
        assert client.post(f"/api/v1/records/{record_id}/versions/1/key-envelopes", headers=headers,
                           json={"recipient_email": doctor_email, "envelope": doctor_envelope}).status_code == 201
        legacy_grant = client.post("/api/v1/records/consent/grant", headers=headers, json={
            "practitioner_email": doctor_email, "category": "General", "access_level": "ReadOnly", "duration_hours": 24,
        })
        assert legacy_grant.status_code == 410
        assert client.get(f"/api/v1/records/{record_id}/envelope", headers=doctor_headers).status_code == 404

        tampered = dict(envelope_payload); tampered["ciphertext_b64"] = base64.b64encode(b"tampered-and-long-enough-tag").decode()
        rejected = client.post("/api/v1/records/upload", headers=headers, json={
            "record_id": f"REC-{uuid4().hex.upper()}", "title": "Rejected", "category": "General",
            "envelope": tampered, "key_envelopes": [recipient],
        })
        assert rejected.status_code == 422

        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204


def test_outbox_operations_are_role_restricted_and_redacted():
    with TestClient(app) as client:
        email = f"ops-patient-{uuid4().hex[:8]}@example.test"
        client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass!123",
                                                   "name": "Ops Patient", "phone": "+1-202-555-0188",
                                                   "role": "Patient"})
        token = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass!123"}).json()["access_token"]
        assert client.get("/api/v1/operations/outbox", headers=auth(token)).status_code == 403

        with SessionLocal() as db:
            db.add(User(email=f"ops-admin-{uuid4().hex[:8]}@example.test", name="Ops Admin",
                        password_hash=hash_password("AdminPass!123"), role="HospitalAdmin",
                        is_verified=True, is_active=True))
            db.commit()
            admin_email = db.scalars(select(User.email).where(User.name == "Ops Admin")).first()
        admin_token = client.post("/api/v1/auth/login", json={"email": admin_email,
                                                                "password": "AdminPass!123"}).json()["access_token"]
        response = client.get("/api/v1/operations/outbox", headers=auth(admin_token))
        assert response.status_code == 200
        assert "counts" in response.json()
        assert all("payload" not in item for item in response.json()["recent"])
        assert client.get("/api/v1/auth/me", headers=auth("invalid-token")).status_code == 401


def test_wallet_challenge_is_bound_and_single_use():
    with TestClient(app) as client:
        email=f"wallet-{uuid4().hex[:8]}@example.test";password="StrongPass!123"
        client.post("/api/v1/auth/register",json={"email":email,"password":password,"name":"Wallet Patient","role":"Patient"})
        token=client.post("/api/v1/auth/login",json={"email":email,"password":password}).json()["access_token"];headers=auth(token);account=Account.create()
        challenge=client.post("/api/v1/blockchain/wallet/challenge",headers=headers,json={"wallet_address":account.address})
        assert challenge.status_code==200;body=challenge.json();assert email in body["message"] and "Chain ID: 31337" in body["message"]
        signature=Account.sign_message(encode_defunct(text=body["message"]),account.key).signature.hex()
        verified=client.post("/api/v1/blockchain/wallet/verify",headers=headers,json={"challenge_id":body["challenge_id"],"signature":signature})
        assert verified.status_code==200 and verified.json()["wallet_address"]==account.address
        assert client.post("/api/v1/blockchain/wallet/verify",headers=headers,json={"challenge_id":body["challenge_id"],"signature":signature}).status_code==400


def test_admin_staff_approval_and_current_role_enforcement():
    with TestClient(app) as client:
        admin_email = f"admin-{uuid4().hex[:8]}@example.test"
        with SessionLocal() as db:
            db.add(User(email=admin_email, name="Test Admin", password_hash=hash_password("AdminPass!123"),
                        role="HospitalAdmin", is_verified=True, is_active=True))
            db.commit()
        login = client.post("/api/v1/auth/login", json={"email": admin_email, "password": "AdminPass!123"})
        headers = auth(login.json()["access_token"])
        doctor_email = f"doctor-{uuid4().hex[:8]}@example.test"
        created = client.post("/api/v1/auth/staff", headers=headers, json={
            "email": doctor_email, "password": "DoctorPass!123", "name": "Test Doctor", "role": "Doctor",
        })
        assert created.status_code == 201
        assert created.json()["is_verified"] is False
        assert client.post(f"/api/v1/auth/staff/{doctor_email}/approve", headers=headers).status_code == 200

        with SessionLocal() as db:
            db.get(User, admin_email).role = "Patient"
            db.commit()
        assert client.get("/api/v1/auth/users", headers=headers).status_code == 403


def test_staff_chain_registration_waits_for_approval():
    with TestClient(app) as client:
        admin_email = f"chain-admin-{uuid4().hex[:8]}@example.test"
        with SessionLocal() as db:
            db.add(User(email=admin_email, name="Chain Admin", password_hash=hash_password("AdminPass!123"),
                        role="HospitalAdmin", is_verified=True, is_active=True))
            db.commit()
        token = client.post("/api/v1/auth/login", json={"email": admin_email, "password": "AdminPass!123"}).json()["access_token"]
        headers = auth(token)
        staff_email = f"pending-chain-{uuid4().hex[:8]}@example.test"
        wallet = Account.create().address
        created = client.post("/api/v1/auth/staff", headers=headers, json={
            "email": staff_email, "password": "DoctorPass!123", "name": "Pending Doctor",
            "role": "Doctor", "wallet_address": wallet,
        })
        assert created.status_code == 201
        with SessionLocal() as db:
            assert db.query(OutboxJob).filter(OutboxJob.dedupe_key.like(f"staff-register:{staff_email}:%")).count() == 0
        approved = client.post(f"/api/v1/auth/staff/{staff_email}/approve", headers=headers)
        assert approved.status_code == 200
        with SessionLocal() as db:
            job = db.query(OutboxJob).filter(OutboxJob.dedupe_key.like(f"staff-register:{staff_email}:%")).one()
            assert job.topic == "STAFF_REGISTER"


def test_appointment_management_and_scoped_audit_history():
    with TestClient(app) as client:
        patient_email = f"audit-patient-{uuid4().hex[:8]}@example.test"
        patient_password = "PatientPass!123"
        assert client.post("/api/v1/auth/register", json={
            "email": patient_email, "password": patient_password, "name": "Audit Patient",
        }).status_code == 201
        patient_token = client.post("/api/v1/auth/login", json={
            "email": patient_email, "password": patient_password,
        }).json()["access_token"]
        patient_headers = auth(patient_token)
        appointment = client.post("/api/v1/appointments", headers=patient_headers, json={
            "service": "primary-care", "preferred_date": "2099-04-01", "preferred_time": "09:30",
            "phone": "+1-202-555-0101",
        })
        assert appointment.status_code == 201
        appointment_id = appointment.json()["id"]
        with SessionLocal() as db:
            request_job = db.query(OutboxJob).filter(OutboxJob.dedupe_key == f"appointment:{appointment_id}:requested").one()
            assert request_job.topic == "NOTIFICATION"
        audit = client.get("/api/v1/audit/events", headers=patient_headers)
        assert audit.status_code == 200
        assert any(item["action"] == "APPOINTMENT_REQUESTED" for item in audit.json()["items"])

        doctor_email = f"audit-doctor-{uuid4().hex[:8]}@example.test"
        with SessionLocal() as db:
            db.add(User(email=doctor_email, name="Queue Doctor", password_hash=hash_password("DoctorPass!123"),
                        role="Doctor", is_verified=True, is_active=True))
            db.commit()
        doctor_token = client.post("/api/v1/auth/login", json={
            "email": doctor_email, "password": "DoctorPass!123",
        }).json()["access_token"]
        doctor_headers = auth(doctor_token)
        queue = client.get("/api/v1/appointments/manage", headers=doctor_headers)
        assert queue.status_code == 200
        assert any(item["id"] == appointment_id for item in queue.json())
        decision = client.patch(f"/api/v1/appointments/{appointment_id}", headers=doctor_headers, json={
            "status": "confirmed",
        })
        assert decision.status_code == 200
        assert decision.json()["status"] == "confirmed"
        with SessionLocal() as db:
            status_job = db.query(OutboxJob).filter(OutboxJob.dedupe_key == f"appointment:{appointment_id}:status:confirmed").one()
            assert status_job.payload["recipient"] == patient_email
            process_jobs(db, limit=100)
            db.refresh(status_job)
            assert status_job.status == "COMPLETE"
        notifications = client.get("/api/v1/notifications/mine", headers=patient_headers)
        assert notifications.status_code == 200
        assert any(item["payload"]["kind"] == "APPOINTMENT_STATUS_CHANGED" for item in notifications.json()["items"])


def test_profile_update_normalizes_input_and_rejects_blank_name():
    with TestClient(app) as client:
        email = f"profile-{uuid4().hex[:8]}@example.test"
        password = "StrongPass!123"
        assert client.post("/api/v1/auth/register", json={
            "email": email, "password": password, "name": "Original Name",
        }).status_code == 201
        token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
        headers = auth(token)
        updated = client.patch("/api/v1/auth/me", headers=headers, json={"name": "  Updated Name  ", "phone": "  +1-202-555-0102  "})
        assert updated.status_code == 200
        assert updated.json()["name"] == "Updated Name"
        assert client.patch("/api/v1/auth/me", headers=headers, json={"name": "   "}).status_code == 422


def test_password_reset_token_is_single_use_and_revokes_sessions():
    with TestClient(app) as client:
        email = f"reset-{uuid4().hex[:8]}@example.test"
        old_password = "OldStrongPass!123"
        new_password = "NewStrongPass!123"
        assert client.post("/api/v1/auth/register", json={
            "email": email, "password": old_password, "name": "Reset Patient",
        }).status_code == 201
        old_token = client.post("/api/v1/auth/login", json={"email": email, "password": old_password}).json()["access_token"]
        assert client.post("/api/v1/auth/password-reset/request", json={"email": email}).status_code == 202
        with SessionLocal() as db:
            job = db.query(OutboxJob).filter(OutboxJob.dedupe_key.like("password-reset:%")).order_by(OutboxJob.created_at.desc()).first()
            reset_token = job.payload["reset_token"]
        assert client.post("/api/v1/auth/password-reset/confirm", json={"token": reset_token, "password": new_password}).status_code == 200
        assert client.get("/api/v1/auth/me", headers=auth(old_token)).status_code == 401
        new_login = client.post("/api/v1/auth/login", json={"email": email, "password": new_password})
        assert new_login.status_code == 200
        assert client.post("/api/v1/auth/password-reset/confirm", json={"token": reset_token, "password": old_password}).status_code == 400
