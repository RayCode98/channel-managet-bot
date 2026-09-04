import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message
from sqlalchemy import select

from ..database import SessionFactory
from ..keyboards import back_home, channel_detail_menu, channels_menu, welcome_buttons_menu
from ..models import AuditLog, Channel, ChannelStatus, Membership, WelcomeButton
from ..repository import (
    can_add_channel,
    ensure_user_workspace,
    get_active_channels,
    get_workspace,
    utcnow,
)
from ..services.welcome import (
    content_from_message,
    parse_welcome_buttons,
    send_channel_welcome,
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
    button_count = len(channel.welcome_buttons)
    status = "Activa" if channel.welcome_enabled else "Desactivada"
    farewell_status = "Activa" if channel.farewell_enabled else "Desactivada"
    await callback.message.edit_text(
        f"⚙️ <b>{escape(channel.title)}</b>\n\n"
        f"👋 <b>Bienvenida:</b> {status}\n"
        f"🔗 <b>Botones:</b> {button_count}\n\n"
        f"🚪 <b>Despedida:</b> {farewell_status}\n\n"
        "La bienvenida se envía al solicitar el ingreso. La despedida se intenta enviar cuando "
        "Telegram informa que un suscriptor abandonó el canal.",
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
        "Puede ser texto enriquecido o una foto con texto. También se aceptan video, "
        "animación, audio, voz o documento.\n\n"
        "Puedes insertar estas variables en el texto:\n"
        "• <code>{nombre}</code>: nombre de la persona que solicita entrar.\n"
        "• <code>{canal}</code>: nombre de este canal.\n\n"
        "Ejemplo: <code>Hola {nombre}, te damos la bienvenida a {canal}.</code>"
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
        content_type, text_template, file_id = content_from_message(message)
        channel.welcome_source_chat_id = message.chat.id
        channel.welcome_source_message_id = message.message_id
        channel.welcome_content_type = content_type
        channel.welcome_text_template = text_template
        channel.welcome_file_id = file_id
        channel.welcome_enabled = True
        await session.commit()
    await state.clear()
    await message.answer(
        "✅ Bienvenida guardada y activada. Las variables se reemplazarán para cada persona.",
        reply_markup=channel_detail_menu(channel),
    )


@router.callback_query(F.data.startswith("welcome:buttons:"))
async def ask_welcome_buttons(callback: CallbackQuery, state: FSMContext) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    if not channel.welcome_source_message_id:
        await callback.answer("Primero configura el contenido de bienvenida.", show_alert=True)
        return
    await state.set_state(ChannelWelcomeFlow.waiting_buttons)
    await state.update_data(channel_id=channel_id)
    await callback.message.answer(
        "🔗 Envía todos los botones en un solo mensaje, uno por línea, con este formato:\n\n"
        "<code>nombre botón - url - color</code>\n\n"
        "Ejemplo:\n"
        "<code>Unirme ahora - https://t.me/mi_canal - verde\n"
        "Ver reglas - https://example.com/reglas - azul\n"
        "Más información - https://example.com/info - normal</code>\n\n"
        "Colores disponibles: <b>azul, verde, rojo o normal</b>.\n"
        "Cada salto de línea crea otro botón. Envía <code>quitar</code> para dejar la bienvenida sin botones."
    )
    await callback.answer()


@router.message(ChannelWelcomeFlow.waiting_buttons, F.text)
async def receive_welcome_buttons(message: Message, state: FSMContext) -> None:
    remove_all = message.text.strip().lower() == "quitar"
    if not remove_all:
        try:
            parsed_buttons = parse_welcome_buttons(message.text)
        except ValueError as exc:
            await message.answer(f"⚠️ {escape(str(exc))}")
            return
    else:
        parsed_buttons = []

    data = await state.get_data()
    async with SessionFactory() as session:
        channel = await owned_channel(session, int(data["channel_id"]), message.from_user.id)
        if channel is None:
            await state.clear()
            await message.answer("Canal no encontrado.")
            return
        channel.welcome_buttons.clear()
        channel.welcome_button_text = None
        channel.welcome_button_url = None
        for row_index, button in enumerate(parsed_buttons):
            channel.welcome_buttons.append(
                WelcomeButton(
                    row_index=row_index,
                    position=0,
                    text=button.text,
                    url=button.url,
                    style=button.style,
                )
            )
        await session.commit()
    await state.clear()
    await message.answer(
        f"✅ Botones actualizados: <b>{len(parsed_buttons)}</b>.",
        reply_markup=channel_detail_menu(channel),
    )


@router.callback_query(F.data.startswith("welcome:manage:"))
async def manage_welcome_buttons(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    if not channel.welcome_buttons:
        await callback.answer("La bienvenida no tiene botones.", show_alert=True)
        return
    await callback.message.edit_text(
        f"🧹 <b>Botones de {escape(channel.title)}</b>\n\n"
        "Pulsa el botón que deseas eliminar. Los demás permanecerán sin cambios.",
        reply_markup=welcome_buttons_menu(channel.telegram_chat_id, channel.welcome_buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("welcome:bdel:"))
async def delete_welcome_button(callback: CallbackQuery) -> None:
    try:
        button_id = int(callback.data.rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("Botón inválido.", show_alert=True)
        return
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        button = await session.scalar(
            select(WelcomeButton)
            .join(Channel, Channel.telegram_chat_id == WelcomeButton.channel_id)
            .where(
                WelcomeButton.id == button_id,
                Channel.workspace_id == workspace.id,
                Channel.status == ChannelStatus.active,
            )
        )
        if button is None:
            await callback.answer("Botón no encontrado.", show_alert=True)
            return
        channel_id = button.channel_id
        await session.delete(button)
        await session.flush()
        remaining = list(
            await session.scalars(
                select(WelcomeButton)
                .where(WelcomeButton.channel_id == channel_id)
                .order_by(WelcomeButton.row_index, WelcomeButton.position)
            )
        )
        for row_index, remaining_button in enumerate(remaining):
            remaining_button.row_index = row_index
            remaining_button.position = 0
        await session.commit()
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("El canal ya no está disponible.", show_alert=True)
        return
    if channel.welcome_buttons:
        await callback.message.edit_reply_markup(
            reply_markup=welcome_buttons_menu(channel.telegram_chat_id, channel.welcome_buttons)
        )
    else:
        await callback.message.edit_text(
            f"⚙️ <b>{escape(channel.title)}</b>\n\nLa bienvenida quedó sin botones.",
            reply_markup=channel_detail_menu(channel),
        )
    await callback.answer("Botón eliminado")


@router.callback_query(F.data.startswith("welcome:preview:"))
async def preview_channel_welcome(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    if not channel.welcome_source_message_id:
        await callback.answer("Primero configura el contenido de bienvenida.", show_alert=True)
        return
    try:
        await send_channel_welcome(
            callback.bot,
            chat_id=callback.from_user.id,
            channel=channel,
            user_name=callback.from_user.full_name,
        )
    except TelegramAPIError as exc:
        logger.warning("Could not render welcome preview for %s: %s", channel_id, exc)
        await callback.answer("Telegram no pudo generar la vista previa.", show_alert=True)
        return
    await callback.answer("Vista previa enviada")


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
        channel.welcome_content_type = None
        channel.welcome_text_template = None
        channel.welcome_file_id = None
        channel.welcome_button_text = None
        channel.welcome_button_url = None
        channel.welcome_buttons.clear()
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
