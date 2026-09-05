"""Entidades enriquecidas y emojis premium.

Revision ID: 20260904_0010
Revises: 20260904_0009
"""

import sqlalchemy as sa
from alembic import op

revision = "20260904_0010"
down_revision = "20260904_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("publications", sa.Column("source_text_plain", sa.Text()))
    op.add_column("publications", sa.Column("source_entities_json", sa.Text()))
    op.add_column("content_templates", sa.Column("source_text_plain", sa.Text()))
    op.add_column("content_templates", sa.Column("source_entities_json", sa.Text()))
    op.add_column("channels", sa.Column("autocomplete_text_plain", sa.Text()))
    op.add_column("channels", sa.Column("autocomplete_entities_json", sa.Text()))
    op.add_column("channels", sa.Column("signature_text_plain", sa.Text()))
    op.add_column("channels", sa.Column("signature_entities_json", sa.Text()))


def downgrade() -> None:
    op.drop_column("channels", "signature_entities_json")
    op.drop_column("channels", "signature_text_plain")
    op.drop_column("channels", "autocomplete_entities_json")
    op.drop_column("channels", "autocomplete_text_plain")
    op.drop_column("content_templates", "source_entities_json")
    op.drop_column("content_templates", "source_text_plain")
    op.drop_column("publications", "source_entities_json")
    op.drop_column("publications", "source_text_plain")
