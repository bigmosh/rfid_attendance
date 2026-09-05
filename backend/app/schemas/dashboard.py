"""Read-only dashboard response schemas."""

from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    total_students: int
    attendance_today: int
    registered_devices: int
    active_rfid_cards: int
