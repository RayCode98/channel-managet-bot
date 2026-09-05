import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, ChatJoinRequest
from sqlalchemy import select

from ..database import SessionFactory
from ..keyboards import join_verification_menu
from ..models import Channel, ChannelStatus, JoinRequestEvent, Membership, Role
from ..repository import utcnow
from ..services.join_filters import blocked_name_scripts, is_current_member
from ..services.welcome import send_channel_welcome

router = Router(name="joins")
logger = logging.getLogger(__name__)


async def send_welcome_silently(
    bot: Bot, *, chat_id: int, channel: Channel, user_name: str
) -> None:
    if not (
        channel.welcome_enabled
        and channel.welcome_source_chat_id
        and channel.welcome_source_message_id
    ):
        return
    try:
        await send_channel_welcome(
            bot,
            chat_id=chat_id,
            channel=channel,
            user_name=user_name,
        )
    except TelegramAPIError as exc:
        logger.info("Could not send channel welcome: %s", exc)


async def block_filtered_request(bot: Bot, *, channel_id: int, user_id: int) -> bool:
    """Ban the requester; fall back to declining the current request."""
    try:
        await bot.ban_chat_member(channel_id, user_id)
    except TelegramAPIError as ban_error:
        logger.warning("Could not ban filtered join requester: %s", ban_error)
        try:
            await bot.decline_chat_join_request(channel_id, user_id)
        except TelegramAPIError as decline_error:
            logger.warning("Could not decline filtered join requester: %s", decline_error)
            return False
        return True
    try:
        await bot.decline_chat_join_request(channel_id, user_id)
    except TelegramAPIError:
        # Banning can consume the pending request, so a failed decline is expected here.
        pass
    return True


@router.chat_join_request()
async def process_join_request(request: ChatJoinRequest, bot: Bot) -> None:
    async with SessionFactory() as session:
        channel = await session.get(Channel, request.chat.id)
        if channel is None or channel.status != ChannelStatus.active:
            return
        event = JoinRequestEvent(
            channel_id=channel.telegram_chat_id,
            user_id=request.from_user.id,
            user_chat_id=request.user_chat_id,
            invite_link=request.invite_link.invite_link if request.invite_link else None,
        )
        session.add(event)

        if channel.join_name_filter_enabled:
            selected_scripts = {item.script_code for item in channel.join_name_scripts}
            matched = blocked_name_scripts(request.from_user.full_name, selected_scripts)
            if matched:
                blocked = await block_filtered_request(
                    bot,
                    channel_id=request.chat.id,
                    user_id=request.from_user.id,
                )
                event.outcome = "alphabet_blocked" if blocked else "moderation_failed"
                await session.commit()
                return

        requirement = channel.join_requirement
        if requirement is not None and requirement.enabled:
            try:
                target_member = await bot.get_chat_member(
                    requirement.target_chat_id, request.from_user.id
                )
                requirement_met = is_current_member(target_member)
            except TelegramAPIError as exc:
                logger.warning("Could not verify required membership: %s", exc)
                requirement_met = False
                event.outcome = "membership_check_failed"
            if not requirement_met:
                try:
                    await bot.send_message(
                        request.user_chat_id,
                        f"🔐 Para aprobar tu solicitud de acceso a "
                        f"<b>{escape(channel.title)}</b>, primero únete a "
                        f"<b>{escape(requirement.target_title)}</b>.\n\n"
                        "Después pulsa <b>Ya me uní, verificar</b>.",
                        reply_markup=join_verification_menu(
                            requirement.invite_url,
                            channel.telegram_chat_id,
                            request.from_user.id,
                        ),
                    )
                    if event.outcome != "membership_check_failed":
                        event.outcome = "requirement_pending"
                except TelegramAPIError as exc:
                    logger.info("Could not send required membership prompt: %s", exc)
                    event.outcome = "requirement_message_failed"
                await session.commit()
                return

            await send_welcome_silently(
                bot,
                chat_id=request.user_chat_id,
                channel=channel,
                user_name=request.from_user.full_name,
            )
            try:
                await bot.approve_chat_join_request(request.chat.id, request.from_user.id)
                event.approved = True
                event.outcome = "approved_requirement"
                event.approved_at = utcnow()
            except TelegramAPIError as exc:
                logger.warning("Could not approve verified join request: %s", exc)
                event.outcome = "approval_failed"
            await session.commit()
            return

        await send_welcome_silently(
            bot,
            chat_id=request.user_chat_id,
            channel=channel,
            user_name=request.from_user.full_name,
        )
        if channel.join_approval_mode == "immediate":
            try:
                await bot.approve_chat_join_request(request.chat.id, request.from_user.id)
                event.approved = True
                event.outcome = "approved_auto"
                event.approved_at = utcnow()
            except TelegramAPIError as exc:
                logger.warning("Could not auto-approve join request: %s", exc)
                event.approved = False
                event.outcome = "approval_failed"
            await session.commit()
            return
        event.outcome = (
            "pending_scheduled" if channel.join_approval_mode == "scheduled" else "pending_manual"
        )
        await session.commit()


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
                    event.outcome = "approved_manual"
                    event.approved_at = utcnow()
                    await session.commit()
            else:
                await bot.decline_chat_join_request(chat_id, user_id)
                label = "❌ Solicitud rechazada"
                event = await session.scalar(
                    select(JoinRequestEvent)
                    .where(
                        JoinRequestEvent.channel_id == chat_id,
                        JoinRequestEvent.user_id == user_id,
                    )
                    .order_by(JoinRequestEvent.created_at.desc())
                )
                if event:
                    event.outcome = "declined_manual"
                    await session.commit()
            await callback.message.edit_text(label)
            await callback.answer()
        except TelegramAPIError:
            await callback.answer("Telegram no permitió completar la acción.", show_alert=True)


@router.callback_query(F.data.startswith("joinverify:"))
async def verify_required_membership(callback: CallbackQuery, bot: Bot) -> None:
    _, channel_id_text, user_id_text = callback.data.split(":", 2)
    channel_id, user_id = int(channel_id_text), int(user_id_text)
    if callback.from_user.id != user_id:
        await callback.answer("Este botón pertenece a otra solicitud.", show_alert=True)
        return

    async with SessionFactory() as session:
        channel = await session.get(Channel, channel_id)
        requirement = channel.join_requirement if channel else None
        if (
            channel is None
            or channel.status != ChannelStatus.active
            or requirement is None
            or not requirement.enabled
        ):
            await callback.answer("Este requisito ya no está disponible.", show_alert=True)
            return
        try:
            target_member = await bot.get_chat_member(requirement.target_chat_id, user_id)
        except TelegramAPIError as exc:
            logger.warning("Could not recheck required membership: %s", exc)
            await callback.answer("No pude verificarlo ahora. Intenta nuevamente.", show_alert=True)
            return
        if not is_current_member(target_member):
            await callback.answer(
                f"Aún no apareces dentro de {requirement.target_title}.",
                show_alert=True,
            )
            return

        await send_welcome_silently(
            bot,
            chat_id=callback.message.chat.id,
            channel=channel,
            user_name=callback.from_user.full_name,
        )
        try:
            await bot.approve_chat_join_request(channel_id, user_id)
        except TelegramAPIError as exc:
            logger.warning("Could not approve request after membership verification: %s", exc)
            await callback.answer(
                "La solicitud ya no está pendiente o Telegram no permitió aprobarla.",
                show_alert=True,
            )
            return
        event = await session.scalar(
            select(JoinRequestEvent)
            .where(
                JoinRequestEvent.channel_id == channel_id,
                JoinRequestEvent.user_id == user_id,
            )
            .order_by(JoinRequestEvent.created_at.desc())
        )
        if event:
            event.approved = True
            event.outcome = "approved_requirement"
            event.approved_at = utcnow()
        await session.commit()
    await callback.message.edit_text(f"✅ Solicitud aprobada para <b>{escape(channel.title)}</b>.")
    await callback.answer("Membresía verificada")
