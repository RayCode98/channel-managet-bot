import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery
from sqlalchemy import select

from ..database import SessionFactory
from ..keyboards import (
    alphabet_filter_menu,
    force_join_menu,
    force_target_menu,
    join_filter_menu,
)
from ..models import (
    AuditLog,
    Channel,
    ChannelStatus,
    JoinNameScript,
    JoinRequirement,
    RequirementChat,
)
from ..repository import get_active_channels, get_workspace, utcnow
from ..services.join_filters import SCRIPT_LABELS
from .channels import owned_channel

router = Router(name="join_filters")
logger = logging.getLogger(__name__)


def admin_capabilities(member) -> tuple[bool, bool, bool]:
    is_owner = member.status == ChatMemberStatus.CREATOR
    is_admin = is_owner or member.status == ChatMemberStatus.ADMINISTRATOR
    can_invite = is_owner or bool(getattr(member, "can_invite_users", False))
    can_restrict = is_owner or bool(getattr(member, "can_restrict_members", False))
    return is_admin, can_invite, can_restrict


def join_filter_text(channel: Channel) -> str:
    selected = len(channel.join_name_scripts)
    requirement = channel.join_requirement
    required_title = escape(requirement.target_title) if requirement else "No configurado"
    return (
        f"🛡 <b>Filtros de unión · {escape(channel.title)}</b>\n\n"
        f"🔤 <b>Filtro de escritura:</b> "
        f"{'Activo' if channel.join_name_filter_enabled else 'Desactivado'} "
        f"({selected} seleccionados)\n"
        f"🔗 <b>Forzar unión:</b> "
        f"{'Activo' if requirement and requirement.enabled else 'Desactivado'}\n"
        f"🎯 <b>Destino requerido:</b> {required_title}\n\n"
        "Los filtros se aplican antes de cualquier autoaceptado y no envían avisos al "
        "administrador."
    )


def alphabet_filter_text(channel: Channel) -> str:
    selected_codes = {item.script_code for item in channel.join_name_scripts}
    selected_labels = [SCRIPT_LABELS[code] for code in selected_codes if code in SCRIPT_LABELS]
    selection = ", ".join(sorted(selected_labels)) if selected_labels else "Ninguno"
    return (
        f"🔤 <b>Filtro de escritura · {escape(channel.title)}</b>\n\n"
        f"Estado: <b>{'Activo' if channel.join_name_filter_enabled else 'Desactivado'}</b>\n"
        f"Bloqueados: <b>{escape(selection)}</b>\n\n"
        "Si el nombre contiene al menos una letra de un sistema seleccionado, el bot "
        "bloqueará al solicitante y rechazará su entrada. Números, símbolos y emojis se ignoran.\n\n"
        "⚠️ Esto reconoce <b>sistemas de escritura Unicode</b>, no nacionalidad. Por ejemplo, "
        "árabe, persa y urdu comparten escritura; Han también puede aparecer en nombres japoneses."
    )


def force_join_text(channel: Channel) -> str:
    requirement = channel.join_requirement
    if requirement is None:
        detail = "Todavía no hay un canal o grupo requerido."
    else:
        detail = (
            f"Destino: <b>{escape(requirement.target_title)}</b>\n"
            f"Estado: <b>{'Activo' if requirement.enabled else 'Desactivado'}</b>"
        )
    return (
        f"🔗 <b>Forzar unión · {escape(channel.title)}</b>\n\n"
        f"{detail}\n\n"
        "Cuando llegue una solicitud, el bot comprobará si la persona ya pertenece al destino. "
        "Si no pertenece, le enviará un botón para unirse y otro para verificar. Al cumplirlo, "
        "aprobará automáticamente la solicitud."
    )


async def refresh_source_capabilities(bot: Bot, channel: Channel) -> tuple[bool, bool]:
    member = await bot.get_chat_member(channel.telegram_chat_id, bot.id)
    _, can_invite, can_restrict = admin_capabilities(member)
    channel.can_invite_users = can_invite
    channel.can_restrict_members = can_restrict
    channel.last_checked_at = utcnow()
    return can_invite, can_restrict


@router.callback_query(F.data.startswith("jfilter:menu:"))
async def show_join_filters(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    await callback.message.edit_text(
        join_filter_text(channel), reply_markup=join_filter_menu(channel)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("jfilter:alpha:"))
async def show_alphabet_filter(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    selected = {item.script_code for item in channel.join_name_scripts}
    await callback.message.edit_text(
        alphabet_filter_text(channel),
        reply_markup=alphabet_filter_menu(channel_id, selected, channel.join_name_filter_enabled),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("jfilter:script:"))
async def toggle_name_script(callback: CallbackQuery) -> None:
    _, _, script_code, channel_id_text = callback.data.split(":", 3)
    if script_code not in SCRIPT_LABELS:
        await callback.answer("Sistema de escritura inválido.", show_alert=True)
        return
    channel_id = int(channel_id_text)
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
        if channel is None:
            await callback.answer("Canal no encontrado.", show_alert=True)
            return
        existing = next(
            (item for item in channel.join_name_scripts if item.script_code == script_code), None
        )
        if existing is None:
            channel.join_name_scripts.append(JoinNameScript(script_code=script_code))
        else:
            channel.join_name_scripts.remove(existing)
            if not channel.join_name_scripts:
                channel.join_name_filter_enabled = False
        await session.commit()
        selected = {item.script_code for item in channel.join_name_scripts}
    await callback.message.edit_text(
        alphabet_filter_text(channel),
        reply_markup=alphabet_filter_menu(channel_id, selected, channel.join_name_filter_enabled),
    )
    await callback.answer("Selección actualizada")


@router.callback_query(F.data.startswith("jfilter:atoggle:"))
async def toggle_alphabet_filter(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
        if channel is None:
            await callback.answer("Canal no encontrado.", show_alert=True)
            return
        enabling = not channel.join_name_filter_enabled
        if enabling and not channel.join_name_scripts:
            await callback.answer("Selecciona al menos un sistema de escritura.", show_alert=True)
            return
        if enabling:
            try:
                can_invite, can_restrict = await refresh_source_capabilities(callback.bot, channel)
            except TelegramAPIError:
                await callback.answer("No pude comprobar los permisos del bot.", show_alert=True)
                return
            if not can_invite or not can_restrict:
                await session.commit()
                await callback.answer(
                    "Concede al bot Invitar usuarios y Restringir miembros.", show_alert=True
                )
                return
        channel.join_name_filter_enabled = enabling
        session.add(
            AuditLog(
                workspace_id=channel.workspace_id,
                actor_user_id=callback.from_user.id,
                action="join_filter.alphabet_toggled",
                details=f"channel_id={channel_id};enabled={enabling}",
            )
        )
        await session.commit()
        selected = {item.script_code for item in channel.join_name_scripts}
    await callback.message.edit_text(
        alphabet_filter_text(channel),
        reply_markup=alphabet_filter_menu(channel_id, selected, channel.join_name_filter_enabled),
    )
    await callback.answer("Filtro actualizado")


@router.callback_query(F.data.startswith("jfilter:force:"))
async def show_force_join(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    await callback.message.edit_text(
        force_join_text(channel),
        reply_markup=force_join_menu(channel_id, channel.join_requirement),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("jfilter:targets:"))
async def show_force_targets(callback: CallbackQuery) -> None:
    source_channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        source = (
            await owned_channel(session, source_channel_id, callback.from_user.id)
            if workspace
            else None
        )
        channels = await get_active_channels(session, workspace.id) if workspace else []
        groups = (
            list(
                await session.scalars(
                    select(RequirementChat)
                    .where(
                        RequirementChat.workspace_id == workspace.id,
                        RequirementChat.active.is_(True),
                    )
                    .order_by(RequirementChat.title)
                )
            )
            if workspace
            else []
        )
    if source is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    available = len(
        [item for item in channels if item.telegram_chat_id != source_channel_id]
    ) + len(groups)
    text = (
        f"🎯 <b>Destino requerido para {escape(source.title)}</b>\n\n"
        "Elige el canal o grupo al que deberán unirse los solicitantes.\n\n"
        "Para agregar un grupo a esta lista, añade el bot como administrador del grupo y "
        "concede <b>Invitar usuarios</b>. Los canales conectados aparecen automáticamente."
    )
    if not available:
        text += "\n\n⚠️ No hay otro canal ni grupo disponible todavía."
    await callback.message.edit_text(
        text,
        reply_markup=force_target_menu(source_channel_id, channels, groups),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("jfilter:target:"))
async def select_force_target(callback: CallbackQuery) -> None:
    _, _, target_kind, target_id_text, source_id_text = callback.data.split(":", 4)
    target_id = int(target_id_text)
    source_id = int(source_id_text)
    if target_kind not in {"c", "g"} or target_id == source_id:
        await callback.answer("Destino inválido.", show_alert=True)
        return

    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        source = await owned_channel(session, source_id, callback.from_user.id)
        if workspace is None or source is None:
            await callback.answer("Canal no encontrado.", show_alert=True)
            return
        if target_kind == "c":
            target = await session.scalar(
                select(Channel).where(
                    Channel.telegram_chat_id == target_id,
                    Channel.workspace_id == workspace.id,
                    Channel.status == ChannelStatus.active,
                )
            )
        else:
            target = await session.scalar(
                select(RequirementChat).where(
                    RequirementChat.telegram_chat_id == target_id,
                    RequirementChat.workspace_id == workspace.id,
                    RequirementChat.active.is_(True),
                )
            )
        if target is None:
            await callback.answer("Destino no disponible.", show_alert=True)
            return
        try:
            source_can_invite, _ = await refresh_source_capabilities(callback.bot, source)
            target_member = await callback.bot.get_chat_member(target_id, callback.bot.id)
            target_is_admin, target_can_invite, _ = admin_capabilities(target_member)
            target_chat = await callback.bot.get_chat(target_id)
        except TelegramAPIError:
            await callback.answer("No pude comprobar el acceso del bot.", show_alert=True)
            return
        if not source_can_invite:
            await session.commit()
            await callback.answer(
                "En el canal protegido, concede al bot Invitar usuarios.", show_alert=True
            )
            return
        if not target_is_admin:
            await callback.answer("El bot debe ser administrador en el destino.", show_alert=True)
            return

        if target_chat.username:
            invite_url = f"https://t.me/{target_chat.username}"
        else:
            if not target_can_invite:
                await callback.answer(
                    "El destino es privado: concede al bot Invitar usuarios.", show_alert=True
                )
                return
            try:
                invite = await callback.bot.create_chat_invite_link(
                    target_id,
                    name="Verificación de acceso",
                    creates_join_request=False,
                )
            except TelegramAPIError:
                await callback.answer("Telegram no permitió crear el enlace.", show_alert=True)
                return
            invite_url = invite.invite_link

        title = target_chat.title or target.title
        target.title = title
        target.username = target_chat.username
        if isinstance(target, RequirementChat):
            target.can_invite_users = target_can_invite
            target.last_checked_at = utcnow()
        requirement = await session.get(JoinRequirement, source_id)
        if requirement is None:
            requirement = JoinRequirement(channel_id=source_id)
            source.join_requirement = requirement
        requirement.target_chat_id = target_id
        requirement.target_title = title
        requirement.target_type = target_chat.type.value
        requirement.invite_url = invite_url
        requirement.enabled = True
        session.add(
            AuditLog(
                workspace_id=workspace.id,
                actor_user_id=callback.from_user.id,
                action="join_filter.requirement_set",
                details=f"channel_id={source_id};target_chat_id={target_id}",
            )
        )
        await session.commit()
    await callback.message.edit_text(
        force_join_text(source),
        reply_markup=force_join_menu(source_id, source.join_requirement),
    )
    await callback.answer("Requisito guardado")


@router.callback_query(F.data.startswith("jfilter:ftoggle:"))
async def toggle_force_join(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
        if channel is None or channel.join_requirement is None:
            await callback.answer("Primero elige un destino requerido.", show_alert=True)
            return
        enabling = not channel.join_requirement.enabled
        if enabling:
            try:
                can_invite, _ = await refresh_source_capabilities(callback.bot, channel)
                target_member = await callback.bot.get_chat_member(
                    channel.join_requirement.target_chat_id, callback.bot.id
                )
                target_is_admin, _, _ = admin_capabilities(target_member)
            except TelegramAPIError:
                await callback.answer("No pude comprobar los permisos del bot.", show_alert=True)
                return
            if not can_invite or not target_is_admin:
                await session.commit()
                await callback.answer(
                    "Revisa que el bot sea administrador en ambos chats y pueda invitar usuarios.",
                    show_alert=True,
                )
                return
        channel.join_requirement.enabled = enabling
        await session.commit()
    await callback.message.edit_text(
        force_join_text(channel),
        reply_markup=force_join_menu(channel_id, channel.join_requirement),
    )
    await callback.answer("Forzar unión actualizado")


@router.callback_query(F.data.startswith("jfilter:fclear:"))
async def clear_force_join(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
        if channel is None:
            await callback.answer("Canal no encontrado.", show_alert=True)
            return
        requirement = channel.join_requirement
        if requirement is not None:
            channel.join_requirement = None
            await session.commit()
    await callback.message.edit_text(
        force_join_text(channel),
        reply_markup=force_join_menu(channel_id, None),
    )
    await callback.answer("Requisito eliminado")
