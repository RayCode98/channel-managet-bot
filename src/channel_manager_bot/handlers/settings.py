from aiogram import F, Router
from aiogram.types import CallbackQuery

from ..database import SessionFactory
from ..keyboards import settings_menu
from ..repository import get_workspace

router = Router(name="settings")


async def render_settings(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
    await callback.message.edit_text(
        "⚙️ <b>Automatizaciones</b>\n\n"
        "Administra el procesamiento automático de solicitudes.\n\n"
        "ℹ️ Bienvenidas, filtros y otras funciones por chat tienen sus propios botones "
        "en el menú principal.",
        reply_markup=settings_menu(workspace.auto_approve),
    )


@router.callback_query(F.data == "settings:show")
async def show_settings(callback: CallbackQuery) -> None:
    await render_settings(callback)
    await callback.answer()


@router.callback_query(F.data == "settings:auto_approve")
async def toggle_auto_approve(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        workspace.auto_approve = not workspace.auto_approve
        await session.commit()
    await render_settings(callback)
    await callback.answer("Configuración actualizada")
