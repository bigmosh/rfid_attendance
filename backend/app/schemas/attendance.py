"""Attendance API request and response schemas for the next implementation step."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import StudentResponse


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


class AttendanceResponse(BaseModel):
    id: int
    status: Literal["recorded"]
    event_time: datetime
    server_received_at: datetime


class AttendanceSuccessResponse(BaseModel):
    success: Literal[True] = True
    student: StudentResponse
    attendance: AttendanceResponse


class AttendanceFailureResponse(BaseModel):
    success: Literal[False] = False
    reason: Literal["unknown_card", "card_disabled", "unknown_device"]
