"""Wallet linking and untrusted transaction receipt verification."""
import base64, hashlib, secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from web3 import Web3
from ..core.auth import verified_user
from ..core.config import settings
from ..core.database import get_db
from ..core.crypto import unwrap_rsa_oaep_sha256, wrap_rsa_oaep_sha256
from ..core.envelopes import KeyEnvelope, RecordEnvelope, canonical_bytes, sha256_digest
from ..models import ChainTransaction, ConsentProjection, EmergencyAccess, EncryptedEnvelope, MedicalRecord, NotificationDelivery, RecordVersion, User, UserKey, WalletChallenge
from ..services.blockchain_service import BlockchainUnavailable, blockchain_service
from ..services.outbox import enqueue

router = APIRouter(prefix="/blockchain", tags=["Wallet & Blockchain"])

class ChallengeRequest(BaseModel): wallet_address: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")
class VerifyWalletRequest(BaseModel): challenge_id: str; signature: str = Field(min_length=130, max_length=132)
class ConsentPrepareRequest(BaseModel):
    practitioner_email: str; category: str = Field(min_length=2, max_length=64); access_level: Literal["ReadOnly", "ReadAndWrite"] = "ReadOnly"; duration_hours: int = Field(ge=1, le=8760)
class RevokePrepareRequest(BaseModel): practitioner_email: str; category: str
class SubmitRequest(BaseModel): intent_id: str; tx_hash: str = Field(pattern=r"^0x[a-fA-F0-9]{64}$")
class EmergencyPrepareRequest(BaseModel): record_id: str; justification: str = Field(min_length=20, max_length=4000); emergency_type: int = Field(ge=1, le=4)
class EmergencyReviewRequest(BaseModel): emergency_id: str; legitimate: bool

def tx_output(row: ChainTransaction) -> dict:
    return {"id": row.id, "status": row.status, "tx_hash": row.tx_hash, "block_number": row.block_number, "confirmations": row.confirmations, "error": row.error}

@router.get("/status")
def chain_status(_: User = Depends(verified_user)): return blockchain_service.health()

@router.post("/wallet/challenge")
def wallet_challenge(req: ChallengeRequest, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    address = Web3.to_checksum_address(req.wallet_address); nonce = secrets.token_urlsafe(24); now = datetime.now(timezone.utc); expiry = now + timedelta(minutes=settings.WALLET_CHALLENGE_MINUTES)
    message = f"{settings.APP_DOMAIN} requests wallet linkage\nAccount: {user.email}\nWallet: {address}\nChain ID: {settings.CHAIN_ID}\nNonce: {nonce}\nIssued At: {now.isoformat()}\nExpiration Time: {expiry.isoformat()}"
    challenge = WalletChallenge(user_email=user.email, wallet_address=address, nonce_hash=hashlib.sha256(nonce.encode()).hexdigest(), domain=settings.APP_DOMAIN, chain_id=settings.CHAIN_ID, message=message, expires_at=expiry)
    db.add(challenge); db.commit(); return {"challenge_id": challenge.id, "message": message, "expires_at": expiry, "chain_id": settings.CHAIN_ID}

@router.post("/wallet/verify")
def wallet_verify(req: VerifyWalletRequest, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    challenge = db.get(WalletChallenge, req.challenge_id); now = datetime.now(timezone.utc)
    expiry = challenge.expires_at.replace(tzinfo=timezone.utc) if challenge and challenge.expires_at.tzinfo is None else challenge.expires_at if challenge else now
    if not challenge or challenge.user_email != user.email or challenge.used_at or expiry <= now or challenge.domain != settings.APP_DOMAIN or challenge.chain_id != settings.CHAIN_ID: raise HTTPException(400, "Challenge is invalid, expired, or already used")
    try: recovered = blockchain_service.recover_wallet(challenge.message, req.signature)
    except Exception as exc: raise HTTPException(422, "Wallet signature recovery failed") from exc
    if recovered.lower() != challenge.wallet_address.lower(): raise HTTPException(403, "Signature does not match the requested wallet")
    existing = db.scalar(select(User).where(User.wallet_address.ilike(recovered), User.email != user.email))
    if existing: raise HTTPException(409, "Wallet is already linked to another account")
    user.wallet_address = recovered; challenge.used_at = now
    if user.role in ("Doctor","HospitalAdmin","SecurityAuditor"): enqueue(db,"STAFF_REGISTER",f"staff-register:{user.email}:{recovered.lower()}",{"wallet":recovered,"role":user.role})
    db.commit(); return {"wallet_address": recovered, "linked": True, "chain_id": settings.CHAIN_ID, "staff_registration":"QUEUED" if user.role != "Patient" else None}

def require_wallet(user: User):
    if not user.wallet_address: raise HTTPException(409, "Link a wallet using an expiring signed challenge first")
    try: blockchain_service.require_ready()
    except BlockchainUnavailable as exc: raise HTTPException(503, str(exc)) from exc

@router.post("/consent/prepare")
def prepare_consent(req: ConsentPrepareRequest, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    if user.role != "Patient": raise HTTPException(403, "Only patients grant consent")
    require_wallet(user); doctor = db.get(User, req.practitioner_email.lower())
    if not doctor or doctor.role != "Doctor" or not doctor.is_active or not doctor.is_verified or not doctor.wallet_address: raise HTTPException(404, "Verified doctor with linked wallet not found")
    valid_until = int((datetime.now(timezone.utc) + timedelta(hours=req.duration_hours)).timestamp()); level = 1 if req.access_level == "ReadOnly" else 2
    projection = ConsentProjection(patient_email=user.email, practitioner_email=doctor.email, category=req.category, access_level=req.access_level, valid_until=datetime.fromtimestamp(valid_until, timezone.utc), status="AWAITING_SIGNATURE", source="CHAIN")
    db.add(projection); db.flush()
    args = {"practitioner": Web3.to_checksum_address(doctor.wallet_address), "categoryCommitment": blockchain_service.category_commitment(req.category), "level": level, "validUntil": valid_until, "_projection_id": projection.id}
    tx = ChainTransaction(operation="ConsentManager:GRANT", status="AWAITING_SIGNATURE", chain_id=settings.CHAIN_ID, sender=user.wallet_address, contract_address=blockchain_service.contracts["ConsentManager"].address, expected_call="grantConsent", expected_args=args)
    db.add(tx); db.commit(); return {"intent_id": tx.id, "status": tx.status, "contract": tx.contract_address, "function": tx.expected_call, "args": [args["practitioner"], args["categoryCommitment"], level, valid_until]}

@router.post("/identity/patient/prepare")
def prepare_patient_registration(user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    if user.role != "Patient": raise HTTPException(403,"Patient role required")
    require_wallet(user); account=blockchain_service.contracts["HealerAuth"].functions.getAccount(Web3.to_checksum_address(user.wallet_address)).call()
    if int(account[0])==1 and bool(account[1]) and bool(account[2]): return {"status":"CONFIRMED","already_registered":True}
    tx=ChainTransaction(operation="HealerAuth:PATIENT_REGISTER",status="AWAITING_SIGNATURE",chain_id=settings.CHAIN_ID,sender=user.wallet_address,contract_address=blockchain_service.contracts["HealerAuth"].address,expected_call="registerPatient",expected_args={})
    db.add(tx);db.commit();return {"intent_id":tx.id,"status":tx.status,"contract":tx.contract_address,"function":"registerPatient","args":[]}

@router.post("/consent/revoke/prepare")
def prepare_revoke(req: RevokePrepareRequest, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    if user.role != "Patient": raise HTTPException(403, "Only patients revoke consent")
    require_wallet(user); doctor = db.get(User, req.practitioner_email.lower())
    projection = db.scalar(select(ConsentProjection).where(ConsentProjection.patient_email == user.email, ConsentProjection.practitioner_email == req.practitioner_email.lower(), ConsentProjection.category == req.category, ConsentProjection.status == "CONFIRMED").order_by(ConsentProjection.created_at.desc()))
    if not doctor or not doctor.wallet_address or not projection: raise HTTPException(404, "Confirmed consent not found")
    args = {"practitioner": Web3.to_checksum_address(doctor.wallet_address), "categoryCommitment": blockchain_service.category_commitment(req.category), "_projection_id": projection.id}
    tx = ChainTransaction(operation="ConsentManager:REVOKE", status="AWAITING_SIGNATURE", chain_id=settings.CHAIN_ID, sender=user.wallet_address, contract_address=blockchain_service.contracts["ConsentManager"].address, expected_call="revokeConsent", expected_args=args)
    db.add(tx); db.commit(); return {"intent_id": tx.id, "status": tx.status, "contract": tx.contract_address, "function": tx.expected_call, "args": [args["practitioner"], args["categoryCommitment"]]}

@router.get("/consents/mine")
def my_chain_consents(user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    if user.role != "Patient": raise HTTPException(403, "Patient role required")
    rows = db.scalars(select(ConsentProjection).where(ConsentProjection.patient_email == user.email, ConsentProjection.source == "CHAIN").order_by(ConsentProjection.created_at.desc())).all()
    return {"items": [{"id": row.id, "practitioner_email": row.practitioner_email, "category": row.category, "access_level": row.access_level, "valid_until": row.valid_until, "status": row.status} for row in rows]}

@router.post("/transactions/submit")
def submit_transaction(req: SubmitRequest, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    row = db.get(ChainTransaction, req.intent_id)
    if not row or row.sender.lower() != (user.wallet_address or "").lower(): raise HTTPException(404, "Transaction intent not found")
    duplicate = db.scalar(select(ChainTransaction).where(ChainTransaction.tx_hash == req.tx_hash.lower(), ChainTransaction.id != row.id))
    if duplicate: return tx_output(duplicate)
    if row.status not in ("AWAITING_SIGNATURE", "SUBMITTED"): return tx_output(row)
    row.tx_hash = req.tx_hash.lower(); row.status = "SUBMITTED"
    try: blockchain_service.process_transaction(db, row)
    except BlockchainUnavailable: pass
    db.commit(); return tx_output(row)

@router.post("/emergency/prepare")
def prepare_emergency(req: EmergencyPrepareRequest, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    if user.role != "Doctor": raise HTTPException(403, "Verified doctor role required")
    require_wallet(user); record = db.get(MedicalRecord, req.record_id); patient = db.get(User, record.patient_email) if record else None
    if not record or not patient or not patient.wallet_address: raise HTTPException(404, "Record with linked patient wallet not found")
    commitment = Web3.keccak(text=req.justification).hex()
    emergency = EmergencyAccess(record_id=record.id, practitioner_email=user.email, justification=req.justification, justification_commitment=commitment, emergency_type=req.emergency_type)
    db.add(emergency); db.flush()
    args = {"patient": Web3.to_checksum_address(patient.wallet_address), "recordId": Web3.keccak(text=record.id).hex(), "justificationCommitment": commitment, "emergencyType": req.emergency_type, "_emergency_id": emergency.id}
    tx = ChainTransaction(operation="BreakGlassEmergency:OPEN", status="AWAITING_SIGNATURE", chain_id=settings.CHAIN_ID, sender=user.wallet_address, contract_address=blockchain_service.contracts["BreakGlassEmergency"].address, expected_call="open", expected_args=args)
    db.add(tx); db.flush(); emergency.chain_tx_id = tx.id; db.commit()
    return {"emergency_id": emergency.id, "intent_id": tx.id, "status": tx.status, "key_delivery_state": emergency.key_delivery_state, "contract": tx.contract_address, "function": "open", "args": [args["patient"], args["recordId"], commitment, req.emergency_type]}

@router.get("/emergency/{emergency_id}")
def emergency_status(emergency_id: str, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    item = db.get(EmergencyAccess, emergency_id)
    if not item or user.email not in (item.practitioner_email, db.get(MedicalRecord, item.record_id).patient_email): raise HTTPException(404, "Emergency request not found")
    deliveries = db.scalars(select(NotificationDelivery).where(NotificationDelivery.dedupe_key.like(f"emergency:{item.id}:%"))).all()
    return {"id": item.id, "status": item.status, "review_status": item.review_status, "key_delivery_state": item.key_delivery_state, "notifications": [{"channel": d.channel, "recipient": d.recipient, "status": d.status, "delivered_at": d.delivered_at} for d in deliveries]}

@router.post("/emergency/review/prepare")
def prepare_emergency_review(req: EmergencyReviewRequest, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    if user.role not in ("SecurityAuditor","HospitalAdmin"): raise HTTPException(403,"Auditor role required")
    require_wallet(user);item=db.get(EmergencyAccess,req.emergency_id)
    if not item or item.chain_session_id is None or item.status!="CONFIRMED":raise HTTPException(404,"Confirmed emergency session not found")
    args={"id":item.chain_session_id,"legitimate":req.legitimate,"_emergency_id":item.id,"_review":"APPROVED" if req.legitimate else "REJECTED"}
    tx=ChainTransaction(operation="BreakGlassEmergency:REVIEW",status="AWAITING_SIGNATURE",chain_id=settings.CHAIN_ID,sender=user.wallet_address,contract_address=blockchain_service.contracts["BreakGlassEmergency"].address,expected_call="review",expected_args=args);db.add(tx);db.commit();return {"intent_id":tx.id,"status":tx.status,"contract":tx.contract_address,"function":"review","args":[item.chain_session_id,req.legitimate]}

@router.get("/emergency/{emergency_id}/envelope")
def emergency_envelope(emergency_id: str, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    item = db.get(EmergencyAccess, emergency_id); record = db.get(MedicalRecord, item.record_id) if item else None; patient = db.get(User, record.patient_email) if record else None
    if not item or item.practitioner_email != user.email or item.status != "CONFIRMED" or item.chain_session_id is None or not user.wallet_address or not patient or not patient.wallet_address: raise HTTPException(403, "Confirmed emergency authorization required")
    try:
        blockchain_service.require_ready(); active = blockchain_service.contracts["BreakGlassEmergency"].functions.isActive(item.chain_session_id, Web3.to_checksum_address(user.wallet_address), Web3.to_checksum_address(patient.wallet_address), Web3.keccak(text=record.id)).call()
    except Exception as exc: raise HTTPException(503, "Could not verify authoritative emergency session") from exc
    if not active: item.key_delivery_state = "BLOCKED_INACTIVE_SESSION"; db.commit(); raise HTTPException(403, "Emergency session is expired, rejected, or revoked")
    if not settings.EMERGENCY_ESCROW_EMAIL or not settings.EMERGENCY_ESCROW_PRIVATE_KEY_PATH: item.key_delivery_state = "UNAVAILABLE_NO_ESCROW"; db.commit(); raise HTTPException(503, "Emergency escrow is not configured")
    version = db.scalar(select(RecordVersion).where(RecordVersion.record_id == record.id).order_by(RecordVersion.version.desc()).limit(1))
    escrow = db.scalar(select(EncryptedEnvelope).where(EncryptedEnvelope.record_version_id == version.id, EncryptedEnvelope.recipient_email == settings.EMERGENCY_ESCROW_EMAIL)) if version else None
    doctor_key = db.scalar(select(UserKey).where(UserKey.user_email == user.email, UserKey.is_active.is_(True)))
    if not version or not escrow or not doctor_key: item.key_delivery_state = "UNAVAILABLE_MISSING_ENVELOPE"; db.commit(); raise HTTPException(503, "Emergency key material is unavailable")
    try:
        private_pem = Path(settings.EMERGENCY_ESCROW_PRIVATE_KEY_PATH).read_bytes()
        raw_key = unwrap_rsa_oaep_sha256(private_pem, base64.b64decode(escrow.wrapped_key, validate=True))
        wrapped = wrap_rsa_oaep_sha256(doctor_key.public_key_spki_b64, raw_key)
    except Exception as exc: item.key_delivery_state = "FAILED"; db.commit(); raise HTTPException(503, "Emergency escrow unwrap failed") from exc
    unsigned = {"format":"healerplus.key-envelope","version":1,"wrapping":"RSA-OAEP-SHA-256","record_id":record.id,"record_version":version.version,"recipient_key_version":doctor_key.version,"wrapped_key_b64":base64.b64encode(wrapped).decode()}
    key_envelope = KeyEnvelope.model_validate({**unsigned,"digest":sha256_digest(canonical_bytes(unsigned))}); encrypted = RecordEnvelope.model_validate(version.envelope_json)
    item.key_delivery_state = "DELIVERED"; db.commit()
    return {"emergency_id":item.id,"key_delivery_state":item.key_delivery_state,"envelope":encrypted.model_dump(mode="json"),"key_envelope":key_envelope.model_dump(mode="json"),"trust_boundary":"Institutional RSA escrow rewrapped this record key to the verified doctor's current RSA key."}

@router.get("/transactions/{transaction_id}")
def transaction_status(transaction_id: str, user: User = Depends(verified_user), db: DbSession = Depends(get_db)):
    row = db.get(ChainTransaction, transaction_id)
    if not row or row.sender.lower() != (user.wallet_address or "").lower(): raise HTTPException(404, "Transaction not found")
    if row.status == "SUBMITTED":
        try: blockchain_service.process_transaction(db, row); db.commit()
        except BlockchainUnavailable: pass
    return tx_output(row)
