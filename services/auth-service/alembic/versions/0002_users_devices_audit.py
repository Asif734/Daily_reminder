"""Add device tracking and audit logs."""

import sqlalchemy as sa

from alembic import op

revision = "0002_users_devices_audit"
down_revision = "0001_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("device_identifier", sa.String(255), nullable=False),
        sa.Column("device_name", sa.String(200), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("app_version", sa.String(32), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_devices"),
        schema="auth",
    )
    op.create_index("ix_auth_devices_user", "devices", ["user_id"], schema="auth")
    op.create_index(
        "uq_auth_devices_user_identifier",
        "devices",
        ["user_id", "device_identifier"],
        unique=True,
        schema="auth",
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("metadata", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("request_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
        schema="audit",
    )
    op.create_index("ix_audit_actor", "audit_logs", ["actor_id"], schema="audit")
    op.create_index("ix_audit_action", "audit_logs", ["action"], schema="audit")
    op.create_index("ix_audit_resource", "audit_logs", ["resource_id"], schema="audit")


def downgrade() -> None:
    op.drop_table("audit_logs", schema="audit")
    op.drop_table("devices", schema="auth")
