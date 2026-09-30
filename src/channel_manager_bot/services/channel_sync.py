import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from html import escape

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
    can_invite_users: bool = False
    can_restrict_members: bool = False
    can_delete_messages: bool = False
    can_edit_messages: bool = False
    can_pin_messages: bool = False
    can_manage_topics: bool = False
    permission_issue: str | None = None
    chat_type: str = "channel"


@dataclass(frozen=True)
class RefreshSummary:
    checked: int = 0
    updated: int = 0
    unavailable: int = 0
    failed: int = 0
    alerts: int = 0


def normalize_chat_type(chat_type) -> str:
    """Return a stable Telegram chat type for enum- and string-based models."""
    return str(getattr(chat_type, "value", chat_type))


def membership_access(member, chat_type: str = "channel") -> tuple[ChannelStatus, bool]:
    if member.status == ChatMemberStatus.CREATOR:
        return ChannelStatus.active, True
    if member.status == ChatMemberStatus.ADMINISTRATOR:
        can_post = chat_type in {"group", "supergroup"} or bool(
            getattr(member, "can_post_messages", False)
        )
        return (
            ChannelStatus.active if can_post else ChannelStatus.missing_permissions,
            can_post,
        )
    return ChannelStatus.removed, False


def membership_capabilities(member) -> tuple[bool, bool]:
    if member.status == ChatMemberStatus.CREATOR:
        return True, True
    if member.status != ChatMemberStatus.ADMINISTRATOR:
        return False, False
    return (
        bool(getattr(member, "can_invite_users", False)),
        bool(getattr(member, "can_restrict_members", False)),
    )


def membership_permissions(member, chat_type: str = "channel") -> dict[str, bool]:
    """Return the Telegram capabilities used by the manager.

    Groups do not expose ``can_post_messages``; being an administrator is
    enough to publish there. Creators are treated as having every capability.
    """
    if member.status == ChatMemberStatus.CREATOR:
        return {
            "can_post_messages": True,
            "can_invite_users": True,
            "can_restrict_members": True,
            "can_delete_messages": True,
            "can_edit_messages": True,
            "can_pin_messages": True,
            "can_manage_topics": True,
        }
    if member.status != ChatMemberStatus.ADMINISTRATOR:
        return {
            "can_post_messages": False,
            "can_invite_users": False,
            "can_restrict_members": False,
            "can_delete_messages": False,
            "can_edit_messages": False,
            "can_pin_messages": False,
            "can_manage_topics": False,
        }
    return {
        "can_post_messages": chat_type in {"group", "supergroup"}
        or bool(getattr(member, "can_post_messages", False)),
        "can_invite_users": bool(getattr(member, "can_invite_users", False)),
        "can_restrict_members": bool(getattr(member, "can_restrict_members", False)),
        "can_delete_messages": bool(getattr(member, "can_delete_messages", False)),
        "can_edit_messages": bool(getattr(member, "can_edit_messages", False)),
        "can_pin_messages": bool(getattr(member, "can_pin_messages", False)),
        "can_manage_topics": bool(getattr(member, "can_manage_topics", False)),
    }


def permission_issue_text(permissions: dict[str, bool], chat_type: str) -> str | None:
    """Describe missing baseline permissions without blocking optional features."""
    labels = []
    if not permissions["can_post_messages"]:
        labels.append("publicar mensajes")
    if chat_type in {"group", "supergroup"} and not permissions["can_delete_messages"]:
        labels.append("eliminar mensajes")
    if not permissions["can_invite_users"]:
        labels.append("invitar usuarios")
    if not permissions["can_restrict_members"]:
        labels.append("restringir miembros")
    return ", ".join(labels) if labels else None


async def fetch_channel_snapshot(bot: Bot, channel_id: int) -> ChannelSnapshot:
    chat = await bot.get_chat(channel_id)
    member = await bot.get_chat_member(channel_id, bot.id)
    chat_type = normalize_chat_type(chat.type)
    status, can_post = membership_access(member, chat_type)
    permissions = membership_permissions(member, chat_type)
    can_invite = permissions["can_invite_users"]
    can_restrict = permissions["can_restrict_members"]
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
        can_invite_users=can_invite,
        can_restrict_members=can_restrict,
        can_delete_messages=permissions["can_delete_messages"],
        can_edit_messages=permissions["can_edit_messages"],
        can_pin_messages=permissions["can_pin_messages"],
        can_manage_topics=permissions["can_manage_topics"],
        permission_issue=permission_issue_text(permissions, chat_type),
        chat_type=chat_type,
    )


def apply_channel_snapshot(channel: Channel, snapshot: ChannelSnapshot) -> None:
    if snapshot.title:
        channel.title = snapshot.title
    channel.username = snapshot.username
    channel.chat_type = snapshot.chat_type
    if snapshot.member_count is not None:
        channel.previous_member_count = channel.member_count
        channel.member_count = snapshot.member_count
    channel.status = snapshot.status
    channel.can_post_messages = snapshot.can_post_messages
    channel.can_invite_users = snapshot.can_invite_users
    channel.can_restrict_members = snapshot.can_restrict_members
    channel.can_delete_messages = snapshot.can_delete_messages
    channel.can_edit_messages = snapshot.can_edit_messages
    channel.can_pin_messages = snapshot.can_pin_messages
    channel.can_manage_topics = snapshot.can_manage_topics
    channel.permission_issue = snapshot.permission_issue
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

    updated = unavailable = failed = alerts = 0
    for channel_id in ids:
        try:
            snapshot = await fetch_channel_snapshot(bot, channel_id)
        except TelegramAPIError as exc:
            if access_was_lost(exc):
                alert = None
                async with SessionFactory() as session:
                    channel = await session.get(Channel, channel_id)
                    if channel is not None:
                        was_checked = channel.last_checked_at is not None
                        previous_status = channel.status
                        channel.status = ChannelStatus.removed
                        channel.can_post_messages = False
                        channel.can_invite_users = False
                        channel.can_restrict_members = False
                        channel.can_delete_messages = False
                        channel.can_edit_messages = False
                        channel.can_pin_messages = False
                        channel.can_manage_topics = False
                        channel.permission_issue = "Telegram no permite acceder a este chat"
                        channel.last_checked_at = utcnow()
                        if (
                            was_checked
                            and previous_status != ChannelStatus.removed
                            and _permission_alert_due(channel)
                        ):
                            channel.last_permission_alert_at = utcnow()
                            alert = (channel.added_by_user_id, channel.title, channel.permission_issue)
                        await session.commit()
                if alert:
                    alerts += 1
                    await _send_permission_alert(bot, *alert)
                unavailable += 1
            else:
                failed += 1
                logger.warning("Could not refresh channel %s: %s", channel_id, exc)
        else:
            alert = None
            async with SessionFactory() as session:
                channel = await session.get(Channel, channel_id)
                if channel is not None:
                    was_checked = channel.last_checked_at is not None
                    previous_issue = channel.permission_issue
                    previous_status = channel.status
                    apply_channel_snapshot(channel, snapshot)
                    issue_changed = snapshot.permission_issue != previous_issue
                    status_changed = snapshot.status != previous_status
                    meaningful_change = status_changed or (
                        issue_changed and previous_issue is not None
                    )
                    if was_checked and meaningful_change and _permission_alert_due(channel):
                        channel.last_permission_alert_at = utcnow()
                        alert = (channel.added_by_user_id, channel.title, snapshot.permission_issue)
                    await session.commit()
                    if snapshot.status == ChannelStatus.active:
                        updated += 1
                    else:
                        unavailable += 1
            if alert:
                alerts += 1
                await _send_permission_alert(bot, *alert)
        await asyncio.sleep(0.05)
    return RefreshSummary(
        checked=len(ids),
        updated=updated,
        unavailable=unavailable,
        failed=failed,
        alerts=alerts,
    )


def _permission_alert_due(channel: Channel) -> bool:
    if channel.last_permission_alert_at is None:
        return True
    return utcnow() - channel.last_permission_alert_at >= timedelta(hours=24)


async def _send_permission_alert(bot: Bot, owner_id: int, title: str, issue: str | None) -> None:
    try:
        if issue:
            text = (
                f"⚠️ <b>{escape(title)}</b> necesita revisar permisos.\n\n"
                f"Faltan o cambiaron: <b>{escape(issue)}</b>.\n"
                "Abre Canales y grupos → Diagnóstico de permisos para ver la solución."
            )
        else:
            text = f"✅ Los permisos de <b>{escape(title)}</b> volvieron a estar disponibles."
        await bot.send_message(owner_id, text)
    except TelegramAPIError as exc:
        logger.info("Could not notify channel owner %s about permissions: %s", owner_id, exc)


async def channel_refresh_loop(bot: Bot, interval_hours: float) -> None:
    interval_seconds = interval_hours * 60 * 60
    while True:
        next_delay = interval_seconds
        try:
            summary = await refresh_channels(bot)
            logger.info(
                "Channel refresh finished: checked=%s updated=%s unavailable=%s failed=%s alerts=%s",
                summary.checked,
                summary.updated,
                summary.unavailable,
                summary.failed,
                summary.alerts,
            )
        except Exception:
            logger.exception("Unexpected error during periodic channel refresh")
            next_delay = min(interval_seconds, 5 * 60)
        await asyncio.sleep(next_delay)
