import json
import re
from collections.abc import Iterable, Sequence

from aiogram.enums import MessageEntityType
from aiogram.types import Message, MessageEntity

from .post_text_length import telegram_text_length

_CUSTOM_EMOJI_HTML = re.compile(r"<tg-emoji\b", re.IGNORECASE)
_CUSTOM_EMOJI_OPENING_TAG = re.compile(r"<tg-emoji\b[^>]*>", re.IGNORECASE)
_CUSTOM_EMOJI_CLOSING_TAG = re.compile(r"</tg-emoji\s*>", re.IGNORECASE)


def message_text_and_entities(message: Message) -> tuple[str | None, list[MessageEntity]]:
    """Return the plain Telegram text and its original UTF-16 based entities."""
    if message.text is not None:
        return message.text, list(message.entities or [])
    return message.caption, list(message.caption_entities or [])


def serialize_entities(entities: Sequence[MessageEntity] | None) -> str:
    return json.dumps(
        [entity.model_dump(mode="json", exclude_none=True) for entity in entities or []],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def deserialize_entities(payload: str | None) -> list[MessageEntity] | None:
    """Return None for legacy/malformed snapshots and a list for valid snapshots."""
    if payload is None:
        return None
    try:
        raw_entities = json.loads(payload)
        if not isinstance(raw_entities, list):
            return None
        return [MessageEntity.model_validate(item) for item in raw_entities]
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def entity_type_value(entity: MessageEntity) -> str:
    return getattr(entity.type, "value", entity.type)


def custom_emoji_count(
    entities: Iterable[MessageEntity] | None = None,
    *,
    html_text: str | None = None,
) -> int:
    if entities is not None:
        return sum(
            entity_type_value(entity) == MessageEntityType.CUSTOM_EMOJI.value for entity in entities
        )
    return len(_CUSTOM_EMOJI_HTML.findall(html_text or ""))


def without_custom_emoji_entities(
    entities: Iterable[MessageEntity],
) -> list[MessageEntity]:
    return [
        entity
        for entity in entities
        if entity_type_value(entity) != MessageEntityType.CUSTOM_EMOJI.value
    ]


def without_custom_emoji_html(html_text: str) -> str:
    """Keep the visible fallback emoji while removing only tg-emoji wrappers."""
    without_opening = _CUSTOM_EMOJI_OPENING_TAG.sub("", html_text)
    return _CUSTOM_EMOJI_CLOSING_TAG.sub("", without_opening)


def stored_custom_emoji_count(entities_json: str | None, html_text: str | None) -> int:
    entities = deserialize_entities(entities_json)
    return (
        custom_emoji_count(entities, html_text=html_text)
        if entities is not None
        else custom_emoji_count(html_text=html_text)
    )


def shifted_entities(entities: Sequence[MessageEntity], offset: int) -> list[MessageEntity]:
    return [entity.model_copy(update={"offset": entity.offset + offset}) for entity in entities]


def join_rich_text_parts(
    parts: Sequence[tuple[str, Sequence[MessageEntity]]], separator: str = "\n\n"
) -> tuple[str | None, list[MessageEntity]]:
    text = ""
    entities: list[MessageEntity] = []
    for part_text, part_entities in parts:
        if not part_text:
            continue
        if text:
            text += separator
        offset = telegram_text_length(text)
        entities.extend(shifted_entities(part_entities, offset))
        text += part_text
    return text or None, entities
