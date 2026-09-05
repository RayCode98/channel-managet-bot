from datetime import UTC, datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from channel_manager_bot.services.relay import (
    is_copyable_content_type,
    relay_confirmed_publication,
    remember_relayed_message,
    url_only_markup,
    was_recently_relayed,
    would_create_cycle,
)


def test_only_regular_messages_are_candidates_for_relay():
    assert is_copyable_content_type("text")
    assert is_copyable_content_type("photo")
    assert not is_copyable_content_type("new_chat_members")
    assert not is_copyable_content_type("invoice")
    assert not is_copyable_content_type("paid_media")


def test_cycle_detection_allows_branches_and_rejects_direct_or_indirect_loops():
    edges = {(1, 2), (2, 3), (1, 4)}

    assert not would_create_cycle(edges, 3, 5)
    assert would_create_cycle(edges, 3, 1)
    assert would_create_cycle(edges, 1, 1)


def test_relay_markup_keeps_only_public_url_buttons_and_rows():
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Web", url="https://example.com"),
                InlineKeyboardButton(text="Acción interna", callback_data="private:action"),
            ],
            [InlineKeyboardButton(text="Canal", url="https://t.me/example")],
        ]
    )

    copied = url_only_markup(markup)

    assert copied is not None
    assert [[button.text for button in row] for row in copied.inline_keyboard] == [
        ["Web"],
        ["Canal"],
    ]
    assert all(button.callback_data is None for row in copied.inline_keyboard for button in row)


def test_recent_relay_output_is_remembered_for_loop_protection():
    remember_relayed_message(-100999, 42)

    assert was_recently_relayed(-100999, 42)
    assert not was_recently_relayed(-100999, 43)


async def test_confirmed_worker_post_triggers_relay(monkeypatch):
    received = {}

    async def fake_relay(bot, **kwargs):
        received["bot"] = bot
        received.update(kwargs)

    monkeypatch.setattr(
        "channel_manager_bot.services.relay.relay_managed_publication_message",
        fake_relay,
    )
    bot = object()
    delete_at = datetime(2026, 9, 5, 18, 0, tzinfo=UTC)

    await relay_confirmed_publication(
        bot,
        publication_id="publication-1",
        source_chat_id=-1001,
        source_message_id=84,
        reply_markup=None,
        delete_at=delete_at,
    )

    assert received == {
        "bot": bot,
        "publication_id": "publication-1",
        "source_chat_id": -1001,
        "source_message_id": 84,
        "reply_markup": None,
        "delete_at": delete_at,
    }


async def test_relay_failure_does_not_fail_confirmed_worker_post(monkeypatch, caplog):
    async def failing_relay(*args, **kwargs):
        raise RuntimeError("secondary delivery failed")

    monkeypatch.setattr(
        "channel_manager_bot.services.relay.relay_managed_publication_message",
        failing_relay,
    )

    await relay_confirmed_publication(
        object(),
        publication_id="publication-2",
        source_chat_id=-1002,
        source_message_id=85,
        reply_markup=None,
    )

    assert "Unexpected relay failure" in caplog.text
