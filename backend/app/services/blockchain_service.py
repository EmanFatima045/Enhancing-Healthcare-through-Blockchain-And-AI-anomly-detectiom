"""Ethereum RPC verification and receipt indexing through maintained web3.py."""
import json
from pathlib import Path
from typing import Any
from eth_account.messages import encode_defunct
from sqlalchemy import select
from web3 import Web3
from web3.exceptions import TransactionNotFound
from web3.logs import DISCARD
from ..core.config import settings
from ..models import ChainTransaction, ConsentProjection, EmergencyAccess, IndexedChainLog, MedicalRecord, utcnow

class BlockchainUnavailable(RuntimeError): pass

class BlockchainService:
    def __init__(self) -> None:
        self.w3 = Web3(Web3.HTTPProvider(settings.RPC_URL, request_kwargs={"timeout": 4})) if settings.RPC_URL else None
        generated = Path(__file__).resolve().parents[1] / "generated" / "contracts" / str(settings.CHAIN_ID)
        manifest_path = generated / "addresses.json"
        self.manifest = json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else {"contracts": {}}
        self.contracts: dict[str, Any] = {}
        overrides = {"HealerAuth": settings.AUTH_ADDRESS, "ConsentManager": settings.CONSENT_ADDRESS, "MedicalAuditRegistry": settings.AUDIT_ADDRESS, "BreakGlassEmergency": settings.BREAK_GLASS_ADDRESS}
        if self.w3:
            for name, item in self.manifest.get("contracts", {}).items():
                address, abi_path = overrides.get(name) or item["address"], generated / item["abi"]
                if abi_path.exists(): self.contracts[name] = self.w3.eth.contract(address=Web3.to_checksum_address(address), abi=json.loads(abi_path.read_text("utf-8")))

    def health(self) -> dict[str, Any]:
        if not self.w3 or not settings.RPC_URL: return {"configured": False, "connected": False, "state": "NOT_CONFIGURED", "chain_id": None, "contracts": {}}
        try:
            if not self.w3.is_connected(): raise BlockchainUnavailable("RPC did not answer")
            chain_id = self.w3.eth.chain_id
            if chain_id != settings.CHAIN_ID: raise BlockchainUnavailable(f"expected chain {settings.CHAIN_ID}, received {chain_id}")
            status = {name: {"address": contract.address, "has_code": len(self.w3.eth.get_code(contract.address)) > 0} for name, contract in self.contracts.items()}
            connected = len(status) == 4 and all(value["has_code"] for value in status.values())
            return {"configured": True, "connected": connected, "state": "READY" if connected else "BYTECODE_MISSING", "chain_id": chain_id, "current_block": self.w3.eth.block_number, "contracts": status}
        except Exception as exc: return {"configured": True, "connected": False, "state": "RPC_INVALID", "error": str(exc), "chain_id": None, "contracts": {}}

    def require_ready(self) -> None:
        if not self.health().get("connected"): raise BlockchainUnavailable("Expected chain and deployed contract bytecode were not verified")

    def recover_wallet(self, message: str, signature: str) -> str:
        account = (self.w3 or Web3()).eth.account
        return Web3.to_checksum_address(account.recover_message(encode_defunct(text=message), signature=signature))

    @staticmethod
    def category_commitment(category: str) -> str: return Web3.keccak(text=category).hex()

    def resolve_consent(self, patient: str, practitioner: str, category: str) -> tuple[bool, int]:
        self.require_ready(); active, level = self.contracts["ConsentManager"].functions.resolveConsent(Web3.to_checksum_address(patient), Web3.to_checksum_address(practitioner), Web3.keccak(text=category)).call()
        return bool(active), int(level)

    def process_transaction(self, db, row: ChainTransaction) -> ChainTransaction:
        self.require_ready(); assert self.w3; row.last_checked_at = utcnow()
        try: receipt = self.w3.eth.get_transaction_receipt(row.tx_hash)
        except TransactionNotFound: row.status = "SUBMITTED"; return row
        tx = self.w3.eth.get_transaction(row.tx_hash); row.block_number, row.block_hash = receipt.blockNumber, receipt.blockHash.hex(); row.confirmations = max(0, self.w3.eth.block_number - receipt.blockNumber + 1)
        if receipt.status != 1: row.status = "REVERTED"; self._invalidate_projection(db, row); return row
        contract = self.contracts.get(row.operation.split(":", 1)[0])
        if not contract or int(tx.get("chainId", settings.CHAIN_ID)) != settings.CHAIN_ID or not tx["to"] or tx["to"].lower() != contract.address.lower() or tx["from"].lower() != (row.sender or "").lower():
            row.status = "FAILED"; row.error = "Receipt sender, chain, or contract mismatch"; self._invalidate_projection(db, row); return row
        function, args = contract.decode_function_input(tx.input); expected = {k: v for k, v in row.expected_args.items() if not k.startswith("_")}
        def normalized(value):
            if isinstance(value, bytes): return "0x" + value.hex()
            if isinstance(value, str) and value.startswith("0x"): return value.lower()
            return str(value).lower()
        if function.fn_name != row.expected_call or any(normalized(args.get(key)) != normalized(value) for key, value in expected.items()):
            row.status = "FAILED"; row.error = "Decoded transaction call did not match prepared intent"; self._invalidate_projection(db, row); return row
        expected_event = {"grantConsent":"ConsentGranted","revokeConsent":"ConsentRevoked","open":"BreakGlassOpened","review":"BreakGlassReviewed","registerPatient":"AccountRegistered"}.get(row.expected_call)
        if not expected_event: row.status="FAILED";row.error="Unsupported prepared call";return row
        logs = getattr(contract.events, expected_event)().process_receipt(receipt, errors=DISCARD)
        if len(logs) != 1: row.status = "FAILED"; row.error = f"Expected exactly one {expected_event} event"; self._invalidate_projection(db, row); return row
        event = logs[0]
        existing = db.scalar(select(IndexedChainLog).where(IndexedChainLog.chain_id == settings.CHAIN_ID, IndexedChainLog.block_hash == event.blockHash.hex(), IndexedChainLog.tx_hash == event.transactionHash.hex(), IndexedChainLog.log_index == event.logIndex))
        if not existing: db.add(IndexedChainLog(chain_id=settings.CHAIN_ID, block_number=event.blockNumber, block_hash=event.blockHash.hex(), tx_hash=event.transactionHash.hex(), log_index=event.logIndex, contract_address=event.address, event_name=event.event, args_json={k: ("0x" + v.hex() if isinstance(v, bytes) else v) for k, v in event.args.items()}))
        if row.confirmations >= settings.CHAIN_CONFIRMATIONS: row.status = "CONFIRMED"; self._apply_projection(db, row, event.args)
        else: row.status = "SUBMITTED"
        return row

    def audit_chain_reset(self, db) -> int:
        if not self.w3: return 0
        changed = 0
        for row in db.scalars(select(ChainTransaction).where(ChainTransaction.status == "CONFIRMED", ChainTransaction.chain_id == settings.CHAIN_ID)):
            try: canonical = self.w3.eth.get_block(row.block_number).hash.hex()
            except Exception: canonical = None
            if canonical != row.block_hash: row.status = "ORPHANED"; self._invalidate_projection(db, row); changed += 1
        return changed

    def _apply_projection(self, db, row: ChainTransaction, event_args=None) -> None:
        projection = db.get(ConsentProjection, row.expected_args.get("_projection_id")) if row.expected_args.get("_projection_id") else None
        if projection: projection.status = "CONFIRMED" if row.expected_call == "grantConsent" else "REVOKED_CHAIN"
        emergency = db.get(EmergencyAccess, row.expected_args.get("_emergency_id")) if row.expected_args.get("_emergency_id") else None
        if emergency:
            if row.expected_call=="review": emergency.review_status=row.expected_args["_review"]
            else: emergency.status = "CONFIRMED"; emergency.chain_session_id = int(event_args.get("sessionId")) if event_args else None
            from .outbox import enqueue
            record = db.get(MedicalRecord, emergency.record_id)
            kind="BREAK_GLASS_REVIEWED" if row.expected_call=="review" else "BREAK_GLASS_CONFIRMED"
            enqueue(db, "NOTIFICATION", f"emergency:{emergency.id}:patient:{kind}", {"recipient": record.patient_email, "kind": kind, "emergency_id": emergency.id})
            enqueue(db, "NOTIFICATION", f"emergency:{emergency.id}:security:{kind}", {"recipient": "local-security-auditor", "kind": "BREAK_GLASS_REVIEW_REQUIRED" if row.expected_call!="review" else kind, "emergency_id": emergency.id})
    def _invalidate_projection(self, db, row: ChainTransaction) -> None:
        projection = db.get(ConsentProjection, row.expected_args.get("_projection_id")) if row.expected_args.get("_projection_id") else None
        if projection and row.expected_call == "grantConsent": projection.status = "INVALID_CHAIN"
        emergency = db.get(EmergencyAccess, row.expected_args.get("_emergency_id")) if row.expected_args.get("_emergency_id") else None
        if emergency: emergency.status = row.status; emergency.key_delivery_state = "NOT_DELIVERED"
    def get_blockchain_overview(self) -> dict[str, Any]: return self.health()

blockchain_service = BlockchainService()
