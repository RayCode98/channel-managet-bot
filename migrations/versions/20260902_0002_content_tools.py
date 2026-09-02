"""Bienvenidas por canal, plantillas y autoeliminación.

Revision ID: 20260902_0002
Revises: 20260902_0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260902_0002"
down_revision = "20260902_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("welcome_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("channels", sa.Column("welcome_source_chat_id", sa.BigInteger()))
    op.add_column("channels", sa.Column("welcome_source_message_id", sa.BigInteger()))
    op.add_column("channels", sa.Column("welcome_button_text", sa.String(64)))
    op.add_column("channels", sa.Column("welcome_button_url", sa.String(2048)))
    op.add_column("publications", sa.Column("delete_after_minutes", sa.Integer()))
    op.add_column("published_messages", sa.Column("delete_at", sa.DateTime(timezone=True)))
    op.add_column("published_messages", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.add_column(
        "published_messages",
        sa.Column("delete_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("published_messages", sa.Column("delete_error", sa.Text()))
    op.create_index("ix_published_messages_delete_at", "published_messages", ["delete_at"])

    op.create_table(
        "content_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "creator_user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.telegram_id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("source_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("source_message_id", sa.BigInteger(), nullable=False),
        sa.Column("preview", sa.String(500)),
        sa.Column("delete_after_minutes", sa.Integer()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_content_templates_workspace_id", "content_templates", ["workspace_id"])
    op.create_table(
        "template_buttons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(64), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
    )
    op.create_index("ix_template_buttons_template_id", "template_buttons", ["template_id"])


def downgrade() -> None:
    op.drop_index("ix_template_buttons_template_id", table_name="template_buttons")
    op.drop_table("template_buttons")
    op.drop_index("ix_content_templates_workspace_id", table_name="content_templates")
    op.drop_table("content_templates")
    op.drop_index("ix_published_messages_delete_at", table_name="published_messages")
    op.drop_column("published_messages", "delete_error")
    op.drop_column("published_messages", "delete_attempts")
    op.drop_column("published_messages", "deleted_at")
    op.drop_column("published_messages", "delete_at")
    op.drop_column("publications", "delete_after_minutes")
    op.drop_column("channels", "welcome_button_url")
    op.drop_column("channels", "welcome_button_text")
    op.drop_column("channels", "welcome_source_message_id")
    op.drop_column("channels", "welcome_source_chat_id")
    op.drop_column("channels", "welcome_enabled")
