"""Create authentication tables."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_auth"
down_revision = None
branch_labels = ("auth",)
depends_on = None


def upgrade() -> None:
    role = postgresql.ENUM("ADMIN", "MEMBER", name="role", schema="auth", create_type=False)
    postgresql.ENUM("ADMIN", "MEMBER", name="role", schema="auth").create(
        op.get_bind(), checkfirst=True
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("role", role, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("timezone", sa.String(64), server_default="UTC", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        schema="auth",
    )
    op.create_index("ix_auth_users_email_lower", "users", ["email"], unique=True, schema="auth")
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("replaced_by_id", sa.Uuid()),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        schema="auth",
    )
    op.create_index("ix_auth_refresh_family", "refresh_tokens", ["family_id"], schema="auth")
    op.create_index("ix_auth_refresh_user", "refresh_tokens", ["user_id"], schema="auth")


def downgrade() -> None:
    op.drop_table("refresh_tokens", schema="auth")
    op.drop_table("users", schema="auth")
    sa.Enum("ADMIN", "MEMBER", name="role", schema="auth").drop(op.get_bind(), checkfirst=True)
