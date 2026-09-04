"""Despedidas personalizadas por canal.

Revision ID: 20260904_0005
Revises: 20260903_0004
"""

import sqlalchemy as sa
from alembic import op

revision = "20260904_0005"
down_revision = "20260903_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("farewell_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("channels", sa.Column("farewell_source_chat_id", sa.BigInteger()))
    op.add_column("channels", sa.Column("farewell_source_message_id", sa.BigInteger()))
    op.add_column("channels", sa.Column("farewell_content_type", sa.String(20)))
    op.add_column("channels", sa.Column("farewell_text_template", sa.Text()))
    op.add_column("channels", sa.Column("farewell_file_id", sa.String(512)))
    op.create_table(
        "farewell_buttons",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "channel_id",
            sa.BigInteger(),
            sa.ForeignKey("channels.telegram_chat_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(64), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("style", sa.String(16)),
    )
    op.create_index("ix_farewell_buttons_channel_id", "farewell_buttons", ["channel_id"])


def downgrade() -> None:
    op.drop_index("ix_farewell_buttons_channel_id", table_name="farewell_buttons")
    op.drop_table("farewell_buttons")
    op.drop_column("channels", "farewell_file_id")
    op.drop_column("channels", "farewell_text_template")
    op.drop_column("channels", "farewell_content_type")
    op.drop_column("channels", "farewell_source_message_id")
    op.drop_column("channels", "farewell_source_chat_id")
    op.drop_column("channels", "farewell_enabled")
