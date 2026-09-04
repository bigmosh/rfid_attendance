"""Contract-level validation tests without a database connection."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.attendance import AttendanceRequest


def test_attendance_request_accepts_timezone_aware_event_time():
    request = AttendanceRequest(
        device_id="attendance-pi-01",
        card_uid="77-48-28-61-92",
        event_time="2026-09-03T21:43:36+03:00",
    )

    assert request.event_time == datetime.fromisoformat("2026-09-03T21:43:36+03:00")


def test_attendance_request_rejects_event_time_without_timezone():
    with pytest.raises(ValidationError, match="timezone offset"):
        AttendanceRequest(
            device_id="attendance-pi-01",
            card_uid="77-48-28-61-92",
            event_time="2026-09-03T21:43:36",
        )
