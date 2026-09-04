"""Add indexes for foreign-key attendance lookups.

Revision ID: 0002_add_foreign_key_indexes
Revises: 0001_initial_schema
Create Date: 2026-09-04
"""

from alembic import op


revision = "0002_add_foreign_key_indexes"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_rfid_cards_student_id", "rfid_cards", ["student_id"])
    op.create_index("ix_attendance_student_id", "attendance", ["student_id"])
    op.create_index("ix_attendance_rfid_card_id", "attendance", ["rfid_card_id"])
    op.create_index("ix_attendance_device_id", "attendance", ["device_id"])


def downgrade():
    op.drop_index("ix_attendance_device_id", table_name="attendance")
    op.drop_index("ix_attendance_rfid_card_id", table_name="attendance")
    op.drop_index("ix_attendance_student_id", table_name="attendance")
    op.drop_index("ix_rfid_cards_student_id", table_name="rfid_cards")
