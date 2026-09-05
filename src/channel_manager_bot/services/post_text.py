from dataclasses import dataclass

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message, MessageEntity

from ..models import Channel, Publication
from .post_text_length import telegram_text_length as _telegram_text_length
from .rich_text import (
    custom_emoji_count,
    deserialize_entities,
    join_rich_text_parts,
    message_text_and_entities,
    serialize_entities,
    without_custom_emoji_entities,
    without_custom_emoji_html,
)

MAX_CHANNEL_TEXT_LENGTH = 500
CAPTIONABLE_CONTENT_TYPES = frozenset({"animation", "audio", "document", "photo", "video", "voice"})


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


@dataclass(frozen=True)
class PostSourceSnapshot:
    source_chat_id: int
    source_message_id: int
    source_content_type: str | None
    source_text_html: str | None
    source_text_plain: str | None
    source_entities_json: str | None


@dataclass(frozen=True)
class PostDelivery:
    message_id: int
    custom_emoji_fallback: bool = False


def post_source_from_message(message: Message) -> PostSourceSnapshot:
    plain_text, entities = message_text_and_entities(message)
    content_type = getattr(message.content_type, "value", message.content_type)
    return PostSourceSnapshot(
        source_chat_id=message.chat.id,
        source_message_id=message.message_id,
        source_content_type=content_type,
        source_text_html=publication_text_html(message),
        source_text_plain=plain_text,
        source_entities_json=serialize_entities(entities),
    )


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
) -> PostDelivery:
    return await send_post_source_to_chat(
        bot=bot,
        source=publication,
        destination_chat_id=channel.telegram_chat_id,
        text_rules_channel=channel,
        reply_markup=reply_markup,
    )


def is_custom_emoji_restriction(exc: TelegramBadRequest) -> bool:
    detail = str(exc).lower()
    return "custom emoji" in detail or "custom_emoji" in detail


def source_custom_emoji_count(source) -> int:
    entities = deserialize_entities(getattr(source, "source_entities_json", None))
    if entities is not None:
        return custom_emoji_count(entities)
    return custom_emoji_count(html_text=getattr(source, "source_text_html", None))


def composed_custom_emoji_count(composed: ComposedPostText) -> int:
    if composed.entities is not None:
        return custom_emoji_count(composed.entities)
    return custom_emoji_count(html_text=composed.html)


def without_custom_emoji(composed: ComposedPostText) -> ComposedPostText:
    if composed.entities is not None:
        return ComposedPostText(
            text=composed.text,
            entities=without_custom_emoji_entities(composed.entities),
            html=None,
        )
    return ComposedPostText(
        text=None,
        entities=None,
        html=without_custom_emoji_html(composed.html or ""),
    )


def original_as_composed(source) -> ComposedPostText | None:
    plain_text = getattr(source, "source_text_plain", None)
    entities = deserialize_entities(getattr(source, "source_entities_json", None))
    if plain_text is not None and entities is not None:
        return ComposedPostText(text=plain_text, entities=entities, html=None)
    html_text = getattr(source, "source_text_html", None)
    if html_text is not None:
        return ComposedPostText(text=None, entities=None, html=html_text)
    return None


async def deliver_composed_post(
    bot: Bot,
    *,
    source,
    destination_chat_id: int,
    reply_markup: InlineKeyboardMarkup | None,
    composed: ComposedPostText,
):
    if source.source_content_type == "text":
        if composed.entities is not None:
            return await bot.send_message(
                chat_id=destination_chat_id,
                text=composed.text or "",
                entities=composed.entities,
                parse_mode=None,
                reply_markup=reply_markup,
            )
        return await bot.send_message(
            chat_id=destination_chat_id,
            text=composed.html or "",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )

    copy_arguments = {
        "chat_id": destination_chat_id,
        "from_chat_id": source.source_chat_id,
        "message_id": source.source_message_id,
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


async def send_post_source_to_chat(
    bot: Bot,
    *,
    source,
    destination_chat_id: int,
    text_rules_channel: Channel,
    reply_markup: InlineKeyboardMarkup | None,
    apply_text_rules: bool = True,
) -> PostDelivery:
    """Finalize autocompletion/signature before a publication or clean relay."""
    original = source.source_text_html
    original_plain = getattr(source, "source_text_plain", None)
    content_type = source.source_content_type

    has_original = bool(
        (original_plain and original_plain.strip()) or (original and original.strip())
    )
    text_can_change = content_type == "text" or content_type in CAPTIONABLE_CONTENT_TYPES
    changes_text = bool(
        apply_text_rules
        and text_can_change
        and (
            (
                not has_original
                and text_rules_channel.autocomplete_enabled
                and text_rules_channel.autocomplete_text
            )
            or (text_rules_channel.signature_enabled and text_rules_channel.signature_text)
        )
    )

    # Publications created before v0.6.0 do not have a source snapshot. Copying them
    # unchanged preserves their original Telegram entities and keeps queued work safe.
    if not content_type:
        sent = await bot.copy_message(
            chat_id=destination_chat_id,
            from_chat_id=source.source_chat_id,
            message_id=source.source_message_id,
            reply_markup=reply_markup,
        )
        return PostDelivery(message_id=sent.message_id)

    composed = compose_channel_post_rich_text(source, text_rules_channel) if changes_text else None
    premium_count = (
        composed_custom_emoji_count(composed)
        if composed is not None
        else source_custom_emoji_count(source)
    )

    try:
        if composed is None:
            sent = await bot.copy_message(
                chat_id=destination_chat_id,
                from_chat_id=source.source_chat_id,
                message_id=source.source_message_id,
                reply_markup=reply_markup,
            )
        else:
            sent = await deliver_composed_post(
                bot,
                source=source,
                destination_chat_id=destination_chat_id,
                reply_markup=reply_markup,
                composed=composed,
            )
        return PostDelivery(message_id=sent.message_id)
    except TelegramBadRequest as exc:
        if not premium_count or not is_custom_emoji_restriction(exc):
            raise
        restriction_error = exc

    fallback_source = composed or original_as_composed(source)
    if fallback_source is None or not text_can_change:
        raise restriction_error
    sent = await deliver_composed_post(
        bot,
        source=source,
        destination_chat_id=destination_chat_id,
        reply_markup=reply_markup,
        composed=without_custom_emoji(fallback_source),
    )
    return PostDelivery(message_id=sent.message_id, custom_emoji_fallback=True)
