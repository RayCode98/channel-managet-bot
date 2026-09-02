import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, ChatMemberUpdated
from sqlalchemy import select

from ..database import SessionFactory
from ..keyboards import back_home, channels_menu
from ..models import AuditLog, Channel, ChannelStatus, Membership
from ..repository import (
    can_add_channel,
    ensure_user_workspace,
    get_active_channels,
    get_workspace,
    utcnow,
)

router = Router(name="channels")
logger = logging.getLogger(__name__)


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
            lines.append(f"• <b>{channel.title}</b> ({handle}){count}")
        text = "\n".join(lines)
    else:
        text = "📢 <b>Canales conectados</b>\n\nTodavía no has agregado ningún canal."
    await callback.message.edit_text(text, reply_markup=channels_menu())
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
                    actor.id, f"✅ <b>{existing.title}</b> quedó conectado correctamente."
                )
            else:
                await bot.send_message(
                    actor.id,
                    f"⚠️ <b>{existing.title}</b> necesita el permiso para publicar mensajes.",
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
                        owner_id, f"🚨 El bot perdió acceso a <b>{existing.title}</b>."
                    )
                except TelegramAPIError as exc:
                    logger.info("Could not notify channel owner: %s", exc)
