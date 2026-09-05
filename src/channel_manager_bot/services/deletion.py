from datetime import UTC, datetime, timedelta

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest


async def delete_scheduled_delivery(
    bot,
    delivery,
    *,
    chat_id: int,
    now: datetime | None = None,
) -> bool:
    """Delete either a primary or relayed delivery using the same retry policy."""
    try:
        await bot.delete_message(chat_id, delivery.telegram_message_id)
        delivery.deleted_at = now or datetime.now(UTC)
        delivery.delete_error = None
        return True
    except TelegramBadRequest as exc:
        if "message to delete not found" in str(exc).lower():
            delivery.deleted_at = now or datetime.now(UTC)
            delivery.delete_error = None
            return True
        delivery.delete_attempts += 1
        delivery.delete_error = str(exc)[:2000]
        delivery.delete_at = (now or datetime.now(UTC)) + timedelta(minutes=10)
    except TelegramAPIError as exc:
        delivery.delete_attempts += 1
        delivery.delete_error = str(exc)[:2000]
        delivery.delete_at = (now or datetime.now(UTC)) + timedelta(minutes=10)
    return False
