"""Persistent application state. Clinical plaintext and raw keys are intentionally excluded."""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(32), default="Patient", index=True)
    wallet_address: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    public_key: Mapped[Optional[str]] = mapped_column(Text)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class UserKey(Base):
    __tablename__ = "user_keys"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_email: Mapped[str] = mapped_column(ForeignKey("users.email", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    algorithm: Mapped[str] = mapped_column(String(32), default="RSA-OAEP-SHA-256")
    public_key_spki_b64: Mapped[str] = mapped_column(Text)
    fingerprint_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    key_size: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("user_email", "version"),)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_email: Mapped[str] = mapped_column(ForeignKey("users.email", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    client_ip_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ip_hash: Mapped[str] = mapped_column(String(64), index=True)
    email_hash: Mapped[str] = mapped_column(String(64), index=True)
    succeeded: Mapped[bool] = mapped_column(Boolean)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_email: Mapped[str] = mapped_column(ForeignKey("users.email"), index=True)
    service: Mapped[str] = mapped_column(String(100))
    practitioner: Mapped[Optional[str]] = mapped_column(String(100))
    preferred_date: Mapped[datetime] = mapped_column(Date)
    preferred_time: Mapped[str] = mapped_column(String(5))
    patient_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(30))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending review")
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MedicalRecord(Base):
    __tablename__ = "medical_records"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    patient_email: Mapped[str] = mapped_column(ForeignKey("users.email"), index=True)
    owner_wallet: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(64), index=True)
    data_hash: Mapped[str] = mapped_column(String(71))
    storage_kind: Mapped[str] = mapped_column(String(32), default="DATABASE_ENVELOPE")
    cid: Mapped[Optional[str]] = mapped_column(String(128))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    versions: Mapped[list["RecordVersion"]] = relationship(back_populates="record", cascade="all, delete-orphan")


class RecordVersion(Base):
    __tablename__ = "record_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    record_id: Mapped[str] = mapped_column(ForeignKey("medical_records.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    ciphertext_b64: Mapped[str] = mapped_column(Text)
    nonce_b64: Mapped[Optional[str]] = mapped_column(String(128))
    data_hash: Mapped[str] = mapped_column(String(64))
    envelope_json: Mapped[Optional[dict]] = mapped_column(JSON)
    envelope_digest: Mapped[Optional[str]] = mapped_column(String(71), index=True)
    key_version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.email"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    record: Mapped[MedicalRecord] = relationship(back_populates="versions")
    __table_args__ = (UniqueConstraint("record_id", "version"),)


class EncryptedEnvelope(Base):
    __tablename__ = "encrypted_envelopes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    record_version_id: Mapped[str] = mapped_column(ForeignKey("record_versions.id", ondelete="CASCADE"), index=True)
    recipient_email: Mapped[str] = mapped_column(ForeignKey("users.email"), index=True)
    wrapped_key: Mapped[str] = mapped_column(Text)
    algorithm: Mapped[str] = mapped_column(String(64), default="RSA-OAEP-SHA-256")
    recipient_key_version: Mapped[int] = mapped_column(Integer, default=1)
    envelope_json: Mapped[Optional[dict]] = mapped_column(JSON)
    envelope_digest: Mapped[Optional[str]] = mapped_column(String(71))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("record_version_id", "recipient_email"),)


class ChainTransaction(Base):
    __tablename__ = "chain_transactions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    operation: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), default="QUEUED", index=True)
    tx_hash: Mapped[Optional[str]] = mapped_column(String(80), unique=True)
    block_number: Mapped[Optional[int]] = mapped_column(Integer)
    block_hash: Mapped[Optional[str]] = mapped_column(String(66))
    chain_id: Mapped[int] = mapped_column(Integer, default=31337)
    sender: Mapped[Optional[str]] = mapped_column(String(42))
    contract_address: Mapped[Optional[str]] = mapped_column(String(42))
    expected_call: Mapped[Optional[str]] = mapped_column(String(80))
    expected_args: Mapped[dict] = mapped_column(JSON, default=dict)
    confirmations: Mapped[int] = mapped_column(Integer, default=0)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ConsentProjection(Base):
    __tablename__ = "consent_projections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_email: Mapped[str] = mapped_column(ForeignKey("users.email"), index=True)
    practitioner_email: Mapped[str] = mapped_column(ForeignKey("users.email"), index=True)
    category: Mapped[str] = mapped_column(String(64))
    access_level: Mapped[str] = mapped_column(String(24))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="PENDING_CHAIN")
    source: Mapped[str] = mapped_column(String(24), default="LOCAL")
    chain_tx_id: Mapped[Optional[str]] = mapped_column(ForeignKey("chain_transactions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(80))
    severity: Mapped[str] = mapped_column(String(16), index=True)
    source: Mapped[str] = mapped_column(String(32))
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_email: Mapped[Optional[str]] = mapped_column(ForeignKey("users.email"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[Optional[str]] = mapped_column(String(128))
    outcome: Mapped[str] = mapped_column(String(24))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class OutboxJob(Base):
    __tablename__ = "outbox_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    topic: Mapped[str] = mapped_column(String(80), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(160), unique=True)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WalletChallenge(Base):
    __tablename__ = "wallet_challenges"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_email: Mapped[str] = mapped_column(ForeignKey("users.email", ondelete="CASCADE"), index=True)
    wallet_address: Mapped[str] = mapped_column(String(42), index=True)
    nonce_hash: Mapped[str] = mapped_column(String(64), unique=True)
    domain: Mapped[str] = mapped_column(String(255))
    chain_id: Mapped[int] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IndexedChainLog(Base):
    __tablename__ = "indexed_chain_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    chain_id: Mapped[int] = mapped_column(Integer)
    block_number: Mapped[int] = mapped_column(Integer)
    block_hash: Mapped[str] = mapped_column(String(66))
    tx_hash: Mapped[str] = mapped_column(String(66))
    log_index: Mapped[int] = mapped_column(Integer)
    contract_address: Mapped[str] = mapped_column(String(42))
    event_name: Mapped[str] = mapped_column(String(80))
    args_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("chain_id", "block_hash", "tx_hash", "log_index"),)


class EmergencyAccess(Base):
    __tablename__ = "emergency_access"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    record_id: Mapped[str] = mapped_column(ForeignKey("medical_records.id"), index=True)
    practitioner_email: Mapped[str] = mapped_column(ForeignKey("users.email"), index=True)
    justification: Mapped[str] = mapped_column(Text)
    justification_commitment: Mapped[str] = mapped_column(String(66))
    emergency_type: Mapped[int] = mapped_column(Integer)
    chain_session_id: Mapped[Optional[int]] = mapped_column(Integer)
    chain_tx_id: Mapped[Optional[str]] = mapped_column(ForeignKey("chain_transactions.id"))
    status: Mapped[str] = mapped_column(String(32), default="AWAITING_SIGNATURE")
    key_delivery_state: Mapped[str] = mapped_column(String(40), default="UNAVAILABLE_NO_ESCROW")
    review_status: Mapped[str] = mapped_column(String(24), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dedupe_key: Mapped[str] = mapped_column(String(160), unique=True)
    channel: Mapped[str] = mapped_column(String(32), default="LOCAL")
    recipient: Mapped[str] = mapped_column(String(254))
    payload_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), default="PENDING")
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_email: Mapped[str] = mapped_column(ForeignKey("users.email"), index=True)
    classification: Mapped[str] = mapped_column(String(80))
    threat_level: Mapped[str] = mapped_column(String(16))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    measurements: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FederatedRound(Base):
    __tablename__ = "federated_rounds"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    round_number: Mapped[int] = mapped_column(Integer, unique=True)
    status: Mapped[str] = mapped_column(String(24), default="SIMULATED")
    metrics: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.email"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
