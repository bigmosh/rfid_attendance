"""Schemas for dashboard-initiated RFID enrollment over device polling."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.students import RFIDCardCreateRequest


EnrollmentStatusValue = Literal["pending", "completed", "cancelled", "expired", "failed"]


class EnrollmentCreateRequest(BaseModel):
    student_id: int = Field(gt=0)
    device_id: str = Field(min_length=1, max_length=128)


class EnrollmentCardSubmitRequest(BaseModel):
    """A card captured by a device while an enrollment is pending.

    ``card_uid`` deliberately matches the attendance endpoint's public naming.
    Validation is delegated to the existing manual-card request schema so both
    enrollment paths enforce precisely the same UID format and normalization.
    """

    device_id: str = Field(min_length=1, max_length=128)
    card_uid: str = Field(max_length=128)

    @field_validator("card_uid")
    @classmethod
    def normalise_card_uid(cls, value: str) -> str:
        return RFIDCardCreateRequest(uid=value).uid


class EnrollmentStudentResponse(BaseModel):
    id: int
    student_number: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class EnrollmentDeviceResponse(BaseModel):
    device_id: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class EnrollmentResponse(BaseModel):
    id: int
    status: EnrollmentStatusValue
    student: EnrollmentStudentResponse
    device: EnrollmentDeviceResponse
    created_at: datetime
    expires_at: datetime
    completed_at: datetime | None = None
    failure_reason: str | None = None


class DeviceEnrollmentResponse(BaseModel):
    status: Literal["none", "pending"]
    enrollment_id: int | None = None
    student: EnrollmentStudentResponse | None = None
    expires_at: datetime | None = None


class EnrollmentCardSubmitResponse(BaseModel):
    success: bool
    status: EnrollmentStatusValue
    reason: Literal[
        "card_already_assigned",
        "enrollment_cancelled",
        "enrollment_expired",
        "student_inactive",
        "device_inactive",
    ] | None = None
    student: EnrollmentStudentResponse | None = None
    card_status: Literal["active"] | None = None


class DeviceListItem(BaseModel):
    id: int
    device_id: str
    name: str
    status: str
    last_seen: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
