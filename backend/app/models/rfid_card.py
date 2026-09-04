"""RFID card database model."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CardStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class RFIDCard(Base):
    __tablename__ = "rfid_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        index=True,
        nullable=False,
    )
    status: Mapped[CardStatus] = mapped_column(
        SqlEnum(
            CardStatus,
            values_callable=lambda enum_class: [item.value for item in enum_class],
            name="card_status",
        ),
        server_default=CardStatus.ACTIVE.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    student: Mapped["Student"] = relationship(back_populates="rfid_cards")
    attendance_records: Mapped[list["Attendance"]] = relationship(back_populates="rfid_card")
