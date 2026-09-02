import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, ChatJoinRequest, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from ..database import SessionFactory
from ..models import Channel, ChannelStatus, JoinRequestEvent, Membership, Role, Workspace

router = Router(name="joins")
logger = logging.getLogger(__name__)


@router.chat_join_request()
async def process_join_request(request: ChatJoinRequest, bot: Bot) -> None:
    async with SessionFactory() as session:
        channel = await session.get(Channel, request.chat.id)
        if channel is None or channel.status != ChannelStatus.active:
            return
        workspace = await session.get(Workspace, channel.workspace_id)
        event = JoinRequestEvent(
            channel_id=channel.telegram_chat_id,
            user_id=request.from_user.id,
            invite_link=request.invite_link.invite_link if request.invite_link else None,
        )
        session.add(event)

        if workspace.welcome_enabled and workspace.welcome_text:
            welcome = workspace.welcome_text.replace(
                "{nombre}", escape(request.from_user.full_name)
            ).replace("{canal}", escape(channel.title))
            try:
                await bot.send_message(request.user_chat_id, welcome)
            except TelegramAPIError as exc:
                logger.info("Could not send pre-approval welcome: %s", exc)

        if workspace.auto_approve:
            try:
                await bot.approve_chat_join_request(request.chat.id, request.from_user.id)
                event.approved = True
            except TelegramAPIError as exc:
                logger.warning("Could not auto-approve join request: %s", exc)
                event.approved = False
            await session.commit()
            return

        owner_ids = list(
            await session.scalars(
                select(Membership.user_id).where(
                    Membership.workspace_id == workspace.id,
                    Membership.role.in_([Role.owner, Role.admin]),
                )
            )
        )
        await session.commit()

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Aprobar",
                    callback_data=f"join:a:{request.chat.id}:{request.from_user.id}",
                ),
                InlineKeyboardButton(
                    text="❌ Rechazar",
                    callback_data=f"join:d:{request.chat.id}:{request.from_user.id}",
                ),
            ]
        ]
    )
    for owner_id in owner_ids:
        try:
            await bot.send_message(
                owner_id,
                f"🙋 <b>Nueva solicitud</b>\n{request.from_user.full_name} desea entrar a <b>{channel.title}</b>.",
                reply_markup=markup,
            )
        except TelegramAPIError as exc:
            logger.info("Could not notify workspace administrator: %s", exc)


async def user_can_manage(session, user_id: int, channel_id: int) -> bool:
    return bool(
        await session.scalar(
            select(Membership.id)
            .join(Channel, Channel.workspace_id == Membership.workspace_id)
            .where(
                Membership.user_id == user_id,
                Membership.role.in_([Role.owner, Role.admin]),
                Channel.telegram_chat_id == channel_id,
            )
        )
    )


@router.callback_query(F.data.startswith("join:"))
async def decide_join(callback: CallbackQuery, bot: Bot) -> None:
    _, decision, chat_id_text, user_id_text = callback.data.split(":", 3)
    chat_id, user_id = int(chat_id_text), int(user_id_text)
    async with SessionFactory() as session:
        if not await user_can_manage(session, callback.from_user.id, chat_id):
            await callback.answer("No tienes permiso para esta acción.", show_alert=True)
            return
        try:
            if decision == "a":
                await bot.approve_chat_join_request(chat_id, user_id)
                label = "✅ Solicitud aprobada"
                event = await session.scalar(
                    select(JoinRequestEvent)
                    .where(
                        JoinRequestEvent.channel_id == chat_id,
                        JoinRequestEvent.user_id == user_id,
                    )
                    .order_by(JoinRequestEvent.created_at.desc())
                )
                if event:
                    event.approved = True
                    await session.commit()
            else:
                await bot.decline_chat_join_request(chat_id, user_id)
                label = "❌ Solicitud rechazada"
            await callback.message.edit_text(label)
            await callback.answer()
        except TelegramAPIError:
            await callback.answer("Telegram no permitió completar la acción.", show_alert=True)
