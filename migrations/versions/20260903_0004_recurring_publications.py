"""Publicaciones recurrentes.

Revision ID: 20260903_0004
Revises: 20260902_0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260903_0004"
down_revision = "20260902_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("publications", sa.Column("recurrence_series_id", postgresql.UUID(as_uuid=True)))
    op.add_column("publications", sa.Column("recurrence_interval_days", sa.Integer()))
    op.add_column("publications", sa.Column("recurrence_sequence", sa.Integer()))
    op.add_column("publications", sa.Column("recurrence_timezone", sa.String(64)))
    op.create_index(
        "ix_publications_recurrence_series_id",
        "publications",
        ["recurrence_series_id"],
    )
    op.create_unique_constraint(
        "uq_publications_recurrence_series_sequence",
        "publications",
        ["recurrence_series_id", "recurrence_sequence"],
    )
    op.create_check_constraint(
        "ck_publications_recurrence_interval_days",
        "publications",
        "recurrence_interval_days BETWEEN 1 AND 365",
    )


def downgrade() -> None:
    op.drop_constraint("ck_publications_recurrence_interval_days", "publications", type_="check")
    op.drop_constraint("uq_publications_recurrence_series_sequence", "publications", type_="unique")
    op.drop_index("ix_publications_recurrence_series_id", table_name="publications")
    op.drop_column("publications", "recurrence_timezone")
    op.drop_column("publications", "recurrence_sequence")
    op.drop_column("publications", "recurrence_interval_days")
    op.drop_column("publications", "recurrence_series_id")
