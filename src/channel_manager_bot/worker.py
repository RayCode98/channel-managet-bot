import asyncio
import logging
from contextlib import suppress

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from redis.asyncio import Redis

from .config import get_settings
from .services.channel_sync import channel_refresh_loop
from .services.member_approvals import scheduled_join_approval_loop
from .services.publisher import (
    claim_next_publication,
    delete_due_messages,
    publish_claimed,
    recover_stale_jobs,
)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    await recover_stale_jobs()
    refresh_task = asyncio.create_task(
        channel_refresh_loop(bot, settings.channel_refresh_hours),
        name="channel-refresh",
    )
    approval_task = asyncio.create_task(
        scheduled_join_approval_loop(bot),
        name="scheduled-join-approvals",
    )
    try:
        while True:
            await redis.set("worker:heartbeat", "ok", ex=15)
            await delete_due_messages(bot)
            publication = await claim_next_publication()
            if publication:
                await publish_claimed(bot, publication.id)
                continue
            await asyncio.sleep(settings.worker_poll_seconds)
    finally:
        refresh_task.cancel()
        approval_task.cancel()
        with suppress(asyncio.CancelledError):
            await refresh_task
        with suppress(asyncio.CancelledError):
            await approval_task
        await redis.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
