"""Dashboard enrollment and device polling HTTP routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas.enrollment import (
    DeviceEnrollmentResponse,
    EnrollmentCardSubmitRequest,
    EnrollmentCardSubmitResponse,
    EnrollmentCreateRequest,
    EnrollmentResponse,
)
from app.services.enrollment import (
    EnrollmentConflictError,
    EnrollmentDeviceMismatchError,
    EnrollmentNotFoundError,
    cancel_enrollment,
    create_enrollment,
    get_enrollment,
    poll_device_enrollment,
    submit_enrollment_card,
)


router = APIRouter(prefix="/api/v1", tags=["enrollment"])


def _conflict(error: EnrollmentConflictError):
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": error.code, "message": error.message},
    )


@router.post("/enrollments", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
def post_enrollment(
    request: EnrollmentCreateRequest,
    database_session: Session = Depends(get_db),
):
    """Create a pending dashboard-to-device RFID enrollment request."""
    try:
        return create_enrollment(
            database_session,
            request,
            get_settings().rfid_enrollment_timeout_seconds,
        )
    except EnrollmentConflictError as error:
        _conflict(error)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.get("/enrollments/{enrollment_id}", response_model=EnrollmentResponse)
def get_enrollment_status(enrollment_id: int, database_session: Session = Depends(get_db)):
    """Return enrollment progress for the dashboard's short-lived modal poll."""
    try:
        return get_enrollment(database_session, enrollment_id)
    except EnrollmentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.post("/enrollments/{enrollment_id}/cancel", response_model=EnrollmentResponse)
def post_cancel_enrollment(enrollment_id: int, database_session: Session = Depends(get_db)):
    """Cancel a pending enrollment while keeping its historical row."""
    try:
        return cancel_enrollment(database_session, enrollment_id)
    except EnrollmentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.get(
    "/devices/{device_id}/enrollment",
    response_model=DeviceEnrollmentResponse,
    response_model_exclude_none=True,
)
def get_device_enrollment(device_id: str, database_session: Session = Depends(get_db)):
    """Return one pending request or `status: none` for Raspberry Pi polling."""
    try:
        return poll_device_enrollment(database_session, device_id)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.post(
    "/enrollments/{enrollment_id}/card",
    response_model=EnrollmentCardSubmitResponse,
)
def post_enrollment_card(
    enrollment_id: int,
    request: EnrollmentCardSubmitRequest,
    database_session: Session = Depends(get_db),
):
    """Accept the next UID captured by the owning attendance device."""
    try:
        return submit_enrollment_card(
            database_session,
            enrollment_id,
            request.device_id,
            request.card_uid,
        )
    except EnrollmentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    except EnrollmentDeviceMismatchError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enrollment does not belong to this device",
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None
