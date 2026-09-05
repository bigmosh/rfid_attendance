"""HTTPS polling client for dashboard-initiated RFID enrollment."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests

from config import API_BASE_URL, DEVICE_ID, REQUEST_TIMEOUT_SECONDS


LOGGER = logging.getLogger(__name__)
POLL_PATH = "/api/v1/devices/{device_id}/enrollment"
SUBMIT_PATH = "/api/v1/enrollments/{enrollment_id}/card"


@dataclass(frozen=True)
class Enrollment:
    """Pending enrollment data consumed by the application coordinator."""

    id: int
    student_name: str
    student_number: str
    expires_at: datetime


@dataclass(frozen=True)
class EnrollmentPollResult:
    status: str
    enrollment: Optional[Enrollment] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class EnrollmentSubmitResult:
    success: bool
    status: str
    student_name: Optional[str] = None
    reason: Optional[str] = None


def _parse_datetime(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def poll_enrollment():
    """Fetch a pending enrollment without disrupting normal attendance mode."""
    endpoint = f"{API_BASE_URL}{POLL_PATH.format(device_id=DEVICE_ID)}"
    try:
        response = requests.get(endpoint, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.Timeout:
        LOGGER.warning("Enrollment polling timed out")
        return EnrollmentPollResult(status="error", reason="network_error")
    except requests.RequestException:
        LOGGER.warning("Enrollment polling failed")
        return EnrollmentPollResult(status="error", reason="network_error")

    if not 200 <= response.status_code < 300:
        LOGGER.warning("Enrollment polling returned HTTP %s", response.status_code)
        return EnrollmentPollResult(status="error", reason="server_error")
    try:
        body = response.json()
    except ValueError:
        LOGGER.warning("Enrollment polling returned malformed JSON")
        return EnrollmentPollResult(status="error", reason="server_error")
    if not isinstance(body, dict):
        return EnrollmentPollResult(status="error", reason="server_error")
    if body.get("status") == "none":
        return EnrollmentPollResult(status="none")
    if body.get("status") != "pending":
        return EnrollmentPollResult(status="error", reason="server_error")

    student = body.get("student")
    expires_at = _parse_datetime(body.get("expires_at"))
    enrollment_id = body.get("enrollment_id")
    if (
        not isinstance(student, dict)
        or not isinstance(enrollment_id, int)
        or not isinstance(student.get("name"), str)
        or not isinstance(student.get("student_number"), str)
        or expires_at is None
    ):
        LOGGER.warning("Enrollment polling returned an unexpected pending response")
        return EnrollmentPollResult(status="error", reason="server_error")
    return EnrollmentPollResult(
        status="pending",
        enrollment=Enrollment(
            id=enrollment_id,
            student_name=student["name"],
            student_number=student["student_number"],
            expires_at=expires_at,
        ),
    )


def submit_enrollment_card(enrollment_id, card_uid):
    """Submit one UID captured while the Pi is in enrollment mode."""
    endpoint = f"{API_BASE_URL}{SUBMIT_PATH.format(enrollment_id=enrollment_id)}"
    try:
        response = requests.post(
            endpoint,
            json={"device_id": DEVICE_ID, "card_uid": card_uid},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        LOGGER.warning("Enrollment card submission timed out")
        return EnrollmentSubmitResult(False, "pending", reason="network_error")
    except requests.RequestException:
        LOGGER.warning("Enrollment card submission failed")
        return EnrollmentSubmitResult(False, "pending", reason="network_error")
    if not 200 <= response.status_code < 300:
        LOGGER.warning("Enrollment card submission returned HTTP %s", response.status_code)
        return EnrollmentSubmitResult(False, "failed", reason="server_error")
    try:
        body = response.json()
    except ValueError:
        LOGGER.warning("Enrollment card submission returned malformed JSON")
        return EnrollmentSubmitResult(False, "failed", reason="server_error")
    if not isinstance(body, dict) or not isinstance(body.get("status"), str):
        return EnrollmentSubmitResult(False, "failed", reason="server_error")

    if body.get("success") is True and body.get("status") == "completed":
        student = body.get("student")
        if isinstance(student, dict) and isinstance(student.get("name"), str):
            return EnrollmentSubmitResult(True, "completed", student_name=student["name"])
    if body.get("success") is False:
        reason = body.get("reason")
        known_reasons = {
            "card_already_assigned",
            "enrollment_cancelled",
            "enrollment_expired",
            "student_inactive",
            "device_inactive",
        }
        if reason in known_reasons:
            return EnrollmentSubmitResult(False, body["status"], reason=reason)

    LOGGER.warning("Enrollment card submission returned an unexpected response")
    return EnrollmentSubmitResult(False, "failed", reason="server_error")
