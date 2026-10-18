"""Real cryptographic primitives only; no fallback or placeholder key material."""

import base64
import hashlib
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt_aes_gcm(plaintext: bytes, associated_data: bytes) -> tuple[bytes, bytes, bytes]:
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    return key, nonce, AESGCM(key).encrypt(nonce, plaintext, associated_data)


def decrypt_aes_gcm(key: bytes, nonce: bytes, ciphertext_with_tag: bytes, associated_data: bytes) -> bytes:
    if len(key) != 32 or len(nonce) != 12:
        raise ValueError("AES-256-GCM requires a 32-byte key and 12-byte nonce")
    return AESGCM(key).decrypt(nonce, ciphertext_with_tag, associated_data)


def validate_rsa_public_key(spki_b64: str) -> tuple[str, int]:
    try:
        der = base64.b64decode(spki_b64, validate=True)
        key = serialization.load_der_public_key(der)
    except Exception as exc:
        raise ValueError("Invalid DER SubjectPublicKeyInfo") from exc
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size < 3072:
        raise ValueError("A real RSA public key of at least 3072 bits is required")
    if key.public_numbers().e != 65537:
        raise ValueError("RSA public exponent 65537 is required")
    return hashlib.sha256(der).hexdigest(), key.key_size


def unwrap_rsa_oaep_sha256(private_key_pem: bytes, wrapped_key: bytes) -> bytes:
    """Test/administrative helper. Patient private keys must never be sent to the backend."""
    key = serialization.load_pem_private_key(private_key_pem, password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError("RSA private key required")
    return key.decrypt(wrapped_key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                                                 algorithm=hashes.SHA256(), label=None))


def wrap_rsa_oaep_sha256(public_key_spki_b64: str, raw_key: bytes) -> bytes:
    key = serialization.load_der_public_key(base64.b64decode(public_key_spki_b64, validate=True))
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size < 3072:
        raise ValueError("RSA-3072 public key required")
    return key.encrypt(raw_key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
