import logging
import uuid
from html import escape

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..database import SessionFactory
from ..keyboards import (
    back_home,
    channel_selector,
    publication_markup,
    template_buttons_menu,
    template_detail_menu,
    templates_menu,
    ttl_label,
    ttl_menu,
)
from ..models import ContentTemplate, Publication, PublicationButton, TemplateButton
from ..repository import get_active_channels, get_workspace
from ..services.post_text import publication_content_type, publication_text_html
from ..states import PublicationFlow, TemplateFlow

router = Router(name="templates")
logger = logging.getLogger(__name__)


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
        f"🗑 <b>Autoeliminación:</b> {ttl_label(template.delete_after_minutes)}\n\n"
        "🔁 La recurrencia se elige después de seleccionar los canales.",
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
            source_content_type=publication_content_type(message),
            source_text_html=publication_text_html(message),
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


@router.callback_query(F.data.startswith("tpl:preview:"))
async def preview_template(callback: CallbackQuery) -> None:
    template_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        template = await owned_template(session, template_id, callback.from_user.id)
    if template is None:
        await callback.answer("Plantilla no encontrada.", show_alert=True)
        return
    try:
        await callback.bot.copy_message(
            chat_id=callback.from_user.id,
            from_chat_id=template.source_chat_id,
            message_id=template.source_message_id,
            reply_markup=publication_markup(template.buttons),
        )
    except TelegramAPIError as exc:
        logger.warning("Could not preview template %s: %s", template.id, exc)
        await callback.answer("Telegram no pudo generar la vista previa.", show_alert=True)
        return
    await callback.answer("Vista previa enviada")


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


@router.callback_query(F.data.startswith("tpl:buttons:"))
async def manage_template_buttons(callback: CallbackQuery) -> None:
    template_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        template = await owned_template(session, template_id, callback.from_user.id)
    if template is None:
        await callback.answer("Plantilla no encontrada.", show_alert=True)
        return
    if not template.buttons:
        await callback.answer("Esta plantilla no tiene botones.", show_alert=True)
        return
    await callback.message.edit_text(
        f"🧹 <b>Botones de {escape(template.name)}</b>\n\n"
        "Pulsa el botón que deseas eliminar. Los demás permanecerán sin cambios.",
        reply_markup=template_buttons_menu(template.id, template.buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tpl:bdel:"))
async def delete_template_button(callback: CallbackQuery) -> None:
    try:
        button_id = uuid.UUID(callback.data.rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("Botón inválido.", show_alert=True)
        return
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        button = await session.scalar(
            select(TemplateButton)
            .join(ContentTemplate, ContentTemplate.id == TemplateButton.template_id)
            .where(
                TemplateButton.id == button_id,
                ContentTemplate.workspace_id == workspace.id,
            )
        )
        if button is None:
            await callback.answer("Botón no encontrado.", show_alert=True)
            return
        template_id = button.template_id
        await session.delete(button)
        await session.flush()
        remaining = list(
            await session.scalars(
                select(TemplateButton)
                .where(TemplateButton.template_id == template_id)
                .order_by(TemplateButton.row_index, TemplateButton.position)
            )
        )
        for row_index, remaining_button in enumerate(remaining):
            remaining_button.row_index = row_index
            remaining_button.position = 0
        await session.commit()
        template = await owned_template(session, str(template_id), callback.from_user.id)
    if template is None:
        await callback.answer("La plantilla ya no está disponible.", show_alert=True)
        return
    if template.buttons:
        await callback.message.edit_reply_markup(
            reply_markup=template_buttons_menu(template.id, template.buttons)
        )
    else:
        await show_template(callback, template)
    await callback.answer("Botón eliminado")


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
            source_content_type=template.source_content_type,
            source_text_html=template.source_text_html,
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
        f"🚀 <b>Usar plantilla: {escape(template.name)}</b>\n\n"
        "Elige los canales de destino. Después podrás publicarla una vez o hacerla recurrente.",
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
