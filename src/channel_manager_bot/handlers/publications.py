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


@router.callback_query(F.data == "pub:new")
async def new_publication(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PublicationFlow.waiting_content)
    await callback.message.edit_text(
        "📝 <b>Nueva publicación</b>\n\n"
        "Envíame el contenido exactamente como debe aparecer: texto con formato, foto, video, "
        "animación, audio o documento. Telegram conservará sus entidades y emojis.\n\n"
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
    async with SessionFactory() as session:
        workspace = await get_workspace(session, message.from_user.id)
        publication = Publication(
            workspace_id=workspace.id,
            creator_user_id=message.from_user.id,
            source_chat_id=message.chat.id,
            source_message_id=message.message_id,
            preview=(message.text or message.caption or "Publicación multimedia")[:500],
        )
        session.add(publication)
        await session.commit()
        publication_id = publication.id
    await state.clear()
    await message.answer(
        "✅ Contenido guardado. Ahora puedes agregar botones o elegir los canales.",
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
        "Elige cuánto tiempo permanecerá el mensaje en cada canal después de publicarse.",
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
        await callback.answer("Primero necesitas conectar al menos un canal.", show_alert=True)
        return
    await state.set_state(PublicationFlow.selecting_channels)
    await callback.message.edit_text(
        "📢 <b>Elige los canales</b>\n\nPuedes publicar el mismo contenido en varios canales.",
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
            await callback.answer("Ese canal no pertenece a tu cuenta.", show_alert=True)
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
        await callback.answer("Selecciona al menos un canal.", show_alert=True)
        return
    await callback.message.edit_text(
        "⏰ <b>Momento de publicación</b>\n\n¿Quieres enviarla ahora o programarla?",
        reply_markup=timing_menu(publication.id),
    )
    await callback.answer()


async def schedule_publication(publication_id: str, user_id: int, scheduled_at: datetime) -> bool:
    async with SessionFactory() as session:
        publication = await owned_publication(session, publication_id, user_id)
        if publication is None or publication.status != PublicationStatus.draft:
            return False
        publication.scheduled_at = scheduled_at
        publication.status = PublicationStatus.scheduled
        await session.commit()
        return True


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


@router.message(PublicationFlow.waiting_schedule, F.text)
async def receive_schedule(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with SessionFactory() as session:
        workspace = await get_workspace(session, message.from_user.id)
    try:
        local_dt = datetime.strptime(message.text.strip(), "%d/%m/%Y %H:%M").replace(
            tzinfo=ZoneInfo(workspace.timezone)
        )
        scheduled_at = local_dt.astimezone(UTC)
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
        lines.append(f"• <b>{label}</b> — {preview}")
    await callback.message.edit_text("\n".join(lines), reply_markup=back_home())
    await callback.answer()
