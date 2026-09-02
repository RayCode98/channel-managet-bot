import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message
from sqlalchemy import select

from ..database import SessionFactory
from ..keyboards import back_home, channel_detail_menu, channels_menu
from ..models import AuditLog, Channel, ChannelStatus, Membership
from ..repository import (
    can_add_channel,
    ensure_user_workspace,
    get_active_channels,
    get_workspace,
    utcnow,
)
from ..states import ChannelWelcomeFlow

router = Router(name="channels")
logger = logging.getLogger(__name__)


async def owned_channel(session, channel_id: int, user_id: int) -> Channel | None:
    workspace = await get_workspace(session, user_id)
    if workspace is None:
        return None
    return await session.scalar(
        select(Channel).where(
            Channel.telegram_chat_id == channel_id,
            Channel.workspace_id == workspace.id,
            Channel.status == ChannelStatus.active,
        )
    )


@router.callback_query(F.data == "channels:list")
async def list_channels(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        channels = await get_active_channels(session, workspace.id)
    if channels:
        lines = ["📢 <b>Canales conectados</b>", ""]
        for channel in channels:
            handle = f"@{channel.username}" if channel.username else "privado"
            count = (
                f" · {channel.member_count:,} miembros" if channel.member_count is not None else ""
            )
            lines.append(f"• <b>{escape(channel.title)}</b> ({handle}){count}")
        text = "\n".join(lines)
    else:
        text = "📢 <b>Canales conectados</b>\n\nTodavía no has agregado ningún canal."
    await callback.message.edit_text(text, reply_markup=channels_menu(channels))
    await callback.answer()


@router.callback_query(F.data.startswith("channel:open:"))
async def open_channel(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    button = channel.welcome_button_text or "Sin botón"
    status = "Activa" if channel.welcome_enabled else "Desactivada"
    await callback.message.edit_text(
        f"⚙️ <b>{escape(channel.title)}</b>\n\n"
        f"👋 <b>Bienvenida:</b> {status}\n"
        f"🔗 <b>Botón:</b> {button}\n\n"
        "La bienvenida se envía por privado cuando llega una solicitud de ingreso, antes de aprobarla.",
        reply_markup=channel_detail_menu(channel),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("welcome:content:"))
async def ask_channel_welcome(callback: CallbackQuery, state: FSMContext) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    await state.set_state(ChannelWelcomeFlow.waiting_content)
    await state.update_data(channel_id=channel_id)
    await callback.message.answer(
        f"👋 Envía la bienvenida para <b>{escape(channel.title)}</b>.\n\n"
        "Puede ser texto enriquecido o una foto con texto. También se aceptan video, animación, audio o documento."
    )
    await callback.answer()


@router.message(ChannelWelcomeFlow.waiting_content, F.chat.type == ChatType.PRIVATE)
async def save_channel_welcome(message: Message, state: FSMContext) -> None:
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
        await message.answer("Envía texto, una foto u otro archivo multimedia compatible.")
        return
    data = await state.get_data()
    async with SessionFactory() as session:
        channel = await owned_channel(session, int(data["channel_id"]), message.from_user.id)
        if channel is None:
            await state.clear()
            await message.answer("Canal no encontrado.")
            return
        channel.welcome_source_chat_id = message.chat.id
        channel.welcome_source_message_id = message.message_id
        channel.welcome_enabled = True
        await session.commit()
    await state.clear()
    await message.answer(
        "✅ Bienvenida guardada y activada. Puedes agregarle un botón desde este menú.",
        reply_markup=channel_detail_menu(channel),
    )


@router.callback_query(F.data.startswith("welcome:button:"))
async def ask_welcome_button(callback: CallbackQuery, state: FSMContext) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    if not channel.welcome_source_message_id:
        await callback.answer("Primero configura el contenido de bienvenida.", show_alert=True)
        return
    await state.set_state(ChannelWelcomeFlow.waiting_button_text)
    await state.update_data(channel_id=channel_id)
    await callback.message.answer(
        "Escribe el texto del botón de bienvenida (máximo 64 caracteres):"
    )
    await callback.answer()


@router.message(ChannelWelcomeFlow.waiting_button_text, F.text)
async def receive_welcome_button_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not 1 <= len(text) <= 64:
        await message.answer("El texto debe tener entre 1 y 64 caracteres.")
        return
    await state.update_data(button_text=text)
    await state.set_state(ChannelWelcomeFlow.waiting_button_url)
    await message.answer("Envía el enlace completo del botón, por ejemplo: https://t.me/mi_canal")


@router.message(ChannelWelcomeFlow.waiting_button_url, F.text)
async def receive_welcome_button_url(message: Message, state: FSMContext) -> None:
    url = message.text.strip()
    if not url.startswith(("https://", "http://", "tg://")):
        await message.answer("El enlace debe comenzar con https://, http:// o tg://")
        return
    data = await state.get_data()
    async with SessionFactory() as session:
        channel = await owned_channel(session, int(data["channel_id"]), message.from_user.id)
        if channel is None:
            await state.clear()
            await message.answer("Canal no encontrado.")
            return
        channel.welcome_button_text = data["button_text"]
        channel.welcome_button_url = url
        await session.commit()
    await state.clear()
    await message.answer(
        "✅ Botón de bienvenida guardado.", reply_markup=channel_detail_menu(channel)
    )


@router.callback_query(F.data.startswith("welcome:toggle:"))
async def toggle_channel_welcome(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
        if channel is None:
            await callback.answer("Canal no encontrado.", show_alert=True)
            return
        if not channel.welcome_source_message_id:
            await callback.answer("Primero configura el contenido de bienvenida.", show_alert=True)
            return
        channel.welcome_enabled = not channel.welcome_enabled
        await session.commit()
    await callback.message.edit_reply_markup(reply_markup=channel_detail_menu(channel))
    await callback.answer("Bienvenida actualizada")


@router.callback_query(F.data.startswith("welcome:clear:"))
async def clear_channel_welcome(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
        if channel is None:
            await callback.answer("Canal no encontrado.", show_alert=True)
            return
        channel.welcome_enabled = False
        channel.welcome_source_chat_id = None
        channel.welcome_source_message_id = None
        channel.welcome_button_text = None
        channel.welcome_button_url = None
        await session.commit()
    await callback.message.edit_text(
        f"⚙️ <b>{escape(channel.title)}</b>\n\nLa bienvenida personalizada fue eliminada.",
        reply_markup=channel_detail_menu(channel),
    )
    await callback.answer()


@router.callback_query(F.data == "channels:add")
async def add_channel_instructions(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        allowed = await can_add_channel(session, workspace.id)
    if not allowed:
        await callback.answer("Tu cuenta alcanzó el límite de canales.", show_alert=True)
        return
    me = await callback.bot.get_me()
    await callback.message.edit_text(
        "➕ <b>Agregar un canal</b>\n\n"
        f"1. Abre tu canal y agrega a @{me.username} como administrador.\n"
        "2. Concede el permiso <b>Publicar mensajes</b>.\n"
        "3. Regresa aquí; el canal se registrará automáticamente.\n\n"
        "La persona que agrega al bot debe ser la misma que usa este panel.",
        reply_markup=back_home(),
    )
    await callback.answer()


@router.my_chat_member(F.chat.type == ChatType.CHANNEL)
async def bot_membership_changed(event: ChatMemberUpdated, bot: Bot) -> None:
    actor = event.from_user
    async with SessionFactory() as session:
        workspace = await ensure_user_workspace(session, actor)
        existing = await session.get(Channel, event.chat.id)
        new_member = event.new_chat_member
        is_admin = new_member.status == ChatMemberStatus.ADMINISTRATOR
        can_post = bool(getattr(new_member, "can_post_messages", False)) if is_admin else False

        if is_admin:
            if existing is not None and existing.workspace_id != workspace.id:
                member_of_owner_workspace = await session.scalar(
                    select(Membership.id).where(
                        Membership.workspace_id == existing.workspace_id,
                        Membership.user_id == actor.id,
                    )
                )
                if member_of_owner_workspace is None:
                    await bot.send_message(
                        actor.id,
                        "⚠️ Este canal ya está vinculado a otra cuenta. Debe desvincularlo su propietario.",
                    )
                    return
            if existing is None and not await can_add_channel(session, workspace.id):
                await bot.send_message(
                    actor.id, "⚠️ No pude agregar el canal: alcanzaste el límite de tu cuenta."
                )
                return
            if existing is None:
                existing = Channel(
                    telegram_chat_id=event.chat.id,
                    workspace_id=workspace.id,
                    title=event.chat.title or str(event.chat.id),
                    username=event.chat.username,
                    added_by_user_id=actor.id,
                )
                session.add(existing)
            existing.title = event.chat.title or existing.title
            existing.username = event.chat.username
            existing.status = (
                ChannelStatus.active if can_post else ChannelStatus.missing_permissions
            )
            existing.can_post_messages = can_post
            existing.last_checked_at = utcnow()
            session.add(
                AuditLog(
                    workspace_id=existing.workspace_id,
                    actor_user_id=actor.id,
                    action="channel.connected",
                    details=f"chat_id={event.chat.id};can_post={can_post}",
                )
            )
            await session.commit()
            if can_post:
                await bot.send_message(
                    actor.id, f"✅ <b>{escape(existing.title)}</b> quedó conectado correctamente."
                )
            else:
                await bot.send_message(
                    actor.id,
                    f"⚠️ <b>{escape(existing.title)}</b> necesita el permiso para publicar mensajes.",
                )
            return

        if existing is not None and new_member.status in {
            ChatMemberStatus.LEFT,
            ChatMemberStatus.KICKED,
            ChatMemberStatus.MEMBER,
        }:
            existing.status = ChannelStatus.removed
            existing.can_post_messages = False
            session.add(
                AuditLog(
                    workspace_id=existing.workspace_id,
                    actor_user_id=actor.id,
                    action="channel.disconnected",
                    details=f"chat_id={event.chat.id}",
                )
            )
            await session.commit()
            owner_id = await session.scalar(
                select(Channel.added_by_user_id).where(Channel.telegram_chat_id == event.chat.id)
            )
            if owner_id:
                try:
                    await bot.send_message(
                        owner_id, f"🚨 El bot perdió acceso a <b>{escape(existing.title)}</b>."
                    )
                except TelegramAPIError as exc:
                    logger.info("Could not notify channel owner: %s", exc)
