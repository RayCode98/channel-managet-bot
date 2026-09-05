import logging
from datetime import timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..database import SessionFactory
from ..keyboards import publication_markup
from ..models import (
    Channel,
    ChannelStatus,
    Publication,
    PublicationButton,
    PublicationChannel,
    PublicationStatus,
    PublishedMessage,
)
from ..repository import utcnow
from .post_text import send_publication_to_channel
from .recurrence import next_recurrence_at

logger = logging.getLogger(__name__)


async def create_next_recurrence(
    session,
    publication: Publication,
    channel_ids: list[int],
) -> Publication | None:
    if not (
        publication.recurrence_series_id
        and publication.recurrence_interval_days
        and publication.recurrence_sequence
        and publication.scheduled_at
    ):
        return None

    next_sequence = publication.recurrence_sequence + 1
    existing = await session.scalar(
        select(Publication.id).where(
            Publication.recurrence_series_id == publication.recurrence_series_id,
            Publication.recurrence_sequence == next_sequence,
        )
    )
    if existing:
        return None

    next_publication = Publication(
        workspace_id=publication.workspace_id,
        creator_user_id=publication.creator_user_id,
        source_chat_id=publication.source_chat_id,
        source_message_id=publication.source_message_id,
        source_content_type=publication.source_content_type,
        source_text_html=publication.source_text_html,
        source_text_plain=publication.source_text_plain,
        source_entities_json=publication.source_entities_json,
        preview=publication.preview,
        status=PublicationStatus.scheduled,
        scheduled_at=next_recurrence_at(
            publication.scheduled_at,
            publication.recurrence_interval_days,
            now=utcnow(),
            timezone_name=publication.recurrence_timezone or "UTC",
        ),
        delete_after_minutes=publication.delete_after_minutes,
        recurrence_series_id=publication.recurrence_series_id,
        recurrence_interval_days=publication.recurrence_interval_days,
        recurrence_sequence=next_sequence,
        recurrence_timezone=publication.recurrence_timezone,
    )
    session.add(next_publication)
    await session.flush()
    for button in publication.buttons:
        session.add(
            PublicationButton(
                publication_id=next_publication.id,
                row_index=button.row_index,
                position=button.position,
                text=button.text,
                url=button.url,
            )
        )
    for channel_id in channel_ids:
        session.add(
            PublicationChannel(
                publication_id=next_publication.id,
                channel_id=channel_id,
            )
        )
    return next_publication


async def recover_stale_jobs() -> int:
    cutoff = utcnow() - timedelta(minutes=5)
    async with SessionFactory() as session:
        jobs = list(
            await session.scalars(
                select(Publication).where(
                    Publication.status == PublicationStatus.publishing,
                    Publication.claimed_at < cutoff,
                )
            )
        )
        for job in jobs:
            job.status = PublicationStatus.scheduled
            job.claimed_at = None
        await session.commit()
        return len(jobs)


async def claim_next_publication() -> Publication | None:
    async with SessionFactory() as session:
        async with session.begin():
            publication = await session.scalar(
                select(Publication)
                .where(
                    Publication.status == PublicationStatus.scheduled,
                    Publication.scheduled_at <= utcnow(),
                )
                .order_by(Publication.scheduled_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if publication is None:
                return None
            publication.status = PublicationStatus.publishing
            publication.claimed_at = utcnow()
            publication_id = publication.id
        return await session.scalar(
            select(Publication)
            .options(selectinload(Publication.buttons))
            .where(Publication.id == publication_id)
        )


async def publish_claimed(bot: Bot, publication_id) -> None:
    async with SessionFactory() as session:
        publication = await session.scalar(
            select(Publication)
            .options(selectinload(Publication.buttons))
            .where(Publication.id == publication_id)
        )
        if publication is None or publication.status != PublicationStatus.publishing:
            return
        channel_ids = list(
            await session.scalars(
                select(PublicationChannel.channel_id).where(
                    PublicationChannel.publication_id == publication.id
                )
            )
        )
        channels = (
            list(
                await session.scalars(
                    select(Channel).where(
                        Channel.telegram_chat_id.in_(channel_ids),
                        Channel.status == ChannelStatus.active,
                    )
                )
            )
            if channel_ids
            else []
        )
        markup = publication_markup(publication.buttons)
        successes = 0
        premium_fallbacks = 0

        for channel in channels:
            existing = await session.scalar(
                select(PublishedMessage).where(
                    PublishedMessage.publication_id == publication.id,
                    PublishedMessage.channel_id == channel.telegram_chat_id,
                )
            )
            if existing and existing.succeeded:
                successes += 1
                continue
            try:
                sent = await send_publication_to_channel(
                    bot=bot,
                    publication=publication,
                    channel=channel,
                    reply_markup=markup,
                )
                result = existing or PublishedMessage(
                    publication_id=publication.id, channel_id=channel.telegram_chat_id
                )
                result.telegram_message_id = sent.message_id
                result.succeeded = True
                result.error = None
                if sent.custom_emoji_fallback:
                    premium_fallbacks += 1
                if publication.delete_after_minutes:
                    result.delete_at = utcnow() + timedelta(
                        minutes=publication.delete_after_minutes
                    )
                if existing is None:
                    session.add(result)
                successes += 1
            except TelegramAPIError as exc:
                logger.warning(
                    "Could not publish %s to %s: %s", publication.id, channel.telegram_chat_id, exc
                )
                result = existing or PublishedMessage(
                    publication_id=publication.id, channel_id=channel.telegram_chat_id
                )
                result.succeeded = False
                result.error = str(exc)[:2000]
                if existing is None:
                    session.add(result)
            await session.commit()

        if successes == len(channels) and channels:
            publication.status = PublicationStatus.published
        elif successes:
            publication.status = PublicationStatus.partial
        else:
            publication.status = PublicationStatus.failed
        publication.claimed_at = None
        next_publication = await create_next_recurrence(session, publication, channel_ids)
        await session.commit()

        try:
            next_text = "\n🔁 La siguiente repetición quedó programada." if next_publication else ""
            premium_text = (
                "\n⚠️ Telegram rechazó los emojis premium en "
                f"<b>{premium_fallbacks}</b> destino(s). La publicación se entregó con su "
                "emoji normal de respaldo."
                if premium_fallbacks
                else ""
            )
            await bot.send_message(
                publication.creator_user_id,
                f"📬 Publicación terminada: <b>{successes}/{len(channels)}</b> entregas exitosas."
                f"{next_text}{premium_text}",
            )
        except TelegramAPIError as exc:
            logger.info("Could not notify publication creator: %s", exc)


async def delete_due_messages(bot: Bot, batch_size: int = 20) -> int:
    async with SessionFactory() as session:
        messages = list(
            await session.scalars(
                select(PublishedMessage)
                .where(
                    PublishedMessage.succeeded.is_(True),
                    PublishedMessage.telegram_message_id.is_not(None),
                    PublishedMessage.delete_at.is_not(None),
                    PublishedMessage.delete_at <= utcnow(),
                    PublishedMessage.deleted_at.is_(None),
                    PublishedMessage.delete_attempts < 5,
                )
                .order_by(PublishedMessage.delete_at)
                .limit(batch_size)
            )
        )
        deleted = 0
        for message in messages:
            try:
                await bot.delete_message(message.channel_id, message.telegram_message_id)
                message.deleted_at = utcnow()
                message.delete_error = None
                deleted += 1
            except TelegramBadRequest as exc:
                if "message to delete not found" in str(exc).lower():
                    message.deleted_at = utcnow()
                    message.delete_error = None
                    deleted += 1
                else:
                    message.delete_attempts += 1
                    message.delete_error = str(exc)[:2000]
                    message.delete_at = utcnow() + timedelta(minutes=10)
            except TelegramAPIError as exc:
                message.delete_attempts += 1
                message.delete_error = str(exc)[:2000]
                message.delete_at = utcnow() + timedelta(minutes=10)
            await session.commit()
        return deleted
