from datetime import time
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.reminder import ReminderType
from app.schemas.reminders import AssignmentMode, ReminderCreate


def test_single_assignment_requires_one_user() -> None:
    user_id = uuid4()
    value = ReminderCreate(
        title="Daily report",
        type=ReminderType.DAILY,
        reminder_time=time(16, 30),
        assignment_mode=AssignmentMode.SINGLE,
        user_ids=[user_id],
    )
    assert value.user_ids == [user_id]


def test_monthly_reminder_requires_due_day() -> None:
    with pytest.raises(ValidationError):
        ReminderCreate(
            title="Monthly report",
            type=ReminderType.MONTHLY,
            reminder_time=time(10),
            assignment_mode=AssignmentMode.ALL,
        )


def test_all_assignment_rejects_explicit_users() -> None:
    with pytest.raises(ValidationError):
        ReminderCreate(
            title="Daily report",
            type=ReminderType.DAILY,
            reminder_time=time(10),
            assignment_mode=AssignmentMode.ALL,
            user_ids=[uuid4()],
        )
