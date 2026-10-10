"""Persist Telegram button colors for posts, templates and autocomplete.

Revision ID: 20261010_0015
Revises: 20261007_0014
"""

import sqlalchemy as sa
from alembic import op

revision = "20261010_0015"
down_revision = "20261007_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable styles so existing buttons remain the normal style."""
    for table in ("publication_buttons", "template_buttons", "autocomplete_buttons"):
        op.add_column(table, sa.Column("style", sa.String(16), nullable=True))


def downgrade() -> None:
    for table in ("autocomplete_buttons", "template_buttons", "publication_buttons"):
        op.drop_column(table, "style")
