"""Dashboard-to-device RFID enrollment tests using in-memory SQLite."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import create_app
from app.models import (
    Attendance,
    CardStatus,
    Device,
    EnrollmentRequest,
    EnrollmentStatus,
    RFIDCard,
    Student,
    StudentStatus,
)


@pytest.fixture
def enrollment_api():
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


def seed_records(session_factory, include_existing_card=False):
    now = datetime.now(timezone.utc)
    with session_factory.begin() as session:
        student_1 = Student(student_number="ST001", name="Student 1")
        student_2 = Student(student_number="ST002", name="Student 2")
        device_1 = Device(device_id="attendance-pi-01", name="Main Device", status="active")
        device_2 = Device(device_id="attendance-pi-02", name="Lab Device", status="active")
        inactive_device = Device(device_id="disabled-pi", name="Disabled Device", status="disabled")
        session.add_all([student_1, student_2, device_1, device_2, inactive_device])
        session.flush()
        if include_existing_card:
            card = RFIDCard(uid="77-48-28-61-92", student_id=student_1.id, status=CardStatus.ACTIVE)
            session.add(card)
            session.flush()
            session.add(
                Attendance(
                    student_id=student_1.id,
                    rfid_card_id=card.id,
                    device_id=device_1.id,
                    event_time=now,
                    server_received_at=now,
                )
            )


def create_enrollment(client, student_id=1, device_id="attendance-pi-01"):
    return client.post(
        "/api/v1/enrollments",
        json={"student_id": student_id, "device_id": device_id},
    )


def test_create_enrollment_validates_student_device_and_one_pending_device(enrollment_api):
    client, session_factory = enrollment_api
    seed_records(session_factory)

    response = create_enrollment(client)
    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert response.json()["student"]["student_number"] == "ST001"
    assert response.json()["device"]["device_id"] == "attendance-pi-01"

    conflict = create_enrollment(client, student_id=2)
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "pending_enrollment_exists"
    assert create_enrollment(client, student_id=999).status_code == 409
    assert create_enrollment(client, student_id=2, device_id="missing-pi").status_code == 409
    assert create_enrollment(client, student_id=2, device_id="disabled-pi").status_code == 409


def test_inactive_student_cannot_start_enrollment_and_device_poll_returns_none_when_idle(enrollment_api):
    client, session_factory = enrollment_api
    seed_records(session_factory)
    with session_factory.begin() as session:
        session.get(Student, 2).status = StudentStatus.INACTIVE

    assert create_enrollment(client, student_id=2).status_code == 409
    assert client.get("/api/v1/devices/attendance-pi-01/enrollment").json() == {"status": "none"}
    assert client.get("/api/v1/devices/disabled-pi/enrollment").json() == {"status": "none"}


def test_pi_polls_pending_enrollment_and_completes_card_assignment(enrollment_api):
    client, session_factory = enrollment_api
    seed_records(session_factory)
    enrollment = create_enrollment(client).json()

    poll = client.get("/api/v1/devices/attendance-pi-01/enrollment")
    assert poll.status_code == 200
    assert poll.json()["status"] == "pending"
    assert poll.json()["enrollment_id"] == enrollment["id"]

    completed = client.post(
        f"/api/v1/enrollments/{enrollment['id']}/card",
        json={"device_id": "attendance-pi-01", "card_uid": "12-34-56-78"},
    )
    assert completed.status_code == 200
    assert completed.json() == {
        "success": True,
        "status": "completed",
        "reason": None,
        "student": {"id": 1, "student_number": "ST001", "name": "Student 1"},
        "card_status": "active",
    }

    with session_factory() as session:
        assert session.get(EnrollmentRequest, enrollment["id"]).status == EnrollmentStatus.COMPLETED
        card = session.scalar(select(RFIDCard).where(RFIDCard.uid == "12-34-56-78"))
        assert card.student_id == 1
        assert card.status == CardStatus.ACTIVE


def test_duplicate_card_keeps_enrollment_pending_for_another_tap(enrollment_api):
    client, session_factory = enrollment_api
    seed_records(session_factory, include_existing_card=True)
    enrollment = create_enrollment(client, student_id=2).json()

    duplicate = client.post(
        f"/api/v1/enrollments/{enrollment['id']}/card",
        json={"device_id": "attendance-pi-01", "card_uid": "77-48-28-61-92"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "pending"
    assert duplicate.json()["reason"] == "card_already_assigned"
    assert client.get("/api/v1/devices/attendance-pi-01/enrollment").json()["status"] == "pending"


def test_enrollment_replacement_preserves_historical_attendance(enrollment_api):
    client, session_factory = enrollment_api
    seed_records(session_factory, include_existing_card=True)
    enrollment = create_enrollment(client, student_id=1).json()

    response = client.post(
        f"/api/v1/enrollments/{enrollment['id']}/card",
        json={"device_id": "attendance-pi-01", "card_uid": "1-2-3-4-5"},
    )
    assert response.json()["success"] is True
    with session_factory() as session:
        cards = list(session.scalars(select(RFIDCard).where(RFIDCard.student_id == 1)))
        old_card = next(card for card in cards if card.uid == "77-48-28-61-92")
        new_card = next(card for card in cards if card.uid == "1-2-3-4-5")
        attendance = session.scalar(select(Attendance).where(Attendance.student_id == 1))
        assert old_card.status == CardStatus.DISABLED
        assert new_card.status == CardStatus.ACTIVE
        assert attendance.rfid_card_id == old_card.id


def test_cancel_expire_wrong_device_and_inactive_student_submission(enrollment_api):
    client, session_factory = enrollment_api
    seed_records(session_factory)
    cancelled = create_enrollment(client).json()
    assert client.post(f"/api/v1/enrollments/{cancelled['id']}/cancel").json()["status"] == "cancelled"
    assert client.get("/api/v1/devices/attendance-pi-01/enrollment").json() == {"status": "none"}
    cancelled_submit = client.post(
        f"/api/v1/enrollments/{cancelled['id']}/card",
        json={"device_id": "attendance-pi-01", "card_uid": "12-34-56-78"},
    )
    assert cancelled_submit.json()["reason"] == "enrollment_cancelled"

    expired = create_enrollment(client, student_id=2).json()
    with session_factory.begin() as session:
        session.get(EnrollmentRequest, expired["id"]).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    expired_submit = client.post(
        f"/api/v1/enrollments/{expired['id']}/card",
        json={"device_id": "attendance-pi-01", "card_uid": "12-34-56-78"},
    )
    assert expired_submit.json()["reason"] == "enrollment_expired"

    active = create_enrollment(client).json()
    wrong_device = client.post(
        f"/api/v1/enrollments/{active['id']}/card",
        json={"device_id": "attendance-pi-02", "card_uid": "12-34-56-78"},
    )
    assert wrong_device.status_code == 403
    with session_factory.begin() as session:
        session.get(Student, 1).status = StudentStatus.INACTIVE
    inactive = client.post(
        f"/api/v1/enrollments/{active['id']}/card",
        json={"device_id": "attendance-pi-01", "card_uid": "12-34-56-78"},
    )
    assert inactive.json()["reason"] == "student_inactive"
    assert inactive.json()["status"] == "failed"

    device_inactive = create_enrollment(client, student_id=2).json()
    with session_factory.begin() as session:
        session.get(Device, 1).status = "disabled"
    inactive_device = client.post(
        f"/api/v1/enrollments/{device_inactive['id']}/card",
        json={"device_id": "attendance-pi-01", "card_uid": "12-34-56-78"},
    )
    assert inactive_device.json()["reason"] == "device_inactive"
    assert inactive_device.json()["status"] == "failed"


def test_devices_endpoint_returns_devices_for_enrollment_selection(enrollment_api):
    client, session_factory = enrollment_api
    seed_records(session_factory)

    response = client.get("/api/v1/devices")
    assert response.status_code == 200
    assert [device["device_id"] for device in response.json()] == [
        "disabled-pi",
        "attendance-pi-02",
        "attendance-pi-01",
    ]
