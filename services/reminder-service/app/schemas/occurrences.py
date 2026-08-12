from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.reminder import OccurrenceStatus, Priority, ReminderType


class OccurrenceView(BaseModel):
    id: UUID
    reminder_id: UUID
    title: str
    description: str | None
    type: ReminderType
    priority: Priority
    scheduled_date: date
    scheduled_at: datetime
    due_at: datetime
    status: OccurrenceStatus
    snoozed_until: datetime | None
    completed_at: datetime | None
    updated_at: datetime


class OccurrencePage(BaseModel):
    items: list[OccurrenceView]
    next_cursor: str | None = None


class SnoozeRequest(BaseModel):
    minutes: int
    device_id: UUID | None = None

    @classmethod
    def allowed_minutes(cls) -> set[int]:
        return {10, 30, 60, 120}


class CompleteRequest(BaseModel):
    device_id: UUID | None = None


class ScanResult(BaseModel):
    created: int
    state_changes: int
