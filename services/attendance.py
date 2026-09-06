"""HTTPS attendance API client for the Raspberry Pi edge application."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests

from config import API_BASE_URL, DEVICE_ID, REQUEST_TIMEOUT_SECONDS
from services.crypto import CryptoConfigurationError, encrypt_payload, load_device_aes_key


LOGGER = logging.getLogger(__name__)
ATTENDANCE_PATH = "/api/v1/attendance/encrypted"
EXPECTED_FAILURE_REASONS = {
    "unknown_card",
    "card_disabled",
    "student_inactive",
    "unknown_device",
}
SECURE_FAILURE_REASONS = {
    "device_key_not_configured",
    "invalid_encrypted_payload",
    "authentication_failed",
    "invalid_plaintext_payload",
}


@dataclass(frozen=True)
class AttendanceResult:
    """Stable result consumed by the application coordinator, not HTTP details."""

    success: bool
    student_name: Optional[str] = None
    student_number: Optional[str] = None
    attendance_id: Optional[int] = None
    attendance_status: Optional[str] = None
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

    plaintext_payload = {
        "card_uid": card_uid,
        "event_time": event_time.isoformat(),
    }
    try:
        encrypted_payload = encrypt_payload(
            plaintext_payload,
            load_device_aes_key(),
            DEVICE_ID,
        )
    except CryptoConfigurationError as error:
        LOGGER.error("Encrypted attendance key configuration error: %s", error)
        return AttendanceResult(success=False, reason="secure_send_failed")

    payload = {
        "device_id": DEVICE_ID,
        "nonce": encrypted_payload.nonce,
        "ciphertext": encrypted_payload.ciphertext,
    }
    endpoint = f"{API_BASE_URL}{ATTENDANCE_PATH}"

    LOGGER.debug("Attendance payload encrypted in %.2f ms", encrypted_payload.encryption_ms)
    LOGGER.info("Submitting encrypted attendance event for device %s", DEVICE_ID)
    request_started = time.perf_counter()
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

    LOGGER.debug(
        "Encrypted attendance request completed in %.2f ms",
        (time.perf_counter() - request_started) * 1000,
    )

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
        if reason in SECURE_FAILURE_REASONS:
            return AttendanceResult(success=False, reason="secure_send_failed")

    if response_body.get("success") is True:
        student = response_body.get("student")
        attendance = response_body.get("attendance")
        if (
            isinstance(student, dict)
            and isinstance(attendance, dict)
            and isinstance(student.get("name"), str)
            and isinstance(student.get("student_number"), str)
            and isinstance(attendance.get("id"), int)
            and attendance.get("status") in {"recorded", "already_recorded_today"}
        ):
            return AttendanceResult(
                success=True,
                student_name=student["name"],
                student_number=student["student_number"],
                attendance_id=attendance["id"],
                attendance_status=attendance["status"],
            )

    LOGGER.warning("Attendance backend returned an unexpected response body")
    return AttendanceResult(success=False, reason="server_error")
