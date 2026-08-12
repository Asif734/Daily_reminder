from datetime import datetime, time
from enum import StrEnum
from uuid import UUID

from reminder_common.db import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column


class ReminderType(StrEnum):
    DAILY = "DAILY"
    MONTHLY = "MONTHLY"


class Priority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class OccurrenceStatus(StrEnum):
    PENDING = "PENDING"
    SNOOZED = "SNOOZED"
    COMPLETED = "COMPLETED"
    OVERDUE = "OVERDUE"


class Reminder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reminders"
    __table_args__ = ({"schema": "reminders"},)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[ReminderType] = mapped_column(Enum(ReminderType, schema="reminders"))
    reminder_time: Mapped[time] = mapped_column(Time, nullable=False)
    monthly_due_day: Mapped[int | None] = mapped_column(Integer)
    days_before: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, schema="reminders"), default=Priority.NORMAL, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[UUID] = mapped_column(Uuid, index=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Assignment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "assignments"
    __table_args__ = (
        Index("uq_reminder_assignment", "reminder_id", "user_id", unique=True),
        {"schema": "reminders"},
    )

    reminder_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("reminders.reminders.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(Uuid, index=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutboxEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "outbox_events"
    __table_args__ = ({"schema": "reminders"},)

    aggregate_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(Uuid, index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Occurrence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "occurrences"
    __table_args__ = (
        Index("uq_occurrence_assignment_cycle", "assignment_id", "cycle_key", unique=True),
        Index("ix_occurrence_due_scan", "status", "next_notification_at"),
        {"schema": "reminders"},
    )

    reminder_id: Mapped[UUID] = mapped_column(Uuid, index=True, nullable=False)
    assignment_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("reminders.assignments.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(Uuid, index=True, nullable=False)
    cycle_key: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduled_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[OccurrenceStatus] = mapped_column(
        Enum(OccurrenceStatus, schema="reminders"), default=OccurrenceStatus.PENDING
    )
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_device_id: Mapped[UUID | None] = mapped_column(Uuid)
    next_notification_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SnoozeEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "snooze_events"
    __table_args__ = ({"schema": "reminders"},)

    occurrence_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("reminders.occurrences.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    snoozed_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snoozed_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    device_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
