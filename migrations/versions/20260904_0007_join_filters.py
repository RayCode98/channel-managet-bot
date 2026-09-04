"""Filtros de escritura y membresía obligatoria por canal.

Revision ID: 20260904_0007
Revises: 20260904_0006
"""

import sqlalchemy as sa
from alembic import op

revision = "20260904_0007"
down_revision = "20260904_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("can_invite_users", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "channels",
        sa.Column("can_restrict_members", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "channels",
        sa.Column(
            "join_name_filter_enabled", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )

    op.create_table(
        "join_name_scripts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("script_code", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.telegram_chat_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id", "script_code", name="uq_join_name_script_channel_code"),
    )
    op.create_index(
        "ix_join_name_scripts_channel_id", "join_name_scripts", ["channel_id"], unique=False
    )

    op.create_table(
        "join_requirements",
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("target_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("target_title", sa.String(length=255), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("invite_url", sa.String(length=2048), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.telegram_chat_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("channel_id"),
    )

    op.create_table(
        "requirement_chats",
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=64)),
        sa.Column("chat_type", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("can_invite_users", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("added_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by_user_id"], ["users.telegram_id"]),
        sa.PrimaryKeyConstraint("telegram_chat_id"),
    )
    op.create_index(
        "ix_requirement_chats_workspace_id", "requirement_chats", ["workspace_id"], unique=False
    )

    op.add_column("join_request_events", sa.Column("user_chat_id", sa.BigInteger()))
    op.add_column(
        "join_request_events",
        sa.Column(
            "outcome",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("join_request_events", "outcome")
    op.drop_column("join_request_events", "user_chat_id")
    op.drop_index("ix_requirement_chats_workspace_id", table_name="requirement_chats")
    op.drop_table("requirement_chats")
    op.drop_table("join_requirements")
    op.drop_index("ix_join_name_scripts_channel_id", table_name="join_name_scripts")
    op.drop_table("join_name_scripts")
    op.drop_column("channels", "join_name_filter_enabled")
    op.drop_column("channels", "can_restrict_members")
    op.drop_column("channels", "can_invite_users")
