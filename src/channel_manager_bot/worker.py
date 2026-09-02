import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from redis.asyncio import Redis

from .config import get_settings
from .services.publisher import claim_next_publication, publish_claimed, recover_stale_jobs


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    await recover_stale_jobs()
    try:
        while True:
            await redis.set("worker:heartbeat", "ok", ex=15)
            publication = await claim_next_publication()
            if publication:
                await publish_claimed(bot, publication.id)
                continue
            await asyncio.sleep(settings.worker_poll_seconds)
    finally:
        await redis.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
