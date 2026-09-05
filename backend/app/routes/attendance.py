"""Attendance-recording HTTP route."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas.attendance import (
    AttendanceFailureResponse,
    AttendanceListResponse,
    AttendanceRequest,
    AttendanceSuccessResponse,
)
from app.services.attendance import record_attendance
from app.services.dashboard import list_attendance


router = APIRouter(prefix="/api/v1", tags=["attendance"])


@router.get("/attendance", response_model=AttendanceListResponse)
def get_attendance(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
    attendance_date: date | None = Query(default=None, alias="date"),
    device_id: str | None = Query(default=None, max_length=128),
    database_session: Session = Depends(get_db),
):
    """Return paginated newest-first attendance records for the dashboard."""
    try:
        return list_attendance(
            database_session,
            page,
            page_size,
            get_settings().app_timezone,
            search=search,
            attendance_date=attendance_date,
            device_id=device_id,
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


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
