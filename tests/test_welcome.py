from types import SimpleNamespace

import pytest

from channel_manager_bot.services.welcome import (
    parse_welcome_buttons,
    render_welcome_text,
    send_channel_farewell,
    send_channel_welcome,
    welcome_markup,
)


def test_multiline_buttons_accept_colors_and_hyphens_in_url():
    buttons = parse_welcome_buttons(
        "Unirme - https://example.com/invite-link - verde\n"
        "Reglas - https://example.com/reglas - azul\n"
        "Aviso - tg://resolve?domain=example - rojo\n"
        "Sitio - https://example.com - normal"
    )

    assert [button.style for button in buttons] == ["success", "primary", "danger", None]
    assert buttons[0].url == "https://example.com/invite-link"


def test_multiline_buttons_report_invalid_line():
    with pytest.raises(ValueError, match="línea 2"):
        parse_welcome_buttons("Correcto - https://example.com - verde\nFalta formato")


def test_welcome_placeholders_are_replaced_and_escaped():
    rendered = render_welcome_text(
        "Hola <b>{nombre}</b>, bienvenido a {canal}.",
        "Ana & Luis",
        "Noticias <Premium>",
    )

    assert rendered == ("Hola <b>Ana &amp; Luis</b>, bienvenido a Noticias &lt;Premium&gt;.")


def test_welcome_markup_keeps_one_button_per_line_and_styles():
    buttons = [
        SimpleNamespace(
            text="Segundo",
            url="https://example.com/2",
            style="danger",
            row_index=1,
            position=0,
        ),
        SimpleNamespace(
            text="Primero",
            url="https://example.com/1",
            style="success",
            row_index=0,
            position=0,
        ),
    ]

    markup = welcome_markup(buttons)

    assert [[button.text for button in row] for row in markup.inline_keyboard] == [
        ["Primero"],
        ["Segundo"],
    ]
    assert [row[0].style for row in markup.inline_keyboard] == ["success", "danger"]


class FakeBot:
    def __init__(self):
        self.method = None
        self.arguments = None

    async def send_message(self, **kwargs):
        self.method = "send_message"
        self.arguments = kwargs

    async def send_photo(self, **kwargs):
        self.method = "send_photo"
        self.arguments = kwargs


@pytest.mark.parametrize(
    ("content_type", "file_id", "expected_method"),
    [("text", None, "send_message"), ("photo", "photo-file-id", "send_photo")],
)
async def test_send_welcome_renders_same_content_for_text_and_media(
    content_type, file_id, expected_method
):
    bot = FakeBot()
    channel = SimpleNamespace(
        title="Canal & Noticias",
        welcome_content_type=content_type,
        welcome_text_template="Hola <b>{nombre}</b> en {canal}",
        welcome_file_id=file_id,
        welcome_buttons=[],
        welcome_source_chat_id=1,
        welcome_source_message_id=2,
    )

    await send_channel_welcome(bot, 123, channel, "Ana <Admin>")

    assert bot.method == expected_method
    rendered = bot.arguments.get("text") or bot.arguments.get("caption")
    assert rendered == "Hola <b>Ana &lt;Admin&gt;</b> en Canal &amp; Noticias"
    if content_type == "photo":
        assert bot.arguments["photo"] == "photo-file-id"


async def test_send_farewell_uses_channel_content_variables_and_buttons():
    bot = FakeBot()
    channel = SimpleNamespace(
        title="Noticias Premium",
        farewell_content_type="text",
        farewell_text_template="Hasta pronto, <b>{nombre}</b>. Saliste de {canal}.",
        farewell_file_id=None,
        farewell_buttons=[
            SimpleNamespace(
                text="Volver",
                url="https://t.me/noticias",
                style="success",
                row_index=0,
                position=0,
            )
        ],
        farewell_source_chat_id=1,
        farewell_source_message_id=2,
    )

    await send_channel_farewell(bot, 456, channel, "Ana & Luis")

    assert bot.method == "send_message"
    assert bot.arguments["chat_id"] == 456
    assert bot.arguments["text"] == (
        "Hasta pronto, <b>Ana &amp; Luis</b>. Saliste de Noticias Premium."
    )
    assert bot.arguments["reply_markup"].inline_keyboard[0][0].text == "Volver"
