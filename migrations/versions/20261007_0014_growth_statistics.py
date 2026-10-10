"""Histórico de crecimiento, estadísticas y enlaces de campaña.

Revision ID: 20261007_0014
Revises: 20261005_0013
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261007_0014"
down_revision = "20261005_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "channel_metric_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "channel_id",
            sa.BigInteger(),
            sa.ForeignKey("channels.telegram_chat_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("member_count", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.String(16), server_default=sa.text("'sync'"), nullable=False),
    )
    op.create_index(
        "ix_channel_metric_snapshots_channel_id",
        "channel_metric_snapshots",
        ["channel_id"],
    )
    op.create_index(
        "ix_channel_metric_snapshots_captured_at",
        "channel_metric_snapshots",
        ["captured_at"],
    )
    op.create_index(
        "ix_channel_metric_snapshots_channel_captured",
        "channel_metric_snapshots",
        ["channel_id", "captured_at"],
    )

    op.create_table(
        "campaign_links",
        sa.Column("token", sa.String(48), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_id",
            sa.BigInteger(),
            sa.ForeignKey("channels.telegram_chat_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("target_url", sa.String(2048), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.telegram_id"]),
    )
    op.create_index("ix_campaign_links_workspace_id", "campaign_links", ["workspace_id"])
    op.create_index("ix_campaign_links_channel_id", "campaign_links", ["channel_id"])

    op.create_table(
        "campaign_clicks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campaign_link_token",
            sa.String(48),
            sa.ForeignKey("campaign_links.token", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("clicked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_campaign_clicks_campaign_link_token", "campaign_clicks", ["campaign_link_token"])
    op.create_index("ix_campaign_clicks_user_id", "campaign_clicks", ["user_id"])
    op.create_index("ix_campaign_clicks_clicked_at", "campaign_clicks", ["clicked_at"])
    op.create_index(
        "ix_campaign_clicks_link_clicked",
        "campaign_clicks",
        ["campaign_link_token", "clicked_at"],
    )
    op.create_index(
        "ix_campaign_clicks_link_user",
        "campaign_clicks",
        ["campaign_link_token", "user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_campaign_clicks_link_user", table_name="campaign_clicks")
    op.drop_index("ix_campaign_clicks_link_clicked", table_name="campaign_clicks")
    op.drop_index("ix_campaign_clicks_clicked_at", table_name="campaign_clicks")
    op.drop_index("ix_campaign_clicks_user_id", table_name="campaign_clicks")
    op.drop_index("ix_campaign_clicks_campaign_link_token", table_name="campaign_clicks")
    op.drop_table("campaign_clicks")
    op.drop_index("ix_campaign_links_channel_id", table_name="campaign_links")
    op.drop_index("ix_campaign_links_workspace_id", table_name="campaign_links")
    op.drop_table("campaign_links")
    op.drop_index(
        "ix_channel_metric_snapshots_channel_captured",
        table_name="channel_metric_snapshots",
    )
    op.drop_index("ix_channel_metric_snapshots_captured_at", table_name="channel_metric_snapshots")
    op.drop_index("ix_channel_metric_snapshots_channel_id", table_name="channel_metric_snapshots")
    op.drop_table("channel_metric_snapshots")
