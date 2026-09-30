import logging
import secrets
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message, ReplyKeyboardRemove
from sqlalchemy import select

from ..database import SessionFactory
from ..keyboards import (
    back_home,
    channel_detail_menu,
    channels_menu,
    chat_connection_keyboard,
    member_approval_label,
    welcome_buttons_menu,
    welcome_menu,
)
from ..models import AuditLog, Channel, ChannelStatus, Membership, Role, User, WelcomeButton
from ..repository import (
    can_add_channel,
    can_manage_workspace,
    ensure_user_workspace,
    get_managed_channels,
    get_workspace,
    utcnow,
)
from ..services.channel_sync import (
    apply_channel_snapshot,
    fetch_channel_snapshot,
    membership_permissions,
    normalize_chat_type,
    permission_issue_text,
    refresh_channels,
)
from ..services.welcome import (
    MAX_WELCOME_BUTTONS,
    content_from_message,
    parse_single_welcome_button,
    parse_welcome_buttons,
    send_channel_welcome,
)
from ..states import ChannelConnectionFlow, ChannelWelcomeFlow

router = Router(name="channels")
logger = logging.getLogger(__name__)


def chat_kind(channel: Channel) -> str:
    return "Grupo" if channel.chat_type in {"group", "supergroup"} else "Canal"


async def owned_channel(session, channel_id: int, user_id: int) -> Channel | None:
    workspace = await get_workspace(session, user_id)
    if workspace is None:
        return None
    return await session.scalar(
        select(Channel).where(
            Channel.telegram_chat_id == channel_id,
            Channel.workspace_id == workspace.id,
            Channel.status != ChannelStatus.removed,
        )
    )


async def render_channels_list(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        channels = await get_managed_channels(session, workspace.id) if workspace else []
    if channels:
        lines = ["📚 <b>Canales y grupos vinculados</b>", ""]
        for channel in channels:
            handle = f"@{channel.username}" if channel.username else "privado"
            count = (
                f" · {channel.member_count:,} miembros" if channel.member_count is not None else ""
            )
            icon = "👥" if channel.chat_type in {"group", "supergroup"} else "📢"
            lines.append(f"• {icon} <b>{escape(channel.title)}</b> ({handle}){count}")
        text = "\n".join(lines)
    else:
        text = (
            "📚 <b>Canales y grupos vinculados</b>\n\nTodavía no has agregado ningún canal o grupo."
        )
    try:
        await callback.message.edit_text(text, reply_markup=channels_menu(channels))
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


def channel_detail_text(channel: Channel) -> str:
    status = "Activa" if channel.welcome_enabled else "Desactivada"
    farewell_status = "Activa" if channel.farewell_enabled else "Desactivada"
    autocomplete_status = "Activo" if channel.autocomplete_enabled else "Desactivado"
    signature_status = "Activa" if channel.signature_enabled else "Desactivada"
    join_filter_status = (
        "Activo"
        if channel.join_name_filter_enabled
        or (channel.join_requirement and channel.join_requirement.enabled)
        else "Desactivado"
    )
    username = f"@{channel.username}" if channel.username else f"{chat_kind(channel)} privado"
    members = f"{channel.member_count:,}" if channel.member_count is not None else "No disponible"
    status_value = getattr(channel.status, "value", channel.status or ChannelStatus.active.value)
    connection_status = {
        ChannelStatus.active.value: "✅ Activo",
        ChannelStatus.missing_permissions.value: "⚠️ Faltan permisos",
        ChannelStatus.removed.value: "🚫 Sin acceso",
    }.get(status_value, "⚠️ Estado desconocido")
    permission_status = (
        f"⚠️ Faltan: {escape(channel.permission_issue)}"
        if channel.permission_issue
        else "✅ Publicación disponible"
    )
    permission_matrix = (
        f"Publicar {'✅' if channel.can_post_messages else '❌'} · "
        f"Eliminar {'✅' if channel.can_delete_messages else '❌'} · "
        f"Invitar {'✅' if channel.can_invite_users else '❌'}\n"
        f"Restringir {'✅' if channel.can_restrict_members else '❌'} · "
        f"Editar {'✅' if channel.can_edit_messages else '❌'} · "
        f"Fijar {'✅' if channel.can_pin_messages else '❌'} · "
        f"Temas {'✅' if channel.can_manage_topics else '❌'}"
    )
    checked = (
        channel.last_checked_at.strftime("%d/%m/%Y %H:%M UTC")
        if channel.last_checked_at
        else "Pendiente"
    )
    return (
        f"⚙️ <b>{escape(channel.title)}</b>\n\n"
        f"🏷 <b>Tipo:</b> {chat_kind(channel)}\n"
        f"🔌 <b>Conexión:</b> {connection_status}\n"
        f"🔗 <b>Usuario:</b> {escape(username)}\n"
        f"👥 <b>Miembros:</b> {members}\n"
        f"🔄 <b>Última sincronización:</b> {checked}\n\n"
        f"🔐 <b>Permisos:</b> {permission_status}\n{permission_matrix}\n\n"
        f"👋 <b>Bienvenida:</b> {status}\n"
        f"🚪 <b>Despedida:</b> {farewell_status}\n"
        f"🪄 <b>Autocompletado:</b> {autocomplete_status}\n"
        f"✍️ <b>Firma:</b> {signature_status}\n"
        f"🛡 <b>Filtros de unión:</b> {join_filter_status}\n"
        f"👥 <b>Aprobación de miembros:</b> {member_approval_label(channel)}\n\n"
        "Estas funciones se administran ahora desde sus botones independientes del menú principal."
    )


def welcome_menu_text(channel: Channel) -> str:
    return (
        f"👋 <b>Bienvenida de {escape(channel.title)}</b>\n\n"
        f"Estado: <b>{'Activa' if channel.welcome_enabled else 'Desactivada'}</b>\n"
        f"Botones: <b>{len(channel.welcome_buttons)}</b>\n\n"
        "Puedes configurar contenido, variables, botones y vista previa para este chat."
    )


@router.callback_query(F.data == "channels:list")
async def list_channels(callback: CallbackQuery) -> None:
    await render_channels_list(callback)
    await callback.answer()


@router.callback_query(F.data == "channels:refresh")
async def refresh_channels_list(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
    if workspace is None:
        await callback.answer("Cuenta no encontrada.", show_alert=True)
        return
    await callback.answer("Sincronizando canales y grupos…")
    await refresh_channels(callback.bot, workspace_id=workspace.id)
    await render_channels_list(callback)


@router.callback_query(F.data.startswith("channel:open:"))
async def open_channel(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal o grupo no encontrado.", show_alert=True)
        return
    await callback.message.edit_text(
        channel_detail_text(channel),
        reply_markup=channel_detail_menu(channel),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("channel:refresh:"))
async def refresh_one_channel(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    await callback.answer("Sincronizando chat…")
    await refresh_channels(
        callback.bot,
        workspace_id=channel.workspace_id,
        channel_ids={channel_id},
    )
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await render_channels_list(callback)
        return
    await callback.message.edit_text(
        channel_detail_text(channel),
        reply_markup=channel_detail_menu(channel),
    )


@router.callback_query(F.data.startswith("channel:diagnose:"))
async def diagnose_channel(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal o grupo no encontrado.", show_alert=True)
        return
    await callback.answer("Consultando permisos en Telegram…")
    try:
        snapshot = await fetch_channel_snapshot(callback.bot, channel_id)
    except TelegramAPIError as exc:
        logger.info("Permission diagnostic failed for %s: %s", channel_id, exc)
        await callback.message.edit_text(
            channel_detail_text(channel)
            + "\n\n❌ Telegram no permitió consultar este chat. "
            "Confirma que el bot siga siendo administrador.",
            reply_markup=channel_detail_menu(channel),
        )
        return
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
        if channel is None:
            await callback.answer("Canal o grupo no encontrado.", show_alert=True)
            return
        apply_channel_snapshot(channel, snapshot)
        channel.connection_method = channel.connection_method or "membership_event"
        await session.commit()
    await callback.message.edit_text(
        channel_detail_text(channel),
        reply_markup=channel_detail_menu(channel),
    )


@router.callback_query(F.data.startswith("channel:admins:"))
async def sync_channel_administrators(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
        allowed = bool(
            channel
            and await can_manage_workspace(session, channel.workspace_id, callback.from_user.id)
        )
    if channel is None:
        await callback.answer("Canal o grupo no encontrado.", show_alert=True)
        return
    if not allowed:
        await callback.answer(
            "Solo un propietario o administrador puede sincronizar miembros.",
            show_alert=True,
        )
        return
    await callback.answer("Sincronizando administradores…")
    try:
        administrators = await callback.bot.get_chat_administrators(channel_id)
    except TelegramAPIError as exc:
        logger.info("Could not sync administrators for %s: %s", channel_id, exc)
        await callback.message.answer("Telegram no permitió consultar los administradores.")
        return
    added = 0
    names: list[str] = []
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
        if channel is None:
            await callback.message.answer("Canal o grupo no encontrado.")
            return
        for administrator in administrators:
            telegram_user = administrator.user
            if telegram_user.is_bot:
                continue
            user = await session.get(User, telegram_user.id)
            if user is None:
                user = User(
                    telegram_id=telegram_user.id,
                    username=telegram_user.username,
                    full_name=telegram_user.full_name,
                )
                session.add(user)
            else:
                user.username = telegram_user.username
                user.full_name = telegram_user.full_name
            existing = await session.scalar(
                select(Membership).where(
                    Membership.workspace_id == channel.workspace_id,
                    Membership.user_id == telegram_user.id,
                )
            )
            if existing is None:
                session.add(
                    Membership(
                        workspace_id=channel.workspace_id,
                        user_id=telegram_user.id,
                        role=Role.editor,
                    )
                )
                added += 1
            names.append(telegram_user.full_name)
        session.add(
            AuditLog(
                workspace_id=channel.workspace_id,
                actor_user_id=callback.from_user.id,
                action="chat.admins_synced",
                details=f"chat_id={channel_id};admins={len(names)};added={added}",
            )
        )
        await session.commit()
    preview = ", ".join(escape(name) for name in names[:10]) or "No se encontraron administradores"
    if len(names) > 10:
        preview += f" y {len(names) - 10} más"
    await callback.message.edit_text(
        channel_detail_text(channel)
        + f"\n\n👥 <b>Administradores sincronizados:</b> {len(names)}\n"
        + f"Nuevos colaboradores: <b>{added}</b>\n{preview}",
        reply_markup=channel_detail_menu(channel),
    )


@router.callback_query(F.data.startswith("welcome:menu:"))
async def show_welcome_menu(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    await callback.message.edit_text(
        welcome_menu_text(channel),
        reply_markup=welcome_menu(channel),
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
        "• <code>{canal}</code>: nombre de este canal o grupo.\n\n"
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
            await message.answer("Canal o grupo no encontrado.")
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
        reply_markup=welcome_menu(channel),
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
        reply_markup=welcome_menu(channel),
    )


@router.callback_query(F.data.startswith("welcome:add:"))
async def ask_extra_welcome_button(callback: CallbackQuery, state: FSMContext) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    if not channel.welcome_source_message_id:
        await callback.answer("Primero configura el contenido de bienvenida.", show_alert=True)
        return
    if len(channel.welcome_buttons) >= MAX_WELCOME_BUTTONS:
        await callback.answer(
            f"Puedes configurar hasta {MAX_WELCOME_BUTTONS} botones.",
            show_alert=True,
        )
        return
    await state.set_state(ChannelWelcomeFlow.waiting_extra_button)
    await state.update_data(channel_id=channel_id)
    await callback.message.answer(
        "➕ Envía el botón nuevo en una sola línea con este formato:\n\n"
        "<code>nombre botón - url - color</code>\n\n"
        "Ejemplo: <code>Ver catálogo - https://example.com/catalogo - azul</code>\n"
        "Colores disponibles: <b>azul, verde, rojo o normal</b>.\n"
        "Los botones existentes se conservarán sin cambios.",
    )
    await callback.answer()


@router.message(ChannelWelcomeFlow.waiting_extra_button, F.text)
async def receive_extra_welcome_button(message: Message, state: FSMContext) -> None:
    try:
        parsed_button = parse_single_welcome_button(message.text)
    except ValueError as exc:
        await message.answer(f"⚠️ {escape(str(exc))}")
        return

    data = await state.get_data()
    async with SessionFactory() as session:
        channel = await owned_channel(session, int(data["channel_id"]), message.from_user.id)
        if channel is None:
            await state.clear()
            await message.answer("Canal no encontrado.")
            return
        if not channel.welcome_source_message_id:
            await state.clear()
            await message.answer("Primero configura el contenido de bienvenida.")
            return
        if len(channel.welcome_buttons) >= MAX_WELCOME_BUTTONS:
            await state.clear()
            await message.answer(
                f"Ya tienes el máximo de {MAX_WELCOME_BUTTONS} botones configurados."
            )
            return
        channel.welcome_buttons.append(
            WelcomeButton(
                row_index=len(channel.welcome_buttons),
                position=0,
                text=parsed_button.text,
                url=parsed_button.url,
                style=parsed_button.style,
            )
        )
        await session.commit()

    await state.clear()
    await message.answer(
        f"✅ Botón agregado. La bienvenida ahora tiene <b>{len(channel.welcome_buttons)}</b> botones.",
        reply_markup=welcome_buttons_menu(channel.telegram_chat_id, channel.welcome_buttons),
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
            f"👋 <b>{escape(channel.title)}</b>\n\nLa bienvenida quedó sin botones.",
            reply_markup=welcome_menu(channel),
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
    await callback.message.edit_text(
        welcome_menu_text(channel),
        reply_markup=welcome_menu(channel),
    )
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
        f"👋 <b>{escape(channel.title)}</b>\n\nLa bienvenida personalizada fue eliminada.",
        reply_markup=welcome_menu(channel),
    )
    await callback.answer()


@router.callback_query(F.data == "channels:add")
async def add_channel_instructions(callback: CallbackQuery, state: FSMContext) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        allowed = bool(
            workspace
            and await can_manage_workspace(session, workspace.id, callback.from_user.id)
            and await can_add_channel(session, workspace.id)
        )
    if not allowed:
        await callback.answer(
            "Solo un propietario/administrador puede agregar chats, o alcanzaste el límite.",
            show_alert=True,
        )
        return
    request_id = secrets.randbelow(2_000_000_000 - 2) + 1
    await state.set_state(ChannelConnectionFlow.waiting_chat_share)
    await state.update_data(chat_request_id=request_id)
    await callback.message.edit_text(
        "➕ <b>Agregar un canal o grupo</b>\n\n"
        "Usa los botones nativos de Telegram para seleccionar el chat que ya conectaste. "
        "Así evitamos confundir canales con grupos o cuentas distintas.\n\n"
        "El bot debe ser administrador. Para publicar en un canal concede "
        "<b>Publicar mensajes</b>; para filtros de unión agrega también "
        "<b>Invitar usuarios</b> y <b>Restringir miembros</b>.\n\n"
        "La persona que selecciona el chat debe ser administradora de ese chat.",
        reply_markup=back_home(),
    )
    await callback.message.answer(
        "Selecciona un chat conectado:",
        reply_markup=chat_connection_keyboard(request_id),
    )
    await callback.answer()


@router.message(
    ChannelConnectionFlow.waiting_chat_share,
    F.chat.type == ChatType.PRIVATE,
    F.chat_shared,
)
async def connect_shared_chat(message: Message, state: FSMContext, bot: Bot) -> None:
    shared = message.chat_shared
    data = await state.get_data()
    expected_request_id = data.get("chat_request_id")
    if expected_request_id not in {shared.request_id, shared.request_id - 1}:
        await message.answer("⚠️ Esta selección no pertenece a una solicitud activa.")
        return
    try:
        actor_member = await bot.get_chat_member(shared.chat_id, message.from_user.id)
        if actor_member.status not in {
            ChatMemberStatus.CREATOR,
            ChatMemberStatus.ADMINISTRATOR,
        }:
            await message.answer(
                "⚠️ Debes ser administrador o propietario del chat para conectarlo."
            )
            return
        snapshot = await fetch_channel_snapshot(bot, shared.chat_id)
        chat = await bot.get_chat(shared.chat_id)
    except TelegramAPIError as exc:
        logger.info("Explicit chat connection failed for %s: %s", shared.chat_id, exc)
        await message.answer(
            "❌ No pude consultar ese chat. Confirma que el bot siga siendo administrador "
            "y vuelve a pulsar Seleccionar canal o Seleccionar grupo."
        )
        return

    async with SessionFactory() as session:
        workspace = await ensure_user_workspace(session, message.from_user)
        if not await can_manage_workspace(session, workspace.id, message.from_user.id):
            await message.answer("⚠️ Solo un propietario o administrador puede conectar chats.")
            return
        existing = await session.get(Channel, shared.chat_id)
        if existing is not None and existing.workspace_id != workspace.id:
            member_of_owner_workspace = await session.scalar(
                select(Membership.id).where(
                    Membership.workspace_id == existing.workspace_id,
                    Membership.user_id == message.from_user.id,
                )
            )
            if member_of_owner_workspace is None:
                await message.answer(
                    "⚠️ Este chat ya está vinculado a otro espacio de trabajo. "
                    "Debe desvincularlo su propietario."
                )
                return
        if existing is None and not await can_add_channel(session, workspace.id):
            await message.answer("⚠️ Alcanzaste el límite de chats vinculados.")
            return
        if existing is None:
            existing = Channel(
                telegram_chat_id=shared.chat_id,
                workspace_id=workspace.id,
                title=chat.title or shared.title or str(shared.chat_id),
                username=chat.username or shared.username,
                chat_type=normalize_chat_type(chat.type),
                added_by_user_id=message.from_user.id,
            )
            session.add(existing)
        apply_channel_snapshot(existing, snapshot)
        existing.connection_method = "chat_shared"
        session.add(
            AuditLog(
                workspace_id=existing.workspace_id,
                actor_user_id=message.from_user.id,
                action="chat.connected_explicit",
                details=(
                    f"chat_id={shared.chat_id};type={snapshot.chat_type};"
                    f"status={snapshot.status.value};issue={snapshot.permission_issue or 'none'}"
                ),
            )
        )
        await session.commit()
    await state.clear()
    status_line = (
        "✅ Puede publicar."
        if snapshot.status == ChannelStatus.active
        else "⚠️ Está conectado, pero necesita permisos para publicar."
    )
    issue_line = (
        f"\nPermisos a revisar: <b>{escape(snapshot.permission_issue)}</b>."
        if snapshot.permission_issue
        else ""
    )
    await message.answer(
        f"✅ <b>{escape(existing.title)}</b> quedó conectado.\n{status_line}{issue_line}",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(ChannelConnectionFlow.waiting_chat_share, F.chat.type == ChatType.PRIVATE, F.text)
async def cancel_chat_connection(message: Message, state: FSMContext) -> None:
    if message.text.strip().casefold() != "❌ cancelar":
        await message.answer("Usa los botones de selección o pulsa ❌ Cancelar.")
        return
    await state.clear()
    await message.answer("Operación cancelada.", reply_markup=ReplyKeyboardRemove())


@router.my_chat_member(F.chat.type.in_({ChatType.CHANNEL, ChatType.GROUP, ChatType.SUPERGROUP}))
async def bot_membership_changed(event: ChatMemberUpdated, bot: Bot) -> None:
    actor = event.from_user
    chat_type = normalize_chat_type(event.chat.type)
    logger.info(
        "Bot membership change received: chat_id=%s type=%s actor_user_id=%s old=%s new=%s",
        event.chat.id,
        chat_type,
        actor.id,
        event.old_chat_member.status,
        event.new_chat_member.status,
    )
    async with SessionFactory() as session:
        workspace = await ensure_user_workspace(session, actor)
        existing = await session.get(Channel, event.chat.id)
        new_member = event.new_chat_member
        is_owner = new_member.status == ChatMemberStatus.CREATOR
        is_admin = is_owner or new_member.status == ChatMemberStatus.ADMINISTRATOR
        permissions = membership_permissions(new_member, chat_type)
        can_post = permissions["can_post_messages"]
        can_invite = permissions["can_invite_users"]
        can_restrict = permissions["can_restrict_members"]

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
                        "⚠️ Este chat ya está vinculado a otra cuenta. Debe desvincularlo su propietario.",
                    )
                    return
            if existing is None and not await can_add_channel(session, workspace.id):
                await bot.send_message(
                    actor.id, "⚠️ No pude agregar el chat: alcanzaste el límite de tu cuenta."
                )
                return
            if existing is None:
                existing = Channel(
                    telegram_chat_id=event.chat.id,
                    workspace_id=workspace.id,
                    title=event.chat.title or str(event.chat.id),
                    username=event.chat.username,
                    chat_type=chat_type,
                    added_by_user_id=actor.id,
                )
                session.add(existing)
            existing.title = event.chat.title or existing.title
            existing.username = event.chat.username
            existing.chat_type = chat_type
            existing.status = (
                ChannelStatus.active if can_post else ChannelStatus.missing_permissions
            )
            existing.can_post_messages = can_post
            existing.can_invite_users = can_invite
            existing.can_restrict_members = can_restrict
            existing.can_delete_messages = permissions["can_delete_messages"]
            existing.can_edit_messages = permissions["can_edit_messages"]
            existing.can_pin_messages = permissions["can_pin_messages"]
            existing.can_manage_topics = permissions["can_manage_topics"]
            existing.permission_issue = permission_issue_text(permissions, chat_type)
            existing.connection_method = "membership_event"
            existing.last_checked_at = utcnow()
            session.add(
                AuditLog(
                    workspace_id=existing.workspace_id,
                    actor_user_id=actor.id,
                    action="chat.connected",
                    details=(
                        f"chat_id={event.chat.id};type={chat_type};"
                        f"can_post={can_post};"
                        f"can_invite={can_invite};can_restrict={can_restrict};"
                        f"issue={existing.permission_issue or 'none'}"
                    ),
                )
            )
            await session.commit()
            logger.info(
                "Chat connection saved: chat_id=%s workspace_id=%s status=%s",
                existing.telegram_chat_id,
                existing.workspace_id,
                existing.status,
            )
            if can_post:
                await bot.send_message(
                    actor.id, f"✅ <b>{escape(existing.title)}</b> quedó conectado correctamente."
                )
            else:
                await bot.send_message(
                    actor.id,
                    f"⚠️ <b>{escape(existing.title)}</b> necesita permisos para publicar.",
                )
            return

        if existing is not None and new_member.status in {
            ChatMemberStatus.LEFT,
            ChatMemberStatus.KICKED,
            ChatMemberStatus.MEMBER,
        }:
            existing.status = ChannelStatus.removed
            existing.can_post_messages = False
            existing.can_invite_users = False
            existing.can_restrict_members = False
            existing.can_delete_messages = False
            existing.can_edit_messages = False
            existing.can_pin_messages = False
            existing.can_manage_topics = False
            existing.permission_issue = "Telegram no permite acceder a este chat"
            session.add(
                AuditLog(
                    workspace_id=existing.workspace_id,
                    actor_user_id=actor.id,
                    action="chat.disconnected",
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
