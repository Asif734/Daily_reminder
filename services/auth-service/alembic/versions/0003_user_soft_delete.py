"""Add member soft deletion."""

import sqlalchemy as sa

from alembic import op

revision = "0003_user_soft_delete"
down_revision = "0002_users_devices_audit"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True)), schema="auth")
    op.create_index("ix_auth_users_deleted_at", "users", ["deleted_at"], schema="auth")

def downgrade() -> None:
    op.drop_index("ix_auth_users_deleted_at", table_name="users", schema="auth")
    op.drop_column("users", "deleted_at", schema="auth")
