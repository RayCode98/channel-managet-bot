import uuid

from channel_manager_bot.keyboards import publication_markup, settings_menu, ttl_label, ttl_menu


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
