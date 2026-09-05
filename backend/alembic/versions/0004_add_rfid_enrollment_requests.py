"""Add dashboard-to-device RFID enrollment requests.

Revision ID: 0004_rfid_enrollment
Revises: 0003_student_status
Create Date: 2026-09-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0004_rfid_enrollment"
down_revision = "0003_student_status"
branch_labels = None
depends_on = None


enrollment_status = postgresql.ENUM(
    "pending",
    "completed",
    "cancelled",
    "expired",
    "failed",
    name="enrollment_status",
    create_type=False,
)


def upgrade():
    enrollment_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "enrollment_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            enrollment_status,
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("card_uid", sa.String(length=128), nullable=True),
        sa.Column("failure_reason", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
    )
    op.create_index(
        "ix_enrollment_requests_device_id",
        "enrollment_requests",
        ["device_id"],
    )
    op.create_index(
        "ix_enrollment_requests_student_id",
        "enrollment_requests",
        ["student_id"],
    )
    op.create_index(
        "uq_enrollment_requests_one_pending_per_device",
        "enrollment_requests",
        ["device_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade():
    op.drop_index(
        "uq_enrollment_requests_one_pending_per_device",
        table_name="enrollment_requests",
    )
    op.drop_index("ix_enrollment_requests_student_id", table_name="enrollment_requests")
    op.drop_index("ix_enrollment_requests_device_id", table_name="enrollment_requests")
    op.drop_table("enrollment_requests")
    enrollment_status.drop(op.get_bind(), checkfirst=True)
