"""Enforce one attendance record per student and local calendar day.

Revision ID: 0005_daily_attendance
Revises: 0004_rfid_enrollment
Create Date: 2026-09-06
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from alembic import context, op
import sqlalchemy as sa

from app.config import get_settings


revision = "0005_daily_attendance"
down_revision = "0004_rfid_enrollment"
branch_labels = None
depends_on = None


def _configured_timezone() -> str:
    """Validate and return the same APP_TIMEZONE used by the application."""
    timezone_name = get_settings().app_timezone
    ZoneInfo(timezone_name)
    return timezone_name


def _postgresql_backfill_and_deduplicate(bind, timezone_name: str):
    """Backfill local dates and retain the earliest row in each duplicate set."""
    safe_timezone_name = timezone_name.replace("'", "''")
    op.execute(
        sa.text(
            "UPDATE attendance "
            "SET attendance_date = "
            f"(server_received_at AT TIME ZONE '{safe_timezone_name}')::date"
        )
    )
    # A deterministic clean-up is required before adding the unique constraint.
    # For each student/day, server_received_at then id selects the canonical row.
    deduplicate = sa.text(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY student_id, attendance_date
                       ORDER BY server_received_at ASC, id ASC
                   ) AS row_number
            FROM attendance
        )
        DELETE FROM attendance
        USING ranked
        WHERE attendance.id = ranked.id
          AND ranked.row_number > 1
        RETURNING attendance.id
        """
    )
    if context.is_offline_mode():
        op.execute(deduplicate)
    else:
        removed_ids = bind.execute(deduplicate).scalars().all()
        print(f"Daily attendance migration removed {len(removed_ids)} duplicate rows")


def _sqlite_backfill_and_deduplicate(bind, timezone_name: str):
    """Provide deterministic local migration coverage for SQLite test fixtures.

    Production uses the PostgreSQL set-based statements above. SQLite does not
    implement PostgreSQL's timezone conversion or anonymous DO blocks, so this
    equivalent path keeps the migration testable without a production database.
    """
    attendance = sa.table(
        "attendance",
        sa.column("id", sa.Integer),
        sa.column("student_id", sa.Integer),
        sa.column("server_received_at", sa.DateTime(timezone=True)),
        sa.column("attendance_date", sa.Date),
    )
    local_timezone = ZoneInfo(timezone_name)
    rows = bind.execute(
        sa.select(
            attendance.c.id,
            attendance.c.student_id,
            attendance.c.server_received_at,
        ).order_by(attendance.c.student_id, attendance.c.server_received_at, attendance.c.id)
    ).mappings()

    seen_dates = set()
    duplicate_ids = []
    for row in rows:
        server_received_at = row.server_received_at
        if isinstance(server_received_at, str):
            server_received_at = datetime.fromisoformat(server_received_at.replace("Z", "+00:00"))
        if server_received_at.tzinfo is None:
            # SQLite does not retain DateTime(timezone=True) offsets. Test data
            # represents the same UTC timestamp stored by production PostgreSQL.
            server_received_at = server_received_at.replace(tzinfo=timezone.utc)
        attendance_date = server_received_at.astimezone(local_timezone).date()
        bind.execute(
            sa.update(attendance)
            .where(attendance.c.id == row.id)
            .values(attendance_date=attendance_date)
        )
        duplicate_key = (row.student_id, attendance_date)
        if duplicate_key in seen_dates:
            duplicate_ids.append(row.id)
        else:
            seen_dates.add(duplicate_key)

    if duplicate_ids:
        bind.execute(sa.delete(attendance).where(attendance.c.id.in_(duplicate_ids)))


def upgrade():
    bind = op.get_bind()
    timezone_name = _configured_timezone()
    op.add_column("attendance", sa.Column("attendance_date", sa.Date(), nullable=True))

    if bind.dialect.name == "postgresql":
        _postgresql_backfill_and_deduplicate(bind, timezone_name)
        op.alter_column("attendance", "attendance_date", nullable=False)
        op.create_unique_constraint(
            "uq_attendance_student_date",
            "attendance",
            ["student_id", "attendance_date"],
        )
    else:
        _sqlite_backfill_and_deduplicate(bind, timezone_name)
        # SQLite cannot add a named UNIQUE constraint after table creation.
        # The equivalent unique index lets the local migration test assert the
        # same student/date integrity rule.
        op.create_index(
            "uq_attendance_student_date",
            "attendance",
            ["student_id", "attendance_date"],
            unique=True,
        )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("uq_attendance_student_date", "attendance", type_="unique")
    else:
        op.drop_index("uq_attendance_student_date", table_name="attendance")
    op.drop_column("attendance", "attendance_date")
