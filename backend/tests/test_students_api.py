"""Student and RFID-card administration API tests using in-memory SQLite."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import create_app
from app.models import Attendance, CardStatus, Device, RFIDCard, Student, StudentStatus


@pytest.fixture
def students_api():
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


def seed_students(session_factory):
    now = datetime.now(timezone.utc)
    with session_factory.begin() as session:
        student_1 = Student(student_number="ST001", name="Student 1")
        student_2 = Student(
            student_number="ST002",
            name="Student 2",
            status=StudentStatus.INACTIVE,
        )
        student_3 = Student(student_number="ST003", name="Alex Example")
        device = Device(device_id="attendance-pi-01", name="Main Device", status="active")
        session.add_all([student_1, student_2, student_3, device])
        session.flush()
        active_card = RFIDCard(
            uid="77-48-28-61-92",
            student_id=student_1.id,
            status=CardStatus.ACTIVE,
        )
        inactive_student_card = RFIDCard(
            uid="51-164-2-51-166",
            student_id=student_2.id,
            status=CardStatus.ACTIVE,
        )
        session.add_all([active_card, inactive_student_card])
        session.flush()
        session.add(
            Attendance(
                student_id=student_1.id,
                rfid_card_id=active_card.id,
                device_id=device.id,
                event_time=now - timedelta(minutes=1),
                server_received_at=now - timedelta(minutes=1),
            )
        )


def test_list_students_supports_pagination_search_and_status(students_api):
    client, session_factory = students_api
    seed_students(session_factory)

    response = client.get("/api/v1/students?page=1&page_size=2")
    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert response.json()["pages"] == 2
    student_one = client.get("/api/v1/students?search=ST001").json()["items"][0]
    assert student_one["rfid_card_status"] == "active"

    assert client.get("/api/v1/students?search=alex").json()["total"] == 1
    inactive = client.get("/api/v1/students?status=inactive")
    assert inactive.status_code == 200
    assert inactive.json()["items"][0]["student_number"] == "ST002"


def test_create_student_normalises_values_and_rejects_duplicates(students_api):
    client, _session_factory = students_api

    response = client.post(
        "/api/v1/students",
        json={"student_number": " st004 ", "name": "  John   Doe  "},
    )
    assert response.status_code == 201
    assert response.json()["student_number"] == "ST004"
    assert response.json()["name"] == "John Doe"
    assert response.json()["status"] == "active"
    assert response.json()["rfid_card"] is None

    duplicate = client.post(
        "/api/v1/students",
        json={"student_number": "st004", "name": "Another Student"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "student_number_exists"


def test_get_update_deactivate_and_reactivate_student(students_api):
    client, session_factory = students_api
    seed_students(session_factory)

    detail = client.get("/api/v1/students/1")
    assert detail.status_code == 200
    assert detail.json()["rfid_card"]["uid"] == "77-48-28-61-92"

    updated = client.patch(
        "/api/v1/students/1",
        json={"name": "Student One", "student_number": "ST101", "status": "inactive"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "inactive"
    assert updated.json()["student_number"] == "ST101"

    reactivated = client.patch("/api/v1/students/1", json={"status": "active"})
    assert reactivated.status_code == 200
    assert reactivated.json()["status"] == "active"
    assert client.get("/api/v1/students/999").status_code == 404

    with session_factory() as session:
        assert session.scalar(select(Attendance).where(Attendance.student_id == 1)) is not None


def test_manual_card_assignment_validation_and_second_active_card_prevention(students_api):
    client, _session_factory = students_api
    created = client.post(
        "/api/v1/students",
        json={"student_number": "ST004", "name": "Card Student"},
    ).json()
    student_id = created["id"]

    invalid = client.post(f"/api/v1/students/{student_id}/rfid-card", json={"uid": "invalid"})
    assert invalid.status_code == 422

    assigned = client.post(
        f"/api/v1/students/{student_id}/rfid-card",
        json={"uid": " 12 - 34 - 56 - 78 "},
    )
    assert assigned.status_code == 201
    assert assigned.json()["uid"] == "12-34-56-78"

    second_active = client.post(
        f"/api/v1/students/{student_id}/rfid-card",
        json={"uid": "11-22-33-44"},
    )
    assert second_active.status_code == 409
    assert second_active.json()["detail"]["code"] == "active_card_exists"

    another_student = client.post(
        "/api/v1/students",
        json={"student_number": "ST005", "name": "Other Student"},
    ).json()
    duplicate_uid = client.post(
        f"/api/v1/students/{another_student['id']}/rfid-card",
        json={"uid": "12-34-56-78"},
    )
    assert duplicate_uid.status_code == 409
    assert duplicate_uid.json()["detail"]["code"] == "rfid_uid_exists"


def test_card_disable_reactivate_replace_and_safe_unassignment(students_api):
    client, session_factory = students_api
    seed_students(session_factory)

    disabled = client.patch("/api/v1/students/1/rfid-card", json={"status": "disabled"})
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"
    reactivated = client.patch("/api/v1/students/1/rfid-card", json={"status": "active"})
    assert reactivated.status_code == 200
    assert reactivated.json()["status"] == "active"

    replaced = client.post(
        "/api/v1/students/1/rfid-card/replace",
        json={"uid": "1-2-3-4-5"},
    )
    assert replaced.status_code == 201
    assert replaced.json()["status"] == "active"

    with session_factory() as session:
        cards = list(session.scalars(select(RFIDCard).where(RFIDCard.student_id == 1)))
        assert {card.status for card in cards} == {CardStatus.ACTIVE, CardStatus.DISABLED}
        historical_attendance = session.scalar(select(Attendance).where(Attendance.student_id == 1))
        assert historical_attendance.rfid_card_id != replaced.json()["id"]

    unassigned = client.post("/api/v1/students/1/rfid-card/unassign")
    assert unassigned.status_code == 200
    assert unassigned.json()["status"] == "disabled"
    assert client.post("/api/v1/students/1/rfid-card/unassign").status_code == 404


def test_student_attendance_and_inactive_student_attendance_response(students_api):
    client, session_factory = students_api
    seed_students(session_factory)

    history = client.get("/api/v1/students/1/attendance?page_size=5")
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["student"]["student_number"] == "ST001"

    inactive_scan = client.post(
        "/api/v1/attendance",
        json={
            "device_id": "attendance-pi-01",
            "card_uid": "51-164-2-51-166",
            "event_time": "2026-09-05T10:30:00+03:00",
        },
    )
    assert inactive_scan.status_code == 200
    assert inactive_scan.json() == {"success": False, "reason": "student_inactive"}

    active_scan = client.post(
        "/api/v1/attendance",
        json={
            "device_id": "attendance-pi-01",
            "card_uid": "77-48-28-61-92",
            "event_time": "2026-09-05T10:30:00+03:00",
        },
    )
    assert active_scan.status_code == 200
    assert active_scan.json()["success"] is True

    with session_factory() as session:
        assert len(list(session.scalars(select(Attendance)))) == 2
