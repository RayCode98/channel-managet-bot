import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select

from ..models import Channel, ChannelStatus
from ..repository import utcnow

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChannelSnapshot:
    title: str | None
    username: str | None
    member_count: int | None
    status: ChannelStatus
    can_post_messages: bool


@dataclass(frozen=True)
class RefreshSummary:
    checked: int = 0
    updated: int = 0
    unavailable: int = 0
    failed: int = 0


def membership_access(member) -> tuple[ChannelStatus, bool]:
    if member.status == ChatMemberStatus.CREATOR:
        return ChannelStatus.active, True
    if member.status == ChatMemberStatus.ADMINISTRATOR:
        can_post = bool(getattr(member, "can_post_messages", False))
        return (
            ChannelStatus.active if can_post else ChannelStatus.missing_permissions,
            can_post,
        )
    return ChannelStatus.removed, False


async def fetch_channel_snapshot(bot: Bot, channel_id: int) -> ChannelSnapshot:
    chat = await bot.get_chat(channel_id)
    member = await bot.get_chat_member(channel_id, bot.id)
    status, can_post = membership_access(member)
    try:
        member_count = await bot.get_chat_member_count(channel_id)
    except TelegramAPIError as exc:
        logger.info("Could not refresh member count for channel %s: %s", channel_id, exc)
        member_count = None
    return ChannelSnapshot(
        title=chat.title,
        username=chat.username,
        member_count=member_count,
        status=status,
        can_post_messages=can_post,
    )


def apply_channel_snapshot(channel: Channel, snapshot: ChannelSnapshot) -> None:
    if snapshot.title:
        channel.title = snapshot.title
    channel.username = snapshot.username
    if snapshot.member_count is not None:
        channel.previous_member_count = channel.member_count
        channel.member_count = snapshot.member_count
    channel.status = snapshot.status
    channel.can_post_messages = snapshot.can_post_messages
    channel.last_checked_at = utcnow()


def access_was_lost(exc: TelegramAPIError) -> bool:
    if isinstance(exc, TelegramForbiddenError):
        return True
    if not isinstance(exc, TelegramBadRequest):
        return False
    message = str(exc).lower()
    return any(
        fragment in message
        for fragment in (
            "chat not found",
            "bot is not a member",
            "bot was kicked",
        )
    )


async def refresh_channels(
    bot: Bot,
    *,
    workspace_id=None,
    channel_ids: set[int] | None = None,
) -> RefreshSummary:
    from ..database import SessionFactory

    query = select(Channel.telegram_chat_id).where(Channel.status != ChannelStatus.removed)
    if workspace_id is not None:
        query = query.where(Channel.workspace_id == workspace_id)
    if channel_ids is not None:
        query = query.where(Channel.telegram_chat_id.in_(channel_ids))
    async with SessionFactory() as session:
        ids = list(await session.scalars(query.order_by(Channel.telegram_chat_id)))

    updated = unavailable = failed = 0
    for channel_id in ids:
        try:
            snapshot = await fetch_channel_snapshot(bot, channel_id)
        except TelegramAPIError as exc:
            if access_was_lost(exc):
                async with SessionFactory() as session:
                    channel = await session.get(Channel, channel_id)
                    if channel is not None:
                        channel.status = ChannelStatus.removed
                        channel.can_post_messages = False
                        channel.last_checked_at = utcnow()
                        await session.commit()
                unavailable += 1
            else:
                failed += 1
                logger.warning("Could not refresh channel %s: %s", channel_id, exc)
        else:
            async with SessionFactory() as session:
                channel = await session.get(Channel, channel_id)
                if channel is not None:
                    apply_channel_snapshot(channel, snapshot)
                    await session.commit()
                    if snapshot.status == ChannelStatus.active:
                        updated += 1
                    else:
                        unavailable += 1
        await asyncio.sleep(0.05)
    return RefreshSummary(
        checked=len(ids),
        updated=updated,
        unavailable=unavailable,
        failed=failed,
    )


async def channel_refresh_loop(bot: Bot, interval_hours: float) -> None:
    interval_seconds = interval_hours * 60 * 60
    while True:
        next_delay = interval_seconds
        try:
            summary = await refresh_channels(bot)
            logger.info(
                "Channel refresh finished: checked=%s updated=%s unavailable=%s failed=%s",
                summary.checked,
                summary.updated,
                summary.unavailable,
                summary.failed,
            )
        except Exception:
            logger.exception("Unexpected error during periodic channel refresh")
            next_delay = min(interval_seconds, 5 * 60)
        await asyncio.sleep(next_delay)
