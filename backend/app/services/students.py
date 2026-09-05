"""Student and RFID-card administration business logic."""

import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import CardStatus, RFIDCard, Student, StudentStatus
from app.schemas.students import (
    RFIDCardCreateRequest,
    RFIDCardResponse,
    RFIDCardStatusUpdateRequest,
    StudentCreateRequest,
    StudentDetailResponse,
    StudentListItem,
    StudentListResponse,
    StudentUpdateRequest,
)


LOGGER = logging.getLogger(__name__)


class StudentNotFoundError(Exception):
    """Raised when a requested student does not exist."""


class CardNotFoundError(Exception):
    """Raised when a student has no card available for an action."""


class ConflictError(Exception):
    """Raised for predictable uniqueness and lifecycle conflicts."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _display_card(student: Student) -> RFIDCard | None:
    """Return the active card, or the newest disabled card for useful details."""
    active_cards = [card for card in student.rfid_cards if card.status == CardStatus.ACTIVE]
    if active_cards:
        return max(active_cards, key=lambda card: card.id)
    return max(student.rfid_cards, key=lambda card: card.id) if student.rfid_cards else None


def _student_detail(student: Student) -> StudentDetailResponse:
    card = _display_card(student)
    return StudentDetailResponse(
        id=student.id,
        student_number=student.student_number,
        name=student.name,
        status=student.status.value,
        created_at=student.created_at,
        rfid_card=RFIDCardResponse.model_validate(card) if card else None,
    )


def _get_student(database_session: Session, student_id: int) -> Student:
    student = database_session.scalar(
        select(Student)
        .options(selectinload(Student.rfid_cards))
        .where(Student.id == student_id)
    )
    if student is None:
        raise StudentNotFoundError
    return student


def _commit(database_session: Session, conflict_code: str | None = None, conflict_message: str | None = None):
    try:
        database_session.commit()
    except IntegrityError as error:
        database_session.rollback()
        if conflict_code and conflict_message:
            raise ConflictError(conflict_code, conflict_message) from error
        raise


def list_students(
    database_session: Session,
    page: int,
    page_size: int,
    search: str | None = None,
    student_status: str | None = None,
) -> StudentListResponse:
    """Return paginated students and their current card status without N+1 queries."""
    filters = []
    if search:
        search_value = f"%{search.strip()}%"
        filters.append(
            Student.name.ilike(search_value) | Student.student_number.ilike(search_value)
        )
    if student_status:
        filters.append(Student.status == StudentStatus(student_status))

    query = select(Student).options(selectinload(Student.rfid_cards)).order_by(Student.name, Student.id)
    count_query = select(func.count()).select_from(Student)
    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total = database_session.scalar(count_query) or 0
    students = database_session.scalars(
        query.offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        StudentListItem(
            id=student.id,
            student_number=student.student_number,
            name=student.name,
            status=student.status.value,
            rfid_card_status=(card.status.value if (card := _display_card(student)) else None),
        )
        for student in students
    ]
    return StudentListResponse.from_items(items, page, page_size, total)


def create_student(database_session: Session, request: StudentCreateRequest) -> StudentDetailResponse:
    """Create a student with a unique, normalised student number."""
    existing = database_session.scalar(
        select(Student.id).where(Student.student_number == request.student_number)
    )
    if existing is not None:
        raise ConflictError("student_number_exists", "Student number already exists")

    student = Student(student_number=request.student_number, name=request.name)
    database_session.add(student)
    _commit(database_session, "student_number_exists", "Student number already exists")
    database_session.refresh(student)
    LOGGER.info("Student created (id=%s)", student.id)
    return _student_detail(student)


def get_student(database_session: Session, student_id: int) -> StudentDetailResponse:
    """Return student details including the active or most recent card."""
    return _student_detail(_get_student(database_session, student_id))


def update_student(
    database_session: Session,
    student_id: int,
    request: StudentUpdateRequest,
) -> StudentDetailResponse:
    """Update student details or lifecycle status without deleting history."""
    student = _get_student(database_session, student_id)
    changes = request.model_dump(exclude_unset=True)
    student_number = changes.get("student_number")
    if student_number and student_number != student.student_number:
        existing = database_session.scalar(
            select(Student.id).where(
                Student.student_number == student_number,
                Student.id != student_id,
            )
        )
        if existing is not None:
            raise ConflictError("student_number_exists", "Student number already exists")
        student.student_number = student_number
    if "name" in changes:
        student.name = changes["name"]
    if "status" in changes:
        student.status = StudentStatus(changes["status"])

    _commit(database_session, "student_number_exists", "Student number already exists")
    database_session.refresh(student)
    LOGGER.info("Student updated (id=%s)", student.id)
    return _student_detail(student)


def _active_card(database_session: Session, student_id: int) -> RFIDCard | None:
    return database_session.scalar(
        select(RFIDCard).where(
            RFIDCard.student_id == student_id,
            RFIDCard.status == CardStatus.ACTIVE,
        )
    )


def _ensure_uid_is_available(database_session: Session, uid: str):
    if database_session.scalar(select(RFIDCard.id).where(RFIDCard.uid == uid)) is not None:
        raise ConflictError("rfid_uid_exists", "RFID UID is already assigned")


def assign_rfid_card(
    database_session: Session,
    student_id: int,
    request: RFIDCardCreateRequest,
) -> RFIDCardResponse:
    """Manually assign the first active card to a student."""
    _get_student(database_session, student_id)
    _ensure_uid_is_available(database_session, request.uid)
    if _active_card(database_session, student_id):
        raise ConflictError("active_card_exists", "Student already has an active RFID card")

    card = RFIDCard(uid=request.uid, student_id=student_id, status=CardStatus.ACTIVE)
    database_session.add(card)
    _commit(database_session, "active_card_exists", "Student already has an active RFID card")
    database_session.refresh(card)
    LOGGER.info("RFID card assigned to student %s", student_id)
    return RFIDCardResponse.model_validate(card)


def replace_rfid_card(
    database_session: Session,
    student_id: int,
    request: RFIDCardCreateRequest,
) -> RFIDCardResponse:
    """Disable the current card and create a new active card atomically."""
    _get_student(database_session, student_id)
    _ensure_uid_is_available(database_session, request.uid)
    current_card = _active_card(database_session, student_id)
    if current_card is not None:
        current_card.status = CardStatus.DISABLED

    card = RFIDCard(uid=request.uid, student_id=student_id, status=CardStatus.ACTIVE)
    database_session.add(card)
    _commit(database_session, "active_card_exists", "Student already has an active RFID card")
    database_session.refresh(card)
    LOGGER.info("RFID card replaced for student %s", student_id)
    return RFIDCardResponse.model_validate(card)


def update_rfid_card_status(
    database_session: Session,
    student_id: int,
    request: RFIDCardStatusUpdateRequest,
) -> RFIDCardResponse:
    """Enable or disable the student's current card while retaining its row."""
    student = _get_student(database_session, student_id)
    card = _display_card(student)
    if card is None:
        raise CardNotFoundError

    desired_status = CardStatus(request.status)
    if desired_status == CardStatus.ACTIVE:
        active_card = _active_card(database_session, student_id)
        if active_card is not None and active_card.id != card.id:
            raise ConflictError("active_card_exists", "Student already has an active RFID card")
    card.status = desired_status
    _commit(database_session, "active_card_exists", "Student already has an active RFID card")
    database_session.refresh(card)
    LOGGER.info("RFID card status updated for student %s", student_id)
    return RFIDCardResponse.model_validate(card)


def unassign_rfid_card(database_session: Session, student_id: int) -> RFIDCardResponse:
    """Safely unassign by disabling the active card, never deleting history."""
    _get_student(database_session, student_id)
    card = _active_card(database_session, student_id)
    if card is None:
        raise CardNotFoundError
    card.status = CardStatus.DISABLED
    _commit(database_session)
    database_session.refresh(card)
    LOGGER.info("RFID card unassigned from student %s", student_id)
    return RFIDCardResponse.model_validate(card)
