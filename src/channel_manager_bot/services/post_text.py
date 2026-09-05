from dataclasses import dataclass

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, Message, MessageEntity

from ..models import Channel, Publication
from .post_text_length import telegram_text_length as _telegram_text_length
from .rich_text import deserialize_entities, join_rich_text_parts

MAX_CHANNEL_TEXT_LENGTH = 500


def telegram_text_length(value: str) -> int:
    return _telegram_text_length(value)


def publication_content_type(message: Message) -> str:
    if message.text:
        return "text"
    if message.photo:
        return "photo"
    for content_type in ("video", "animation", "audio", "document", "voice"):
        if getattr(message, content_type):
            return content_type
    raise ValueError("Tipo de publicación no compatible.")


def publication_text_html(message: Message) -> str | None:
    text = message.html_text
    return text.strip() if text and text.strip() else None


def compose_channel_post_text(original_html: str | None, channel: Channel) -> str | None:
    original = original_html.strip() if original_html and original_html.strip() else None
    parts: list[str] = []
    if original:
        parts.append(original)
    elif channel.autocomplete_enabled and channel.autocomplete_text:
        parts.append(channel.autocomplete_text.strip())
    if channel.signature_enabled and channel.signature_text:
        parts.append(channel.signature_text.strip())
    return "\n\n".join(part for part in parts if part) or None


@dataclass(frozen=True)
class ComposedPostText:
    text: str | None
    entities: list[MessageEntity] | None
    html: str | None


def compose_channel_post_rich_text(publication: Publication, channel: Channel) -> ComposedPostText:
    """Compose a post while retaining Telegram entities whenever snapshots exist."""
    original_html = publication.source_text_html
    original_plain = getattr(publication, "source_text_plain", None)
    original_entities_json = getattr(publication, "source_entities_json", None)
    has_original = bool(
        (original_plain and original_plain.strip()) or (original_html and original_html.strip())
    )

    auto_applies = bool(
        not has_original and channel.autocomplete_enabled and channel.autocomplete_text
    )
    signature_applies = bool(channel.signature_enabled and channel.signature_text)

    parts: list[tuple[str, list[MessageEntity]]] = []
    snapshots_available = True

    if has_original:
        original_entities = deserialize_entities(original_entities_json)
        if original_plain is None or original_entities is None:
            snapshots_available = False
        else:
            parts.append((original_plain, original_entities))
    elif auto_applies:
        auto_plain = getattr(channel, "autocomplete_text_plain", None)
        auto_entities = deserialize_entities(getattr(channel, "autocomplete_entities_json", None))
        if auto_plain is None or auto_entities is None:
            snapshots_available = False
        else:
            parts.append((auto_plain, auto_entities))

    if signature_applies:
        signature_plain = getattr(channel, "signature_text_plain", None)
        signature_entities = deserialize_entities(getattr(channel, "signature_entities_json", None))
        if signature_plain is None or signature_entities is None:
            snapshots_available = False
        else:
            parts.append((signature_plain, signature_entities))

    if snapshots_available:
        text, entities = join_rich_text_parts(parts)
        return ComposedPostText(text=text, entities=entities, html=None)

    return ComposedPostText(
        text=None,
        entities=None,
        html=compose_channel_post_text(original_html, channel),
    )


async def send_publication_to_channel(
    bot: Bot,
    publication: Publication,
    channel: Channel,
    reply_markup: InlineKeyboardMarkup | None,
):
    """Copy a post and override its text only when channel rules change it."""
    original = publication.source_text_html
    original_plain = getattr(publication, "source_text_plain", None)
    content_type = publication.source_content_type

    has_original = bool(
        (original_plain and original_plain.strip()) or (original and original.strip())
    )
    changes_text = bool(
        (not has_original and channel.autocomplete_enabled and channel.autocomplete_text)
        or (channel.signature_enabled and channel.signature_text)
    )

    # Publications created before v0.6.0 do not have a source snapshot. Copying them
    # unchanged preserves their original Telegram entities and keeps queued work safe.
    if not content_type:
        return await bot.copy_message(
            chat_id=channel.telegram_chat_id,
            from_chat_id=publication.source_chat_id,
            message_id=publication.source_message_id,
            reply_markup=reply_markup,
        )

    if not changes_text:
        return await bot.copy_message(
            chat_id=channel.telegram_chat_id,
            from_chat_id=publication.source_chat_id,
            message_id=publication.source_message_id,
            reply_markup=reply_markup,
        )

    composed = compose_channel_post_rich_text(publication, channel)

    if content_type == "text":
        if composed.entities is not None:
            return await bot.send_message(
                chat_id=channel.telegram_chat_id,
                text=composed.text or "",
                entities=composed.entities,
                parse_mode=None,
                reply_markup=reply_markup,
            )
        return await bot.send_message(
            chat_id=channel.telegram_chat_id,
            text=composed.html or "",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )

    copy_arguments = {
        "chat_id": channel.telegram_chat_id,
        "from_chat_id": publication.source_chat_id,
        "message_id": publication.source_message_id,
        "reply_markup": reply_markup,
    }
    if composed.entities is not None:
        copy_arguments["caption"] = composed.text or ""
        copy_arguments["caption_entities"] = composed.entities
        copy_arguments["parse_mode"] = None
    else:
        copy_arguments["caption"] = composed.html or ""
        copy_arguments["parse_mode"] = ParseMode.HTML
    return await bot.copy_message(**copy_arguments)
