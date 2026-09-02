from channel_manager_bot.keyboards import publication_markup


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
