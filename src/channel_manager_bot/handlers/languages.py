from aiogram import F, Router
from aiogram.types import CallbackQuery

from ..database import SessionFactory
from ..i18n import LANGUAGE_BY_CODE, set_current_language, tr
from ..keyboards import language_menu
from ..repository import get_workspace

router = Router(name="languages")


@router.callback_query(F.data == "language:list")
async def show_languages(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        f"🌐 <b>{tr('language_title')}</b>\n\n{tr('language_prompt')}",
        reply_markup=language_menu(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("language:set:"))
async def change_language(callback: CallbackQuery) -> None:
    code = callback.data.rsplit(":", 1)[1]
    option = LANGUAGE_BY_CODE.get(code)
    if option is None:
        await callback.answer("Idioma no disponible.", show_alert=True)
        return
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        if workspace is None:
            await callback.answer("Cuenta no encontrada.", show_alert=True)
            return
        workspace.language_code = code
        await session.commit()
    set_current_language(code)
    await callback.message.edit_text(
        f"🌐 <b>{tr('language_title')}</b>\n\n✅ {tr('language_saved', language=option.name)}",
        reply_markup=language_menu(),
    )
    await callback.answer(tr("language_saved", language=option.name))
