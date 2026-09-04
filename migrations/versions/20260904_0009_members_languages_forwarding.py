"""Miembros por chat, idiomas y modo de reenvío.

Revision ID: 20260904_0009
Revises: 20260904_0008
"""

import sqlalchemy as sa
from alembic import op

revision = "20260904_0009"
down_revision = "20260904_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column(
            "language_code",
            sa.String(length=8),
            server_default=sa.text("'es'"),
            nullable=False,
        ),
    )
    op.add_column(
        "relay_rules",
        sa.Column(
            "preserve_forward_header",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )

    op.add_column(
        "channels",
        sa.Column(
            "join_approval_mode",
            sa.String(length=16),
            server_default=sa.text("'manual'"),
            nullable=False,
        ),
    )
    op.add_column("channels", sa.Column("join_approval_interval_hours", sa.Integer()))
    op.add_column(
        "channels", sa.Column("join_approval_next_run_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "channels", sa.Column("join_approval_last_run_at", sa.DateTime(timezone=True))
    )
    op.create_check_constraint(
        "ck_channels_join_approval_mode",
        "channels",
        "join_approval_mode IN ('manual', 'immediate', 'scheduled')",
    )
    op.create_check_constraint(
        "ck_channels_join_approval_interval",
        "channels",
        "join_approval_interval_hours IS NULL "
        "OR join_approval_interval_hours IN (1, 6, 12, 24, 48)",
    )
    op.create_index(
        "ix_channels_join_approval_next_run_at",
        "channels",
        ["join_approval_next_run_at"],
    )

    # Conserva el comportamiento global anterior, pero lo convierte en una
    # configuración independiente para cada chat existente.
    op.execute(
        sa.text(
            """
            UPDATE channels AS c
            SET join_approval_mode = 'immediate'
            FROM workspaces AS w
            WHERE c.workspace_id = w.id AND w.auto_approve = TRUE
            """
        )
    )

    op.add_column(
        "join_request_events",
        sa.Column("approval_claimed_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "join_request_events",
        sa.Column(
            "approval_attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column("join_request_events", sa.Column("approval_error", sa.Text()))
    op.add_column(
        "join_request_events",
        sa.Column("approved_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_column("join_request_events", "approved_at")
    op.drop_column("join_request_events", "approval_error")
    op.drop_column("join_request_events", "approval_attempts")
    op.drop_column("join_request_events", "approval_claimed_at")
    op.drop_index("ix_channels_join_approval_next_run_at", table_name="channels")
    op.drop_constraint(
        "ck_channels_join_approval_interval", "channels", type_="check"
    )
    op.drop_constraint("ck_channels_join_approval_mode", "channels", type_="check")
    op.drop_column("channels", "join_approval_last_run_at")
    op.drop_column("channels", "join_approval_next_run_at")
    op.drop_column("channels", "join_approval_interval_hours")
    op.drop_column("channels", "join_approval_mode")
    op.drop_column("relay_rules", "preserve_forward_header")
    op.drop_column("workspaces", "language_code")
