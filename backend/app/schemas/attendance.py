"""Attendance API request and response schemas for the next implementation step."""

from datetime import date, datetime
from math import ceil
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import StudentResponse


class DeviceResponse(BaseModel):
    device_id: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class AttendanceRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    card_uid: str = Field(min_length=1, max_length=128)
    event_time: datetime

    @field_validator("event_time")
    @classmethod
    def event_time_requires_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("event_time must include a timezone offset")
        return value


class EncryptedAttendanceRequest(BaseModel):
    """Outer encrypted transport; card UID and event time stay confidential."""

    device_id: str = Field(min_length=1, max_length=128)
    nonce: str = Field(min_length=1, max_length=256)
    ciphertext: str = Field(min_length=1, max_length=4096)


class AttendanceResponse(BaseModel):
    id: int
    status: Literal["recorded", "already_recorded_today"]
    attendance_date: date
    event_time: datetime
    server_received_at: datetime


class AttendanceSuccessResponse(BaseModel):
    success: Literal[True] = True
    student: StudentResponse
    attendance: AttendanceResponse


class AttendanceFailureResponse(BaseModel):
    success: Literal[False] = False
    reason: Literal["unknown_card", "card_disabled", "unknown_device", "student_inactive"]


class AttendanceEncryptedFailureResponse(BaseModel):
    """Safe expected failures specific to encrypted attendance transport."""

    success: Literal[False] = False
    reason: Literal[
        "unknown_device",
        "device_key_not_configured",
        "invalid_encrypted_payload",
        "authentication_failed",
        "invalid_plaintext_payload",
    ]


class AttendanceListItem(BaseModel):
    id: int
    student: StudentResponse
    device: DeviceResponse
    attendance_date: date
    event_time: datetime
    server_received_at: datetime
    # Persisted rows are always recorded. The second-scan status is returned
    # only by POST /attendance and does not create a dashboard row.
    status: Literal["recorded", "already_recorded_today"] = "recorded"


class AttendanceListResponse(BaseModel):
    items: list[AttendanceListItem]
    page: int
    page_size: int
    total: int
    pages: int

    @classmethod
    def from_items(cls, items, page, page_size, total):
        return cls(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            pages=ceil(total / page_size) if total else 0,
        )
