from datetime import UTC, date, datetime, time
from uuid import uuid4

from app.models.reminder import Assignment, Reminder, ReminderType
from app.services.occurrences import occurrence_window, occurrence_windows


def reminder(reminder_type: ReminderType, due_day: int | None = None, days_before: int = 5) -> Reminder:
    return Reminder(
        id=uuid4(),
        title="Test",
        type=reminder_type,
        reminder_time=time(10),
        monthly_due_day=due_day,
        days_before=days_before,
        created_by=uuid4(),
    )


def assignment(timezone: str = "UTC") -> Assignment:
    return Assignment(
        id=uuid4(), reminder_id=uuid4(), user_id=uuid4(), timezone=timezone, created_at=datetime.now(UTC)
    )


def test_daily_cycle_is_local_date() -> None:
    result = occurrence_window(reminder(ReminderType.DAILY), assignment("Asia/Dhaka"), date(2026, 8, 12))
    assert result is not None
    cycle, scheduled, due = result
    assert cycle == "2026-08-12"
    assert scheduled == datetime(2026, 8, 12, 4, tzinfo=UTC)
    assert due == scheduled


def test_daily_secondary_time_creates_independent_occurrence() -> None:
    item = reminder(ReminderType.DAILY)
    item.secondary_reminder_time = time(16, 30)
    windows = occurrence_windows(item, assignment("Asia/Dhaka"), date(2026, 8, 12))
    assert [window[0] for window in windows] == ["2026-08-12", "2026-08-12#2"]
    assert windows[1][1] == datetime(2026, 8, 12, 10, 30, tzinfo=UTC)


def test_monthly_cycle_starts_days_before_due() -> None:
    item = reminder(ReminderType.MONTHLY, due_day=15, days_before=5)
    assert occurrence_window(item, assignment(), date(2026, 8, 9)) is None
    result = occurrence_window(item, assignment(), date(2026, 8, 10))
    assert result is not None
    assert result[0] == "2026-08"
    assert result[1] == datetime(2026, 8, 10, 10, tzinfo=UTC)
    assert result[2] == datetime(2026, 8, 15, 10, tzinfo=UTC)


def test_monthly_cycle_clamps_february_due_date() -> None:
    result = occurrence_window(
        reminder(ReminderType.MONTHLY, due_day=31), assignment(), date(2024, 2, 24)
    )
    assert result is not None
    assert result[2] == datetime(2024, 2, 29, 10, tzinfo=UTC)
