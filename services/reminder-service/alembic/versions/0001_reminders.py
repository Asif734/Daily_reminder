"""Create reminder definitions, assignments and transactional outbox."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_reminders"
down_revision = None
branch_labels = ("reminders",)
depends_on = None


def upgrade() -> None:
    postgresql.ENUM("DAILY", "MONTHLY", name="remindertype", schema="reminders").create(
        op.get_bind(), checkfirst=True
    )
    postgresql.ENUM("LOW", "NORMAL", "HIGH", name="priority", schema="reminders").create(
        op.get_bind(), checkfirst=True
    )
    reminder_type = postgresql.ENUM(
        "DAILY", "MONTHLY", name="remindertype", schema="reminders", create_type=False
    )
    priority = postgresql.ENUM(
        "LOW", "NORMAL", "HIGH", name="priority", schema="reminders", create_type=False
    )
    op.create_table(
        "reminders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("type", reminder_type, nullable=False),
        sa.Column("reminder_time", sa.Time(), nullable=False),
        sa.Column("monthly_due_day", sa.Integer()),
        sa.Column("days_before", sa.Integer(), server_default="5", nullable=False),
        sa.Column("priority", priority, server_default="NORMAL", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("monthly_due_day IS NULL OR monthly_due_day BETWEEN 1 AND 31", name="monthly_day"),
        sa.CheckConstraint("days_before BETWEEN 0 AND 31", name="days_before"),
        sa.PrimaryKeyConstraint("id", name="pk_reminders"),
        schema="reminders",
    )
    op.create_index("ix_reminders_creator", "reminders", ["created_by"], schema="reminders")
    op.create_table(
        "assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reminder_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reminder_id"], ["reminders.reminders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_assignments"),
        schema="reminders",
    )
    op.create_index("uq_reminder_assignment", "assignments", ["reminder_id", "user_id"], unique=True, schema="reminders")
    op.create_index("ix_assignments_user", "assignments", ["user_id"], schema="reminders")
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_type", sa.String(80), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_events"),
        schema="reminders",
    )
    op.create_index("ix_outbox_aggregate", "outbox_events", ["aggregate_id"], schema="reminders")
    op.create_index("ix_outbox_event_type", "outbox_events", ["event_type"], schema="reminders")


def downgrade() -> None:
    op.drop_table("outbox_events", schema="reminders")
    op.drop_table("assignments", schema="reminders")
    op.drop_table("reminders", schema="reminders")
    postgresql.ENUM(name="priority", schema="reminders").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="remindertype", schema="reminders").drop(op.get_bind(), checkfirst=True)
