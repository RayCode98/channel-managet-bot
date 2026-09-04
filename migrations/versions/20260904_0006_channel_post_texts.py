"""Autocompletado y firma por canal.

Revision ID: 20260904_0006
Revises: 20260904_0005
"""

import sqlalchemy as sa
from alembic import op

revision = "20260904_0006"
down_revision = "20260904_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("autocomplete_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("channels", sa.Column("autocomplete_text", sa.Text()))
    op.add_column(
        "channels",
        sa.Column("signature_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("channels", sa.Column("signature_text", sa.Text()))
    op.add_column("publications", sa.Column("source_content_type", sa.String(20)))
    op.add_column("publications", sa.Column("source_text_html", sa.Text()))
    op.add_column("content_templates", sa.Column("source_content_type", sa.String(20)))
    op.add_column("content_templates", sa.Column("source_text_html", sa.Text()))


def downgrade() -> None:
    op.drop_column("content_templates", "source_text_html")
    op.drop_column("content_templates", "source_content_type")
    op.drop_column("publications", "source_text_html")
    op.drop_column("publications", "source_content_type")
    op.drop_column("channels", "signature_text")
    op.drop_column("channels", "signature_enabled")
    op.drop_column("channels", "autocomplete_text")
    op.drop_column("channels", "autocomplete_enabled")
