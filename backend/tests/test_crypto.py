"""Unit tests for backend AES-128-GCM configuration and decryption."""

import base64
import json

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.services.crypto import (
    AES_KEY_BYTES,
    GCM_NONCE_BYTES,
    DeviceKeyConfigurationError,
    InvalidEncryptedPayloadError,
    decrypt_transport_payload,
    parse_device_key_mapping,
)


KEY = b"0123456789abcdef"
KEY_BASE64 = base64.b64encode(KEY).decode("ascii")
DEVICE_ID = "attendance-pi-01"


def encrypted_transport(payload, key=KEY, device_id=DEVICE_ID):
    nonce = b"123456789012"
    plaintext = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, device_id.encode("utf-8"))
    return base64.b64encode(nonce).decode(), base64.b64encode(ciphertext).decode()


def test_device_key_mapping_requires_base64_aes128_keys():
    keys = parse_device_key_mapping(json.dumps({DEVICE_ID: KEY_BASE64}))
    assert keys[DEVICE_ID] == KEY
    assert len(keys[DEVICE_ID]) == AES_KEY_BYTES
    for malformed in ("[]", "not json", json.dumps({DEVICE_ID: "not base64"})):
        with pytest.raises(DeviceKeyConfigurationError):
            parse_device_key_mapping(malformed)


def test_decrypt_transport_round_trip_uses_12_byte_nonce_and_device_aad():
    nonce, ciphertext = encrypted_transport({"card_uid": "77-48-28-61-92", "event_time": "2026-09-06T14:20:10+03:00"})
    decrypted = decrypt_transport_payload(nonce, ciphertext, KEY, DEVICE_ID)

    assert len(base64.b64decode(nonce)) == GCM_NONCE_BYTES
    assert decrypted.payload["card_uid"] == "77-48-28-61-92"
    assert decrypted.decryption_ms >= 0


def test_tampered_ciphertext_wrong_key_and_wrong_aad_fail_authentication():
    nonce, ciphertext = encrypted_transport({"name": "Mäkelä"})
    tampered = bytearray(base64.b64decode(ciphertext))
    tampered[-1] ^= 1

    with pytest.raises(InvalidTag):
        decrypt_transport_payload(nonce, base64.b64encode(tampered).decode(), KEY, DEVICE_ID)
    with pytest.raises(InvalidTag):
        decrypt_transport_payload(nonce, ciphertext, b"fedcba9876543210", DEVICE_ID)
    with pytest.raises(InvalidTag):
        decrypt_transport_payload(nonce, ciphertext, KEY, "attendance-pi-02")


def test_malformed_base64_and_wrong_nonce_length_are_rejected_before_decryption():
    with pytest.raises(InvalidEncryptedPayloadError):
        decrypt_transport_payload("not base64", "not base64", KEY, DEVICE_ID)
    short_nonce = base64.b64encode(b"short").decode()
    with pytest.raises(InvalidEncryptedPayloadError):
        decrypt_transport_payload(short_nonce, base64.b64encode(b"ciphertext").decode(), KEY, DEVICE_ID)
