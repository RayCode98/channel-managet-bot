import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatMemberUpdated
from sqlalchemy import select

from ..database import SessionFactory
from ..models import AuditLog, Membership, RequirementChat
from ..repository import ensure_user_workspace, utcnow

router = Router(name="requirement_chats")
logger = logging.getLogger(__name__)


@router.my_chat_member(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def requirement_chat_membership_changed(event: ChatMemberUpdated, bot: Bot) -> None:
    actor = event.from_user
    async with SessionFactory() as session:
        workspace = await ensure_user_workspace(session, actor)
        existing = await session.get(RequirementChat, event.chat.id)
        member = event.new_chat_member
        is_owner = member.status == ChatMemberStatus.CREATOR
        is_admin = is_owner or member.status == ChatMemberStatus.ADMINISTRATOR

        if is_admin:
            if existing is not None and existing.workspace_id != workspace.id:
                allowed = await session.scalar(
                    select(Membership.id).where(
                        Membership.workspace_id == existing.workspace_id,
                        Membership.user_id == actor.id,
                    )
                )
                if allowed is None:
                    await bot.send_message(
                        actor.id,
                        "⚠️ Este grupo ya está vinculado a otra cuenta.",
                    )
                    return
            if existing is None:
                existing = RequirementChat(
                    telegram_chat_id=event.chat.id,
                    workspace_id=workspace.id,
                    title=event.chat.title or str(event.chat.id),
                    username=event.chat.username,
                    chat_type=event.chat.type.value,
                    added_by_user_id=actor.id,
                )
                session.add(existing)
            existing.title = event.chat.title or existing.title
            existing.username = event.chat.username
            existing.chat_type = event.chat.type.value
            existing.active = True
            existing.can_invite_users = is_owner or bool(getattr(member, "can_invite_users", False))
            existing.last_checked_at = utcnow()
            session.add(
                AuditLog(
                    workspace_id=existing.workspace_id,
                    actor_user_id=actor.id,
                    action="requirement_chat.connected",
                    details=(f"chat_id={event.chat.id};can_invite={existing.can_invite_users}"),
                )
            )
            await session.commit()
            permission_note = (
                ""
                if existing.can_invite_users or existing.username
                else "\n⚠️ Como es privado, concede también <b>Invitar usuarios</b>."
            )
            try:
                await bot.send_message(
                    actor.id,
                    f"✅ <b>{escape(existing.title)}</b> ya puede usarse para Forzar unión."
                    f"{permission_note}",
                )
            except TelegramAPIError as exc:
                logger.info("Could not confirm requirement chat registration: %s", exc)
            return

        if existing is not None and member.status in {
            ChatMemberStatus.LEFT,
            ChatMemberStatus.KICKED,
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.RESTRICTED,
        }:
            existing.active = False
            existing.can_invite_users = False
            existing.last_checked_at = utcnow()
            session.add(
                AuditLog(
                    workspace_id=existing.workspace_id,
                    actor_user_id=actor.id,
                    action="requirement_chat.disconnected",
                    details=f"chat_id={event.chat.id}",
                )
            )
            await session.commit()
