"""Read-only dashboard queries."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Attendance, CardStatus, Device, RFIDCard, Student
from app.schemas.attendance import (
    AttendanceListItem,
    AttendanceListResponse,
    DeviceResponse,
)
from app.schemas.common import StudentResponse
from app.schemas.dashboard import DashboardSummaryResponse


def today_bounds(app_timezone, now=None):
    """Return timezone-aware start/end boundaries for the configured local day."""
    timezone = ZoneInfo(app_timezone)
    local_now = (now or datetime.now(timezone)).astimezone(timezone)
    start = datetime.combine(local_now.date(), time.min, tzinfo=timezone)
    return start, start + timedelta(days=1)


def get_dashboard_summary(database_session, app_timezone, now=None):
    """Return real counts for the overview cards."""
    start, end = today_bounds(app_timezone, now=now)
    return DashboardSummaryResponse(
        total_students=database_session.scalar(select(func.count()).select_from(Student)) or 0,
        attendance_today=database_session.scalar(
            select(func.count())
            .select_from(Attendance)
            .where(Attendance.event_time >= start, Attendance.event_time < end)
        )
        or 0,
        registered_devices=database_session.scalar(select(func.count()).select_from(Device))
        or 0,
        active_rfid_cards=database_session.scalar(
            select(func.count())
            .select_from(RFIDCard)
            .where(RFIDCard.status == CardStatus.ACTIVE)
        )
        or 0,
    )


def list_attendance(
    database_session,
    page,
    page_size,
    app_timezone,
    search=None,
    attendance_date=None,
    device_id=None,
    student_id=None,
):
    """Return newest-first attendance records with joined student/device data."""
    filters = []
    if search:
        search_value = f"%{search.strip()}%"
        filters.append(
            Student.name.ilike(search_value) | Student.student_number.ilike(search_value)
        )
    if attendance_date:
        start = datetime.combine(
            attendance_date,
            time.min,
            tzinfo=ZoneInfo(app_timezone),
        )
        end = start + timedelta(days=1)
        filters.extend((Attendance.event_time >= start, Attendance.event_time < end))
    if device_id:
        filters.append(Device.device_id == device_id)
    if student_id is not None:
        filters.append(Attendance.student_id == student_id)

    base_query = select(Attendance).join(Attendance.student).join(Attendance.device)
    count_query = select(func.count()).select_from(Attendance).join(Attendance.student).join(Attendance.device)
    if filters:
        base_query = base_query.where(*filters)
        count_query = count_query.where(*filters)

    total = database_session.scalar(count_query) or 0
    records = database_session.scalars(
        base_query.options(joinedload(Attendance.student), joinedload(Attendance.device))
        .order_by(Attendance.event_time.desc(), Attendance.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        AttendanceListItem(
            id=record.id,
            student=StudentResponse.model_validate(record.student),
            device=DeviceResponse.model_validate(record.device),
            event_time=record.event_time,
            server_received_at=record.server_received_at,
        )
        for record in records
    ]
    return AttendanceListResponse.from_items(items, page, page_size, total)
