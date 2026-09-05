"""Student and manual RFID-card administration routes."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas.attendance import AttendanceListResponse
from app.schemas.students import (
    RFIDCardCreateRequest,
    RFIDCardResponse,
    RFIDCardStatusUpdateRequest,
    StudentCreateRequest,
    StudentDetailResponse,
    StudentListResponse,
    StudentStatusValue,
    StudentUpdateRequest,
)
from app.services.dashboard import list_attendance
from app.services.students import (
    CardNotFoundError,
    ConflictError,
    StudentNotFoundError,
    assign_rfid_card,
    create_student,
    get_student,
    list_students,
    replace_rfid_card,
    unassign_rfid_card,
    update_rfid_card_status,
    update_student,
)


router = APIRouter(prefix="/api/v1/students", tags=["students"])


def _not_found(error: Exception):
    if isinstance(error, StudentNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    if isinstance(error, CardNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFID card not found")
    raise error


def _conflict(error: ConflictError):
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": error.code, "message": error.message},
    )


@router.get("", response_model=StudentListResponse)
def get_students(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
    student_status: StudentStatusValue | None = Query(default=None, alias="status"),
    database_session: Session = Depends(get_db),
):
    """Return paginated students for the administrative dashboard."""
    try:
        return list_students(database_session, page, page_size, search, student_status)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.post("", response_model=StudentDetailResponse, status_code=status.HTTP_201_CREATED)
def post_student(
    request: StudentCreateRequest,
    database_session: Session = Depends(get_db),
):
    """Create a student without assigning a physical RFID card."""
    try:
        return create_student(database_session, request)
    except ConflictError as error:
        _conflict(error)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.get("/{student_id}", response_model=StudentDetailResponse)
def get_student_detail(student_id: int, database_session: Session = Depends(get_db)):
    """Return a student and their active or most recently disabled card."""
    try:
        return get_student(database_session, student_id)
    except StudentNotFoundError as error:
        _not_found(error)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.patch("/{student_id}", response_model=StudentDetailResponse)
def patch_student(
    student_id: int,
    request: StudentUpdateRequest,
    database_session: Session = Depends(get_db),
):
    """Edit student details or safely change the lifecycle status."""
    try:
        return update_student(database_session, student_id, request)
    except StudentNotFoundError as error:
        _not_found(error)
    except ConflictError as error:
        _conflict(error)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.get("/{student_id}/attendance", response_model=AttendanceListResponse)
def get_student_attendance(
    student_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    attendance_date: date | None = Query(default=None, alias="date"),
    database_session: Session = Depends(get_db),
):
    """Return the student's paginated attendance history."""
    try:
        get_student(database_session, student_id)
        return list_attendance(
            database_session,
            page,
            page_size,
            get_settings().app_timezone,
            attendance_date=attendance_date,
            student_id=student_id,
        )
    except StudentNotFoundError as error:
        _not_found(error)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.post(
    "/{student_id}/rfid-card",
    response_model=RFIDCardResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_rfid_card(
    student_id: int,
    request: RFIDCardCreateRequest,
    database_session: Session = Depends(get_db),
):
    """Manually assign an RFID UID where no active card exists yet."""
    try:
        return assign_rfid_card(database_session, student_id, request)
    except (StudentNotFoundError, CardNotFoundError) as error:
        _not_found(error)
    except ConflictError as error:
        _conflict(error)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.patch("/{student_id}/rfid-card", response_model=RFIDCardResponse)
def patch_rfid_card(
    student_id: int,
    request: RFIDCardStatusUpdateRequest,
    database_session: Session = Depends(get_db),
):
    """Enable or disable a student's current card without deleting it."""
    try:
        return update_rfid_card_status(database_session, student_id, request)
    except (StudentNotFoundError, CardNotFoundError) as error:
        _not_found(error)
    except ConflictError as error:
        _conflict(error)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.post(
    "/{student_id}/rfid-card/replace",
    response_model=RFIDCardResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_replacement_rfid_card(
    student_id: int,
    request: RFIDCardCreateRequest,
    database_session: Session = Depends(get_db),
):
    """Disable an old active card and create a new active card."""
    try:
        return replace_rfid_card(database_session, student_id, request)
    except (StudentNotFoundError, CardNotFoundError) as error:
        _not_found(error)
    except ConflictError as error:
        _conflict(error)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.post("/{student_id}/rfid-card/unassign", response_model=RFIDCardResponse)
def post_unassign_rfid_card(student_id: int, database_session: Session = Depends(get_db)):
    """Disable the active card as a safe unassignment operation."""
    try:
        return unassign_rfid_card(database_session, student_id)
    except (StudentNotFoundError, CardNotFoundError) as error:
        _not_found(error)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None
