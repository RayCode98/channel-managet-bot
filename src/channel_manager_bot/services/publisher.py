import logging
from datetime import timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..database import SessionFactory
from ..keyboards import publication_markup
from ..models import (
    Channel,
    ChannelStatus,
    Publication,
    PublicationChannel,
    PublicationStatus,
    PublishedMessage,
)
from ..repository import utcnow

logger = logging.getLogger(__name__)


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
                sent = await bot.copy_message(
                    chat_id=channel.telegram_chat_id,
                    from_chat_id=publication.source_chat_id,
                    message_id=publication.source_message_id,
                    reply_markup=markup,
                )
                result = existing or PublishedMessage(
                    publication_id=publication.id, channel_id=channel.telegram_chat_id
                )
                result.telegram_message_id = sent.message_id
                result.succeeded = True
                result.error = None
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
        await session.commit()

        try:
            await bot.send_message(
                publication.creator_user_id,
                f"📬 Publicación terminada: <b>{successes}/{len(channels)}</b> entregas exitosas.",
            )
        except TelegramAPIError as exc:
            logger.info("Could not notify publication creator: %s", exc)
