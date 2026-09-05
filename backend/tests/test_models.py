"""Database-model tests using local in-memory SQLite only."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
import app.models
from app.models import Attendance, Device, EnrollmentRequest, RFIDCard, Student, StudentStatus


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as database_session:
        yield database_session


def test_models_define_expected_tables_foreign_keys_timestamps_and_indexes():
    tables = Base.metadata.tables
    assert set(tables) == {
        "students",
        "rfid_cards",
        "devices",
        "attendance",
        "enrollment_requests",
    }
    assert tables["students"].c.status.type.enums == ["active", "inactive"]

    assert {foreign_key.target_fullname for foreign_key in tables["rfid_cards"].foreign_keys} == {
        "students.id"
    }
    assert {foreign_key.target_fullname for foreign_key in tables["attendance"].foreign_keys} == {
        "students.id",
        "rfid_cards.id",
        "devices.id",
    }
    assert {foreign_key.target_fullname for foreign_key in tables["enrollment_requests"].foreign_keys} == {
        "students.id",
        "devices.id",
    }

    for table_name in ("students", "rfid_cards", "devices", "attendance", "enrollment_requests"):
        assert tables[table_name].c.created_at.type.timezone is True
    assert tables["devices"].c.last_seen.type.timezone is True
    assert tables["attendance"].c.event_time.type.timezone is True
    assert tables["attendance"].c.server_received_at.type.timezone is True
    assert tables["enrollment_requests"].c.expires_at.type.timezone is True
    assert tables["enrollment_requests"].c.completed_at.type.timezone is True

    assert {index.name for index in tables["rfid_cards"].indexes} == {
        "ix_rfid_cards_student_id",
        "uq_rfid_cards_one_active_per_student",
    }
    assert {index.name for index in tables["attendance"].indexes} == {
        "ix_attendance_student_id",
        "ix_attendance_rfid_card_id",
        "ix_attendance_device_id",
    }
    assert {index.name for index in tables["enrollment_requests"].indexes} == {
        "ix_enrollment_requests_device_id",
        "ix_enrollment_requests_student_id",
        "uq_enrollment_requests_one_pending_per_device",
    }


def test_model_relationships_link_attendance_to_student_card_and_device(session):
    student = Student(student_number="ST100", name="Relationship Test")
    device = Device(device_id="test-device", name="Test Device", status="active")
    session.add_all([student, device])
    session.flush()

    card = RFIDCard(uid="10-20-30-40-50", student_id=student.id, status="active")
    session.add(card)
    session.flush()

    attendance = Attendance(
        student_id=student.id,
        rfid_card_id=card.id,
        device_id=device.id,
        event_time=datetime.now(timezone.utc),
    )
    session.add(attendance)
    session.flush()

    assert card.student is student
    assert attendance.student is student
    assert attendance.rfid_card is card
    assert attendance.device is device
    assert attendance in student.attendance_records
    assert attendance in card.attendance_records
    assert attendance in device.attendance_records


def test_student_number_is_unique(session):
    session.add(Student(student_number="ST001", name="Student 1"))
    session.flush()
    session.add(Student(student_number="ST001", name="Duplicate Student"))

    with pytest.raises(IntegrityError):
        session.flush()


def test_student_status_defaults_to_active(session):
    student = Student(student_number="ST099", name="Status Test")
    session.add(student)
    session.flush()

    assert student.status == StudentStatus.ACTIVE


def test_rfid_uid_is_unique(session):
    student = Student(student_number="ST101", name="Card Test")
    session.add(student)
    session.flush()
    session.add(RFIDCard(uid="1-2-3-4-5", student_id=student.id, status="active"))
    session.flush()
    session.add(RFIDCard(uid="1-2-3-4-5", student_id=student.id, status="active"))

    with pytest.raises(IntegrityError):
        session.flush()


def test_only_one_active_card_is_allowed_per_student(session):
    student = Student(student_number="ST102", name="Active Card Test")
    session.add(student)
    session.flush()
    session.add(RFIDCard(uid="1-2-3-4", student_id=student.id, status="active"))
    session.flush()
    session.add(RFIDCard(uid="5-6-7-8", student_id=student.id, status="active"))

    with pytest.raises(IntegrityError):
        session.flush()


def test_device_identifier_is_unique(session):
    session.add(Device(device_id="attendance-pi-01", name="Device", status="active"))
    session.flush()
    session.add(Device(device_id="attendance-pi-01", name="Duplicate", status="active"))

    with pytest.raises(IntegrityError):
        session.flush()
