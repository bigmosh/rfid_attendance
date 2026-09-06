"""Data-level verification of the daily-attendance migration on SQLite fixtures."""

from datetime import date, datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.exc import IntegrityError

from app.config import get_settings


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
MIGRATION_PATH = BACKEND_DIRECTORY / "alembic" / "versions" / "0005_daily_attendance.py"


def _daily_attendance_migration():
    spec = spec_from_file_location("daily_attendance_migration", MIGRATION_PATH)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _old_attendance_table(metadata):
    return sa.Table(
        "attendance",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("student_id", sa.Integer, nullable=False),
        sa.Column("rfid_card_id", sa.Integer, nullable=False),
        sa.Column("device_id", sa.Integer, nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("server_received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def test_daily_attendance_migration_backfills_local_dates_and_keeps_earliest_duplicate(
    monkeypatch,
):
    """Existing same-day scans are reduced deterministically before uniqueness."""
    monkeypatch.setenv("APP_TIMEZONE", "Europe/Helsinki")
    get_settings.cache_clear()
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    attendance = _old_attendance_table(metadata)
    metadata.create_all(engine)
    utc = timezone.utc
    with engine.begin() as connection:
        connection.execute(
            attendance.insert(),
            [
                # Student 1: retain id 1, delete later scans on 6 September.
                {"id": 1, "student_id": 1, "rfid_card_id": 1, "device_id": 1, "event_time": datetime(2026, 9, 6, 5, 0, tzinfo=utc), "server_received_at": datetime(2026, 9, 6, 5, 0, tzinfo=utc), "created_at": datetime(2026, 9, 6, 5, 0, tzinfo=utc)},
                {"id": 2, "student_id": 1, "rfid_card_id": 1, "device_id": 1, "event_time": datetime(2026, 9, 6, 6, 0, tzinfo=utc), "server_received_at": datetime(2026, 9, 6, 6, 0, tzinfo=utc), "created_at": datetime(2026, 9, 6, 6, 0, tzinfo=utc)},
                {"id": 3, "student_id": 1, "rfid_card_id": 1, "device_id": 1, "event_time": datetime(2026, 9, 6, 7, 0, tzinfo=utc), "server_received_at": datetime(2026, 9, 6, 7, 0, tzinfo=utc), "created_at": datetime(2026, 9, 6, 7, 0, tzinfo=utc)},
                # Student 2 keeps their independent attendance on the same day.
                {"id": 4, "student_id": 2, "rfid_card_id": 2, "device_id": 1, "event_time": datetime(2026, 9, 6, 5, 30, tzinfo=utc), "server_received_at": datetime(2026, 9, 6, 5, 30, tzinfo=utc), "created_at": datetime(2026, 9, 6, 5, 30, tzinfo=utc)},
                # 21:30 UTC is 00:30 on 7 September in Europe/Helsinki.
                {"id": 5, "student_id": 1, "rfid_card_id": 1, "device_id": 1, "event_time": datetime(2026, 9, 6, 21, 30, tzinfo=utc), "server_received_at": datetime(2026, 9, 6, 21, 30, tzinfo=utc), "created_at": datetime(2026, 9, 6, 21, 30, tzinfo=utc)},
            ],
        )
        migration_context = MigrationContext.configure(connection)
        with Operations.context(migration_context):
            _daily_attendance_migration().upgrade()

        migrated = sa.Table("attendance", sa.MetaData(), autoload_with=connection)
        rows = connection.execute(
            sa.select(migrated.c.id, migrated.c.student_id, migrated.c.attendance_date)
            .order_by(migrated.c.id)
        ).all()
        assert rows == [
            (1, 1, date(2026, 9, 6)),
            (4, 2, date(2026, 9, 6)),
            (5, 1, date(2026, 9, 7)),
        ]

        with pytest.raises(IntegrityError):
            connection.execute(
                migrated.insert().values(
                    id=6,
                    student_id=1,
                    rfid_card_id=1,
                    device_id=1,
                    event_time=datetime(2026, 9, 6, 8, 0, tzinfo=utc),
                    server_received_at=datetime(2026, 9, 6, 8, 0, tzinfo=utc),
                    created_at=datetime(2026, 9, 6, 8, 0, tzinfo=utc),
                    attendance_date=date(2026, 9, 6),
                )
            )
    get_settings.cache_clear()
