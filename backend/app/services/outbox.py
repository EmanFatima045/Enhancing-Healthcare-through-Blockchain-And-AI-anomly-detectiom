"""Idempotent background jobs for scoped service writes and deterministic local notifications."""
from datetime import datetime, timezone
from sqlalchemy import select
from web3 import Web3
from ..core.config import settings
from ..models import NotificationDelivery, OutboxJob
from .blockchain_service import blockchain_service

def enqueue(db, topic: str, dedupe_key: str, payload: dict) -> OutboxJob:
    existing = db.scalar(select(OutboxJob).where(OutboxJob.dedupe_key == dedupe_key))
    if existing: return existing
    job = OutboxJob(topic=topic, dedupe_key=dedupe_key, payload=payload, status="PENDING"); db.add(job); return job

def process_jobs(db, limit: int = 25) -> dict:
    processed = failed = 0
    for job in db.scalars(select(OutboxJob).where(OutboxJob.status.in_(["PENDING", "RETRY", "SUBMITTED"])).order_by(OutboxJob.created_at).limit(limit)):
        job.attempts += 1
        try:
            if job.status=="SUBMITTED" and job.payload.get("tx_hash"):
                try: receipt=blockchain_service.w3.eth.get_transaction_receipt(job.payload["tx_hash"])
                except Exception: continue
                job.status="COMPLETE" if receipt.status==1 else "FAILED";processed+=1;continue
            if job.topic == "NOTIFICATION":
                delivery = db.scalar(select(NotificationDelivery).where(NotificationDelivery.dedupe_key == job.dedupe_key))
                if not delivery:
                    delivery = NotificationDelivery(dedupe_key=job.dedupe_key, channel="LOCAL", recipient=job.payload["recipient"], payload_json=job.payload, status="DELIVERED", delivered_at=datetime.now(timezone.utc)); db.add(delivery)
                job.status = "COMPLETE"
            elif job.topic == "RECORD_ANCHOR":
                tx_hash=_write_record_anchor(job.payload);job.payload={**job.payload,"tx_hash":tx_hash};job.status="SUBMITTED"
            elif job.topic == "STAFF_REGISTER":
                _write_staff(job.payload); job.status = "COMPLETE"
            elif job.topic == "INCIDENT_ATTESTATION":
                tx_hash=_write_incident(job.payload);job.payload={**job.payload,"tx_hash":tx_hash} if tx_hash else job.payload;job.status="SUBMITTED" if tx_hash else "COMPLETE"
            else: raise RuntimeError("Unsupported outbox topic")
            processed += 1
        except Exception as exc:
            job.status = "RETRY" if job.attempts < 10 else "FAILED"; job.payload = {**job.payload, "last_error": type(exc).__name__}; failed += 1
    db.commit(); return {"processed": processed, "failed": failed}

def _write_record_anchor(payload: dict) -> str:
    if "RECORD_ANCHOR" not in settings.SERVICE_SIGNER_SCOPES or not settings.SERVICE_SIGNER_PRIVATE_KEY: raise RuntimeError("Scoped record anchor signer is unavailable")
    blockchain_service.require_ready(); w3 = blockchain_service.w3; contract = blockchain_service.contracts["MedicalAuditRegistry"]
    account = w3.eth.account.from_key(settings.SERVICE_SIGNER_PRIVATE_KEY)
    fn = contract.functions.registerRecord(Web3.keccak(text=payload["record_id"]), Web3.to_checksum_address(payload["patient_wallet"]), bytes.fromhex(payload["envelope_digest"].removeprefix("sha256:")), Web3.keccak(text=payload["storage"]), Web3.keccak(text=payload["category"]))
    tx = fn.build_transaction({"from": account.address, "nonce": w3.eth.get_transaction_count(account.address, "pending"), "chainId": settings.CHAIN_ID})
    signed = account.sign_transaction(tx); return w3.eth.send_raw_transaction(signed.raw_transaction).hex()

def _write_staff(payload: dict) -> None:
    if "STAFF_ADMIN" not in settings.SERVICE_SIGNER_SCOPES or not settings.STAFF_ADMIN_PRIVATE_KEY: raise RuntimeError("Scoped staff administrator signer is unavailable")
    blockchain_service.require_ready();w3=blockchain_service.w3;contract=blockchain_service.contracts["HealerAuth"];account=w3.eth.account.from_key(settings.STAFF_ADMIN_PRIVATE_KEY);target=Web3.to_checksum_address(payload["wallet"]);role={"Doctor":2,"HospitalAdmin":4,"SecurityAuditor":5}[payload["role"]]
    current=contract.functions.getAccount(target).call()
    if int(current[0])==0:
        tx=contract.functions.registerStaff(target,role).build_transaction({"from":account.address,"nonce":w3.eth.get_transaction_count(account.address,"pending"),"chainId":settings.CHAIN_ID});receipt=w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(account.sign_transaction(tx).raw_transaction),timeout=60)
        if receipt.status!=1:raise RuntimeError("registerStaff reverted")
    current=contract.functions.getAccount(target).call()
    if not bool(current[1]):
        tx=contract.functions.setVerified(target,True).build_transaction({"from":account.address,"nonce":w3.eth.get_transaction_count(account.address,"pending"),"chainId":settings.CHAIN_ID});receipt=w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(account.sign_transaction(tx).raw_transaction),timeout=60)
        if receipt.status!=1:raise RuntimeError("setVerified reverted")

def _write_incident(payload: dict) -> str | None:
    if "INCIDENT_ATTESTATION" not in settings.SERVICE_SIGNER_SCOPES or not settings.SERVICE_SIGNER_PRIVATE_KEY: raise RuntimeError("Scoped incident attestation signer is unavailable")
    blockchain_service.require_ready();w3=blockchain_service.w3;contract=blockchain_service.contracts["MedicalAuditRegistry"];account=w3.eth.account.from_key(settings.SERVICE_SIGNER_PRIVATE_KEY)
    commitment=Web3.keccak(text=payload["incident_id"])
    if contract.functions.incidentAttested(commitment).call(): return None
    tx=contract.functions.attestIncident(commitment).build_transaction({"from":account.address,"nonce":w3.eth.get_transaction_count(account.address,"pending"),"chainId":settings.CHAIN_ID});signed=account.sign_transaction(tx);return w3.eth.send_raw_transaction(signed.raw_transaction).hex()
