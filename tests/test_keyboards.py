import uuid

from channel_manager_bot.keyboards import (
    channel_detail_menu,
    composer_menu,
    publication_markup,
    recurrence_interval_menu,
    recurrence_label,
    settings_menu,
    template_detail_menu,
    timing_menu,
    ttl_label,
    ttl_menu,
)
from channel_manager_bot.models import Channel, WelcomeButton


class Button:
    def __init__(self, text, url, row_index, position):
        self.text = text
        self.url = url
        self.row_index = row_index
        self.position = position


def test_publication_markup_groups_and_orders_rows():
    buttons = [
        Button("Segundo", "https://example.com/2", 0, 1),
        Button("Abajo", "https://example.com/3", 1, 0),
        Button("Primero", "https://example.com/1", 0, 0),
    ]
    markup = publication_markup(buttons)
    assert [[button.text for button in row] for row in markup.inline_keyboard] == [
        ["Primero", "Segundo"],
        ["Abajo"],
    ]


def test_publication_markup_is_none_without_buttons():
    assert publication_markup([]) is None


def test_ttl_labels_and_callbacks():
    item_id = uuid.uuid4()
    markup = ttl_menu("pub", item_id)
    assert ttl_label(1440) == "24 horas"
    assert ttl_label(None) == "No"
    callbacks = [row[0].callback_data for row in markup.inline_keyboard]
    assert f"pub:setttl:{item_id}:0" in callbacks
    assert f"pub:setttl:{item_id}:10080" in callbacks


def test_settings_menu_has_no_global_welcome_actions():
    markup = settings_menu(auto_approve=True)
    callbacks = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert "settings:auto_approve" in callbacks
    assert not any("welcome" in callback for callback in callbacks)


def test_configured_channel_has_buttons_and_preview_actions():
    channel = Channel(
        telegram_chat_id=-1001234567890,
        title="Canal",
        welcome_enabled=True,
        welcome_source_message_id=10,
    )
    channel.welcome_buttons.append(
        WelcomeButton(
            id=1,
            channel_id=channel.telegram_chat_id,
            row_index=0,
            position=0,
            text="Entrar",
            url="https://example.com",
        )
    )

    markup = channel_detail_menu(channel)
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]

    assert "welcome:buttons:-1001234567890" in callbacks
    assert "welcome:manage:-1001234567890" in callbacks
    assert "welcome:preview:-1001234567890" in callbacks


def test_publication_and_template_menus_offer_button_management():
    item_id = uuid.uuid4()
    publication_callbacks = [
        button.callback_data for row in composer_menu(item_id, 2).inline_keyboard for button in row
    ]
    template_callbacks = [
        button.callback_data
        for row in template_detail_menu(item_id, 2, None).inline_keyboard
        for button in row
    ]

    assert f"pub:buttons:{item_id}" in publication_callbacks
    assert f"tpl:buttons:{item_id}" in template_callbacks
    assert f"tpl:preview:{item_id}" in template_callbacks


def test_recurrence_menus_offer_presets_custom_interval_and_start_choice():
    item_id = uuid.uuid4()
    timing_callbacks = [
        button.callback_data for row in timing_menu(item_id).inline_keyboard for button in row
    ]
    interval_callbacks = [
        button.callback_data
        for row in recurrence_interval_menu(item_id).inline_keyboard
        for button in row
    ]

    assert f"pub:repeat:{item_id}" in timing_callbacks
    assert f"pub:setrepeat:{item_id}:1" in interval_callbacks
    assert f"pub:setrepeat:{item_id}:30" in interval_callbacks
    assert f"pub:repeatcustom:{item_id}" in interval_callbacks
    assert recurrence_label(1) == "Cada día"
    assert recurrence_label(14) == "Cada 14 días"
    assert all(len(callback.encode()) <= 64 for callback in interval_callbacks)
