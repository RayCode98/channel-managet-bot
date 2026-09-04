"""Grupos vinculados y reglas de reenvío.

Revision ID: 20260904_0008
Revises: 20260904_0007
"""

import sqlalchemy as sa
from alembic import op

revision = "20260904_0008"
down_revision = "20260904_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column(
            "chat_type",
            sa.String(length=20),
            server_default=sa.text("'channel'"),
            nullable=False,
        ),
    )

    # Los grupos que ya se habían vinculado como requisito de unión pasan al
    # catálogo único. Así no es necesario volver a agregarlos después de migrar.
    op.execute(
        sa.text(
            """
            INSERT INTO channels (
                telegram_chat_id,
                workspace_id,
                title,
                username,
                chat_type,
                status,
                can_post_messages,
                can_invite_users,
                can_restrict_members,
                join_name_filter_enabled,
                added_by_user_id,
                created_at,
                last_checked_at
            )
            SELECT
                telegram_chat_id,
                workspace_id,
                title,
                username,
                chat_type,
                CASE
                    WHEN active THEN 'active'::channel_status_enum
                    ELSE 'removed'::channel_status_enum
                END,
                active,
                can_invite_users,
                FALSE,
                FALSE,
                added_by_user_id,
                created_at,
                last_checked_at
            FROM requirement_chats
            ON CONFLICT (telegram_chat_id) DO NOTHING
            """
        )
    )
    op.drop_index("ix_requirement_chats_workspace_id", table_name="requirement_chats")
    op.drop_table("requirement_chats")

    op.create_table(
        "relay_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("source_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("creator_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["creator_user_id"], ["users.telegram_id"]),
        sa.ForeignKeyConstraint(
            ["source_chat_id"], ["channels.telegram_chat_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_chat_id", name="uq_relay_rule_source_chat"),
    )
    op.create_index("ix_relay_rules_workspace_id", "relay_rules", ["workspace_id"])
    op.create_index("ix_relay_rules_source_chat_id", "relay_rules", ["source_chat_id"])

    op.create_table(
        "relay_destinations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("relay_rule_id", sa.UUID(), nullable=False),
        sa.Column("destination_chat_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["destination_chat_id"], ["channels.telegram_chat_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["relay_rule_id"], ["relay_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "relay_rule_id",
            "destination_chat_id",
            name="uq_relay_destination_rule_chat",
        ),
    )
    op.create_index(
        "ix_relay_destinations_relay_rule_id", "relay_destinations", ["relay_rule_id"]
    )
    op.create_index(
        "ix_relay_destinations_destination_chat_id",
        "relay_destinations",
        ["destination_chat_id"],
    )

    op.create_table(
        "relay_deliveries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("relay_rule_id", sa.UUID(), nullable=False),
        sa.Column("source_message_id", sa.BigInteger(), nullable=False),
        sa.Column("destination_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger()),
        sa.Column("succeeded", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["destination_chat_id"], ["channels.telegram_chat_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["relay_rule_id"], ["relay_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "relay_rule_id",
            "source_message_id",
            "destination_chat_id",
            name="uq_relay_delivery_message_destination",
        ),
    )
    op.create_index(
        "ix_relay_deliveries_relay_rule_id", "relay_deliveries", ["relay_rule_id"]
    )
    op.create_index(
        "ix_relay_deliveries_destination_chat_id",
        "relay_deliveries",
        ["destination_chat_id"],
    )
    op.create_index(
        "ix_relay_deliveries_output_message",
        "relay_deliveries",
        ["destination_chat_id", "telegram_message_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_relay_deliveries_output_message", table_name="relay_deliveries")
    op.drop_index("ix_relay_deliveries_destination_chat_id", table_name="relay_deliveries")
    op.drop_index("ix_relay_deliveries_relay_rule_id", table_name="relay_deliveries")
    op.drop_table("relay_deliveries")
    op.drop_index("ix_relay_destinations_destination_chat_id", table_name="relay_destinations")
    op.drop_index("ix_relay_destinations_relay_rule_id", table_name="relay_destinations")
    op.drop_table("relay_destinations")
    op.drop_index("ix_relay_rules_source_chat_id", table_name="relay_rules")
    op.drop_index("ix_relay_rules_workspace_id", table_name="relay_rules")
    op.drop_table("relay_rules")

    op.create_table(
        "requirement_chats",
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=64)),
        sa.Column("chat_type", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("can_invite_users", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("added_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["added_by_user_id"], ["users.telegram_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("telegram_chat_id"),
    )
    op.create_index(
        "ix_requirement_chats_workspace_id", "requirement_chats", ["workspace_id"]
    )
    op.execute(
        sa.text(
            """
            INSERT INTO requirement_chats (
                telegram_chat_id,
                workspace_id,
                title,
                username,
                chat_type,
                active,
                can_invite_users,
                added_by_user_id,
                created_at,
                last_checked_at
            )
            SELECT
                telegram_chat_id,
                workspace_id,
                title,
                username,
                chat_type,
                status = 'active'::channel_status_enum,
                can_invite_users,
                added_by_user_id,
                created_at,
                last_checked_at
            FROM channels
            WHERE chat_type IN ('group', 'supergroup')
            """
        )
    )
    # La versión anterior no podía usar grupos como destinos de publicaciones.
    op.execute(sa.text("DELETE FROM channels WHERE chat_type IN ('group', 'supergroup')"))
    op.drop_column("channels", "chat_type")
