"""Attendance-event database model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Attendance(Base):
    __tablename__ = "attendance"

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
