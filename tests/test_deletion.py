from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import DeleteMessage

from channel_manager_bot.services.deletion import delete_scheduled_delivery


class DeletingBot:
    def __init__(self, error: TelegramBadRequest | None = None):
        self.error = error
        self.calls = []

    async def delete_message(self, chat_id, message_id):
        self.calls.append((chat_id, message_id))
        if self.error:
            raise self.error


def delivery():
    return SimpleNamespace(
        telegram_message_id=91,
        deleted_at=None,
        delete_attempts=0,
        delete_error=None,
        delete_at=None,
    )


async def test_scheduled_delivery_deletes_primary_or_relay_message():
    bot = DeletingBot()
    item = delivery()
    now = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)

    deleted = await delete_scheduled_delivery(bot, item, chat_id=-1002, now=now)

    assert deleted is True
    assert bot.calls == [(-1002, 91)]
    assert item.deleted_at == now
    assert item.delete_error is None


async def test_scheduled_delivery_retries_a_rejected_deletion():
    method = DeleteMessage(chat_id=-1002, message_id=91)
    bot = DeletingBot(TelegramBadRequest(method=method, message="not enough rights"))
    item = delivery()
    now = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)

    deleted = await delete_scheduled_delivery(bot, item, chat_id=-1002, now=now)

    assert deleted is False
    assert item.delete_attempts == 1
    assert "not enough rights" in item.delete_error
    assert item.delete_at == now + timedelta(minutes=10)
