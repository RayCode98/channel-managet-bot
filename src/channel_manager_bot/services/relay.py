import logging
import uuid
from collections import deque

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

COPYABLE_CONTENT_TYPES = frozenset(
    {
        "animation",
        "audio",
        "contact",
        "dice",
        "document",
        "game",
        "location",
        "photo",
        "poll",
        "sticker",
        "story",
        "text",
        "venue",
        "video",
        "video_note",
        "voice",
    }
)


def is_copyable_content_type(content_type) -> bool:
    value = getattr(content_type, "value", content_type)
    return value in COPYABLE_CONTENT_TYPES


def would_create_cycle(edges: set[tuple[int, int]], source: int, destination: int) -> bool:
    if source == destination:
        return True
    adjacency: dict[int, set[int]] = {}
    for edge_source, edge_destination in edges:
        adjacency.setdefault(edge_source, set()).add(edge_destination)

    pending = [destination]
    visited: set[int] = set()
    while pending:
        current = pending.pop()
        if current == source:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(adjacency.get(current, set()) - visited)
    return False


def url_only_markup(markup: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup | None:
    if markup is None:
        return None
    rows = []
    for row in markup.inline_keyboard:
        url_buttons = [
            InlineKeyboardButton(
                text=button.text,
                url=button.url,
                style=getattr(button, "style", None),
            )
            for button in row
            if button.url
        ]
        if url_buttons:
            rows.append(url_buttons)
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


_RECENT_LIMIT = 5000
_recent_order: deque[tuple[int, int]] = deque()
_recent_set: set[tuple[int, int]] = set()


def remember_relayed_message(chat_id: int, message_id: int) -> None:
    key = (chat_id, message_id)
    if key in _recent_set:
        return
    if len(_recent_order) >= _RECENT_LIMIT:
        _recent_set.discard(_recent_order.popleft())
    _recent_order.append(key)
    _recent_set.add(key)


def was_recently_relayed(chat_id: int, message_id: int) -> bool:
    return (chat_id, message_id) in _recent_set


async def relay_managed_publication_message(
    bot: Bot,
    *,
    publication_id,
    source_chat_id: int,
    source_message_id: int,
    reply_markup: InlineKeyboardMarkup | None,
) -> int:
    """Relay a worker publication even when Telegram emits no channel_post update."""
    # Local imports keep the pure relay helpers usable without application settings.
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.orm import selectinload

    from ..database import SessionFactory
    from ..models import (
        Channel,
        ChannelStatus,
        PublicationChannel,
        RelayDelivery,
        RelayRule,
    )

    async with SessionFactory() as session:
        rule = await session.scalar(
            select(RelayRule)
            .join(Channel, Channel.telegram_chat_id == RelayRule.source_chat_id)
            .options(selectinload(RelayRule.destinations))
            .where(
                RelayRule.source_chat_id == source_chat_id,
                RelayRule.enabled.is_(True),
                Channel.status == ChannelStatus.active,
            )
        )
        if rule is None or not rule.destinations:
            return 0

        destination_ids = [item.destination_chat_id for item in rule.destinations]
        direct_destination_ids = set(
            await session.scalars(
                select(PublicationChannel.channel_id).where(
                    PublicationChannel.publication_id == publication_id,
                    PublicationChannel.channel_id.in_(destination_ids),
                )
            )
        )
        destinations = list(
            await session.scalars(
                select(Channel).where(
                    Channel.telegram_chat_id.in_(destination_ids),
                    Channel.status == ChannelStatus.active,
                    Channel.can_post_messages.is_(True),
                )
            )
        )

        successes = 0
        for destination in destinations:
            destination_chat_id = destination.telegram_chat_id
            if destination_chat_id in direct_destination_ids:
                logger.info(
                    "Skipping worker relay duplicate for publication %s to %s",
                    publication_id,
                    destination_chat_id,
                )
                continue

            delivery_id = uuid.uuid4()
            claimed = await session.scalar(
                pg_insert(RelayDelivery)
                .values(
                    id=delivery_id,
                    relay_rule_id=rule.id,
                    source_message_id=source_message_id,
                    destination_chat_id=destination_chat_id,
                    succeeded=False,
                )
                .on_conflict_do_nothing(constraint="uq_relay_delivery_message_destination")
                .returning(RelayDelivery.id)
            )
            await session.commit()
            if not claimed:
                continue

            delivery = await session.get(RelayDelivery, delivery_id)
            try:
                if rule.preserve_forward_header:
                    sent = await bot.forward_message(
                        chat_id=destination_chat_id,
                        from_chat_id=source_chat_id,
                        message_id=source_message_id,
                    )
                else:
                    sent = await bot.copy_message(
                        chat_id=destination_chat_id,
                        from_chat_id=source_chat_id,
                        message_id=source_message_id,
                        reply_markup=url_only_markup(reply_markup),
                    )
                delivery.telegram_message_id = sent.message_id
                delivery.succeeded = True
                delivery.error = None
                remember_relayed_message(destination_chat_id, sent.message_id)
                successes += 1
            except TelegramAPIError as exc:
                logger.warning(
                    "Could not relay worker publication %s from %s to %s: %s",
                    publication_id,
                    source_chat_id,
                    destination_chat_id,
                    exc,
                )
                delivery.succeeded = False
                delivery.error = str(exc)[:2000]
            await session.commit()
        return successes


async def relay_confirmed_publication(
    bot: Bot,
    *,
    publication_id,
    source_chat_id: int,
    source_message_id: int | None,
    reply_markup: InlineKeyboardMarkup | None,
) -> None:
    """Run secondary relay delivery without risking the confirmed primary post."""
    if source_message_id is None:
        return
    try:
        await relay_managed_publication_message(
            bot,
            publication_id=publication_id,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
            reply_markup=reply_markup,
        )
    except Exception:
        # Reenvío es una entrega secundaria y no debe revertir ni repetir una
        # publicación principal que Telegram ya confirmó.
        logger.exception(
            "Unexpected relay failure for publication %s from %s",
            publication_id,
            source_chat_id,
        )
