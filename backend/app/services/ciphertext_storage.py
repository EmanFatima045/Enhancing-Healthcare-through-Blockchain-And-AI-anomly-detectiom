"""Optional real remote storage adapters. The database remains the durable LOCAL copy."""

import re
from typing import Any

import requests

from ..core.config import settings

CID = re.compile(r"^[a-zA-Z0-9]{32,128}$")


class CiphertextStorage:
    def store(self, record_id: str, canonical_envelope: bytes) -> dict[str, Any]:
        mode = settings.CIPHERTEXT_STORAGE
        if mode == "local":
            return {"status": "LOCAL", "cid": None, "error": None}
        try:
            if mode == "kubo":
                if not settings.KUBO_API_URL:
                    raise RuntimeError("KUBO_API_URL is not configured")
                response = requests.post(f"{settings.KUBO_API_URL}/api/v0/add",
                                         files={"file": (f"{record_id}.json", canonical_envelope, "application/json")},
                                         params={"pin": "true", "cid-version": "1"}, timeout=20)
                response.raise_for_status()
                cid = response.json().get("Hash")
            elif mode == "pinata":
                if not settings.PINATA_JWT:
                    raise RuntimeError("PINATA_JWT is not configured")
                response = requests.post("https://uploads.pinata.cloud/v3/files",
                                         headers={"Authorization": f"Bearer {settings.PINATA_JWT}"},
                                         files={"file": (f"{record_id}.json", canonical_envelope, "application/json")},
                                         data={"network": "public", "name": f"{record_id}.json"}, timeout=30)
                response.raise_for_status()
                body = response.json()
                cid = body.get("data", {}).get("cid") or body.get("IpfsHash")
            else:
                raise RuntimeError("Unsupported HEALER_CIPHERTEXT_STORAGE value")
            if not isinstance(cid, str) or not CID.fullmatch(cid):
                raise RuntimeError("Storage provider returned no valid CID")
            return {"status": mode.upper(), "cid": cid, "error": None}
        except Exception as exc:
            return {"status": "LOCAL_REMOTE_FAILED", "cid": None, "error": type(exc).__name__}


ciphertext_storage = CiphertextStorage()
