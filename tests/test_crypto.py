"""Hardware-independent AES-128-GCM tests for the Raspberry Pi service."""

import base64
import unittest

from cryptography.exceptions import InvalidTag

from services.crypto import (
    AES_KEY_BYTES,
    GCM_NONCE_BYTES,
    CryptoConfigurationError,
    decode_aes128_key,
    decrypt_payload,
    encrypt_payload,
    serialize_payload,
)


KEY = b"0123456789abcdef"
DEVICE_ID = "attendance-pi-01"
PAYLOAD = {"event_time": "2026-09-06T14:20:10+03:00", "card_uid": "77-48-28-61-92"}


class EdgeCryptoTests(unittest.TestCase):
    def test_base64_encoded_16_byte_key_is_accepted(self):
        encoded = base64.b64encode(KEY).decode("ascii")
        self.assertEqual(len(decode_aes128_key(encoded)), AES_KEY_BYTES)

    def test_missing_invalid_and_wrong_length_keys_are_rejected(self):
        for encoded in ("", "not base64!", base64.b64encode(b"too short").decode("ascii")):
            with self.assertRaises(CryptoConfigurationError):
                decode_aes128_key(encoded)

    def test_round_trip_uses_a_12_byte_nonce_and_deterministic_plaintext(self):
        encrypted = encrypt_payload(PAYLOAD, KEY, DEVICE_ID)
        nonce = base64.b64decode(encrypted.nonce, validate=True)

        self.assertEqual(len(nonce), GCM_NONCE_BYTES)
        self.assertEqual(decrypt_payload(encrypted.nonce, encrypted.ciphertext, KEY, DEVICE_ID), PAYLOAD)
        self.assertEqual(
            serialize_payload({"card_uid": PAYLOAD["card_uid"], "event_time": PAYLOAD["event_time"]}),
            serialize_payload(PAYLOAD),
        )

    def test_identical_plaintext_encryptions_use_different_nonce_and_ciphertext(self):
        first = encrypt_payload(PAYLOAD, KEY, DEVICE_ID)
        second = encrypt_payload(PAYLOAD, KEY, DEVICE_ID)

        self.assertNotEqual(first.nonce, second.nonce)
        self.assertNotEqual(first.ciphertext, second.ciphertext)
        self.assertEqual(decrypt_payload(first.nonce, first.ciphertext, KEY, DEVICE_ID), PAYLOAD)
        self.assertEqual(decrypt_payload(second.nonce, second.ciphertext, KEY, DEVICE_ID), PAYLOAD)

    def test_tampered_ciphertext_wrong_aad_and_wrong_key_fail_authentication(self):
        encrypted = encrypt_payload({"name": "Mäkelä", **PAYLOAD}, KEY, DEVICE_ID)
        ciphertext = bytearray(base64.b64decode(encrypted.ciphertext))
        ciphertext[-1] ^= 1
        tampered = base64.b64encode(ciphertext).decode("ascii")

        with self.assertRaises(InvalidTag):
            decrypt_payload(encrypted.nonce, tampered, KEY, DEVICE_ID)
        with self.assertRaises(InvalidTag):
            decrypt_payload(encrypted.nonce, encrypted.ciphertext, KEY, "attendance-pi-02")
        with self.assertRaises(InvalidTag):
            decrypt_payload(encrypted.nonce, encrypted.ciphertext, b"fedcba9876543210", DEVICE_ID)
