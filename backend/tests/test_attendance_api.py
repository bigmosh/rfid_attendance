"""Attendance API tests using local in-memory SQLite only."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import create_app
import app.models
from app.models import Attendance, CardStatus, Device, RFIDCard, Student


def _seed_records(session_factory, card_status=CardStatus.ACTIVE):
    with session_factory.begin() as session:
        student = Student(student_number="ST001", name="Student 1")
        device = Device(
            device_id="attendance-pi-01",
            name="Main Attendance Device",
            status="active",
        )
        session.add_all([student, device])
        session.flush()
        session.add(
            RFIDCard(
                uid="77-48-28-61-92",
                student_id=student.id,
                status=card_status,
            )
        )


@pytest.fixture
def attendance_api():
    local_engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(local_engine)
    session_factory = sessionmaker(bind=local_engine)
    application = create_app()

    def override_get_db():
        database_session = session_factory()
        try:
            yield database_session
        finally:
            database_session.close()

    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application) as client:
        yield client, session_factory
    application.dependency_overrides.clear()


def _valid_request():
    return {
        "device_id": "attendance-pi-01",
        "card_uid": "77-48-28-61-92",
        "event_time": "2026-09-04T10:30:00+03:00",
    }


def _parse_timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_registered_card_creates_attendance_returns_student_and_updates_last_seen(
    attendance_api,
):
    client, session_factory = attendance_api
    _seed_records(session_factory)

    response = client.post("/api/v1/attendance", json=_valid_request())

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["student"] == {
        "id": 1,
        "student_number": "ST001",
        "name": "Student 1",
    }
    assert body["attendance"]["id"] == 1
    assert body["attendance"]["status"] == "recorded"
    assert body["attendance"]["event_time"] == "2026-09-04T10:30:00+03:00"
    assert _parse_timestamp(body["attendance"]["server_received_at"]).tzinfo is not None

    with session_factory() as session:
        records = list(session.scalars(select(Attendance)))
        device = session.scalar(
            select(Device).where(Device.device_id == "attendance-pi-01")
        )

    assert len(records) == 1
    assert records[0].student_id == 1
    assert records[0].rfid_card_id == 1
    assert records[0].device_id == 1
    assert device.last_seen is not None


def test_unknown_card_returns_application_response_and_updates_last_seen(attendance_api):
    client, session_factory = attendance_api
    _seed_records(session_factory)
    request = _valid_request()
    request["card_uid"] = "1-2-3-4-5"

    response = client.post("/api/v1/attendance", json=request)

    assert response.status_code == 200
    assert response.json() == {"success": False, "reason": "unknown_card"}
    with session_factory() as session:
        assert session.scalar(select(Device.last_seen)) is not None
        assert list(session.scalars(select(Attendance))) == []


def test_disabled_card_returns_application_response_without_attendance(attendance_api):
    client, session_factory = attendance_api
    _seed_records(session_factory, card_status=CardStatus.DISABLED)

    response = client.post("/api/v1/attendance", json=_valid_request())

    assert response.status_code == 200
    assert response.json() == {"success": False, "reason": "card_disabled"}
    with session_factory() as session:
        assert list(session.scalars(select(Attendance))) == []


@pytest.mark.parametrize(
    ("device_id", "deactivate_device"),
    (("missing-device", False), ("attendance-pi-01", True)),
)
def test_unknown_or_inactive_device_returns_unknown_device(
    attendance_api,
    device_id,
    deactivate_device,
):
    client, session_factory = attendance_api
    _seed_records(session_factory)
    if deactivate_device:
        with session_factory.begin() as session:
            device = session.scalar(
                select(Device).where(Device.device_id == "attendance-pi-01")
            )
            device.status = "disabled"

    request = _valid_request()
    request["device_id"] = device_id

    response = client.post("/api/v1/attendance", json=request)

    assert response.status_code == 200
    assert response.json() == {"success": False, "reason": "unknown_device"}
    with session_factory() as session:
        assert list(session.scalars(select(Attendance))) == []


def test_missing_required_field_returns_validation_error(attendance_api):
    client, session_factory = attendance_api
    _seed_records(session_factory)
    request = _valid_request()
    del request["event_time"]

    response = client.post("/api/v1/attendance", json=request)

    assert response.status_code == 422


def test_timezone_naive_event_time_returns_validation_error(attendance_api):
    client, session_factory = attendance_api
    _seed_records(session_factory)
    request = _valid_request()
    request["event_time"] = "2026-09-04T10:30:00"

    response = client.post("/api/v1/attendance", json=request)

    assert response.status_code == 422
