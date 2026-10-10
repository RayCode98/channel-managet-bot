"""Queries shared by the v0.15 growth and statistics screens."""

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func, select

from ..models import (
    Channel,
    ChannelMetricSnapshot,
    ChannelStatus,
    JoinRequestEvent,
    Publication,
    PublishedMessage,
    RelayDelivery,
    RelayRule,
)
from ..services.member_approvals import (
    REAL_PENDING_REQUEST_OUTCOMES,
    latest_request_event_condition,
)


@dataclass(frozen=True)
class ChannelGrowth:
    channel_id: int
    title: str
    current: int | None
    baseline: int | None
    change: int | None
    percent: float | None


@dataclass(frozen=True)
class PublicationMetrics:
    deliveries: int
    successful: int
    failed: int
    publications: int
    success_rate: float


@dataclass(frozen=True)
class MemberMetrics:
    received: int
    approved: int
    active_pending: int


def period_start(days: int, now: datetime | None = None) -> datetime:
    safe_days = max(1, min(days, 365))
    base = now or datetime.now(UTC)
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)
    return base - timedelta(days=safe_days)


async def channel_growth(
    session,
    channel: Channel,
    days: int = 30,
    *,
    now: datetime | None = None,
) -> ChannelGrowth:
    start = period_start(days, now)
    baseline = await session.scalar(
        select(ChannelMetricSnapshot.member_count)
        .where(
            ChannelMetricSnapshot.channel_id == channel.telegram_chat_id,
            ChannelMetricSnapshot.captured_at <= start,
        )
        .order_by(ChannelMetricSnapshot.captured_at.desc())
        .limit(1)
    )
    if baseline is None:
        baseline = await session.scalar(
            select(ChannelMetricSnapshot.member_count)
            .where(
                ChannelMetricSnapshot.channel_id == channel.telegram_chat_id,
                ChannelMetricSnapshot.captured_at >= start,
            )
            .order_by(ChannelMetricSnapshot.captured_at)
            .limit(1)
        )
    current = channel.member_count
    change = current - baseline if current is not None and baseline is not None else None
    percent = (change / baseline * 100) if change is not None and baseline else None
    return ChannelGrowth(
        channel_id=channel.telegram_chat_id,
        title=channel.title,
        current=current,
        baseline=baseline,
        change=change,
        percent=percent,
    )


async def workspace_growth(
    session,
    workspace_id,
    days: int = 30,
    *,
    now: datetime | None = None,
) -> list[ChannelGrowth]:
    channels = list(
        await session.scalars(
            select(Channel)
            .where(
                Channel.workspace_id == workspace_id,
                Channel.status == ChannelStatus.active,
            )
            .order_by(Channel.title)
        )
    )
    return [await channel_growth(session, channel, days, now=now) for channel in channels]


async def publication_metrics(
    session,
    workspace_id,
    days: int = 30,
    *,
    now: datetime | None = None,
) -> PublicationMetrics:
    start = period_start(days, now)
    deliveries = await session.scalar(
        select(func.count())
        .select_from(PublishedMessage)
        .join(Publication, Publication.id == PublishedMessage.publication_id)
        .where(Publication.workspace_id == workspace_id, PublishedMessage.sent_at >= start)
    )
    successful = await session.scalar(
        select(func.count())
        .select_from(PublishedMessage)
        .join(Publication, Publication.id == PublishedMessage.publication_id)
        .where(
            Publication.workspace_id == workspace_id,
            PublishedMessage.sent_at >= start,
            PublishedMessage.succeeded.is_(True),
        )
    )
    failed = await session.scalar(
        select(func.count())
        .select_from(PublishedMessage)
        .join(Publication, Publication.id == PublishedMessage.publication_id)
        .where(
            Publication.workspace_id == workspace_id,
            PublishedMessage.sent_at >= start,
            PublishedMessage.succeeded.is_(False),
        )
    )
    publications = await session.scalar(
        select(func.count(func.distinct(PublishedMessage.publication_id)))
        .select_from(PublishedMessage)
        .join(Publication, Publication.id == PublishedMessage.publication_id)
        .where(
            Publication.workspace_id == workspace_id,
            PublishedMessage.sent_at >= start,
            PublishedMessage.succeeded.is_(True),
        )
    )
    total = deliveries or 0
    successful_count = successful or 0
    return PublicationMetrics(
        deliveries=total,
        successful=successful_count,
        failed=failed or 0,
        publications=publications or 0,
        success_rate=(successful_count / total * 100) if total else 0.0,
    )


async def member_metrics(
    session,
    workspace_id,
    days: int = 30,
    *,
    now: datetime | None = None,
) -> MemberMetrics:
    start = period_start(days, now)
    received_requesters = (
        select(JoinRequestEvent.channel_id, JoinRequestEvent.user_id)
        .select_from(JoinRequestEvent)
        .join(Channel, Channel.telegram_chat_id == JoinRequestEvent.channel_id)
        .where(
            Channel.workspace_id == workspace_id,
            JoinRequestEvent.created_at >= start,
        )
        .distinct()
        .subquery()
    )
    received = await session.scalar(select(func.count()).select_from(received_requesters))
    approved_requesters = (
        select(JoinRequestEvent.channel_id, JoinRequestEvent.user_id)
        .select_from(JoinRequestEvent)
        .join(Channel, Channel.telegram_chat_id == JoinRequestEvent.channel_id)
        .where(
            Channel.workspace_id == workspace_id,
            JoinRequestEvent.approved.is_(True),
            JoinRequestEvent.approved_at >= start,
        )
        .distinct()
        .subquery()
    )
    approved = await session.scalar(select(func.count()).select_from(approved_requesters))
    pending_requesters = (
        select(JoinRequestEvent.channel_id, JoinRequestEvent.user_id)
        .select_from(JoinRequestEvent)
        .join(Channel, Channel.telegram_chat_id == JoinRequestEvent.channel_id)
        .where(
            Channel.workspace_id == workspace_id,
            JoinRequestEvent.approved.is_(False),
            JoinRequestEvent.outcome.in_(REAL_PENDING_REQUEST_OUTCOMES),
            latest_request_event_condition(),
        )
        .distinct()
        .subquery()
    )
    active_pending = await session.scalar(select(func.count()).select_from(pending_requesters))
    return MemberMetrics(
        received=received or 0,
        approved=approved or 0,
        active_pending=active_pending or 0,
    )


async def relay_metrics(
    session,
    workspace_id,
    days: int = 30,
    *,
    now: datetime | None = None,
) -> tuple[int, int]:
    start = period_start(days, now)
    successful = await session.scalar(
        select(func.count())
        .select_from(RelayDelivery)
        .join(RelayRule, RelayRule.id == RelayDelivery.relay_rule_id)
        .where(
            RelayRule.workspace_id == workspace_id,
            RelayDelivery.created_at >= start,
            RelayDelivery.succeeded.is_(True),
        )
    )
    failed = await session.scalar(
        select(func.count())
        .select_from(RelayDelivery)
        .join(RelayRule, RelayRule.id == RelayDelivery.relay_rule_id)
        .where(
            RelayRule.workspace_id == workspace_id,
            RelayDelivery.created_at >= start,
            RelayDelivery.succeeded.is_(False),
        )
    )
    return successful or 0, failed or 0


async def best_posting_hours(
    session,
    workspace_id,
    timezone_name: str,
    days: int = 30,
    *,
    now: datetime | None = None,
) -> list[tuple[int, int]]:
    start = period_start(days, now)
    rows = list(
        await session.scalars(
            select(PublishedMessage.sent_at)
            .join(Publication, Publication.id == PublishedMessage.publication_id)
            .where(
                Publication.workspace_id == workspace_id,
                PublishedMessage.succeeded.is_(True),
                PublishedMessage.sent_at >= start,
            )
        )
    )
    timezone = ZoneInfo(timezone_name)
    counts = Counter(item.astimezone(timezone).hour for item in rows if item is not None)
    return counts.most_common(5)


async def top_publications(
    session,
    workspace_id,
    days: int = 30,
    *,
    now: datetime | None = None,
) -> list[tuple[str, int]]:
    start = period_start(days, now)
    rows = await session.execute(
        select(
            Publication.preview,
            func.count(PublishedMessage.id).label("deliveries"),
        )
        .join(PublishedMessage, PublishedMessage.publication_id == Publication.id)
        .where(
            Publication.workspace_id == workspace_id,
            PublishedMessage.succeeded.is_(True),
            PublishedMessage.sent_at >= start,
        )
        .group_by(Publication.id, Publication.preview)
        .order_by(desc("deliveries"))
        .limit(5)
    )
    return [(preview or "Multimedia", int(deliveries)) for preview, deliveries in rows]


async def workspace_summary(
    session,
    workspace_id,
    days: int = 30,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    growth = await workspace_growth(session, workspace_id, days, now=now)
    publications = await publication_metrics(session, workspace_id, days, now=now)
    members = await member_metrics(session, workspace_id, days, now=now)
    relay_successful, relay_failed = await relay_metrics(session, workspace_id, days, now=now)
    return {
        "growth": growth,
        "publications": publications,
        "members": members,
        "relay_successful": relay_successful,
        "relay_failed": relay_failed,
    }
