import uuid

from channel_manager_bot.keyboards import (
    alphabet_filter_menu,
    channel_detail_menu,
    channel_post_text_menu,
    composer_menu,
    farewell_menu,
    feature_channels_menu,
    join_verification_menu,
    main_menu,
    publication_markup,
    recurrence_interval_menu,
    recurrence_label,
    settings_menu,
    template_detail_menu,
    timing_menu,
    ttl_label,
    ttl_menu,
    welcome_menu,
)
from channel_manager_bot.models import Channel, FarewellButton, WelcomeButton


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


def test_feature_first_navigation_and_welcome_menu():
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

    main_callbacks = [button.callback_data for row in main_menu().inline_keyboard for button in row]
    channel_callbacks = [
        button.callback_data
        for row in channel_detail_menu(channel).inline_keyboard
        for button in row
    ]
    welcome_callbacks = [
        button.callback_data for row in welcome_menu(channel).inline_keyboard for button in row
    ]

    assert "feature:channels:welcome" in main_callbacks
    assert "feature:channels:farewell" in main_callbacks
    assert "feature:channels:auto" in main_callbacks
    assert "feature:channels:signature" in main_callbacks
    assert "feature:channels:joinfilter" in main_callbacks
    assert channel_callbacks == ["channel:refresh:-1001234567890", "channels:list"]
    assert "welcome:buttons:-1001234567890" in welcome_callbacks
    assert "welcome:manage:-1001234567890" in welcome_callbacks
    assert "welcome:preview:-1001234567890" in welcome_callbacks
    assert "feature:channels:welcome" in welcome_callbacks


def test_feature_channel_list_routes_directly_to_selected_configuration():
    channel = Channel(
        telegram_chat_id=-1001234567890,
        title="Canal",
        farewell_enabled=True,
    )

    button = feature_channels_menu([channel], "farewell").inline_keyboard[0][0]

    assert button.text == "✅ Canal"
    assert button.callback_data == "farewell:menu:-1001234567890"


def test_join_filter_channel_list_and_alphabet_callbacks_are_valid():
    channel = Channel(
        telegram_chat_id=-1001234567890,
        title="Canal protegido",
        join_name_filter_enabled=True,
    )
    channel_button = feature_channels_menu([channel], "joinfilter").inline_keyboard[0][0]
    alphabet = alphabet_filter_menu(channel.telegram_chat_id, {"arab", "deva"}, True)
    callbacks = [
        button.callback_data
        for row in alphabet.inline_keyboard
        for button in row
        if button.callback_data
    ]

    assert channel_button.text == "✅ Canal protegido"
    assert channel_button.callback_data == "jfilter:menu:-1001234567890"
    assert "jfilter:script:arab:-1001234567890" in callbacks
    assert "jfilter:script:deva:-1001234567890" in callbacks
    assert "jfilter:atoggle:-1001234567890" in callbacks
    assert all(len(callback.encode()) <= 64 for callback in callbacks)


def test_join_verification_callback_belongs_to_requester():
    markup = join_verification_menu(
        "https://t.me/destino",
        -1001234567890,
        987654321,
    )

    assert markup.inline_keyboard[0][0].url == "https://t.me/destino"
    assert markup.inline_keyboard[1][0].callback_data == ("joinverify:-1001234567890:987654321")


def test_configured_farewell_has_preview_and_button_management():
    channel = Channel(
        telegram_chat_id=-1001234567890,
        title="Canal",
        farewell_enabled=True,
        farewell_source_message_id=20,
    )
    channel.farewell_buttons.append(
        FarewellButton(
            id=2,
            channel_id=channel.telegram_chat_id,
            row_index=0,
            position=0,
            text="Volver",
            url="https://example.com",
        )
    )

    callbacks = [
        button.callback_data for row in farewell_menu(channel).inline_keyboard for button in row
    ]

    assert "farewell:manage:-1001234567890" in callbacks
    assert "farewell:preview:-1001234567890" in callbacks
    assert "farewell:toggle:-1001234567890" in callbacks


def test_channel_post_text_menu_offers_preview_toggle_and_clear():
    channel = Channel(
        telegram_chat_id=-1001234567890,
        title="Canal",
        autocomplete_enabled=True,
        autocomplete_text="Texto automático",
    )

    callbacks = [
        button.callback_data
        for row in channel_post_text_menu(channel, "auto").inline_keyboard
        for button in row
    ]

    assert "posttext:preview:auto:-1001234567890" in callbacks
    assert "posttext:toggle:auto:-1001234567890" in callbacks
    assert "posttext:clear:auto:-1001234567890" in callbacks
    assert all(len(callback.encode()) <= 64 for callback in callbacks)


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
