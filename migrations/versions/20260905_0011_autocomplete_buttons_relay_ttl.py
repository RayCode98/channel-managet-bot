"""Botones de autocompletado y autoeliminación de reenvíos.

Revision ID: 20260905_0011
Revises: 20260904_0010
"""

import sqlalchemy as sa
from alembic import op

revision = "20260905_0011"
down_revision = "20260904_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "autocomplete_buttons",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("row_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("text", sa.String(length=64), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.ForeignKeyConstraint(
            ["channel_id"],
            ["channels.telegram_chat_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_autocomplete_buttons_channel_id",
        "autocomplete_buttons",
        ["channel_id"],
    )

    op.add_column("relay_deliveries", sa.Column("delete_at", sa.DateTime(timezone=True)))
    op.add_column("relay_deliveries", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.add_column(
        "relay_deliveries",
        sa.Column("delete_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("relay_deliveries", sa.Column("delete_error", sa.Text()))
    op.create_index(
        "ix_relay_deliveries_delete_at",
        "relay_deliveries",
        ["delete_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_relay_deliveries_delete_at", table_name="relay_deliveries")
    op.drop_column("relay_deliveries", "delete_error")
    op.drop_column("relay_deliveries", "delete_attempts")
    op.drop_column("relay_deliveries", "deleted_at")
    op.drop_column("relay_deliveries", "delete_at")

    op.drop_index("ix_autocomplete_buttons_channel_id", table_name="autocomplete_buttons")
    op.drop_table("autocomplete_buttons")
