from types import SimpleNamespace

from channel_manager_bot.services.post_text import (
    compose_channel_post_text,
    send_publication_to_channel,
    telegram_text_length,
)


def channel(**overrides):
    values = {
        "telegram_chat_id": -1001234567890,
        "autocomplete_enabled": True,
        "autocomplete_text": "Descripción automática",
        "signature_enabled": True,
        "signature_text": "<b>Firma del canal</b>",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def publication(content_type, text_html):
    return SimpleNamespace(
        source_chat_id=123,
        source_message_id=456,
        source_content_type=content_type,
        source_text_html=text_html,
    )


def test_autocomplete_is_used_only_when_original_description_is_empty():
    configured_channel = channel()

    without_description = compose_channel_post_text(None, configured_channel)
    with_description = compose_channel_post_text("Texto original", configured_channel)

    assert without_description == "Descripción automática\n\n<b>Firma del canal</b>"
    assert with_description == "Texto original\n\n<b>Firma del canal</b>"
    assert "Descripción automática" not in with_description


def test_signature_can_be_the_only_caption():
    configured_channel = channel(autocomplete_enabled=False)

    assert compose_channel_post_text(None, configured_channel) == "<b>Firma del canal</b>"


def test_telegram_length_counts_emoji_as_utf16_surrogate_pair():
    assert telegram_text_length("A😀") == 3


class FakeBot:
    def __init__(self):
        self.method = None
        self.arguments = None

    async def send_message(self, **kwargs):
        self.method = "send_message"
        self.arguments = kwargs
        return SimpleNamespace(message_id=10)

    async def copy_message(self, **kwargs):
        self.method = "copy_message"
        self.arguments = kwargs
        return SimpleNamespace(message_id=11)


async def test_text_post_is_rebuilt_when_signature_is_added():
    bot = FakeBot()

    await send_publication_to_channel(
        bot,
        publication("text", "Texto original"),
        channel(),
        reply_markup=None,
    )

    assert bot.method == "send_message"
    assert bot.arguments["text"] == "Texto original\n\n<b>Firma del canal</b>"


async def test_media_without_caption_receives_autocomplete_and_signature():
    bot = FakeBot()

    await send_publication_to_channel(
        bot,
        publication("photo", None),
        channel(),
        reply_markup=None,
    )

    assert bot.method == "copy_message"
    assert bot.arguments["caption"] == "Descripción automática\n\n<b>Firma del canal</b>"


async def test_legacy_publication_is_copied_without_channel_text_changes():
    bot = FakeBot()

    await send_publication_to_channel(
        bot,
        publication(None, None),
        channel(),
        reply_markup=None,
    )

    assert bot.method == "copy_message"
    assert "caption" not in bot.arguments
