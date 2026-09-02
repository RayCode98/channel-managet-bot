"""Esquema inicial multiempresa.

Revision ID: 20260902_0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260902_0001"
down_revision = None
branch_labels = None
depends_on = None

role_enum = sa.Enum("owner", "admin", "editor", name="role_enum")
channel_status_enum = sa.Enum(
    "active", "missing_permissions", "removed", name="channel_status_enum"
)
publication_status_enum = sa.Enum(
    "draft",
    "scheduled",
    "publishing",
    "published",
    "partial",
    "failed",
    "cancelled",
    name="publication_status_enum",
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.String(64)),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "owner_user_id", sa.BigInteger(), sa.ForeignKey("users.telegram_id"), nullable=False
        ),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("auto_approve", sa.Boolean(), nullable=False),
        sa.Column("welcome_enabled", sa.Boolean(), nullable=False),
        sa.Column("welcome_text", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.telegram_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", role_enum, nullable=False),
        sa.UniqueConstraint("workspace_id", "user_id"),
    )
    op.create_table(
        "channels",
        sa.Column("telegram_chat_id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("username", sa.String(64)),
        sa.Column("status", channel_status_enum, nullable=False),
        sa.Column("can_post_messages", sa.Boolean(), nullable=False),
        sa.Column("member_count", sa.Integer()),
        sa.Column("previous_member_count", sa.Integer()),
        sa.Column(
            "added_by_user_id", sa.BigInteger(), sa.ForeignKey("users.telegram_id"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_channels_workspace_id", "channels", ["workspace_id"])
    op.create_table(
        "publications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "creator_user_id", sa.BigInteger(), sa.ForeignKey("users.telegram_id"), nullable=False
        ),
        sa.Column("source_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("source_message_id", sa.BigInteger(), nullable=False),
        sa.Column("preview", sa.String(500)),
        sa.Column("status", publication_status_enum, nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_publications_workspace_id", "publications", ["workspace_id"])
    op.create_index("ix_publications_status", "publications", ["status"])
    op.create_index("ix_publications_scheduled_at", "publications", ["scheduled_at"])
    op.create_table(
        "publication_buttons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "publication_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(64), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
    )
    op.create_index(
        "ix_publication_buttons_publication_id", "publication_buttons", ["publication_id"]
    )
    op.create_table(
        "publication_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "publication_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_id",
            sa.BigInteger(),
            sa.ForeignKey("channels.telegram_chat_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("publication_id", "channel_id"),
    )
    op.create_index(
        "ix_publication_channels_publication_id", "publication_channels", ["publication_id"]
    )
    op.create_table(
        "published_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "publication_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("publications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_id",
            sa.BigInteger(),
            sa.ForeignKey("channels.telegram_chat_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("telegram_message_id", sa.BigInteger()),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column(
            "sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("publication_id", "channel_id"),
    )
    op.create_index(
        "ix_published_messages_publication_id", "published_messages", ["publication_id"]
    )
    op.create_table(
        "join_request_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "channel_id",
            sa.BigInteger(),
            sa.ForeignKey("channels.telegram_chat_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("invite_link", sa.String(2048)),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_join_request_events_channel_id", "join_request_events", ["channel_id"])
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
        ),
        sa.Column("actor_user_id", sa.BigInteger()),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("details", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_audit_logs_workspace_id", "audit_logs", ["workspace_id"])


def downgrade() -> None:
    for table in [
        "audit_logs",
        "join_request_events",
        "published_messages",
        "publication_channels",
        "publication_buttons",
        "publications",
        "channels",
        "memberships",
        "workspaces",
        "users",
    ]:
        op.drop_table(table)
    publication_status_enum.drop(op.get_bind(), checkfirst=True)
    channel_status_enum.drop(op.get_bind(), checkfirst=True)
    role_enum.drop(op.get_bind(), checkfirst=True)
