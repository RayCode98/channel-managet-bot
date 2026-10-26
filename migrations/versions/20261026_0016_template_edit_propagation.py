"""Associate template-created publications with their source template.

Revision ID: 20261026_0016
Revises: 20261010_0015
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261026_0016"
down_revision = "20261010_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "publications",
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_publications_template_id", "publications", ["template_id"])
    op.create_foreign_key(
        "fk_publications_template_id_content_templates",
        "publications",
        "content_templates",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_publications_template_id_content_templates",
        "publications",
        type_="foreignkey",
    )
    op.drop_index("ix_publications_template_id", table_name="publications")
    op.drop_column("publications", "template_id")
