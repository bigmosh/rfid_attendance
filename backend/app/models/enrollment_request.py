"""Dashboard-initiated RFID card enrollment request model."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EnrollmentStatus(str, Enum):
    """Lifecycle state for a device-assisted card enrollment."""

    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


class EnrollmentRequest(Base):
    __tablename__ = "enrollment_requests"
    __table_args__ = (
        Index(
            "uq_enrollment_requests_one_pending_per_device",
            "device_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id"),
        index=True,
        nullable=False,
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        index=True,
        nullable=False,
    )
    status: Mapped[EnrollmentStatus] = mapped_column(
        SqlEnum(
            EnrollmentStatus,
            values_callable=lambda enum_class: [item.value for item in enum_class],
            name="enrollment_status",
        ),
        server_default=EnrollmentStatus.PENDING.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    card_uid: Mapped[str | None] = mapped_column(String(128))
    failure_reason: Mapped[str | None] = mapped_column(String(64))

    device: Mapped["Device"] = relationship(back_populates="enrollment_requests")
    student: Mapped["Student"] = relationship(back_populates="enrollment_requests")
