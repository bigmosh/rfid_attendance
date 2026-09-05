"""Add student lifecycle status and enforce one active card per student.

Revision ID: 0003_add_student_status_and_active_card_constraint
Revises: 0002_add_foreign_key_indexes
Create Date: 2026-09-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003_add_student_status_and_active_card_constraint"
down_revision = "0002_add_foreign_key_indexes"
branch_labels = None
depends_on = None


student_status = postgresql.ENUM(
    "active",
    "inactive",
    name="student_status",
    create_type=False,
)


def upgrade():
    student_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "students",
        sa.Column(
            "status",
            student_status,
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )
    op.create_index(
        "uq_rfid_cards_one_active_per_student",
        "rfid_cards",
        ["student_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade():
    op.drop_index("uq_rfid_cards_one_active_per_student", table_name="rfid_cards")
    op.drop_column("students", "status")
    student_status.drop(op.get_bind(), checkfirst=True)
