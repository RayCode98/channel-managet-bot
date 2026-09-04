from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from channel_manager_bot.services.relay import (
    is_copyable_content_type,
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
    assert all(
        button.callback_data is None
        for row in copied.inline_keyboard
        for button in row
    )


def test_recent_relay_output_is_remembered_for_loop_protection():
    remember_relayed_message(-100999, 42)

    assert was_recently_relayed(-100999, 42)
    assert not was_recently_relayed(-100999, 43)
