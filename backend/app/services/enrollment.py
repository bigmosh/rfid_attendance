"""Device-polling RFID enrollment workflow."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Device,
    EnrollmentRequest,
    EnrollmentStatus,
    RFIDCard,
    Student,
    StudentStatus,
)
from app.schemas.enrollment import (
    DeviceEnrollmentResponse,
    EnrollmentCardSubmitResponse,
    EnrollmentCreateRequest,
    EnrollmentDeviceResponse,
    EnrollmentResponse,
    EnrollmentStudentResponse,
)
from app.services.students import ConflictError, prepare_rfid_card_assignment


LOGGER = logging.getLogger(__name__)


class EnrollmentNotFoundError(Exception):
    """Raised when a requested enrollment does not exist."""


class EnrollmentConflictError(Exception):
    """Raised for a predictable enrollment creation conflict."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class EnrollmentDeviceMismatchError(Exception):
    """Raised when a device tries to submit another device's enrollment."""


def utc_now() -> datetime:
    """Return one timezone-aware UTC timestamp for enrollment decisions."""
    return datetime.now(timezone.utc)


def _student_response(student: Student) -> EnrollmentStudentResponse:
    return EnrollmentStudentResponse.model_validate(student)


def _device_response(device: Device) -> EnrollmentDeviceResponse:
    return EnrollmentDeviceResponse.model_validate(device)


def _enrollment_response(enrollment: EnrollmentRequest) -> EnrollmentResponse:
    return EnrollmentResponse(
        id=enrollment.id,
        status=enrollment.status.value,
        student=_student_response(enrollment.student),
        device=_device_response(enrollment.device),
        created_at=enrollment.created_at,
        expires_at=enrollment.expires_at,
        completed_at=enrollment.completed_at,
        failure_reason=enrollment.failure_reason,
    )


def _load_enrollment(database_session: Session, enrollment_id: int) -> EnrollmentRequest:
    enrollment = database_session.scalar(
        select(EnrollmentRequest)
        .options(
            joinedload(EnrollmentRequest.student),
            joinedload(EnrollmentRequest.device),
        )
        .where(EnrollmentRequest.id == enrollment_id)
    )
    if enrollment is None:
        raise EnrollmentNotFoundError
    return enrollment


def _expire_if_needed(enrollment: EnrollmentRequest, now: datetime) -> bool:
    expires_at = enrollment.expires_at
    # PostgreSQL returns timezone-aware values for TIMESTAMPTZ. SQLite used by
    # the local tests does not preserve tzinfo, so treat its stored value as UTC.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if enrollment.status == EnrollmentStatus.PENDING and expires_at <= now:
        enrollment.status = EnrollmentStatus.EXPIRED
        return True
    return False


def _commit(database_session: Session):
    try:
        database_session.commit()
    except IntegrityError:
        database_session.rollback()
        raise


def _pending_for_device(database_session: Session, device_id: int) -> EnrollmentRequest | None:
    return database_session.scalar(
        select(EnrollmentRequest)
        .options(
            joinedload(EnrollmentRequest.student),
            joinedload(EnrollmentRequest.device),
        )
        .where(
            EnrollmentRequest.device_id == device_id,
            EnrollmentRequest.status == EnrollmentStatus.PENDING,
        )
    )


def create_enrollment(
    database_session: Session,
    request: EnrollmentCreateRequest,
    timeout_seconds: int,
) -> EnrollmentResponse:
    """Create one pending enrollment for an active device and active student."""
    student = database_session.get(Student, request.student_id)
    if student is None:
        raise EnrollmentConflictError("student_not_found", "Student not found")
    if student.status != StudentStatus.ACTIVE:
        raise EnrollmentConflictError("student_inactive", "Student is inactive")

    device = database_session.scalar(
        select(Device).where(Device.device_id == request.device_id)
    )
    if device is None:
        raise EnrollmentConflictError("device_not_found", "Device not found")
    if device.status != "active":
        raise EnrollmentConflictError("device_inactive", "Device is inactive")

    now = utc_now()
    existing = _pending_for_device(database_session, device.id)
    if existing is not None and _expire_if_needed(existing, now):
        _commit(database_session)
        existing = None
    if existing is not None:
        raise EnrollmentConflictError(
            "pending_enrollment_exists",
            "Device already has a pending enrollment",
        )

    enrollment = EnrollmentRequest(
        device_id=device.id,
        student_id=student.id,
        status=EnrollmentStatus.PENDING,
        created_at=now,
        expires_at=now + timedelta(seconds=timeout_seconds),
    )
    database_session.add(enrollment)
    try:
        _commit(database_session)
    except IntegrityError as error:
        raise EnrollmentConflictError(
            "pending_enrollment_exists",
            "Device already has a pending enrollment",
        ) from error
    database_session.refresh(enrollment)
    enrollment.student = student
    enrollment.device = device
    LOGGER.info("Enrollment created (id=%s, device=%s)", enrollment.id, device.device_id)
    return _enrollment_response(enrollment)


def get_enrollment(database_session: Session, enrollment_id: int) -> EnrollmentResponse:
    """Return an enrollment and mark it expired when its deadline has passed."""
    enrollment = _load_enrollment(database_session, enrollment_id)
    if _expire_if_needed(enrollment, utc_now()):
        _commit(database_session)
        LOGGER.info("Enrollment expired (id=%s)", enrollment.id)
    return _enrollment_response(enrollment)


def poll_device_enrollment(
    database_session: Session,
    device_identifier: str,
) -> DeviceEnrollmentResponse:
    """Return a device's pending enrollment without a background worker."""
    device = database_session.scalar(select(Device).where(Device.device_id == device_identifier))
    if device is None or device.status != "active":
        return DeviceEnrollmentResponse(status="none")

    enrollment = _pending_for_device(database_session, device.id)
    if enrollment is None:
        return DeviceEnrollmentResponse(status="none")
    if _expire_if_needed(enrollment, utc_now()):
        _commit(database_session)
        LOGGER.info("Enrollment expired while polled (id=%s)", enrollment.id)
        return DeviceEnrollmentResponse(status="none")
    return DeviceEnrollmentResponse(
        status="pending",
        enrollment_id=enrollment.id,
        student=_student_response(enrollment.student),
        expires_at=enrollment.expires_at,
    )


def cancel_enrollment(database_session: Session, enrollment_id: int) -> EnrollmentResponse:
    """Cancel a pending enrollment while retaining it for audit history."""
    enrollment = _load_enrollment(database_session, enrollment_id)
    if _expire_if_needed(enrollment, utc_now()):
        _commit(database_session)
    elif enrollment.status == EnrollmentStatus.PENDING:
        enrollment.status = EnrollmentStatus.CANCELLED
        _commit(database_session)
        LOGGER.info("Enrollment cancelled (id=%s)", enrollment.id)
    return _enrollment_response(enrollment)


def submit_enrollment_card(
    database_session: Session,
    enrollment_id: int,
    device_identifier: str,
    card_uid: str,
) -> EnrollmentCardSubmitResponse:
    """Complete enrollment or return a safe, predictable device outcome."""
    enrollment = _load_enrollment(database_session, enrollment_id)
    if enrollment.device.device_id != device_identifier:
        raise EnrollmentDeviceMismatchError

    now = utc_now()
    if _expire_if_needed(enrollment, now):
        _commit(database_session)
        return EnrollmentCardSubmitResponse(
            success=False,
            status="expired",
            reason="enrollment_expired",
        )
    if enrollment.status == EnrollmentStatus.CANCELLED:
        return EnrollmentCardSubmitResponse(
            success=False,
            status="cancelled",
            reason="enrollment_cancelled",
        )
    if enrollment.status != EnrollmentStatus.PENDING:
        return EnrollmentCardSubmitResponse(success=False, status=enrollment.status.value)

    if enrollment.student.status != StudentStatus.ACTIVE:
        enrollment.status = EnrollmentStatus.FAILED
        enrollment.failure_reason = "student_inactive"
        _commit(database_session)
        return EnrollmentCardSubmitResponse(
            success=False,
            status="failed",
            reason="student_inactive",
        )
    if enrollment.device.status != "active":
        enrollment.status = EnrollmentStatus.FAILED
        enrollment.failure_reason = "device_inactive"
        _commit(database_session)
        return EnrollmentCardSubmitResponse(
            success=False,
            status="failed",
            reason="device_inactive",
        )

    if database_session.scalar(select(RFIDCard.id).where(RFIDCard.uid == card_uid)) is not None:
        LOGGER.info("Enrollment card is already assigned (id=%s)", enrollment.id)
        return EnrollmentCardSubmitResponse(
            success=False,
            status="pending",
            reason="card_already_assigned",
        )

    try:
        prepare_rfid_card_assignment(
            database_session,
            enrollment.student_id,
            card_uid,
            replace_existing=True,
        )
        enrollment.status = EnrollmentStatus.COMPLETED
        enrollment.completed_at = now
        enrollment.card_uid = card_uid
        _commit(database_session)
    except (ConflictError, IntegrityError):
        # A concurrent request can pass the lookup above just before another
        # transaction inserts the same UID. The database uniqueness constraint
        # remains authoritative; present that race as the same recoverable
        # duplicate-card result and leave this enrollment pending.
        database_session.rollback()
        return EnrollmentCardSubmitResponse(
            success=False,
            status="pending",
            reason="card_already_assigned",
        )

    LOGGER.info("Enrollment completed (id=%s)", enrollment.id)
    return EnrollmentCardSubmitResponse(
        success=True,
        status="completed",
        student=_student_response(enrollment.student),
        card_status="active",
    )


def list_devices(database_session: Session) -> list[Device]:
    """Return devices for enrollment selection without management actions."""
    return list(database_session.scalars(select(Device).order_by(Device.name, Device.id)))
