"""Attendance-recording HTTP route."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.attendance import (
    AttendanceFailureResponse,
    AttendanceRequest,
    AttendanceSuccessResponse,
)
from app.services.attendance import record_attendance


router = APIRouter(prefix="/api/v1", tags=["attendance"])


@router.post(
    "/attendance",
    response_model=AttendanceSuccessResponse | AttendanceFailureResponse,
)
def create_attendance(
    attendance_request: AttendanceRequest,
    database_session: Session = Depends(get_db),
):
    """Record one attendance event for a valid device and active RFID card."""
    try:
        return record_attendance(database_session, attendance_request)
    except SQLAlchemyError:
        # The service rolls back and logs the database error before re-raising.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None
