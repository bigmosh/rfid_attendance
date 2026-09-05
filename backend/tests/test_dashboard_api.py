"""Read-only dashboard API tests using in-memory SQLite only."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import create_app
import app.models
from app.models import Attendance, CardStatus, Device, RFIDCard, Student
from app.services.dashboard import get_dashboard_summary, today_bounds


HELSINKI = ZoneInfo("Europe/Helsinki")


@pytest.fixture
def dashboard_api():
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


def seed_dashboard_records(session_factory):
    now = datetime.now(HELSINKI)
    with session_factory.begin() as session:
        student_1 = Student(student_number="ST001", name="Student 1")
        student_2 = Student(student_number="ST002", name="Student 2")
        device_1 = Device(device_id="attendance-pi-01", name="Main Attendance Device", status="active")
        device_2 = Device(device_id="attendance-pi-02", name="Lab Attendance Device", status="active")
        session.add_all([student_1, student_2, device_1, device_2])
        session.flush()
        card_1 = RFIDCard(uid="77-48-28-61-92", student_id=student_1.id, status=CardStatus.ACTIVE)
        card_2 = RFIDCard(uid="51-164-2-51-166", student_id=student_2.id, status=CardStatus.ACTIVE)
        session.add_all([card_1, card_2])
        session.flush()
        session.add_all([
            Attendance(student_id=student_1.id, rfid_card_id=card_1.id, device_id=device_1.id, event_time=now - timedelta(minutes=20), server_received_at=now - timedelta(minutes=20)),
            Attendance(student_id=student_2.id, rfid_card_id=card_2.id, device_id=device_2.id, event_time=now - timedelta(minutes=5), server_received_at=now - timedelta(minutes=5)),
            Attendance(student_id=student_1.id, rfid_card_id=card_1.id, device_id=device_1.id, event_time=now - timedelta(days=1), server_received_at=now - timedelta(days=1)),
        ])


def test_summary_returns_real_counts_and_empty_database_is_zero(dashboard_api):
    client, session_factory = dashboard_api
    empty_response = client.get("/api/v1/dashboard/summary")
    assert empty_response.status_code == 200
    assert empty_response.json() == {
        "total_students": 0,
        "attendance_today": 0,
        "registered_devices": 0,
        "active_rfid_cards": 0,
    }

    seed_dashboard_records(session_factory)
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    assert response.json()["total_students"] == 2
    assert response.json()["registered_devices"] == 2
    assert response.json()["active_rfid_cards"] == 2
    assert response.json()["attendance_today"] == 2


def test_attendance_list_is_newest_first_and_paginated(dashboard_api):
    client, session_factory = dashboard_api
    seed_dashboard_records(session_factory)

    response = client.get("/api/v1/attendance?page=1&page_size=2")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["pages"] == 2
    assert [item["student"]["student_number"] for item in body["items"]] == ["ST002", "ST001"]
    assert body["items"][0]["device"]["device_id"] == "attendance-pi-02"
    assert body["items"][0]["status"] == "recorded"


def test_attendance_list_filters_by_search_date_and_device(dashboard_api):
    client, session_factory = dashboard_api
    seed_dashboard_records(session_factory)
    date_value = datetime.now(HELSINKI).date().isoformat()

    search_response = client.get("/api/v1/attendance?search=ST002")
    assert search_response.json()["total"] == 1
    assert search_response.json()["items"][0]["student"]["name"] == "Student 2"

    date_response = client.get(f"/api/v1/attendance?date={date_value}")
    assert date_response.json()["total"] == 2

    device_response = client.get("/api/v1/attendance?device_id=attendance-pi-01")
    assert device_response.json()["total"] == 2


def test_today_bounds_use_finland_timezone():
    start, end = today_bounds(
        "Europe/Helsinki",
        now=datetime(2026, 9, 5, 0, 30, tzinfo=ZoneInfo("UTC")),
    )

    assert start.isoformat() == "2026-09-05T00:00:00+03:00"
    assert end.isoformat() == "2026-09-06T00:00:00+03:00"
