"""Student database model."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StudentStatus(str, Enum):
    """Lifecycle state for a student without deleting historical records."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[StudentStatus] = mapped_column(
        SqlEnum(
            StudentStatus,
            values_callable=lambda enum_class: [item.value for item in enum_class],
            name="student_status",
        ),
        server_default=StudentStatus.ACTIVE.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    rfid_cards: Mapped[list["RFIDCard"]] = relationship(back_populates="student")
    attendance_records: Mapped[list["Attendance"]] = relationship(back_populates="student")
