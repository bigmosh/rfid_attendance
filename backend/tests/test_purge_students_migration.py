"""Behaviour checks for the intentional one-time student data purge."""

from datetime import date, datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401  Ensure all tables are registered on Base metadata.
from app.database import Base
from app.models import Attendance, CardStatus, Device, EnrollmentRequest, RFIDCard, Student


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    BACKEND_DIRECTORY / "alembic" / "versions" / "0006_purge_students.py"
)


def _load_purge_migration():
    specification = spec_from_file_location("purge_students_migration", MIGRATION_PATH)
    assert specification is not None
    assert specification.loader is not None
    module = module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_purge_students_migration_deletes_dependents_and_preserves_devices():
    """Foreign-key ordered deletion removes student data but not device rows."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(connection)

    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        device = Device(
            device_id="attendance-pi-01",
            name="Main Attendance Device",
            status="active",
        )
        student = Student(student_number="ST001", name="Student 1")
        session.add_all((device, student))
        session.flush()

        card = RFIDCard(
            uid="77-48-28-61-92",
            student_id=student.id,
            status=CardStatus.ACTIVE,
        )
        session.add(card)
        session.flush()

        session.add_all(
            (
                Attendance(
                    student_id=student.id,
                    rfid_card_id=card.id,
                    device_id=device.id,
                    attendance_date=date.today(),
                    event_time=now,
                    server_received_at=now,
                ),
                EnrollmentRequest(
                    device_id=device.id,
                    student_id=student.id,
                    expires_at=now + timedelta(minutes=1),
                ),
            )
        )
        session.commit()

    migration = _load_purge_migration()
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(EnrollmentRequest)) == 0
        assert session.scalar(select(func.count()).select_from(Attendance)) == 0
        assert session.scalar(select(func.count()).select_from(RFIDCard)) == 0
        assert session.scalar(select(func.count()).select_from(Student)) == 0

        assert session.scalar(select(func.count()).select_from(Device)) == 1
        assert session.scalar(select(Device.device_id)) == "attendance-pi-01"
