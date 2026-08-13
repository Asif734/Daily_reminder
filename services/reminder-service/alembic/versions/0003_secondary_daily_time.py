"""Add an optional second daily reminder time."""

import sqlalchemy as sa

from alembic import op

revision = "0003_secondary_daily_time"
down_revision = "0002_occurrences"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("reminders", sa.Column("secondary_reminder_time", sa.Time()), schema="reminders")
    op.create_check_constraint(
        "secondary_time_daily_only",
        "reminders",
        "secondary_reminder_time IS NULL OR type = 'DAILY'",
        schema="reminders",
    )
    op.create_check_constraint(
        "secondary_time_distinct",
        "reminders",
        "secondary_reminder_time IS NULL OR secondary_reminder_time <> reminder_time",
        schema="reminders",
    )

def downgrade() -> None:
    op.drop_constraint("secondary_time_distinct", "reminders", schema="reminders", type_="check")
    op.drop_constraint("secondary_time_daily_only", "reminders", schema="reminders", type_="check")
    op.drop_column("reminders", "secondary_reminder_time", schema="reminders")
