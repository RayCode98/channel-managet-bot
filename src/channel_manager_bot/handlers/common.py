import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ErrorEvent, Message
from redis.asyncio import Redis
from sqlalchemy import text

from ..config import get_settings
from ..database import SessionFactory
from ..keyboards import main_menu
from ..repository import ensure_user_workspace

router = Router(name="common")
logger = logging.getLogger(__name__)


@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with SessionFactory() as session:
        workspace = await ensure_user_workspace(session, message.from_user)
    await message.answer(
        f"👋 <b>Bienvenido a {workspace.name}</b>\n\n"
        "Desde aquí puedes administrar canales, preparar contenido y revisar resultados.",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "home")
async def home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "🏠 <b>Panel de administración</b>\n\n¿Qué deseas hacer?",
        reply_markup=main_menu(),
    )
    await callback.answer()


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Operación cancelada.", reply_markup=main_menu())


@router.message(Command("health"))
async def health(message: Message, redis: Redis, bot: Bot) -> None:
    if message.from_user.id not in get_settings().platform_admin_ids:
        return
    async with SessionFactory() as session:
        await session.execute(text("SELECT 1"))
    heartbeat = await redis.get("worker:heartbeat")
    me = await bot.get_me()
    status = "activo" if heartbeat else "sin señal"
    await message.answer(f"✅ Bot: @{me.username}\n✅ Base de datos\n⚙️ Worker: {status}")


@router.error()
async def global_error(event: ErrorEvent) -> bool:
    logger.exception("Unhandled update error", exc_info=event.exception)
    return True
