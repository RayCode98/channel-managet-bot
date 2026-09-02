import uuid
from html import escape

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..database import SessionFactory
from ..keyboards import (
    back_home,
    channel_selector,
    template_detail_menu,
    templates_menu,
    ttl_label,
    ttl_menu,
)
from ..models import ContentTemplate, Publication, PublicationButton, TemplateButton
from ..repository import get_active_channels, get_workspace
from ..states import PublicationFlow, TemplateFlow

router = Router(name="templates")


async def owned_template(session, template_id: str, user_id: int) -> ContentTemplate | None:
    try:
        parsed = uuid.UUID(template_id)
    except ValueError:
        return None
    workspace = await get_workspace(session, user_id)
    if workspace is None:
        return None
    return await session.scalar(
        select(ContentTemplate)
        .options(selectinload(ContentTemplate.buttons))
        .where(ContentTemplate.id == parsed, ContentTemplate.workspace_id == workspace.id)
    )


async def show_template(callback: CallbackQuery, template: ContentTemplate) -> None:
    preview = escape((template.preview or "Contenido multimedia").replace("\n", " ")[:200])
    await callback.message.edit_text(
        f"🧩 <b>{escape(template.name)}</b>\n\n"
        f"📝 {preview}\n"
        f"🔗 <b>Botones:</b> {len(template.buttons)}\n"
        f"🗑 <b>Autoeliminación:</b> {ttl_label(template.delete_after_minutes)}",
        reply_markup=template_detail_menu(
            template.id, len(template.buttons), template.delete_after_minutes
        ),
    )


@router.callback_query(F.data == "tpl:list")
async def list_templates(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        templates = list(
            await session.scalars(
                select(ContentTemplate)
                .where(ContentTemplate.workspace_id == workspace.id)
                .order_by(ContentTemplate.updated_at.desc())
                .limit(30)
            )
        )
    rows = [
        [
            InlineKeyboardButton(
                text=f"🧩 {template.name}"[:64], callback_data=f"tpl:open:{template.id}"
            )
        ]
        for template in templates
    ]
    rows.extend(templates_menu().inline_keyboard)
    text = "🧩 <b>Plantillas</b>\n\nSelecciona una plantilla para usarla o editar sus opciones."
    if not templates:
        text += "\n\nTodavía no has creado ninguna."
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "tpl:new")
async def new_template(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TemplateFlow.waiting_name)
    await callback.message.edit_text(
        "🧩 <b>Nueva plantilla</b>\n\nEscribe un nombre que te ayude a reconocerla, por ejemplo: <i>Promoción de fin de semana</i>.",
        reply_markup=back_home(),
    )
    await callback.answer()


@router.message(TemplateFlow.waiting_name, F.text)
async def receive_template_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not 1 <= len(name) <= 100:
        await message.answer("El nombre debe tener entre 1 y 100 caracteres.")
        return
    await state.update_data(template_name=name)
    await state.set_state(TemplateFlow.waiting_content)
    await message.answer(
        "Ahora envía el contenido de la plantilla: texto enriquecido, foto, video, animación, audio o documento."
    )


@router.message(TemplateFlow.waiting_content, F.chat.type == ChatType.PRIVATE)
async def receive_template_content(message: Message, state: FSMContext) -> None:
    if not any(
        [
            message.text,
            message.photo,
            message.video,
            message.animation,
            message.audio,
            message.document,
            message.voice,
        ]
    ):
        await message.answer("Ese contenido no es compatible. Envía texto o contenido multimedia.")
        return
    data = await state.get_data()
    async with SessionFactory() as session:
        workspace = await get_workspace(session, message.from_user.id)
        template = ContentTemplate(
            workspace_id=workspace.id,
            creator_user_id=message.from_user.id,
            name=data["template_name"],
            source_chat_id=message.chat.id,
            source_message_id=message.message_id,
            preview=(message.text or message.caption or "Contenido multimedia")[:500],
        )
        session.add(template)
        await session.commit()
    await state.clear()
    await message.answer(
        "✅ Plantilla creada. Ya puedes añadir botones, autoeliminación o utilizarla.",
        reply_markup=template_detail_menu(template.id, 0, None),
    )


@router.callback_query(F.data.startswith("tpl:open:"))
async def open_template(callback: CallbackQuery) -> None:
    template_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        template = await owned_template(session, template_id, callback.from_user.id)
    if template is None:
        await callback.answer("Plantilla no encontrada.", show_alert=True)
        return
    await show_template(callback, template)
    await callback.answer()


@router.callback_query(F.data.startswith("tpl:button:"))
async def ask_template_button(callback: CallbackQuery, state: FSMContext) -> None:
    template_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        template = await owned_template(session, template_id, callback.from_user.id)
    if template is None:
        await callback.answer("Plantilla no encontrada.", show_alert=True)
        return
    await state.set_state(TemplateFlow.waiting_button_text)
    await state.update_data(template_id=template_id)
    await callback.message.answer("Escribe el texto del botón (máximo 64 caracteres):")
    await callback.answer()


@router.message(TemplateFlow.waiting_button_text, F.text)
async def receive_template_button_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not 1 <= len(text) <= 64:
        await message.answer("El texto debe tener entre 1 y 64 caracteres.")
        return
    await state.update_data(button_text=text)
    await state.set_state(TemplateFlow.waiting_button_url)
    await message.answer("Envía el enlace completo del botón:")


@router.message(TemplateFlow.waiting_button_url, F.text)
async def receive_template_button_url(message: Message, state: FSMContext) -> None:
    url = message.text.strip()
    if not url.startswith(("https://", "http://", "tg://")):
        await message.answer("El enlace debe comenzar con https://, http:// o tg://")
        return
    data = await state.get_data()
    async with SessionFactory() as session:
        template = await owned_template(session, data["template_id"], message.from_user.id)
        if template is None:
            await state.clear()
            await message.answer("Plantilla no encontrada.")
            return
        count = await session.scalar(
            select(func.count())
            .select_from(TemplateButton)
            .where(TemplateButton.template_id == template.id)
        )
        if (count or 0) >= 20:
            await message.answer("La plantilla ya alcanzó el máximo de 20 botones.")
            return
        session.add(
            TemplateButton(
                template_id=template.id,
                row_index=count or 0,
                position=0,
                text=data["button_text"],
                url=url,
            )
        )
        await session.commit()
        button_count = (count or 0) + 1
    await state.clear()
    await message.answer(
        "✅ Botón añadido a la plantilla.",
        reply_markup=template_detail_menu(template.id, button_count, template.delete_after_minutes),
    )


@router.callback_query(F.data.startswith("tpl:ttl:"))
async def choose_template_ttl(callback: CallbackQuery) -> None:
    template_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        template = await owned_template(session, template_id, callback.from_user.id)
    if template is None:
        await callback.answer("Plantilla no encontrada.", show_alert=True)
        return
    await callback.message.edit_text(
        "🗑 <b>Autoeliminación de la plantilla</b>\n\n"
        "El tiempo comenzará a contar cuando cada publicación sea enviada.",
        reply_markup=ttl_menu("tpl", template.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tpl:setttl:"))
async def set_template_ttl(callback: CallbackQuery) -> None:
    _, _, template_id, minutes_text = callback.data.split(":", 3)
    minutes = int(minutes_text)
    async with SessionFactory() as session:
        template = await owned_template(session, template_id, callback.from_user.id)
        if template is None:
            await callback.answer("Plantilla no encontrada.", show_alert=True)
            return
        template.delete_after_minutes = minutes or None
        await session.commit()
    await show_template(callback, template)
    await callback.answer("Autoeliminación actualizada")


@router.callback_query(F.data.startswith("tpl:use:"))
async def use_template(callback: CallbackQuery, state: FSMContext) -> None:
    template_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        template = await owned_template(session, template_id, callback.from_user.id)
        if template is None:
            await callback.answer("Plantilla no encontrada.", show_alert=True)
            return
        channels = await get_active_channels(session, template.workspace_id)
        if not channels:
            await callback.answer("Primero conecta al menos un canal.", show_alert=True)
            return
        publication = Publication(
            workspace_id=template.workspace_id,
            creator_user_id=callback.from_user.id,
            source_chat_id=template.source_chat_id,
            source_message_id=template.source_message_id,
            preview=template.preview,
            delete_after_minutes=template.delete_after_minutes,
        )
        session.add(publication)
        await session.flush()
        for button in template.buttons:
            session.add(
                PublicationButton(
                    publication_id=publication.id,
                    row_index=button.row_index,
                    position=button.position,
                    text=button.text,
                    url=button.url,
                )
            )
        await session.commit()
    await state.set_state(PublicationFlow.selecting_channels)
    await callback.message.edit_text(
        f"🚀 <b>Usar plantilla: {escape(template.name)}</b>\n\nElige los canales de destino.",
        reply_markup=channel_selector(publication.id, channels, set()),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tpl:delete:"))
async def ask_delete_template(callback: CallbackQuery) -> None:
    template_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        template = await owned_template(session, template_id, callback.from_user.id)
    if template is None:
        await callback.answer("Plantilla no encontrada.", show_alert=True)
        return
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Sí, eliminar", callback_data=f"tpl:confirmdelete:{template.id}"
                )
            ],
            [InlineKeyboardButton(text="Cancelar", callback_data=f"tpl:open:{template.id}")],
        ]
    )
    await callback.message.edit_text(
        f"¿Eliminar definitivamente la plantilla <b>{escape(template.name)}</b>?",
        reply_markup=markup,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tpl:confirmdelete:"))
async def delete_template(callback: CallbackQuery) -> None:
    template_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        template = await owned_template(session, template_id, callback.from_user.id)
        if template is None:
            await callback.answer("Plantilla no encontrada.", show_alert=True)
            return
        await session.delete(template)
        await session.commit()
    await callback.message.edit_text("✅ Plantilla eliminada.", reply_markup=templates_menu())
    await callback.answer()
