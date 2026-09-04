from types import SimpleNamespace

from aiogram.enums import ChatMemberStatus, ChatType

from channel_manager_bot.models import Channel, ChannelStatus
from channel_manager_bot.services.channel_sync import (
    ChannelSnapshot,
    apply_channel_snapshot,
    fetch_channel_snapshot,
    membership_access,
    membership_capabilities,
    normalize_chat_type,
)


def test_membership_access_requires_admin_post_permission():
    active = SimpleNamespace(
        status=ChatMemberStatus.ADMINISTRATOR,
        can_post_messages=True,
    )
    missing = SimpleNamespace(
        status=ChatMemberStatus.ADMINISTRATOR,
        can_post_messages=False,
    )

    assert membership_access(active) == (ChannelStatus.active, True)
    assert membership_access(missing) == (ChannelStatus.missing_permissions, False)


def test_group_admin_can_publish_without_channel_specific_permission():
    admin = SimpleNamespace(
        status=ChatMemberStatus.ADMINISTRATOR,
        can_post_messages=False,
    )

    assert membership_access(admin, "supergroup") == (ChannelStatus.active, True)


def test_membership_capabilities_reads_join_filter_permissions():
    member = SimpleNamespace(
        status=ChatMemberStatus.ADMINISTRATOR,
        can_invite_users=True,
        can_restrict_members=False,
    )

    assert membership_capabilities(member) == (True, False)


def test_normalize_chat_type_accepts_aiogram_enum_and_plain_string():
    assert normalize_chat_type(ChatType.CHANNEL) == "channel"
    assert normalize_chat_type("supergroup") == "supergroup"


class FakeBot:
    id = 777

    async def get_chat(self, channel_id):
        return SimpleNamespace(
            title="Nombre actualizado",
            username="canal_nuevo",
            type="channel",
        )

    async def get_chat_member(self, channel_id, user_id):
        assert user_id == self.id
        return SimpleNamespace(
            status=ChatMemberStatus.ADMINISTRATOR,
            can_post_messages=True,
            can_invite_users=True,
            can_restrict_members=True,
        )

    async def get_chat_member_count(self, channel_id):
        return 250


async def test_fetch_and_apply_channel_snapshot_updates_current_information():
    snapshot = await fetch_channel_snapshot(FakeBot(), -1001234567890)
    channel = Channel(
        telegram_chat_id=-1001234567890,
        title="Nombre anterior",
        username="canal_anterior",
        member_count=200,
        previous_member_count=150,
        status=ChannelStatus.active,
        can_post_messages=True,
    )

    apply_channel_snapshot(channel, snapshot)

    assert channel.title == "Nombre actualizado"
    assert channel.username == "canal_nuevo"
    assert channel.previous_member_count == 200
    assert channel.member_count == 250
    assert channel.last_checked_at is not None
    assert channel.can_invite_users
    assert channel.can_restrict_members
    assert channel.chat_type == "channel"


def test_unavailable_snapshot_updates_access_without_erasing_member_count():
    channel = Channel(
        telegram_chat_id=-1001234567890,
        title="Canal",
        member_count=200,
        status=ChannelStatus.active,
        can_post_messages=True,
    )
    snapshot = ChannelSnapshot(
        title="Canal nuevo",
        username=None,
        member_count=None,
        status=ChannelStatus.removed,
        can_post_messages=False,
    )

    apply_channel_snapshot(channel, snapshot)

    assert channel.title == "Canal nuevo"
    assert channel.member_count == 200
    assert channel.status == ChannelStatus.removed
    assert not channel.can_post_messages
