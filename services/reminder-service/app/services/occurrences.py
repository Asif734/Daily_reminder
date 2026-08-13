from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reminder import (
    Assignment,
    Occurrence,
    OccurrenceStatus,
    Reminder,
    ReminderType,
)
from app.services.calendar import monthly_due_date


def local_instant(day: date, reminder_time: time, timezone: str) -> datetime:
    local = datetime.combine(day, reminder_time, ZoneInfo(timezone))
    return local.astimezone(UTC)


def occurrence_window(
    reminder: Reminder, assignment: Assignment, local_today: date
) -> tuple[str, datetime, datetime] | None:
    if reminder.type is ReminderType.DAILY:
        instant = local_instant(local_today, reminder.reminder_time, assignment.timezone)
        return local_today.isoformat(), instant, instant
    due_day = monthly_due_date(local_today.year, local_today.month, reminder.monthly_due_day or 1)
    start_day = due_day - timedelta(days=reminder.days_before)
    if local_today < start_day:
        return None
    due_at = local_instant(due_day, reminder.reminder_time, assignment.timezone)
    scheduled_day = min(max(local_today, start_day), due_day)
    return due_day.strftime("%Y-%m"), local_instant(scheduled_day, reminder.reminder_time, assignment.timezone), due_at


def occurrence_windows(reminder: Reminder, assignment: Assignment, local_today: date) -> list[tuple[str, datetime, datetime]]:
    primary = occurrence_window(reminder, assignment, local_today)
    if primary is None:
        return []
    windows = [primary]
    if reminder.type is ReminderType.DAILY and reminder.secondary_reminder_time is not None:
        instant = local_instant(local_today, reminder.secondary_reminder_time, assignment.timezone)
        windows.append((f"{local_today.isoformat()}#2", instant, instant))
    return windows


async def materialize(session: AsyncSession, now: datetime) -> int:
    rows = (
        await session.execute(
            select(Reminder, Assignment)
            .join(Assignment, Assignment.reminder_id == Reminder.id)
            .where(Reminder.is_active.is_(True), Reminder.deleted_at.is_(None))
        )
    ).all()
    created = 0
    for reminder, assignment in rows:
        local_today = now.astimezone(ZoneInfo(assignment.timezone)).date()
        for cycle_key, scheduled_at, due_at in occurrence_windows(reminder, assignment, local_today):
            existing = await session.scalar(
                select(Occurrence.id).where(
                    Occurrence.assignment_id == assignment.id, Occurrence.cycle_key == cycle_key
                )
            )
            if existing is not None:
                continue
            session.add(
                Occurrence(
                    reminder_id=reminder.id,
                    assignment_id=assignment.id,
                    user_id=assignment.user_id,
                    cycle_key=cycle_key,
                    scheduled_date=scheduled_at,
                    scheduled_at=scheduled_at,
                    due_at=due_at,
                    status=OccurrenceStatus.PENDING,
                    next_notification_at=scheduled_at,
                )
            )
            created += 1
    await session.flush()
    return created


async def update_due_states(session: AsyncSession, now: datetime) -> int:
    occurrences = list(
        await session.scalars(
            select(Occurrence).where(
                Occurrence.status.in_([OccurrenceStatus.PENDING, OccurrenceStatus.SNOOZED])
            )
        )
    )
    changed = 0
    for occurrence in occurrences:
        if (
            occurrence.status is OccurrenceStatus.SNOOZED
            and occurrence.snoozed_until
            and occurrence.snoozed_until <= now
        ):
            occurrence.status = OccurrenceStatus.PENDING
            occurrence.next_notification_at = now
            changed += 1
        if occurrence.due_at < now:
            reminder = await session.get(Reminder, occurrence.reminder_id)
            if reminder and reminder.type is ReminderType.MONTHLY:
                occurrence.status = OccurrenceStatus.OVERDUE
                occurrence.next_notification_at = max(
                    occurrence.next_notification_at or now, now
                )
                changed += 1
    return changed
