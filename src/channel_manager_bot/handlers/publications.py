import uuid
from datetime import UTC, datetime
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..database import SessionFactory
from ..keyboards import (
    back_home,
    channel_selector,
    composer_menu,
    main_menu,
    publication_buttons_menu,
    recurrence_interval_menu,
    recurrence_label,
    recurrence_start_menu,
    timing_menu,
    ttl_label,
    ttl_menu,
)
from ..models import (
    Channel,
    ChannelStatus,
    Publication,
    PublicationButton,
    PublicationChannel,
    PublicationStatus,
)
from ..repository import get_active_channels, get_workspace, utcnow
from ..services.post_text import publication_content_type, publication_text_html
from ..services.rich_text import (
    custom_emoji_count,
    message_text_and_entities,
    serialize_entities,
    stored_custom_emoji_count,
)
from ..states import PublicationFlow

router = Router(name="publications")


async def owned_publication(session, publication_id: str, user_id: int) -> Publication | None:
    try:
        parsed = uuid.UUID(publication_id)
    except ValueError:
        return None
    workspace = await get_workspace(session, user_id)
    return await session.scalar(
        select(Publication)
        .options(selectinload(Publication.buttons))
        .where(Publication.id == parsed, Publication.workspace_id == workspace.id)
    )


async def show_publication_editor(callback: CallbackQuery, publication: Publication) -> None:
    preview = escape((publication.preview or "Contenido multimedia").replace("\n", " ")[:200])
    premium_count = stored_custom_emoji_count(
        publication.source_entities_json, publication.source_text_html
    )
    premium_line = (
        f"\n✨ <b>Emojis premium:</b> {premium_count} detectados" if premium_count else ""
    )
    await callback.message.edit_text(
        "📝 <b>Configurar publicación</b>\n\n"
        f"{preview}\n\n"
        f"🔗 <b>Botones:</b> {len(publication.buttons)}\n"
        f"🗑 <b>Autoeliminación:</b> {ttl_label(publication.delete_after_minutes)}"
        f"{premium_line}",
        reply_markup=composer_menu(
            publication.id,
            len(publication.buttons),
            publication.delete_after_minutes,
        ),
    )


@router.callback_query(F.data == "pub:new")
async def new_publication(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PublicationFlow.waiting_content)
    await callback.message.edit_text(
        "📝 <b>Nueva publicación</b>\n\n"
        "Envíame el contenido exactamente como debe aparecer: texto con formato, foto, video, "
        "animación, audio o documento. Puedes insertar emojis premium directamente desde el "
        "selector de Telegram; el bot conservará sus entidades.\n\n"
        "Envía /cancel para salir.",
        reply_markup=back_home(),
    )
    await callback.answer()


@router.message(PublicationFlow.waiting_content, F.chat.type == ChatType.PRIVATE)
async def receive_content(message: Message, state: FSMContext) -> None:
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
        await message.answer(
            "Ese tipo de contenido todavía no es compatible. Envíame texto o un archivo multimedia."
        )
        return
    source_text_plain, source_entities = message_text_and_entities(message)
    premium_count = custom_emoji_count(source_entities)
    async with SessionFactory() as session:
        workspace = await get_workspace(session, message.from_user.id)
        publication = Publication(
            workspace_id=workspace.id,
            creator_user_id=message.from_user.id,
            source_chat_id=message.chat.id,
            source_message_id=message.message_id,
            source_content_type=publication_content_type(message),
            source_text_html=publication_text_html(message),
            source_text_plain=source_text_plain,
            source_entities_json=serialize_entities(source_entities),
            preview=(message.text or message.caption or "Publicación multimedia")[:500],
        )
        session.add(publication)
        await session.commit()
        publication_id = publication.id
    await state.clear()
    premium_notice = (
        f"\n✨ Detectamos <b>{premium_count}</b> emoji{'s' if premium_count != 1 else ''} "
        "premium y conservamos sus identificadores."
        if premium_count
        else ""
    )
    await message.answer(
        "✅ Contenido guardado. Ahora puedes agregar botones o elegir los destinos."
        f"{premium_notice}",
        reply_markup=composer_menu(publication_id, 0),
    )


@router.callback_query(F.data.startswith("pub:button:"))
async def ask_button_text(callback: CallbackQuery, state: FSMContext) -> None:
    publication_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        publication = await owned_publication(session, publication_id, callback.from_user.id)
    if publication is None or publication.status != PublicationStatus.draft:
        await callback.answer("La publicación ya no se puede editar.", show_alert=True)
        return
    await state.set_state(PublicationFlow.waiting_button_text)
    await state.update_data(publication_id=publication_id)
    await callback.message.answer("Escribe el texto del botón (máximo 64 caracteres):")
    await callback.answer()


@router.message(PublicationFlow.waiting_button_text, F.text)
async def receive_button_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not 1 <= len(text) <= 64:
        await message.answer("El texto debe tener entre 1 y 64 caracteres.")
        return
    await state.update_data(button_text=text)
    await state.set_state(PublicationFlow.waiting_button_url)
    await message.answer("Ahora envía el enlace completo, por ejemplo: https://t.me/mi_canal")


@router.message(PublicationFlow.waiting_button_url, F.text)
async def receive_button_url(message: Message, state: FSMContext) -> None:
    url = message.text.strip()
    if not (url.startswith(("https://", "http://", "tg://"))):
        await message.answer("El enlace debe comenzar con https://, http:// o tg://")
        return
    data = await state.get_data()
    async with SessionFactory() as session:
        publication = await owned_publication(session, data["publication_id"], message.from_user.id)
        if publication is None or publication.status != PublicationStatus.draft:
            await state.clear()
            await message.answer("La publicación ya no se puede editar.", reply_markup=main_menu())
            return
        count = await session.scalar(
            select(func.count())
            .select_from(PublicationButton)
            .where(PublicationButton.publication_id == publication.id)
        )
        if (count or 0) >= 20:
            await message.answer("Esta versión permite hasta 20 botones.")
            return
        session.add(
            PublicationButton(
                publication_id=publication.id,
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
        f"✅ Botón agregado. Total: {button_count}.",
        reply_markup=composer_menu(publication.id, button_count, publication.delete_after_minutes),
    )


@router.callback_query(F.data.startswith("pub:edit:"))
async def edit_publication(callback: CallbackQuery) -> None:
    publication_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        publication = await owned_publication(session, publication_id, callback.from_user.id)
    if publication is None or publication.status != PublicationStatus.draft:
        await callback.answer("La publicación ya no se puede editar.", show_alert=True)
        return
    await show_publication_editor(callback, publication)
    await callback.answer()


@router.callback_query(F.data.startswith("pub:buttons:"))
async def manage_publication_buttons(callback: CallbackQuery) -> None:
    publication_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        publication = await owned_publication(session, publication_id, callback.from_user.id)
    if publication is None or publication.status != PublicationStatus.draft:
        await callback.answer("La publicación ya no se puede editar.", show_alert=True)
        return
    if not publication.buttons:
        await callback.answer("Esta publicación no tiene botones.", show_alert=True)
        return
    await callback.message.edit_text(
        "🧹 <b>Administrar botones</b>\n\n"
        "Pulsa el botón que deseas eliminar. Los demás permanecerán sin cambios.",
        reply_markup=publication_buttons_menu(publication.id, publication.buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pub:bdel:"))
async def delete_publication_button(callback: CallbackQuery) -> None:
    try:
        button_id = uuid.UUID(callback.data.rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("Botón inválido.", show_alert=True)
        return
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        button = await session.scalar(
            select(PublicationButton)
            .join(Publication, Publication.id == PublicationButton.publication_id)
            .where(
                PublicationButton.id == button_id,
                Publication.workspace_id == workspace.id,
                Publication.status == PublicationStatus.draft,
            )
        )
        if button is None:
            await callback.answer("Botón no encontrado.", show_alert=True)
            return
        publication_id = button.publication_id
        await session.delete(button)
        await session.flush()
        remaining = list(
            await session.scalars(
                select(PublicationButton)
                .where(PublicationButton.publication_id == publication_id)
                .order_by(PublicationButton.row_index, PublicationButton.position)
            )
        )
        for row_index, remaining_button in enumerate(remaining):
            remaining_button.row_index = row_index
            remaining_button.position = 0
        await session.commit()
        publication = await owned_publication(session, str(publication_id), callback.from_user.id)
    if publication is None:
        await callback.answer("La publicación ya no está disponible.", show_alert=True)
        return
    if publication.buttons:
        await callback.message.edit_reply_markup(
            reply_markup=publication_buttons_menu(publication.id, publication.buttons)
        )
    else:
        await show_publication_editor(callback, publication)
    await callback.answer("Botón eliminado")


@router.callback_query(F.data.startswith("pub:ttl:"))
async def choose_publication_ttl(callback: CallbackQuery) -> None:
    publication_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        publication = await owned_publication(session, publication_id, callback.from_user.id)
    if publication is None or publication.status != PublicationStatus.draft:
        await callback.answer("La publicación ya no se puede editar.", show_alert=True)
        return
    await callback.message.edit_text(
        "🗑 <b>Autoeliminación</b>\n\n"
        "Elige cuánto tiempo permanecerá el mensaje en cada destino después de publicarse.",
        reply_markup=ttl_menu("pub", publication.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pub:setttl:"))
async def set_publication_ttl(callback: CallbackQuery) -> None:
    _, _, publication_id, minutes_text = callback.data.split(":", 3)
    minutes = int(minutes_text)
    async with SessionFactory() as session:
        publication = await owned_publication(session, publication_id, callback.from_user.id)
        if publication is None or publication.status != PublicationStatus.draft:
            await callback.answer("La publicación ya no se puede editar.", show_alert=True)
            return
        publication.delete_after_minutes = minutes or None
        await session.commit()
    await callback.message.edit_text(
        f"✅ Autoeliminación: <b>{ttl_label(publication.delete_after_minutes)}</b>.\n\n"
        "Puedes seguir configurando la publicación.",
        reply_markup=composer_menu(
            publication.id, len(publication.buttons), publication.delete_after_minutes
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pub:channels:"))
async def choose_channels(callback: CallbackQuery, state: FSMContext) -> None:
    publication_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        publication = await owned_publication(session, publication_id, callback.from_user.id)
        if publication is None:
            await callback.answer("Publicación no encontrada.", show_alert=True)
            return
        channels = await get_active_channels(session, publication.workspace_id)
        selected = set(
            await session.scalars(
                select(PublicationChannel.channel_id).where(
                    PublicationChannel.publication_id == publication.id
                )
            )
        )
    if not channels:
        await callback.answer(
            "Primero necesitas conectar al menos un canal o grupo.", show_alert=True
        )
        return
    await state.set_state(PublicationFlow.selecting_channels)
    await callback.message.edit_text(
        "🎯 <b>Elige los destinos</b>\n\n"
        "Puedes publicar el mismo contenido en varios canales y grupos.",
        reply_markup=channel_selector(publication.id, channels, selected),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pub:toggle:"))
async def toggle_channel(callback: CallbackQuery) -> None:
    _, _, publication_id, channel_id_text = callback.data.split(":", 3)
    channel_id = int(channel_id_text)
    async with SessionFactory() as session:
        publication = await owned_publication(session, publication_id, callback.from_user.id)
        if publication is None:
            await callback.answer("Publicación no encontrada.", show_alert=True)
            return
        channel = await session.scalar(
            select(Channel).where(
                Channel.telegram_chat_id == channel_id,
                Channel.workspace_id == publication.workspace_id,
                Channel.status == ChannelStatus.active,
            )
        )
        if channel is None:
            await callback.answer("Ese destino no pertenece a tu cuenta.", show_alert=True)
            return
        existing = await session.scalar(
            select(PublicationChannel).where(
                PublicationChannel.publication_id == publication.id,
                PublicationChannel.channel_id == channel_id,
            )
        )
        if existing:
            await session.delete(existing)
        else:
            session.add(PublicationChannel(publication_id=publication.id, channel_id=channel_id))
        await session.commit()
        channels = await get_active_channels(session, publication.workspace_id)
        selected = set(
            await session.scalars(
                select(PublicationChannel.channel_id).where(
                    PublicationChannel.publication_id == publication.id
                )
            )
        )
    await callback.message.edit_reply_markup(
        reply_markup=channel_selector(publication.id, channels, selected)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pub:all:"))
async def select_all_channels(callback: CallbackQuery) -> None:
    publication_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        publication = await owned_publication(session, publication_id, callback.from_user.id)
        if publication is None:
            await callback.answer("Publicación no encontrada.", show_alert=True)
            return
        channels = await get_active_channels(session, publication.workspace_id)
        existing = set(
            await session.scalars(
                select(PublicationChannel.channel_id).where(
                    PublicationChannel.publication_id == publication.id
                )
            )
        )
        for channel in channels:
            if channel.telegram_chat_id not in existing:
                session.add(
                    PublicationChannel(
                        publication_id=publication.id, channel_id=channel.telegram_chat_id
                    )
                )
        await session.commit()
        selected = {channel.telegram_chat_id for channel in channels}
    await callback.message.edit_reply_markup(
        reply_markup=channel_selector(publication.id, channels, selected)
    )
    await callback.answer("Todos seleccionados")


@router.callback_query(F.data.startswith("pub:time:"))
async def choose_time(callback: CallbackQuery) -> None:
    publication_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        publication = await owned_publication(session, publication_id, callback.from_user.id)
        total = (
            await session.scalar(
                select(func.count())
                .select_from(PublicationChannel)
                .where(PublicationChannel.publication_id == publication.id)
            )
            if publication
            else 0
        )
    if not total:
        await callback.answer("Selecciona al menos un destino.", show_alert=True)
        return
    await callback.message.edit_text(
        "⏰ <b>Momento de publicación</b>\n\n"
        "¿Quieres enviarla ahora, programarla una vez o hacerla recurrente?",
        reply_markup=timing_menu(publication.id),
    )
    await callback.answer()


async def schedule_publication(
    publication_id: str,
    user_id: int,
    scheduled_at: datetime,
    recurrence_days: int | None = None,
) -> bool:
    if recurrence_days is not None and not 1 <= recurrence_days <= 365:
        return False
    async with SessionFactory() as session:
        publication = await owned_publication(session, publication_id, user_id)
        if publication is None or publication.status != PublicationStatus.draft:
            return False
        publication.scheduled_at = scheduled_at
        publication.status = PublicationStatus.scheduled
        if recurrence_days:
            workspace = await get_workspace(session, user_id)
            publication.recurrence_series_id = uuid.uuid4()
            publication.recurrence_interval_days = recurrence_days
            publication.recurrence_sequence = 1
            publication.recurrence_timezone = workspace.timezone
        await session.commit()
        return True


def parse_scheduled_at(value: str, timezone_name: str) -> datetime:
    local_dt = datetime.strptime(value.strip(), "%d/%m/%Y %H:%M").replace(
        tzinfo=ZoneInfo(timezone_name)
    )
    return local_dt.astimezone(UTC)


async def show_recurrence_start(callback: CallbackQuery, publication_id: str, days: int) -> None:
    await callback.message.edit_text(
        f"🔁 <b>{recurrence_label(days)}</b>\n\n"
        "Elige cuándo debe realizarse la primera publicación. La serie continuará hasta que "
        "la detengas desde el Plan de contenido.",
        reply_markup=recurrence_start_menu(uuid.UUID(publication_id), days),
    )


@router.callback_query(F.data.startswith("pub:now:"))
async def publish_now(callback: CallbackQuery, state: FSMContext) -> None:
    publication_id = callback.data.rsplit(":", 1)[1]
    if not await schedule_publication(publication_id, callback.from_user.id, utcnow()):
        await callback.answer("No se pudo programar.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "🚀 <b>Publicación enviada a la cola</b>\n\nSe procesará en unos segundos.",
        reply_markup=main_menu(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pub:schedule:"))
async def ask_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    publication_id = callback.data.rsplit(":", 1)[1]
    await state.set_state(PublicationFlow.waiting_schedule)
    await state.update_data(publication_id=publication_id)
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
    await callback.message.answer(
        "Escribe la fecha y hora con este formato:\n<b>05/09/2026 18:30</b>\n\n"
        f"Zona horaria: <code>{workspace.timezone}</code>"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pub:repeat:"))
async def choose_recurrence(callback: CallbackQuery) -> None:
    publication_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        publication = await owned_publication(session, publication_id, callback.from_user.id)
    if publication is None or publication.status != PublicationStatus.draft:
        await callback.answer("La publicación ya no se puede editar.", show_alert=True)
        return
    await callback.message.edit_text(
        "🔁 <b>Publicación recurrente</b>\n\n"
        "Elige cada cuántos días debe repetirse. Se conservarán el contenido, los botones, "
        "los destinos y la autoeliminación.",
        reply_markup=recurrence_interval_menu(publication.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pub:setrepeat:"))
async def choose_recurrence_interval(callback: CallbackQuery) -> None:
    _, _, publication_id, days_text = callback.data.split(":", 3)
    days = int(days_text)
    async with SessionFactory() as session:
        publication = await owned_publication(session, publication_id, callback.from_user.id)
    if publication is None or publication.status != PublicationStatus.draft:
        await callback.answer("La publicación ya no se puede editar.", show_alert=True)
        return
    await show_recurrence_start(callback, publication_id, days)
    await callback.answer()


@router.callback_query(F.data.startswith("pub:repeatcustom:"))
async def ask_custom_recurrence(callback: CallbackQuery, state: FSMContext) -> None:
    publication_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        publication = await owned_publication(session, publication_id, callback.from_user.id)
    if publication is None or publication.status != PublicationStatus.draft:
        await callback.answer("La publicación ya no se puede editar.", show_alert=True)
        return
    await state.set_state(PublicationFlow.waiting_recurrence_interval)
    await state.update_data(publication_id=publication_id)
    await callback.message.answer(
        "Escribe el número de días entre publicaciones, del <b>1 al 365</b>."
    )
    await callback.answer()


@router.message(PublicationFlow.waiting_recurrence_interval, F.text)
async def receive_custom_recurrence(message: Message, state: FSMContext) -> None:
    try:
        days = int(message.text.strip())
    except ValueError:
        days = 0
    if not 1 <= days <= 365:
        await message.answer("Escribe un número entero entre 1 y 365.")
        return
    data = await state.get_data()
    async with SessionFactory() as session:
        publication = await owned_publication(session, data["publication_id"], message.from_user.id)
    if publication is None or publication.status != PublicationStatus.draft:
        await state.clear()
        await message.answer("La publicación ya no se puede editar.", reply_markup=main_menu())
        return
    await state.clear()
    await message.answer(
        f"🔁 <b>{recurrence_label(days)}</b>\n\n"
        "Elige cuándo debe realizarse la primera publicación. La serie continuará hasta que "
        "la detengas desde el Plan de contenido.",
        reply_markup=recurrence_start_menu(publication.id, days),
    )


@router.callback_query(F.data.startswith("pub:repeatnow:"))
async def start_recurrence_now(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, publication_id, days_text = callback.data.split(":", 3)
    days = int(days_text)
    if not await schedule_publication(
        publication_id,
        callback.from_user.id,
        utcnow(),
        recurrence_days=days,
    ):
        await callback.answer("No se pudo programar.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        f"🔁 <b>Recurrencia activada: {recurrence_label(days)}</b>\n\n"
        "La primera publicación se enviará en unos segundos.",
        reply_markup=main_menu(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pub:repeatdate:"))
async def ask_recurrence_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, publication_id, days_text = callback.data.split(":", 3)
    days = int(days_text)
    await state.set_state(PublicationFlow.waiting_recurrence_schedule)
    await state.update_data(publication_id=publication_id, recurrence_days=days)
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
    await callback.message.answer(
        "Escribe la fecha y hora de la primera publicación:\n"
        "<b>05/09/2026 18:30</b>\n\n"
        f"Zona horaria: <code>{workspace.timezone}</code>"
    )
    await callback.answer()


@router.message(PublicationFlow.waiting_schedule, F.text)
async def receive_schedule(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with SessionFactory() as session:
        workspace = await get_workspace(session, message.from_user.id)
    try:
        scheduled_at = parse_scheduled_at(message.text, workspace.timezone)
    except (ValueError, ZoneInfoNotFoundError):
        await message.answer("Formato inválido. Usa, por ejemplo: <b>05/09/2026 18:30</b>")
        return
    if scheduled_at <= utcnow():
        await message.answer("La fecha debe estar en el futuro.")
        return
    if not await schedule_publication(data["publication_id"], message.from_user.id, scheduled_at):
        await state.clear()
        await message.answer("La publicación ya no está disponible.", reply_markup=main_menu())
        return
    await state.clear()
    await message.answer(
        f"✅ Programada para <b>{message.text.strip()}</b> ({workspace.timezone}).",
        reply_markup=main_menu(),
    )


@router.message(PublicationFlow.waiting_recurrence_schedule, F.text)
async def receive_recurrence_schedule(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with SessionFactory() as session:
        workspace = await get_workspace(session, message.from_user.id)
    try:
        scheduled_at = parse_scheduled_at(message.text, workspace.timezone)
    except (ValueError, ZoneInfoNotFoundError):
        await message.answer("Formato inválido. Usa, por ejemplo: <b>05/09/2026 18:30</b>")
        return
    if scheduled_at <= utcnow():
        await message.answer("La fecha debe estar en el futuro.")
        return
    days = int(data["recurrence_days"])
    if not await schedule_publication(
        data["publication_id"],
        message.from_user.id,
        scheduled_at,
        recurrence_days=days,
    ):
        await state.clear()
        await message.answer("La publicación ya no está disponible.", reply_markup=main_menu())
        return
    await state.clear()
    await message.answer(
        f"✅ Primera publicación: <b>{message.text.strip()}</b> ({workspace.timezone}).\n"
        f"🔁 Repetición: <b>{recurrence_label(days)}</b>, hasta que la detengas.",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data.startswith("pub:cancel:"))
async def cancel_publication(callback: CallbackQuery, state: FSMContext) -> None:
    publication_id = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        publication = await owned_publication(session, publication_id, callback.from_user.id)
        if publication and publication.status in {
            PublicationStatus.draft,
            PublicationStatus.scheduled,
        }:
            publication.status = PublicationStatus.cancelled
            await session.commit()
    await state.clear()
    await callback.message.edit_text("Publicación cancelada.", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "pub:list")
async def list_publications(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        rows = list(
            await session.scalars(
                select(Publication)
                .where(Publication.workspace_id == workspace.id)
                .order_by(Publication.created_at.desc())
                .limit(10)
            )
        )
    lines = ["📚 <b>Últimas publicaciones</b>", ""]
    if not rows:
        lines.append("No hay publicaciones todavía.")
    for item in rows:
        label = {
            PublicationStatus.draft: "Borrador",
            PublicationStatus.scheduled: "Programada",
            PublicationStatus.publishing: "Publicando",
            PublicationStatus.published: "Publicada",
            PublicationStatus.partial: "Parcial",
            PublicationStatus.failed: "Fallida",
            PublicationStatus.cancelled: "Cancelada",
        }[item.status]
        preview = escape((item.preview or "Multimedia").replace("\n", " ")[:55])
        recurrence = (
            f" · 🔁 {recurrence_label(item.recurrence_interval_days)}"
            if item.recurrence_interval_days
            else ""
        )
        lines.append(f"• <b>{label}</b>{recurrence} — {preview}")
    await callback.message.edit_text("\n".join(lines), reply_markup=back_home())
    await callback.answer()
