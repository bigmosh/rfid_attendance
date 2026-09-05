"""Attendance lookup and persistence business logic."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
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


def record_attendance(
    database_session: Session,
    attendance_request: AttendanceRequest,
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

        server_received_at = datetime.now(timezone.utc)
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

        attendance = Attendance(
            student_id=card.student_id,
            rfid_card_id=card.id,
            device_id=device.id,
            event_time=attendance_request.event_time,
            server_received_at=server_received_at,
        )
        database_session.add(attendance)
        database_session.commit()
        database_session.refresh(attendance)

        LOGGER.info("Attendance recorded (id=%s)", attendance.id)
        return AttendanceSuccessResponse(
            student=StudentResponse.model_validate(card.student),
            attendance=AttendanceResponse(
                id=attendance.id,
                status="recorded",
                event_time=attendance_request.event_time,
                server_received_at=server_received_at,
            ),
        )
    except SQLAlchemyError:
        database_session.rollback()
        LOGGER.exception("Unexpected database error while recording attendance")
        raise
