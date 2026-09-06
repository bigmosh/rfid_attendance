"""AES-128-GCM utilities for encrypted Raspberry Pi attendance payloads."""

import base64
import binascii
import json
import os
import time
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import DEVICE_AES_KEY_BASE64


AES_KEY_BYTES = 16
GCM_NONCE_BYTES = 12


class CryptoConfigurationError(ValueError):
    """Raised for a missing, malformed, or wrong-length local AES key."""


@dataclass(frozen=True)
class EncryptedPayload:
    """Base64-safe AES-GCM transport fields and lightweight timing metadata."""

    nonce: str
    ciphertext: str
    encryption_ms: float


def decode_aes128_key(encoded_key: str) -> bytes:
    """Decode exactly one Base64-encoded 16-byte AES-128 key."""
    if not encoded_key:
        raise CryptoConfigurationError("DEVICE_AES_KEY_BASE64 is not configured")
    try:
        key = base64.b64decode(encoded_key, validate=True)
    except (binascii.Error, ValueError) as error:
        raise CryptoConfigurationError("DEVICE_AES_KEY_BASE64 is not valid Base64") from error
    if len(key) != AES_KEY_BYTES:
        raise CryptoConfigurationError("DEVICE_AES_KEY_BASE64 must decode to 16 bytes")
    return key


def load_device_aes_key() -> bytes:
    """Read and validate the Pi key without ever logging its value."""
    return decode_aes128_key(DEVICE_AES_KEY_BASE64)


def serialize_payload(payload: dict) -> bytes:
    """Encode payload JSON deterministically for reproducible crypto testing."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def encrypt_payload(payload: dict, key: bytes, device_id: str) -> EncryptedPayload:
    """Encrypt a payload with a fresh 96-bit nonce and device ID as AAD."""
    if len(key) != AES_KEY_BYTES:
        raise CryptoConfigurationError("AES-128-GCM key must be 16 bytes")
    nonce = os.urandom(GCM_NONCE_BYTES)
    started = time.perf_counter()
    ciphertext = AESGCM(key).encrypt(nonce, serialize_payload(payload), device_id.encode("utf-8"))
    elapsed_ms = (time.perf_counter() - started) * 1000
    return EncryptedPayload(
        nonce=base64.b64encode(nonce).decode("ascii"),
        ciphertext=base64.b64encode(ciphertext).decode("ascii"),
        encryption_ms=elapsed_ms,
    )


def decrypt_payload(nonce: str, ciphertext: str, key: bytes, device_id: str) -> dict:
    """Decrypt a transport payload; InvalidTag deliberately reaches callers."""
    try:
        nonce_bytes = base64.b64decode(nonce, validate=True)
        ciphertext_bytes = base64.b64decode(ciphertext, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Encrypted transport fields are not valid Base64") from error
    if len(nonce_bytes) != GCM_NONCE_BYTES:
        raise ValueError("AES-GCM nonce must be 12 bytes")
    plaintext = AESGCM(key).decrypt(
        nonce_bytes,
        ciphertext_bytes,
        device_id.encode("utf-8"),
    )
    value = json.loads(plaintext.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Encrypted plaintext must be a JSON object")
    return value


__all__ = [
    "AES_KEY_BYTES",
    "GCM_NONCE_BYTES",
    "CryptoConfigurationError",
    "EncryptedPayload",
    "InvalidTag",
    "decode_aes128_key",
    "load_device_aes_key",
    "serialize_payload",
    "encrypt_payload",
    "decrypt_payload",
]
