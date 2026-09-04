from aiogram import F, Router
from aiogram.types import CallbackQuery

from ..database import SessionFactory
from ..keyboards import feature_channels_menu
from ..repository import get_active_channels, get_workspace

router = Router(name="feature_navigation")

FEATURES = {
    "welcome": ("👋", "Bienvenidas", "configurar la bienvenida"),
    "farewell": ("🚪", "Despedidas", "configurar la despedida"),
    "auto": ("🪄", "Autocompletado", "configurar el autocompletado"),
    "signature": ("✍️", "Firmas", "configurar la firma"),
}


@router.callback_query(F.data.startswith("feature:channels:"))
async def choose_feature_channel(callback: CallbackQuery) -> None:
    kind = callback.data.rsplit(":", 1)[1]
    feature = FEATURES.get(kind)
    if feature is None:
        await callback.answer("Opción inválida.", show_alert=True)
        return
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        channels = await get_active_channels(session, workspace.id) if workspace else []
    icon, title, action = feature
    text = f"{icon} <b>{title}</b>\n\nSelecciona el canal donde deseas {action}."
    if not channels:
        text += "\n\nTodavía no tienes canales activos. Agrégalos desde <b>Mis canales</b>."
    await callback.message.edit_text(
        text,
        reply_markup=feature_channels_menu(channels, kind),
    )
    await callback.answer()
