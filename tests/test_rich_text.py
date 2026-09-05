from aiogram.types import Message, MessageEntity

from channel_manager_bot.services.post_text_length import telegram_text_length
from channel_manager_bot.services.rich_text import (
    custom_emoji_count,
    deserialize_entities,
    join_rich_text_parts,
    message_text_and_entities,
    serialize_entities,
    stored_custom_emoji_count,
    without_custom_emoji_entities,
    without_custom_emoji_html,
)


def custom_emoji(emoji_id: str, *, offset: int = 0, length: int = 2) -> MessageEntity:
    return MessageEntity(
        type="custom_emoji",
        offset=offset,
        length=length,
        custom_emoji_id=emoji_id,
    )


def test_custom_emoji_snapshot_round_trip_preserves_id():
    payload = serialize_entities([custom_emoji("premium-123")])
    restored = deserialize_entities(payload)

    assert restored is not None
    assert len(restored) == 1
    assert restored[0].custom_emoji_id == "premium-123"
    assert custom_emoji_count(restored) == 1


def test_message_snapshot_reads_caption_entities():
    message = Message.model_validate(
        {
            "message_id": 1,
            "date": 0,
            "chat": {"id": 10, "type": "private"},
            "photo": [
                {
                    "file_id": "photo-id",
                    "file_unique_id": "photo-unique-id",
                    "width": 100,
                    "height": 100,
                }
            ],
            "caption": "😀 Oferta",
            "caption_entities": [
                {
                    "type": "custom_emoji",
                    "offset": 0,
                    "length": 2,
                    "custom_emoji_id": "premium-456",
                }
            ],
        }
    )

    text, entities = message_text_and_entities(message)

    assert text == "😀 Oferta"
    assert custom_emoji_count(entities) == 1
    assert entities[0].custom_emoji_id == "premium-456"


def test_join_rich_text_parts_shifts_utf16_offsets():
    original = custom_emoji("first", length=2)
    signature = custom_emoji("second", length=1)

    text, entities = join_rich_text_parts([("😀 Oferta", [original]), ("⭐ Firma", [signature])])

    assert text == "😀 Oferta\n\n⭐ Firma"
    assert entities[0].offset == 0
    assert entities[1].offset == telegram_text_length("😀 Oferta\n\n")


def test_stored_count_falls_back_to_legacy_html():
    assert (
        stored_custom_emoji_count(
            None,
            '<tg-emoji emoji-id="one">😀</tg-emoji> <tg-emoji emoji-id="two">⭐</tg-emoji>',
        )
        == 2
    )


def test_custom_emoji_fallback_keeps_visible_emoji_and_other_entities():
    custom = custom_emoji("premium")
    bold = MessageEntity(type="bold", offset=3, length=6)

    assert without_custom_emoji_entities([custom, bold]) == [bold]
    assert (
        without_custom_emoji_html('<tg-emoji emoji-id="premium">😀</tg-emoji> <b>Oferta</b>')
        == "😀 <b>Oferta</b>"
    )
