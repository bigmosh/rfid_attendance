"""Attendance-event database model."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "attendance_date",
            name="uq_attendance_student_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        index=True,
        nullable=False,
    )
    rfid_card_id: Mapped[int] = mapped_column(
        ForeignKey("rfid_cards.id"),
        index=True,
        nullable=False,
    )
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id"),
        index=True,
        nullable=False,
    )
    # Derived from server_received_at in APP_TIMEZONE. This is the
    # authoritative local calendar day used for daily attendance uniqueness.
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    server_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    student: Mapped["Student"] = relationship(back_populates="attendance_records")
    rfid_card: Mapped["RFIDCard"] = relationship(back_populates="attendance_records")
    device: Mapped["Device"] = relationship(back_populates="attendance_records")
