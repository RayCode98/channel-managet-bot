from types import SimpleNamespace

from aiogram.types import MessageEntity

from channel_manager_bot.services.post_text import (
    compose_channel_post_text,
    send_publication_to_channel,
    telegram_text_length,
)
from channel_manager_bot.services.rich_text import serialize_entities


def channel(**overrides):
    values = {
        "telegram_chat_id": -1001234567890,
        "autocomplete_enabled": True,
        "autocomplete_text": "Descripción automática",
        "autocomplete_text_plain": None,
        "autocomplete_entities_json": None,
        "signature_enabled": True,
        "signature_text": "<b>Firma del canal</b>",
        "signature_text_plain": None,
        "signature_entities_json": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def publication(content_type, text_html, **overrides):
    values = {
        "source_chat_id": 123,
        "source_message_id": 456,
        "source_content_type": content_type,
        "source_text_html": text_html,
        "source_text_plain": None,
        "source_entities_json": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


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


async def test_custom_emoji_entities_survive_signature_composition():
    bot = FakeBot()
    original_entity = MessageEntity(
        type="custom_emoji",
        offset=0,
        length=2,
        custom_emoji_id="original-premium-id",
    )
    signature_entity = MessageEntity(
        type="custom_emoji",
        offset=0,
        length=1,
        custom_emoji_id="signature-premium-id",
    )
    configured_channel = channel(
        autocomplete_enabled=False,
        signature_text='<tg-emoji emoji-id="signature-premium-id">⭐</tg-emoji> Firma',
        signature_text_plain="⭐ Firma",
        signature_entities_json=serialize_entities([signature_entity]),
    )

    await send_publication_to_channel(
        bot,
        publication(
            "text",
            '<tg-emoji emoji-id="original-premium-id">😀</tg-emoji> Oferta',
            source_text_plain="😀 Oferta",
            source_entities_json=serialize_entities([original_entity]),
        ),
        configured_channel,
        reply_markup=None,
    )

    assert bot.method == "send_message"
    assert bot.arguments["text"] == "😀 Oferta\n\n⭐ Firma"
    assert bot.arguments["parse_mode"] is None
    assert [entity.custom_emoji_id for entity in bot.arguments["entities"]] == [
        "original-premium-id",
        "signature-premium-id",
    ]
    assert bot.arguments["entities"][1].offset == telegram_text_length("😀 Oferta\n\n")


async def test_unchanged_custom_emoji_post_uses_native_copy():
    bot = FakeBot()
    configured_channel = channel(signature_enabled=False, signature_text=None)

    await send_publication_to_channel(
        bot,
        publication(
            "text",
            '<tg-emoji emoji-id="premium-id">😀</tg-emoji> Oferta',
            source_text_plain="😀 Oferta",
            source_entities_json=serialize_entities(
                [
                    MessageEntity(
                        type="custom_emoji",
                        offset=0,
                        length=2,
                        custom_emoji_id="premium-id",
                    )
                ]
            ),
        ),
        configured_channel,
        reply_markup=None,
    )

    assert bot.method == "copy_message"
    assert "caption" not in bot.arguments


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
