"""Encrypted-attendance adapter that reuses the normal attendance service."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Device
from app.schemas.attendance import (
    AttendanceEncryptedFailureResponse,
    AttendanceRequest,
    AttendanceSuccessResponse,
    EncryptedAttendanceRequest,
)
from app.services.attendance import record_attendance
from app.services.crypto import (
    DeviceKeyConfigurationError,
    InvalidEncryptedPayloadError,
    InvalidPlaintextPayloadError,
    InvalidTag,
    decrypt_transport_payload,
    parse_device_key_mapping,
)


LOGGER = logging.getLogger(__name__)


def record_encrypted_attendance(
    database_session: Session,
    encrypted_request: EncryptedAttendanceRequest,
    app_timezone: str,
    device_aes_keys_json: str,
) -> AttendanceSuccessResponse | AttendanceEncryptedFailureResponse:
    """Authenticate, decrypt, validate, then reuse normal attendance logic."""
    LOGGER.info("Encrypted attendance request received for device %s", encrypted_request.device_id)
    device = database_session.scalar(
        select(Device).where(Device.device_id == encrypted_request.device_id)
    )
    if device is None or device.status != "active":
        LOGGER.info("Unknown device for encrypted attendance")
        return AttendanceEncryptedFailureResponse(reason="unknown_device")

    try:
        key = parse_device_key_mapping(device_aes_keys_json).get(encrypted_request.device_id)
    except DeviceKeyConfigurationError:
        LOGGER.error("Encrypted attendance key configuration is invalid")
        return AttendanceEncryptedFailureResponse(reason="device_key_not_configured")
    if key is None:
        LOGGER.warning("No encrypted attendance key is configured for device %s", device.id)
        return AttendanceEncryptedFailureResponse(reason="device_key_not_configured")

    try:
        decrypted = decrypt_transport_payload(
            encrypted_request.nonce,
            encrypted_request.ciphertext,
            key,
            encrypted_request.device_id,
        )
    except InvalidEncryptedPayloadError:
        LOGGER.warning("Malformed encrypted attendance transport received")
        return AttendanceEncryptedFailureResponse(reason="invalid_encrypted_payload")
    except InvalidTag:
        LOGGER.warning("Encrypted attendance authentication failed")
        return AttendanceEncryptedFailureResponse(reason="authentication_failed")
    except InvalidPlaintextPayloadError:
        LOGGER.warning("Authenticated attendance plaintext was invalid")
        return AttendanceEncryptedFailureResponse(reason="invalid_plaintext_payload")

    try:
        attendance_request = AttendanceRequest(
            device_id=encrypted_request.device_id,
            **decrypted.payload,
        )
    except (TypeError, ValueError):
        LOGGER.warning("Authenticated attendance plaintext failed validation")
        return AttendanceEncryptedFailureResponse(reason="invalid_plaintext_payload")

    LOGGER.debug("Encrypted attendance authenticated in %.2f ms", decrypted.decryption_ms)
    return record_attendance(database_session, attendance_request, app_timezone)
