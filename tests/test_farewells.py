from types import SimpleNamespace

from aiogram.enums import ChatMemberStatus

from channel_manager_bot.services.welcome import is_voluntary_channel_departure


def departure_event(*, old_status, new_status, actor_id=10, user_id=10, is_bot=False):
    user = SimpleNamespace(id=user_id, is_bot=is_bot)
    return SimpleNamespace(
        from_user=SimpleNamespace(id=actor_id),
        old_chat_member=SimpleNamespace(status=old_status, user=user),
        new_chat_member=SimpleNamespace(status=new_status, user=user),
    )


def test_detects_only_voluntary_user_departure():
    event = departure_event(
        old_status=ChatMemberStatus.MEMBER,
        new_status=ChatMemberStatus.LEFT,
    )

    assert is_voluntary_channel_departure(event)


def test_ignores_admin_removal_and_bot_departure():
    removed_by_admin = departure_event(
        old_status=ChatMemberStatus.MEMBER,
        new_status=ChatMemberStatus.LEFT,
        actor_id=99,
    )
    bot_departure = departure_event(
        old_status=ChatMemberStatus.MEMBER,
        new_status=ChatMemberStatus.LEFT,
        is_bot=True,
    )

    assert not is_voluntary_channel_departure(removed_by_admin)
    assert not is_voluntary_channel_departure(bot_departure)
