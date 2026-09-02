"""Variables, botones múltiples y vista previa de bienvenidas.

Revision ID: 20260902_0003
Revises: 20260902_0002
"""

import sqlalchemy as sa
from alembic import op

revision = "20260902_0003"
down_revision = "20260902_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("channels", sa.Column("welcome_content_type", sa.String(20)))
    op.add_column("channels", sa.Column("welcome_text_template", sa.Text()))
    op.add_column("channels", sa.Column("welcome_file_id", sa.String(512)))

    op.create_table(
        "welcome_buttons",
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
    op.create_index("ix_welcome_buttons_channel_id", "welcome_buttons", ["channel_id"])

    # Conserva el botón único configurado por versiones 0.2.x.
    op.execute(
        sa.text(
            """
            INSERT INTO welcome_buttons
                (channel_id, row_index, position, text, url, style)
            SELECT telegram_chat_id, 0, 0, welcome_button_text, welcome_button_url, NULL
            FROM channels
            WHERE welcome_button_text IS NOT NULL
              AND welcome_button_url IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_welcome_buttons_channel_id", table_name="welcome_buttons")
    op.drop_table("welcome_buttons")
    op.drop_column("channels", "welcome_file_id")
    op.drop_column("channels", "welcome_text_template")
    op.drop_column("channels", "welcome_content_type")
