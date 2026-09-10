"""Purge one-time thesis demo student, card, enrollment, and attendance data.

Revision ID: 0006_purge_students
Revises: 0005_daily_attendance
Create Date: 2026-09-10

This intentional data reset preserves registered devices. Deleted student
records and dependent historical rows cannot be reconstructed safely, so this
migration has no downgrade data restoration path.
"""

from alembic import op


revision = "0006_purge_students"
down_revision = "0005_daily_attendance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Delete all student-dependent data while preserving devices."""
    # enrollment_requests and attendance reference student/card rows; delete
    # dependents first so PostgreSQL foreign keys remain valid throughout.
    op.execute("DELETE FROM enrollment_requests")
    op.execute("DELETE FROM attendance")
    op.execute("DELETE FROM rfid_cards")
    op.execute("DELETE FROM students")


def downgrade() -> None:
    """No-op: intentionally purged demo data cannot be restored safely."""
    pass
