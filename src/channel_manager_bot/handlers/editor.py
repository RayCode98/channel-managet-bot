"""Professional publication editor entry point.

The publication workflow is intentionally kept in ``publications.py`` so old
deep links continue to work.  This router provides the v0.14 workspace around
that workflow: a guided entry screen, draft recovery, and a short in-product
guide.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from ..database import SessionFactory
from ..keyboards import back_home, editor_menu
from ..models import Publication, PublicationStatus
from ..repository import get_workspace

router = Router(name="editor")


@router.callback_query(F.data == "editor:menu")
async def show_editor_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🧰 <b>Editor profesional</b>\n\n"
        "Crea publicaciones enriquecidas y trabaja en ellas por etapas: contenido, "
        "botones, destinos, vista previa, autoeliminación y programación.\n\n"
        "Los cambios se guardan automáticamente como borrador para que puedas continuar "
        "después o duplicar una publicación sin volver a empezar.",
        reply_markup=editor_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "editor:new")
async def start_editor_new(callback: CallbackQuery, state: FSMContext) -> None:
    # Keep this callback separate from pub:new so existing bookmarks and old
    # clients can still use the original entry point.
    await callback.message.edit_text(
        "🧰 <b>Editor profesional · nuevo borrador</b>\n\n"
        "Envíame el texto con formato o un archivo multimedia. Después podrás editar el "
        "contenido, agregar hasta 20 botones, elegir chats, previsualizar el resultado y "
        "publicar ahora o programarlo.\n\n"
        "Puedes enviar /cancel en cualquier momento.",
        reply_markup=back_home(),
    )
    from ..states import PublicationFlow
    await state.set_state(PublicationFlow.waiting_content)
    await callback.answer()


@router.callback_query(F.data == "editor:help")
async def editor_help(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "ℹ️ <b>Cómo trabajar con el editor</b>\n\n"
        "1. Envía el contenido con formato, foto, video, audio, voz o documento.\n"
        "2. Ajusta botones y elimínalos individualmente cuando sea necesario.\n"
        "3. Elige uno, varios o todos tus canales y grupos.\n"
        "4. Usa <b>Vista previa final</b> para comprobar firma, autocompletado y botones.\n"
        "5. Publica ahora, programa una fecha o crea una serie recurrente.\n\n"
        "La autoeliminación se aplica a cada destino y también a los reenvíos asociados.",
        reply_markup=editor_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "editor:drafts")
async def list_editor_drafts(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        rows = (
            list(
                await session.scalars(
                    select(Publication)
                    .where(
                        Publication.workspace_id == workspace.id,
                        Publication.status == PublicationStatus.draft,
                    )
                    .order_by(Publication.updated_at.desc(), Publication.created_at.desc())
                    .limit(30)
                )
            )
            if workspace
            else []
        )

    keyboard_rows = [
        [
            # Reuse the canonical publication editor callback so a draft
            # opened from this screen behaves exactly like one opened later.
            InlineKeyboardButton(
                text=f"📝 {(item.preview or 'Multimedia').replace(chr(10), ' ')[:55]}",
                callback_data=f"pub:edit:{item.id}",
            )
        ]
        for item in rows
    ]
    keyboard_rows.extend(editor_menu().inline_keyboard[-1:])
    if not rows:
        text = (
            "🗂 <b>Borradores</b>\n\n"
            "No tienes borradores pendientes. Crea una publicación para que el editor la "
            "guarde automáticamente mientras la configuras."
        )
    else:
        text = (
            "🗂 <b>Borradores</b>\n\n"
            "Selecciona uno para continuar exactamente donde lo dejaste."
        )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
    )
    await callback.answer()
