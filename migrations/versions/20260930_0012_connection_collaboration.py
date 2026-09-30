"""Conexión explícita, permisos y colaboración.

Revision ID: 20260930_0012
Revises: 20260905_0011
"""

import sqlalchemy as sa
from alembic import op

revision = "20260930_0012"
down_revision = "20260905_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("active_workspace_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_active_workspace_id",
        "users",
        "workspaces",
        ["active_workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "channels",
        sa.Column("can_delete_messages", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "channels",
        sa.Column("can_edit_messages", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "channels",
        sa.Column("can_pin_messages", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "channels",
        sa.Column("can_manage_topics", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("channels", sa.Column("permission_issue", sa.Text()))
    op.add_column(
        "channels", sa.Column("last_permission_alert_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "channels",
        sa.Column(
            "connection_method",
            sa.String(length=32),
            server_default="membership_event",
            nullable=False,
        ),
    )

    role_enum = sa.Enum("owner", "admin", "editor", name="role_enum", create_type=False)
    op.create_table(
        "workspace_invites",
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", role_enum, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.telegram_id"]),
        sa.ForeignKeyConstraint(
            ["used_by_user_id"], ["users.telegram_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("token"),
    )
    op.create_index(
        "ix_workspace_invites_workspace_id",
        "workspace_invites",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_invites_workspace_id", table_name="workspace_invites")
    op.drop_table("workspace_invites")
    op.drop_constraint("fk_users_active_workspace_id", "users", type_="foreignkey")
    op.drop_column("users", "active_workspace_id")
    op.drop_column("channels", "connection_method")
    op.drop_column("channels", "last_permission_alert_at")
    op.drop_column("channels", "permission_issue")
    op.drop_column("channels", "can_manage_topics")
    op.drop_column("channels", "can_pin_messages")
    op.drop_column("channels", "can_edit_messages")
    op.drop_column("channels", "can_delete_messages")
