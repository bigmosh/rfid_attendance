"""Seed-data tests using local in-memory SQLite only."""

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
import app.models
from app.models import Device, RFIDCard, Student
from scripts import seed_demo_data


def test_seed_demo_data_is_idempotent_and_creates_expected_records(monkeypatch):
    local_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(local_engine)
    local_session_factory = sessionmaker(bind=local_engine)
    monkeypatch.setattr(seed_demo_data, "SessionLocal", local_session_factory)

    seed_demo_data.seed_demo_data()
    seed_demo_data.seed_demo_data()

    with local_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Student)) == 2
        assert session.scalar(select(func.count()).select_from(RFIDCard)) == 2
        assert session.scalar(select(func.count()).select_from(Device)) == 1

        device = session.scalar(
            select(Device).where(Device.device_id == "attendance-pi-01")
        )
        assert device.name == "Main Attendance Device"
        assert device.status == "active"

        student_1 = session.scalar(
            select(Student).where(Student.student_number == "ST001")
        )
        student_2 = session.scalar(
            select(Student).where(Student.student_number == "ST002")
        )
        assert student_1.name == "Student 1"
        assert student_2.name == "Student 2"

        uids = set(session.scalars(select(RFIDCard.uid)))
        assert uids == {"77-48-28-61-92", "51-164-2-51-166"}
