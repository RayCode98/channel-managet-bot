"""Editor profesional e índice para solicitudes pendientes reales.

Revision ID: 20261005_0013
Revises: 20260930_0012
"""

from alembic import op

revision = "20261005_0013"
down_revision = "20260930_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Members counts are grouped by channel and requester.  This index keeps
    # the distinct-count query fast when a user retries a join request.
    op.create_index(
        "ix_join_request_events_pending_requester",
        "join_request_events",
        ["channel_id", "user_id", "created_at", "id", "approved", "outcome"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_join_request_events_pending_requester",
        table_name="join_request_events",
    )
