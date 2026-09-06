"""AES-128-GCM transport helpers for encrypted attendance requests."""

import base64
import binascii
import json
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


AES_KEY_BYTES = 16
GCM_NONCE_BYTES = 12


class DeviceKeyConfigurationError(ValueError):
    """Raised when the environment device-key mapping is unusable."""


class InvalidEncryptedPayloadError(ValueError):
    """Raised for malformed Base64 fields or a non-96-bit nonce."""


class InvalidPlaintextPayloadError(ValueError):
    """Raised when authenticated plaintext is not a JSON object."""


@dataclass(frozen=True)
class DecryptedPayload:
    payload: dict
    decryption_ms: float


def decode_aes128_key(encoded_key: str) -> bytes:
    """Decode a single Base64 AES-128 key without revealing its value."""
    try:
        key = base64.b64decode(encoded_key, validate=True)
    except (binascii.Error, ValueError) as error:
        raise DeviceKeyConfigurationError("Device AES key is not valid Base64") from error
    if len(key) != AES_KEY_BYTES:
        raise DeviceKeyConfigurationError("Device AES key must decode to 16 bytes")
    return key


def parse_device_key_mapping(encoded_mapping: str) -> dict[str, bytes]:
    """Parse DEVICE_AES_KEYS_JSON into validated AES-128 keys."""
    if not encoded_mapping:
        return {}
    try:
        mapping = json.loads(encoded_mapping)
    except json.JSONDecodeError as error:
        raise DeviceKeyConfigurationError("DEVICE_AES_KEYS_JSON is not valid JSON") from error
    if not isinstance(mapping, dict):
        raise DeviceKeyConfigurationError("DEVICE_AES_KEYS_JSON must be a JSON object")

    keys = {}
    for device_id, encoded_key in mapping.items():
        if not isinstance(device_id, str) or not isinstance(encoded_key, str):
            raise DeviceKeyConfigurationError("DEVICE_AES_KEYS_JSON contains an invalid entry")
        keys[device_id] = decode_aes128_key(encoded_key)
    return keys


def decrypt_transport_payload(
    nonce: str,
    ciphertext: str,
    key: bytes,
    device_id: str,
) -> DecryptedPayload:
    """Authenticate/decrypt a Base64 AES-GCM transport payload using AAD."""
    try:
        nonce_bytes = base64.b64decode(nonce, validate=True)
        ciphertext_bytes = base64.b64decode(ciphertext, validate=True)
    except (binascii.Error, ValueError) as error:
        raise InvalidEncryptedPayloadError("Encrypted fields are not valid Base64") from error
    if len(nonce_bytes) != GCM_NONCE_BYTES:
        raise InvalidEncryptedPayloadError("AES-GCM nonce must be 12 bytes")

    from time import perf_counter

    started = perf_counter()
    plaintext = AESGCM(key).decrypt(
        nonce_bytes,
        ciphertext_bytes,
        device_id.encode("utf-8"),
    )
    elapsed_ms = (perf_counter() - started) * 1000
    try:
        payload = json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidPlaintextPayloadError("Authenticated plaintext is not valid JSON") from error
    if not isinstance(payload, dict):
        raise InvalidPlaintextPayloadError("Authenticated plaintext must be a JSON object")
    return DecryptedPayload(payload=payload, decryption_ms=elapsed_ms)


__all__ = [
    "AES_KEY_BYTES",
    "GCM_NONCE_BYTES",
    "InvalidTag",
    "DeviceKeyConfigurationError",
    "InvalidEncryptedPayloadError",
    "InvalidPlaintextPayloadError",
    "DecryptedPayload",
    "decode_aes128_key",
    "parse_device_key_mapping",
    "decrypt_transport_payload",
]
