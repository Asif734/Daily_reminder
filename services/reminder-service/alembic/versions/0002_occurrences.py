"""Add reminder occurrences and immutable snooze events."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_occurrences"
down_revision = "0001_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    postgresql.ENUM(
        "PENDING", "SNOOZED", "COMPLETED", "OVERDUE", name="occurrencestatus", schema="reminders"
    ).create(op.get_bind(), checkfirst=True)
    occurrence_status = postgresql.ENUM(
        "PENDING",
        "SNOOZED",
        "COMPLETED",
        "OVERDUE",
        name="occurrencestatus",
        schema="reminders",
        create_type=False,
    )
    op.create_table(
        "occurrences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reminder_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("cycle_key", sa.String(32), nullable=False),
        sa.Column("scheduled_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", occurrence_status, nullable=False),
        sa.Column("snoozed_until", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_device_id", sa.Uuid()),
        sa.Column("next_notification_at", sa.DateTime(timezone=True)),
        sa.Column("last_notified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["reminders.assignments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_occurrences"),
        schema="reminders",
    )
    op.create_index("ix_occurrences_reminder", "occurrences", ["reminder_id"], schema="reminders")
    op.create_index("ix_occurrences_user", "occurrences", ["user_id"], schema="reminders")
    op.create_index("uq_occurrence_assignment_cycle", "occurrences", ["assignment_id", "cycle_key"], unique=True, schema="reminders")
    op.create_index("ix_occurrence_due_scan", "occurrences", ["status", "next_notification_at"], schema="reminders")
    op.create_table(
        "snooze_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("occurrence_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("snoozed_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_id", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["occurrence_id"], ["reminders.occurrences.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_snooze_events"),
        schema="reminders",
    )
    op.create_index("ix_snooze_occurrence", "snooze_events", ["occurrence_id"], schema="reminders")


def downgrade() -> None:
    op.drop_table("snooze_events", schema="reminders")
    op.drop_table("occurrences", schema="reminders")
    postgresql.ENUM(name="occurrencestatus", schema="reminders").drop(op.get_bind(), checkfirst=True)
