import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from sqlalchemy import func, or_, select

from ..models import Channel, ChannelStatus, JoinRequestEvent
from ..repository import utcnow

logger = logging.getLogger(__name__)

APPROVAL_BATCH_LIMIT = 200
APPROVAL_INTERVALS = {1, 6, 12, 24, 48}
PENDING_APPROVAL_OUTCOMES = {
    "pending",
    "pending_manual",
    "pending_scheduled",
    "approval_retry",
}


@dataclass(frozen=True)
class ApprovalSummary:
    claimed: int = 0
    approved: int = 0
    unavailable: int = 0
    failed: int = 0


def next_scheduled_run(scheduled_for, now, interval_hours: int):
    if interval_hours not in APPROVAL_INTERVALS:
        raise ValueError("Intervalo de aprobación no permitido.")
    candidate = scheduled_for or now
    step = timedelta(hours=interval_hours)
    while candidate <= now:
        candidate += step
    return candidate


async def pending_join_count(session, channel_id: int) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(JoinRequestEvent)
            .where(
                JoinRequestEvent.channel_id == channel_id,
                JoinRequestEvent.approved.is_(False),
                JoinRequestEvent.outcome.in_(PENDING_APPROVAL_OUTCOMES | {"approval_processing"}),
            )
        )
        or 0
    )


async def process_pending_join_requests(
    bot: Bot,
    channel_id: int,
    *,
    limit: int = APPROVAL_BATCH_LIMIT,
) -> ApprovalSummary:
    from ..database import SessionFactory

    safe_limit = max(1, min(limit, APPROVAL_BATCH_LIMIT))
    now = utcnow()
    stale_claim = now - timedelta(minutes=10)
    async with SessionFactory() as session:
        events = list(
            await session.scalars(
                select(JoinRequestEvent)
                .where(
                    JoinRequestEvent.channel_id == channel_id,
                    JoinRequestEvent.approved.is_(False),
                    JoinRequestEvent.outcome.in_(PENDING_APPROVAL_OUTCOMES),
                    or_(
                        JoinRequestEvent.approval_claimed_at.is_(None),
                        JoinRequestEvent.approval_claimed_at < stale_claim,
                    ),
                )
                .order_by(JoinRequestEvent.created_at, JoinRequestEvent.id)
                .limit(safe_limit)
                .with_for_update(skip_locked=True)
            )
        )
        for event in events:
            event.outcome = "approval_processing"
            event.approval_claimed_at = now
            event.approval_attempts += 1
            event.approval_error = None
        await session.commit()
        event_ids = [event.id for event in events]

    approved = unavailable = failed = 0
    for event_id in event_ids:
        async with SessionFactory() as session:
            event = await session.get(JoinRequestEvent, event_id)
            if event is None or event.outcome != "approval_processing":
                continue
            try:
                await bot.approve_chat_join_request(event.channel_id, event.user_id)
            except TelegramBadRequest as exc:
                event.outcome = "request_unavailable"
                event.approval_error = str(exc)[:2000]
                event.approval_claimed_at = None
                unavailable += 1
            except TelegramAPIError as exc:
                event.outcome = "approval_retry"
                event.approval_error = str(exc)[:2000]
                event.approval_claimed_at = None
                failed += 1
            else:
                event.approved = True
                event.approved_at = utcnow()
                event.outcome = "approved_batch"
                event.approval_claimed_at = None
                approved += 1
            await session.commit()
        await asyncio.sleep(0.03)

    return ApprovalSummary(
        claimed=len(event_ids),
        approved=approved,
        unavailable=unavailable,
        failed=failed,
    )


async def claim_due_approval_channel() -> int | None:
    from ..database import SessionFactory

    now = utcnow()
    async with SessionFactory() as session:
        channel = await session.scalar(
            select(Channel)
            .where(
                Channel.status == ChannelStatus.active,
                Channel.can_invite_users.is_(True),
                Channel.join_approval_mode == "scheduled",
                Channel.join_approval_interval_hours.in_(APPROVAL_INTERVALS),
                Channel.join_approval_next_run_at.is_not(None),
                Channel.join_approval_next_run_at <= now,
            )
            .order_by(Channel.join_approval_next_run_at, Channel.telegram_chat_id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if channel is None:
            return None
        channel.join_approval_last_run_at = now
        channel.join_approval_next_run_at = next_scheduled_run(
            channel.join_approval_next_run_at,
            now,
            channel.join_approval_interval_hours,
        )
        channel_id = channel.telegram_chat_id
        await session.commit()
        return channel_id


async def scheduled_join_approval_loop(bot: Bot, poll_seconds: float = 60) -> None:
    while True:
        try:
            processed_any = False
            while channel_id := await claim_due_approval_channel():
                processed_any = True
                summary = await process_pending_join_requests(bot, channel_id)
                logger.info(
                    "Scheduled join approvals for %s: claimed=%s approved=%s "
                    "unavailable=%s failed=%s",
                    channel_id,
                    summary.claimed,
                    summary.approved,
                    summary.unavailable,
                    summary.failed,
                )
            await asyncio.sleep(1 if processed_any else poll_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Unexpected error in scheduled join approval loop")
            await asyncio.sleep(min(poll_seconds, 60))
