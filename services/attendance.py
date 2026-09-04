"""HTTPS attendance API client for the Raspberry Pi edge application."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests

from config import API_BASE_URL, DEVICE_ID, REQUEST_TIMEOUT_SECONDS


LOGGER = logging.getLogger(__name__)
ATTENDANCE_PATH = "/api/v1/attendance"
EXPECTED_FAILURE_REASONS = {
    "unknown_card",
    "card_disabled",
    "unknown_device",
}


@dataclass(frozen=True)
class AttendanceResult:
    """Stable result consumed by the application coordinator, not HTTP details."""

    success: bool
    student_name: Optional[str] = None
    student_number: Optional[str] = None
    attendance_id: Optional[int] = None
    reason: Optional[str] = None


def submit_attendance(card_uid, event_time=None):
    """Send one card event to the backend and return a predictable result.

    ``event_time`` defaults to the Raspberry Pi's local, timezone-aware system
    time. TLS verification is deliberately left at Requests' secure default.
    """
    if event_time is None:
        event_time = datetime.now().astimezone()
    if event_time.tzinfo is None or event_time.utcoffset() is None:
        raise ValueError("event_time must be timezone-aware")

    payload = {
        "device_id": DEVICE_ID,
        "card_uid": card_uid,
        "event_time": event_time.isoformat(),
    }
    endpoint = f"{API_BASE_URL}{ATTENDANCE_PATH}"

    LOGGER.info("Submitting attendance event for device %s", DEVICE_ID)
    try:
        response = requests.post(
            endpoint,
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        LOGGER.warning("Attendance request timed out")
        return AttendanceResult(success=False, reason="network_error")
    except requests.ConnectionError:
        LOGGER.warning("Attendance connection failed")
        return AttendanceResult(success=False, reason="network_error")
    except requests.RequestException:
        LOGGER.warning("Attendance request failed")
        return AttendanceResult(success=False, reason="network_error")

    if not 200 <= response.status_code < 300:
        LOGGER.warning("Attendance backend returned HTTP %s", response.status_code)
        return AttendanceResult(success=False, reason="server_error")

    try:
        response_body = response.json()
    except ValueError:
        LOGGER.warning("Attendance backend returned malformed JSON")
        return AttendanceResult(success=False, reason="server_error")

    return _parse_response(response_body)


def _parse_response(response_body):
    """Translate a backend JSON object into the edge application's result type."""
    if not isinstance(response_body, dict):
        LOGGER.warning("Attendance backend returned an unexpected response body")
        return AttendanceResult(success=False, reason="server_error")

    if response_body.get("success") is False:
        reason = response_body.get("reason")
        if reason in EXPECTED_FAILURE_REASONS:
            return AttendanceResult(success=False, reason=reason)

    if response_body.get("success") is True:
        student = response_body.get("student")
        attendance = response_body.get("attendance")
        if (
            isinstance(student, dict)
            and isinstance(attendance, dict)
            and isinstance(student.get("name"), str)
            and isinstance(student.get("student_number"), str)
            and isinstance(attendance.get("id"), int)
        ):
            return AttendanceResult(
                success=True,
                student_name=student["name"],
                student_number=student["student_number"],
                attendance_id=attendance["id"],
            )

    LOGGER.warning("Attendance backend returned an unexpected response body")
    return AttendanceResult(success=False, reason="server_error")
