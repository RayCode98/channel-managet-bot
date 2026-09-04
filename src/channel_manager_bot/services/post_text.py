from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, Message

from ..models import Channel, Publication

MAX_CHANNEL_TEXT_LENGTH = 500


def telegram_text_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


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


async def send_publication_to_channel(
    bot: Bot,
    publication: Publication,
    channel: Channel,
    reply_markup: InlineKeyboardMarkup | None,
):
    """Copy a post and override its text only when channel rules change it."""
    original = publication.source_text_html
    final_text = compose_channel_post_text(original, channel)
    content_type = publication.source_content_type

    # Publications created before v0.6.0 do not have a source snapshot. Copying them
    # unchanged preserves their original Telegram entities and keeps queued work safe.
    if not content_type:
        return await bot.copy_message(
            chat_id=channel.telegram_chat_id,
            from_chat_id=publication.source_chat_id,
            message_id=publication.source_message_id,
            reply_markup=reply_markup,
        )

    if content_type == "text" and final_text != original:
        return await bot.send_message(
            chat_id=channel.telegram_chat_id,
            text=final_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )

    copy_arguments = {
        "chat_id": channel.telegram_chat_id,
        "from_chat_id": publication.source_chat_id,
        "message_id": publication.source_message_id,
        "reply_markup": reply_markup,
    }
    if content_type != "text" and final_text != original:
        copy_arguments["caption"] = final_text or ""
        copy_arguments["parse_mode"] = ParseMode.HTML
    return await bot.copy_message(**copy_arguments)
