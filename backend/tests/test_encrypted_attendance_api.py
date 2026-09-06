"""Encrypted attendance API tests using in-memory SQLite and fake test keys."""

import base64
import json

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base, get_db
from app.main import create_app
from app.models import Attendance, CardStatus, Device, RFIDCard, Student, StudentStatus


KEY = b"0123456789abcdef"
KEY_BASE64 = base64.b64encode(KEY).decode("ascii")
DEVICE_ID = "attendance-pi-01"


def _encrypt_bytes(plaintext: bytes, key=KEY, aad=DEVICE_ID):
    nonce = b"123456789012"
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad.encode("utf-8"))
    return base64.b64encode(nonce).decode(), base64.b64encode(ciphertext).decode()


def _encrypted_request(payload=None, key=KEY, device_id=DEVICE_ID, aad=DEVICE_ID):
    payload = payload or {
        "card_uid": "77-48-28-61-92",
        "event_time": "2026-09-06T14:20:10+03:00",
    }
    plaintext = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    nonce, ciphertext = _encrypt_bytes(plaintext, key, aad)
    return {"device_id": device_id, "nonce": nonce, "ciphertext": ciphertext}


@pytest.fixture
def encrypted_api(monkeypatch):
    monkeypatch.setenv("DEVICE_AES_KEYS_JSON", json.dumps({DEVICE_ID: KEY_BASE64, "attendance-pi-02": KEY_BASE64}))
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    application = create_app()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application) as client:
        yield client, session_factory
    application.dependency_overrides.clear()
    get_settings.cache_clear()


def _seed(session_factory, card_status=CardStatus.ACTIVE, student_status=StudentStatus.ACTIVE):
    with session_factory.begin() as session:
        student = Student(student_number="ST001", name="Student 1", status=student_status)
        device = Device(device_id=DEVICE_ID, name="Main Device", status="active")
        other_device = Device(device_id="attendance-pi-02", name="Second Device", status="active")
        session.add_all([student, device, other_device])
        session.flush()
        session.add(RFIDCard(uid="77-48-28-61-92", student_id=student.id, status=card_status))


def _attendance_count(session_factory):
    with session_factory() as session:
        return session.scalar(select(func.count()).select_from(Attendance))


def test_valid_encrypted_attendance_records_then_deduplicates_daily(encrypted_api):
    client, session_factory = encrypted_api
    _seed(session_factory)

    first = client.post("/api/v1/attendance/encrypted", json=_encrypted_request())
    repeat = client.post("/api/v1/attendance/encrypted", json=_encrypted_request())

    assert first.status_code == 200
    assert first.json()["success"] is True
    assert first.json()["attendance"]["status"] == "recorded"
    assert first.json()["attendance"]["attendance_date"]
    assert repeat.json()["attendance"]["status"] == "already_recorded_today"
    assert repeat.json()["attendance"]["id"] == first.json()["attendance"]["id"]
    assert _attendance_count(session_factory) == 1


def test_unknown_device_missing_key_and_malformed_transport_create_no_attendance(encrypted_api, monkeypatch):
    client, session_factory = encrypted_api
    _seed(session_factory)

    unknown = _encrypted_request(device_id="unknown-device", aad="unknown-device")
    assert client.post("/api/v1/attendance/encrypted", json=unknown).json()["reason"] == "unknown_device"

    monkeypatch.setenv("DEVICE_AES_KEYS_JSON", "{}")
    get_settings.cache_clear()
    assert client.post("/api/v1/attendance/encrypted", json=_encrypted_request()).json()["reason"] == "device_key_not_configured"

    monkeypatch.setenv("DEVICE_AES_KEYS_JSON", json.dumps({DEVICE_ID: KEY_BASE64}))
    get_settings.cache_clear()
    malformed = {"device_id": DEVICE_ID, "nonce": "not base64", "ciphertext": "also not base64"}
    assert client.post("/api/v1/attendance/encrypted", json=malformed).json()["reason"] == "invalid_encrypted_payload"
    assert _attendance_count(session_factory) == 0


def test_wrong_nonce_tampering_wrong_key_and_modified_device_aad_fail_cleanly(encrypted_api):
    client, session_factory = encrypted_api
    _seed(session_factory)

    wrong_nonce = _encrypted_request()
    wrong_nonce["nonce"] = base64.b64encode(b"short").decode()
    assert client.post("/api/v1/attendance/encrypted", json=wrong_nonce).json()["reason"] == "invalid_encrypted_payload"

    tampered = _encrypted_request()
    ciphertext = bytearray(base64.b64decode(tampered["ciphertext"]))
    ciphertext[-1] ^= 1
    tampered["ciphertext"] = base64.b64encode(ciphertext).decode()
    assert client.post("/api/v1/attendance/encrypted", json=tampered).json()["reason"] == "authentication_failed"

    wrong_key = _encrypted_request(key=b"fedcba9876543210")
    assert client.post("/api/v1/attendance/encrypted", json=wrong_key).json()["reason"] == "authentication_failed"

    changed_device = _encrypted_request(device_id="attendance-pi-02", aad=DEVICE_ID)
    assert client.post("/api/v1/attendance/encrypted", json=changed_device).json()["reason"] == "authentication_failed"
    assert _attendance_count(session_factory) == 0


def test_invalid_authenticated_plaintext_and_domain_rejections_are_preserved(encrypted_api):
    client, session_factory = encrypted_api
    _seed(session_factory)

    nonce, ciphertext = _encrypt_bytes(b"not json")
    invalid_json = {"device_id": DEVICE_ID, "nonce": nonce, "ciphertext": ciphertext}
    assert client.post("/api/v1/attendance/encrypted", json=invalid_json).json()["reason"] == "invalid_plaintext_payload"

    assert client.post(
        "/api/v1/attendance/encrypted",
        json=_encrypted_request({"event_time": "2026-09-06T14:20:10+03:00"}),
    ).json()["reason"] == "invalid_plaintext_payload"
    assert client.post(
        "/api/v1/attendance/encrypted",
        json=_encrypted_request({"card_uid": "77-48-28-61-92", "event_time": "invalid"}),
    ).json()["reason"] == "invalid_plaintext_payload"

    unknown_card = _encrypted_request({"card_uid": "1-2-3-4-5", "event_time": "2026-09-06T14:20:10+03:00"})
    assert client.post("/api/v1/attendance/encrypted", json=unknown_card).json()["reason"] == "unknown_card"

    with session_factory.begin() as session:
        session.scalar(select(RFIDCard)).status = CardStatus.DISABLED
    assert client.post("/api/v1/attendance/encrypted", json=_encrypted_request()).json()["reason"] == "card_disabled"

    with session_factory.begin() as session:
        session.scalar(select(RFIDCard)).status = CardStatus.ACTIVE
        session.scalar(select(Student)).status = StudentStatus.INACTIVE
    assert client.post("/api/v1/attendance/encrypted", json=_encrypted_request()).json()["reason"] == "student_inactive"
    assert _attendance_count(session_factory) == 0


def test_plaintext_attendance_endpoint_remains_available_for_baseline(encrypted_api):
    client, session_factory = encrypted_api
    _seed(session_factory)

    response = client.post(
        "/api/v1/attendance",
        json={
            "device_id": DEVICE_ID,
            "card_uid": "77-48-28-61-92",
            "event_time": "2026-09-06T14:20:10+03:00",
        },
    )

    assert response.status_code == 200
    assert response.json()["attendance"]["status"] == "recorded"
