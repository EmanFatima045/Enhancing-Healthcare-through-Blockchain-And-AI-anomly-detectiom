"""Canonical encrypted-envelope formats shared with browser WebCrypto."""

import base64
import binascii
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def canonical_bytes(value: dict) -> bytes:
    """RFC-8785-compatible for this schema: sorted ASCII keys, UTF-8, no insignificant whitespace."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_digest(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def decode_b64(value: str, field: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
        if base64.b64encode(decoded).decode("ascii") != value:
            raise ValueError(f"{field} must be canonical base64")
        return decoded
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"{field} must be canonical base64") from exc


class RecordAAD(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["healerplus.record-aad"] = "healerplus.record-aad"
    record_id: str = Field(pattern=r"^REC-[A-F0-9]{32}$")
    record_version: int = Field(ge=1, le=1_000_000)


class RecordEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["healerplus.record-envelope"] = "healerplus.record-envelope"
    version: Literal[1] = 1
    cipher: Literal["AES-256-GCM"] = "AES-256-GCM"
    key_version: int = Field(ge=1, le=1_000_000)
    nonce_b64: str = Field(max_length=32)
    ciphertext_b64: str = Field(min_length=24, max_length=2_000_000)
    aad: RecordAAD
    digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")

    @model_validator(mode="after")
    def verify_envelope(self):
        if len(decode_b64(self.nonce_b64, "nonce_b64")) != 12:
            raise ValueError("AES-GCM nonce must be exactly 12 bytes")
        if len(decode_b64(self.ciphertext_b64, "ciphertext_b64")) < 16:
            raise ValueError("ciphertext must contain the 128-bit GCM authentication tag")
        payload = self.model_dump(exclude={"digest"}, mode="json")
        if sha256_digest(canonical_bytes(payload)) != self.digest:
            raise ValueError("encrypted envelope digest mismatch")
        return self


class KeyEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["healerplus.key-envelope"] = "healerplus.key-envelope"
    version: Literal[1] = 1
    wrapping: Literal["RSA-OAEP-SHA-256"] = "RSA-OAEP-SHA-256"
    record_id: str = Field(pattern=r"^REC-[A-F0-9]{32}$")
    record_version: int = Field(ge=1, le=1_000_000)
    recipient_key_version: int = Field(ge=1, le=1_000_000)
    wrapped_key_b64: str = Field(min_length=64, max_length=2048)
    digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")

    @model_validator(mode="after")
    def verify_envelope(self):
        if len(decode_b64(self.wrapped_key_b64, "wrapped_key_b64")) < 384:
            raise ValueError("wrapped key is too short for a supported RSA-3072 key")
        payload = self.model_dump(exclude={"digest"}, mode="json")
        if sha256_digest(canonical_bytes(payload)) != self.digest:
            raise ValueError("key envelope digest mismatch")
        return self
