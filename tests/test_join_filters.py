from types import SimpleNamespace

from aiogram.enums import ChatMemberStatus

from channel_manager_bot.services.join_filters import (
    blocked_name_scripts,
    detect_name_scripts,
    is_current_member,
)


def test_detects_popular_unicode_writing_systems():
    assert detect_name_scripts("Ramón") == {"latin"}
    assert detect_name_scripts("Иван") == {"cyrl"}
    assert detect_name_scripts("محمد") == {"arab"}
    assert detect_name_scripts("रवि") == {"deva"}
    assert detect_name_scripts("王") == {"hani"}
    assert detect_name_scripts("한글") == {"hang"}


def test_mixed_name_matches_any_selected_script_and_ignores_symbols():
    assert blocked_name_scripts("Alex محمد 123 🚀", {"arab", "hebr"}) == {"arab"}
    assert detect_name_scripts("123 🚀 !!!") == set()


def test_current_member_accepts_restricted_only_when_still_a_member():
    for status in (
        ChatMemberStatus.CREATOR,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.MEMBER,
    ):
        assert is_current_member(SimpleNamespace(status=status))

    assert is_current_member(SimpleNamespace(status=ChatMemberStatus.RESTRICTED, is_member=True))
    assert not is_current_member(
        SimpleNamespace(status=ChatMemberStatus.RESTRICTED, is_member=False)
    )
    assert not is_current_member(SimpleNamespace(status=ChatMemberStatus.LEFT))
