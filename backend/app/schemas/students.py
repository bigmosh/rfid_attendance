"""Student and RFID-card administration API schemas."""

import re
from datetime import datetime
from math import ceil
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


StudentStatusValue = Literal["active", "inactive"]
CardStatusValue = Literal["active", "disabled"]


def _normalise_text(value: str, field_name: str) -> str:
    normalised = " ".join(value.split())
    if not normalised:
        raise ValueError(f"{field_name} must not be empty")
    return normalised


class StudentCreateRequest(BaseModel):
    student_number: str = Field(max_length=64)
    name: str = Field(max_length=255)

    @field_validator("student_number")
    @classmethod
    def normalise_student_number(cls, value: str) -> str:
        return _normalise_text(value, "student_number").upper()

    @field_validator("name")
    @classmethod
    def normalise_name(cls, value: str) -> str:
        return _normalise_text(value, "name")


class StudentUpdateRequest(BaseModel):
    student_number: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, max_length=255)
    status: StudentStatusValue | None = None

    @field_validator("student_number")
    @classmethod
    def normalise_optional_student_number(cls, value: str | None) -> str | None:
        return _normalise_text(value, "student_number").upper() if value is not None else None

    @field_validator("name")
    @classmethod
    def normalise_optional_name(cls, value: str | None) -> str | None:
        return _normalise_text(value, "name") if value is not None else None

    @model_validator(mode="after")
    def has_at_least_one_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one student field must be supplied")
        return self


class RFIDCardCreateRequest(BaseModel):
    uid: str = Field(max_length=128)

    @field_validator("uid")
    @classmethod
    def normalise_uid(cls, value: str) -> str:
        normalised = "-".join(part.strip() for part in value.strip().split("-"))
        if not re.fullmatch(r"\d+(?:-\d+){3,9}", normalised):
            raise ValueError("uid must contain 4 to 10 decimal values separated by hyphens")
        return normalised


class RFIDCardStatusUpdateRequest(BaseModel):
    status: CardStatusValue


class RFIDCardResponse(BaseModel):
    id: int
    uid: str
    status: CardStatusValue
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StudentListItem(BaseModel):
    id: int
    student_number: str
    name: str
    status: StudentStatusValue
    rfid_card_status: CardStatusValue | None = None


class StudentListResponse(BaseModel):
    items: list[StudentListItem]
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


class StudentDetailResponse(BaseModel):
    id: int
    student_number: str
    name: str
    status: StudentStatusValue
    created_at: datetime
    rfid_card: RFIDCardResponse | None = None
