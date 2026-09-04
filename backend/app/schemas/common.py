"""Schemas shared by API responses."""

from pydantic import BaseModel, ConfigDict


class StudentResponse(BaseModel):
    id: int
    student_number: str
    name: str

    model_config = ConfigDict(from_attributes=True)
