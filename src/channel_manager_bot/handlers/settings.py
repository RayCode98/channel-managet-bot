from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..database import SessionFactory
from ..keyboards import main_menu, settings_menu
from ..repository import get_workspace
from ..states import SettingsFlow

router = Router(name="settings")


async def render_settings(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
    welcome = workspace.welcome_text or "Sin mensaje configurado"
    await callback.message.edit_text(
        f"⚙️ <b>Automatizaciones</b>\n\n<b>Bienvenida actual:</b>\n{welcome[:800]}",
        reply_markup=settings_menu(workspace.auto_approve, workspace.welcome_enabled),
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


@router.callback_query(F.data == "settings:welcome_toggle")
async def toggle_welcome(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        if not workspace.welcome_text and not workspace.welcome_enabled:
            await callback.answer("Primero configura el mensaje de bienvenida.", show_alert=True)
            return
        workspace.welcome_enabled = not workspace.welcome_enabled
        await session.commit()
    await render_settings(callback)
    await callback.answer("Configuración actualizada")


@router.callback_query(F.data == "settings:welcome_text")
async def ask_welcome_text(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFlow.waiting_welcome_text)
    await callback.message.answer(
        "Envíame el mensaje de bienvenida. Se enviará antes de aprobar una solicitud.\n\n"
        "Puedes usar <code>{nombre}</code> y <code>{canal}</code>."
    )
    await callback.answer()


@router.message(SettingsFlow.waiting_welcome_text, F.text)
async def save_welcome_text(message: Message, state: FSMContext) -> None:
    text = message.html_text.strip()
    if len(text) > 3500:
        await message.answer("El mensaje es demasiado largo; usa máximo 3,500 caracteres.")
        return
    async with SessionFactory() as session:
        workspace = await get_workspace(session, message.from_user.id)
        workspace.welcome_text = text
        workspace.welcome_enabled = True
        await session.commit()
    await state.clear()
    await message.answer("✅ Bienvenida guardada y activada.", reply_markup=main_menu())
