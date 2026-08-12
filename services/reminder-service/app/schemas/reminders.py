from datetime import datetime, time
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.reminder import Priority, ReminderType


class AssignmentMode(StrEnum):
    SINGLE = "SINGLE"
    MULTIPLE = "MULTIPLE"
    ALL = "ALL"


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    type: ReminderType
    reminder_time: time
    monthly_due_day: int | None = Field(default=None, ge=1, le=31)
    days_before: int = Field(default=5, ge=0, le=31)
    priority: Priority = Priority.NORMAL
    assignment_mode: AssignmentMode
    user_ids: list[UUID] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def validate_rules(self) -> "ReminderCreate":
        if self.type is ReminderType.MONTHLY and self.monthly_due_day is None:
            raise ValueError("monthly_due_day is required for monthly reminders")
        if self.type is ReminderType.DAILY and self.monthly_due_day is not None:
            raise ValueError("monthly_due_day is only valid for monthly reminders")
        unique_users = list(dict.fromkeys(self.user_ids))
        self.user_ids = unique_users
        if self.assignment_mode is AssignmentMode.SINGLE and len(unique_users) != 1:
            raise ValueError("single assignment requires exactly one user")
        if self.assignment_mode is AssignmentMode.MULTIPLE and len(unique_users) < 1:
            raise ValueError("multiple assignment requires at least one user")
        if self.assignment_mode is AssignmentMode.ALL and unique_users:
            raise ValueError("all assignment must not include user_ids")
        return self


class ReminderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    reminder_time: time | None = None
    monthly_due_day: int | None = Field(default=None, ge=1, le=31)
    days_before: int | None = Field(default=None, ge=0, le=31)
    priority: Priority | None = None


class ReminderView(BaseModel):
    id: UUID
    title: str
    description: str | None
    type: ReminderType
    reminder_time: time
    monthly_due_day: int | None
    days_before: int
    priority: Priority
    is_active: bool
    created_by: UUID
    assigned_user_ids: list[UUID]
    created_at: datetime
    updated_at: datetime


class ReminderPage(BaseModel):
    items: list[ReminderView]
    total: int
    limit: int
    offset: int
