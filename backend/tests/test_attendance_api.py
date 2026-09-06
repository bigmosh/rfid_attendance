"""Attendance API tests using local in-memory SQLite only."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import create_app
import app.models
from app.models import Attendance, CardStatus, Device, RFIDCard, Student, StudentStatus
from app.services import attendance as attendance_service


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


def _freeze_receipt_time(monkeypatch, value):
    monkeypatch.setattr(attendance_service, "utc_now", lambda: value)


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
    assert body["attendance"]["attendance_date"]
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


def test_first_scan_records_once_and_repeat_returns_original_row_for_local_day(
    attendance_api,
    monkeypatch,
):
    client, session_factory = attendance_api
    _seed_records(session_factory)
    receipt = datetime(2026, 9, 6, 8, 0, tzinfo=timezone.utc)
    _freeze_receipt_time(monkeypatch, receipt)

    first = client.post("/api/v1/attendance", json=_valid_request())
    repeat = client.post("/api/v1/attendance", json=_valid_request())

    assert first.json()["attendance"]["status"] == "recorded"
    assert first.json()["attendance"]["attendance_date"] == "2026-09-06"
    assert repeat.json()["success"] is True
    assert repeat.json()["attendance"]["id"] == first.json()["attendance"]["id"]
    assert repeat.json()["attendance"]["status"] == "already_recorded_today"
    assert repeat.json()["attendance"]["attendance_date"] == "2026-09-06"
    with session_factory() as session:
        assert len(list(session.scalars(select(Attendance)))) == 1


def test_next_local_day_creates_a_new_attendance_row(attendance_api, monkeypatch):
    client, session_factory = attendance_api
    _seed_records(session_factory)
    _freeze_receipt_time(monkeypatch, datetime(2026, 9, 6, 20, 30, tzinfo=timezone.utc))
    first = client.post("/api/v1/attendance", json=_valid_request())
    # 21:30 UTC is 00:30 on 7 September in Europe/Helsinki.
    _freeze_receipt_time(monkeypatch, datetime(2026, 9, 6, 21, 30, tzinfo=timezone.utc))
    next_day = client.post("/api/v1/attendance", json=_valid_request())

    assert first.json()["attendance"]["attendance_date"] == "2026-09-06"
    assert next_day.json()["attendance"]["status"] == "recorded"
    assert next_day.json()["attendance"]["attendance_date"] == "2026-09-07"
    with session_factory() as session:
        assert len(list(session.scalars(select(Attendance)))) == 2


def test_same_student_on_another_device_or_replacement_card_is_still_deduplicated(
    attendance_api,
    monkeypatch,
):
    client, session_factory = attendance_api
    _seed_records(session_factory)
    receipt = datetime(2026, 9, 6, 8, 0, tzinfo=timezone.utc)
    _freeze_receipt_time(monkeypatch, receipt)
    first = client.post("/api/v1/attendance", json=_valid_request()).json()

    with session_factory.begin() as session:
        session.add(Device(device_id="attendance-pi-02", name="Second Device", status="active"))
    by_other_device = _valid_request()
    by_other_device["device_id"] = "attendance-pi-02"
    assert client.post("/api/v1/attendance", json=by_other_device).json()["attendance"]["status"] == "already_recorded_today"

    with session_factory.begin() as session:
        card = session.scalar(select(RFIDCard).where(RFIDCard.uid == "77-48-28-61-92"))
        card.status = CardStatus.DISABLED
        session.add(RFIDCard(uid="10-20-30-40-50", student_id=card.student_id, status=CardStatus.ACTIVE))
    replacement_request = _valid_request()
    replacement_request["card_uid"] = "10-20-30-40-50"
    replacement = client.post("/api/v1/attendance", json=replacement_request).json()
    assert replacement["attendance"]["status"] == "already_recorded_today"
    assert replacement["attendance"]["id"] == first["attendance"]["id"]
    with session_factory() as session:
        assert len(list(session.scalars(select(Attendance)))) == 1


def test_different_students_each_receive_one_daily_attendance(attendance_api, monkeypatch):
    client, session_factory = attendance_api
    _seed_records(session_factory)
    _freeze_receipt_time(monkeypatch, datetime(2026, 9, 6, 8, 0, tzinfo=timezone.utc))
    with session_factory.begin() as session:
        student = Student(student_number="ST002", name="Student 2")
        session.add(student)
        session.flush()
        session.add(RFIDCard(uid="51-164-2-51-166", student_id=student.id, status=CardStatus.ACTIVE))

    assert client.post("/api/v1/attendance", json=_valid_request()).json()["attendance"]["status"] == "recorded"
    second_request = _valid_request()
    second_request["card_uid"] = "51-164-2-51-166"
    assert client.post("/api/v1/attendance", json=second_request).json()["attendance"]["status"] == "recorded"
    with session_factory() as session:
        assert len(list(session.scalars(select(Attendance)))) == 2


def test_unique_conflict_race_returns_already_recorded_today(attendance_api, monkeypatch):
    """Exercise recovery when another transaction inserts after the first lookup."""
    client, session_factory = attendance_api
    _seed_records(session_factory)
    receipt = datetime(2026, 9, 6, 8, 0, tzinfo=timezone.utc)
    _freeze_receipt_time(monkeypatch, receipt)
    with session_factory.begin() as session:
        session.add(
            Attendance(
                student_id=1,
                rfid_card_id=1,
                device_id=1,
                attendance_date=receipt.astimezone(ZoneInfo("Europe/Helsinki")).date(),
                event_time=receipt,
                server_received_at=receipt,
            )
        )

    original_lookup = attendance_service._existing_attendance
    calls = 0

    def lookup_after_race(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        return original_lookup(*args, **kwargs)

    monkeypatch.setattr(attendance_service, "_existing_attendance", lookup_after_race)
    response = client.post("/api/v1/attendance", json=_valid_request())

    assert response.status_code == 200
    assert response.json()["attendance"]["status"] == "already_recorded_today"
    with session_factory() as session:
        assert len(list(session.scalars(select(Attendance)))) == 1


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


def test_inactive_student_returns_existing_domain_failure_without_attendance(attendance_api):
    client, session_factory = attendance_api
    _seed_records(session_factory)
    with session_factory.begin() as session:
        session.get(Student, 1).status = StudentStatus.INACTIVE

    response = client.post("/api/v1/attendance", json=_valid_request())

    assert response.json() == {"success": False, "reason": "student_inactive"}
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
