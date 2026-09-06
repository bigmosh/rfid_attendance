"""Attendance lookup and persistence business logic."""

import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Attendance, CardStatus, Device, RFIDCard, StudentStatus
from app.schemas.attendance import (
    AttendanceFailureResponse,
    AttendanceRequest,
    AttendanceResponse,
    AttendanceSuccessResponse,
)
from app.schemas.common import StudentResponse


LOGGER = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return the backend-authoritative, timezone-aware receipt timestamp."""
    return datetime.now(timezone.utc)


def attendance_date_for_receipt(server_received_at: datetime, app_timezone: str) -> date:
    """Return the authoritative local attendance day for a backend receipt."""
    if server_received_at.tzinfo is None or server_received_at.utcoffset() is None:
        raise ValueError("server_received_at must be timezone-aware")
    return server_received_at.astimezone(ZoneInfo(app_timezone)).date()


def _existing_attendance(
    database_session: Session,
    student_id: int,
    attendance_date: date,
) -> Attendance | None:
    return database_session.scalar(
        select(Attendance).where(
            Attendance.student_id == student_id,
            Attendance.attendance_date == attendance_date,
        )
    )


def _response_datetime(value: datetime) -> datetime:
    """Keep database values timezone-aware even in SQLite-based local tests."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _success_response(
    student,
    attendance: Attendance,
    attendance_status: str,
    event_time: datetime | None = None,
    server_received_at: datetime | None = None,
):
    return AttendanceSuccessResponse(
        student=StudentResponse.model_validate(student),
        attendance=AttendanceResponse(
            id=attendance.id,
            status=attendance_status,
            attendance_date=attendance.attendance_date,
            event_time=event_time or _response_datetime(attendance.event_time),
            server_received_at=server_received_at
            or _response_datetime(attendance.server_received_at),
        ),
    )


def record_attendance(
    database_session: Session,
    attendance_request: AttendanceRequest,
    app_timezone: str,
) -> AttendanceSuccessResponse | AttendanceFailureResponse:
    """Record one valid request and return an expected domain outcome.

    The caller owns the session lifetime. This function commits expected device
    activity and attendance changes explicitly, and rolls back every database
    error before allowing the route to return a generic HTTP 500 response.
    """
    LOGGER.info("Attendance request received for device %s", attendance_request.device_id)

    try:
        device = database_session.scalar(
            select(Device).where(Device.device_id == attendance_request.device_id)
        )
        if device is None or device.status != "active":
            LOGGER.info("Unknown device")
            return AttendanceFailureResponse(reason="unknown_device")

        server_received_at = utc_now()
        # A known active device has communicated, even if its card is unknown.
        device.last_seen = server_received_at

        card = database_session.scalar(
            select(RFIDCard).where(RFIDCard.uid == attendance_request.card_uid)
        )
        if card is None:
            database_session.commit()
            LOGGER.info("Unknown card")
            return AttendanceFailureResponse(reason="unknown_card")

        if card.status != CardStatus.ACTIVE:
            database_session.commit()
            LOGGER.info("Disabled card")
            return AttendanceFailureResponse(reason="card_disabled")

        if card.student.status != StudentStatus.ACTIVE:
            database_session.commit()
            LOGGER.info("Inactive student")
            return AttendanceFailureResponse(reason="student_inactive")

        attendance_date = attendance_date_for_receipt(server_received_at, app_timezone)
        existing = _existing_attendance(database_session, card.student_id, attendance_date)
        if existing is not None:
            database_session.commit()
            LOGGER.info(
                "Attendance already recorded today (id=%s, student=%s)",
                existing.id,
                card.student_id,
            )
            return _success_response(card.student, existing, "already_recorded_today")

        attendance = Attendance(
            student_id=card.student_id,
            rfid_card_id=card.id,
            device_id=device.id,
            attendance_date=attendance_date,
            event_time=attendance_request.event_time,
            server_received_at=server_received_at,
        )
        database_session.add(attendance)
        try:
            database_session.commit()
        except IntegrityError:
            # The unique student/date constraint is the final authority if two
            # valid scans race across devices or processes.
            database_session.rollback()
            existing = _existing_attendance(
                database_session,
                card.student_id,
                attendance_date,
            )
            if existing is None:
                raise
            device = database_session.scalar(
                select(Device).where(Device.device_id == attendance_request.device_id)
            )
            if device is not None:
                device.last_seen = server_received_at
                database_session.commit()
            LOGGER.info(
                "Concurrent attendance resolved as already recorded (id=%s, student=%s)",
                existing.id,
                card.student_id,
            )
            return _success_response(card.student, existing, "already_recorded_today")
        database_session.refresh(attendance)

        LOGGER.info("Attendance recorded (id=%s)", attendance.id)
        return _success_response(
            card.student,
            attendance,
            "recorded",
            event_time=attendance_request.event_time,
            server_received_at=server_received_at,
        )
    except SQLAlchemyError:
        database_session.rollback()
        LOGGER.exception("Unexpected database error while recording attendance")
        raise
