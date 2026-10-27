import logging
import uuid
from html import escape

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
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
from ..models import (
    ContentTemplate,
    Publication,
    PublicationButton,
    PublicationStatus,
    TemplateButton,
)
from ..repository import get_active_channels, get_workspace
from ..services.post_text import publication_content_type, publication_text_html
from ..services.rich_text import (
    custom_emoji_count,
    message_text_and_entities,
    serialize_entities,
    stored_custom_emoji_count,
)
from ..services.welcome import parse_button_color, parse_button_spec
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


async def sync_recurrent_publications(session, template: ContentTemplate) -> int:
    """Apply the current template snapshot to its future recurring publication."""
    publications = list(
        await session.scalars(
            select(Publication)
            .options(selectinload(Publication.buttons))
            .where(
                Publication.template_id == template.id,
                Publication.workspace_id == template.workspace_id,
                Publication.status == PublicationStatus.scheduled,
                Publication.scheduled_at.is_not(None),
                Publication.recurrence_interval_days.is_not(None),
            )
        )
    )
    for publication in publications:
        publication.source_chat_id = template.source_chat_id
        publication.source_message_id = template.source_message_id
        publication.source_content_type = template.source_content_type
        publication.source_text_html = template.source_text_html
        publication.source_text_plain = template.source_text_plain
        publication.source_entities_json = template.source_entities_json
        publication.preview = template.preview
        publication.delete_after_minutes = template.delete_after_minutes
        publication.buttons.clear()
        publication.buttons.extend(
            PublicationButton(
                row_index=button.row_index,
                position=button.position,
                text=button.text,
                url=button.url,
                style=getattr(button, "style", None),
            )
            for button in template.buttons
        )
    return len(publications)


async def show_template(callback: CallbackQuery, template: ContentTemplate) -> None:
    preview = escape((template.preview or "Contenido multimedia").replace("\n", " ")[:200])
    premium_count = stored_custom_emoji_count(
        template.source_entities_json, template.source_text_html
    )
    premium_line = (
        f"✨ <b>Emojis premium:</b> {premium_count} detectados\n" if premium_count else ""
    )
    await callback.message.edit_text(
        f"🧩 <b>{escape(template.name)}</b>\n\n"
        f"📝 {preview}\n"
        f"🔗 <b>Botones:</b> {len(template.buttons)}\n"
        f"🗑 <b>Autoeliminación:</b> {ttl_label(template.delete_after_minutes)}\n\n"
        f"{premium_line}"
        "🔁 La recurrencia se elige después de seleccionar los destinos.",
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


@router.callback_query(F.data == "tpl:clear")
async def ask_clear_templates(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        total = (
            await session.scalar(
                select(func.count())
                .select_from(ContentTemplate)
                .where(ContentTemplate.workspace_id == workspace.id)
            )
            or 0
        )
    if not total:
        await callback.answer("No hay plantillas para eliminar.", show_alert=True)
        return
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Sí, eliminar todas", callback_data="tpl:clear:confirm")],
            [InlineKeyboardButton(text="Cancelar", callback_data="tpl:list")],
        ]
    )
    await callback.message.edit_text(
        f"⚠️ <b>Eliminar todas las plantillas</b>\n\n"
        f"Se eliminarán definitivamente <b>{total}</b> plantilla(s) y sus botones.\n"
        "Las publicaciones ya creadas a partir de ellas no se modificarán.",
        reply_markup=markup,
    )
    await callback.answer()


@router.callback_query(F.data == "tpl:clear:confirm")
async def clear_templates(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        templates = list(
            await session.scalars(
                select(ContentTemplate).where(ContentTemplate.workspace_id == workspace.id)
            )
        )
        for template in templates:
            await session.delete(template)
        await session.commit()
    await callback.message.edit_text(
        f"✅ Se eliminaron <b>{len(templates)}</b> plantilla(s).",
        reply_markup=templates_menu(),
    )
    await callback.answer("Plantillas eliminadas")


@router.message(TemplateFlow.waiting_name, F.text)
async def receive_template_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not 1 <= len(name) <= 100:
        await message.answer("El nombre debe tener entre 1 y 100 caracteres.")
        return
    await state.update_data(template_name=name)
    await state.set_state(TemplateFlow.waiting_content)
    await message.answer(
        "Ahora envía el contenido de la plantilla: texto enriquecido, foto, video, animación, "
        "audio o documento. Puedes insertar emojis premium desde el selector de Telegram; "
        "si la API no los autoriza en un destino, se usará su emoji normal de respaldo."
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
    source_text_plain, source_entities = message_text_and_entities(message)
    premium_count = custom_emoji_count(source_entities)
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
            source_text_plain=source_text_plain,
            source_entities_json=serialize_entities(source_entities),
            preview=(message.text or message.caption or "Contenido multimedia")[:500],
        )
        session.add(template)
        await session.commit()
    await state.clear()
    premium_notice = (
        f"\n✨ Detectamos <b>{premium_count}</b> emoji{'s' if premium_count != 1 else ''} premium."
        if premium_count
        else ""
    )
    await message.answer(
        "✅ Plantilla creada. Ya puedes añadir botones, autoeliminación o utilizarla."
        f"{premium_notice}",
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


@router.callback_query(F.data.startswith("tpl:editcontent:"))
async def ask_edit_template_content(callback: CallbackQuery, state: FSMContext) -> None:
    template_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        template = await owned_template(session, template_id, callback.from_user.id)
    if template is None:
        await callback.answer("Plantilla no encontrada.", show_alert=True)
        return
    await state.set_state(TemplateFlow.waiting_content_edit)
    await state.update_data(template_id=template_id)
    await callback.message.answer(
        "✏️ <b>Editar descripción de la plantilla</b>\n\n"
        "Envía el nuevo texto enriquecido o contenido multimedia. Esta descripción sustituirá "
        "la de la plantilla y se aplicará a sus publicaciones recurrentes futuras."
    )
    await callback.answer()


@router.message(TemplateFlow.waiting_content_edit, F.chat.type == ChatType.PRIVATE)
async def receive_edited_template_content(message: Message, state: FSMContext) -> None:
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
    source_text_plain, source_entities = message_text_and_entities(message)
    premium_count = custom_emoji_count(source_entities)
    try:
        async with SessionFactory() as session:
            template = await owned_template(session, data["template_id"], message.from_user.id)
            if template is None:
                await state.clear()
                await message.answer("Plantilla no encontrada.", reply_markup=templates_menu())
                return
            template.source_chat_id = message.chat.id
            template.source_message_id = message.message_id
            template.source_content_type = publication_content_type(message)
            template.source_text_html = publication_text_html(message)
            template.source_text_plain = source_text_plain
            template.source_entities_json = serialize_entities(source_entities)
            template.preview = (message.text or message.caption or "Contenido multimedia")[:500]
            recurrent_count = await sync_recurrent_publications(session, template)
            await session.commit()
            template_id = template.id
            button_count = len(template.buttons)
            delete_after_minutes = template.delete_after_minutes
    except SQLAlchemyError:
        logger.exception("Could not update template content for user %s", message.from_user.id)
        await state.clear()
        await message.answer(
            "⚠️ No pude guardar la descripción porque la base de datos aún no tiene la "
            "migración de esta versión. Ejecuta en el VPS:\n\n"
            "<code>docker compose run --rm migrate alembic upgrade head</code>\n\n"
            "Después vuelve a enviar el contenido.",
            reply_markup=templates_menu(),
        )
        return
    await state.clear()
    premium_notice = (
        f"\n✨ Detectamos <b>{premium_count}</b> emoji{'s' if premium_count != 1 else ''} premium."
        if premium_count
        else ""
    )
    recurring_notice = (
        f"\n🔁 Actualicé también <b>{recurrent_count}</b> publicación(es) recurrente(s) futuras."
        if recurrent_count
        else "\nℹ️ No hay publicaciones recurrentes futuras vinculadas a esta plantilla."
    )
    await message.answer(
        f"✅ Descripción de la plantilla actualizada.{premium_notice}{recurring_notice}",
        reply_markup=template_detail_menu(template_id, button_count, delete_after_minutes),
    )


@router.callback_query(F.data.startswith("tpl:editname:"))
async def ask_edit_template_name(callback: CallbackQuery, state: FSMContext) -> None:
    template_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        template = await owned_template(session, template_id, callback.from_user.id)
    if template is None:
        await callback.answer("Plantilla no encontrada.", show_alert=True)
        return
    await state.set_state(TemplateFlow.waiting_name_edit)
    await state.update_data(template_id=template_id)
    await callback.message.answer(
        f"✏️ Nombre actual: <b>{escape(template.name)}</b>\n\n"
        "Escribe el nuevo nombre de la plantilla (máximo 100 caracteres):"
    )
    await callback.answer()


@router.message(TemplateFlow.waiting_name_edit, F.text)
async def receive_edited_template_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not 1 <= len(name) <= 100:
        await message.answer("El nombre debe tener entre 1 y 100 caracteres.")
        return
    data = await state.get_data()
    async with SessionFactory() as session:
        template = await owned_template(session, data["template_id"], message.from_user.id)
        if template is None:
            await state.clear()
            await message.answer("Plantilla no encontrada.", reply_markup=templates_menu())
            return
        template.name = name
        await session.commit()
        template_id = template.id
        button_count = len(template.buttons)
        delete_after_minutes = template.delete_after_minutes
    await state.clear()
    await message.answer(
        "✅ Nombre de la plantilla actualizado.",
        reply_markup=template_detail_menu(template_id, button_count, delete_after_minutes),
    )


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
    if not url.startswith(("https://", "http://", "tg://")) or len(url) > 2048:
        await message.answer(
            "El enlace debe comenzar con https://, http:// o tg:// y no superar 2048 caracteres."
        )
        return
    await state.update_data(button_url=url)
    await state.set_state(TemplateFlow.waiting_button_color)
    await message.answer(
        "Elige el color del botón: <b>azul</b>, <b>verde</b>, <b>rojo</b> o <b>normal</b>."
    )


@router.message(TemplateFlow.waiting_button_color, F.text)
async def receive_template_button_color(message: Message, state: FSMContext) -> None:
    try:
        style = parse_button_color(message.text)
    except ValueError as exc:
        await message.answer(str(exc))
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
            await state.clear()
            await message.answer("La plantilla ya alcanzó el máximo de 20 botones.")
            return
        session.add(
            TemplateButton(
                template_id=template.id,
                row_index=count or 0,
                position=0,
                text=data["button_text"],
                url=data["button_url"],
                style=style,
            )
        )
        await session.flush()
        template = await owned_template(session, str(template.id), message.from_user.id)
        if template is None:
            await state.clear()
            await message.answer(
                "La plantilla ya no está disponible.", reply_markup=templates_menu()
            )
            return
        recurrent_count = await sync_recurrent_publications(session, template)
        await session.commit()
        button_count = (count or 0) + 1
    await state.clear()
    await message.answer(
        "✅ Botón añadido a la plantilla."
        + (
            f" Se actualizó también {recurrent_count} publicación(es) recurrente(s) futura(s)."
            if recurrent_count
            else ""
        ),
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
        "Pulsa ✏️ para editar o 🗑 para eliminar. Los cambios se aplicarán también a las "
        "publicaciones recurrentes futuras de esta plantilla.",
        reply_markup=template_buttons_menu(template.id, template.buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tpl:bedit:"))
async def edit_template_button(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        button_id = uuid.UUID(callback.data.rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("Botón inválido.", show_alert=True)
        return
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        if workspace is None:
            await callback.answer("Espacio de trabajo no encontrado.", show_alert=True)
            return
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
    await state.set_state(TemplateFlow.waiting_button_edit)
    await state.update_data(button_id=str(button.id))
    await callback.message.answer(
        f"✏️ Editando <b>{escape(button.text)}</b>.\n\n"
        "Envía una sola línea con el formato:\n"
        "<code>Texto del botón - https://ejemplo.com - azul</code>\n"
        "También se acepta el formato anterior de dos partes; quedará en color normal."
    )
    await callback.answer()


@router.message(TemplateFlow.waiting_button_edit, F.text)
async def receive_edited_template_button(message: Message, state: FSMContext) -> None:
    try:
        parsed = parse_button_spec(message.text.strip(), allow_legacy=True)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    data = await state.get_data()
    async with SessionFactory() as session:
        workspace = await get_workspace(session, message.from_user.id)
        if workspace is None:
            await state.clear()
            await message.answer("Espacio de trabajo no encontrado.", reply_markup=templates_menu())
            return
        try:
            button_id = uuid.UUID(data["button_id"])
        except (KeyError, ValueError):
            await state.clear()
            await message.answer("Botón inválido.", reply_markup=templates_menu())
            return
        button = await session.scalar(
            select(TemplateButton)
            .join(ContentTemplate, ContentTemplate.id == TemplateButton.template_id)
            .where(
                TemplateButton.id == button_id,
                ContentTemplate.workspace_id == workspace.id,
            )
        )
        if button is None:
            await state.clear()
            await message.answer("El botón ya no está disponible.", reply_markup=templates_menu())
            return
        button.text = parsed.text
        button.url = parsed.url
        button.style = parsed.style
        await session.flush()
        template = await owned_template(session, str(button.template_id), message.from_user.id)
        if template is None:
            await state.clear()
            await message.answer(
                "La plantilla ya no está disponible.", reply_markup=templates_menu()
            )
            return
        recurrent_count = await sync_recurrent_publications(session, template)
        await session.commit()
        template_id = template.id
        button_count = len(template.buttons)
        delete_after_minutes = template.delete_after_minutes
    await state.clear()
    await message.answer(
        "✅ Botón de la plantilla actualizado."
        + (
            f" Se actualizó también {recurrent_count} publicación(es) recurrente(s) futura(s)."
            if recurrent_count
            else ""
        ),
        reply_markup=template_detail_menu(template_id, button_count, delete_after_minutes),
    )


@router.callback_query(F.data.startswith("tpl:bdel:"))
async def delete_template_button(callback: CallbackQuery) -> None:
    try:
        button_id = uuid.UUID(callback.data.rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("Botón inválido.", show_alert=True)
        return
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        if workspace is None:
            await callback.answer("Espacio de trabajo no encontrado.", show_alert=True)
            return
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
        recurrent_count = await sync_recurrent_publications(session, template) if template else 0
        await session.commit()
    if template is None:
        await callback.answer("La plantilla ya no está disponible.", show_alert=True)
        return
    if template.buttons:
        await callback.message.edit_reply_markup(
            reply_markup=template_buttons_menu(template.id, template.buttons)
        )
    else:
        await show_template(callback, template)
    message = "Botón eliminado"
    if recurrent_count:
        message += f" y actualizado en {recurrent_count} publicación(es) recurrente(s) futura(s)"
    await callback.answer(message)


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
        recurrent_count = await sync_recurrent_publications(session, template)
        await session.commit()
    await show_template(callback, template)
    message = "Autoeliminación actualizada"
    if recurrent_count:
        message += f" y aplicada a {recurrent_count} publicación(es) recurrente(s) futura(s)"
    await callback.answer(message)


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
            await callback.answer("Primero conecta al menos un canal o grupo.", show_alert=True)
            return
        publication = Publication(
            workspace_id=template.workspace_id,
            template_id=template.id,
            creator_user_id=callback.from_user.id,
            source_chat_id=template.source_chat_id,
            source_message_id=template.source_message_id,
            source_content_type=template.source_content_type,
            source_text_html=template.source_text_html,
            source_text_plain=template.source_text_plain,
            source_entities_json=template.source_entities_json,
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
                    style=getattr(button, "style", None),
                )
            )
        await session.commit()
    await state.set_state(PublicationFlow.selecting_channels)
    await callback.message.edit_text(
        f"🚀 <b>Usar plantilla: {escape(template.name)}</b>\n\n"
        "Elige los canales o grupos de destino. Después podrás publicarla una vez o hacerla "
        "recurrente.",
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
