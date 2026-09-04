from datetime import timedelta
from html import escape
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import func, select

from ..database import SessionFactory
from ..keyboards import (
    member_approval_label,
    member_interval_menu,
    member_settings_menu,
    members_channels_menu,
)
from ..models import AuditLog, Channel, JoinRequestEvent
from ..repository import get_active_channels, get_workspace, utcnow
from ..services.member_approvals import (
    APPROVAL_INTERVALS,
    PENDING_APPROVAL_OUTCOMES,
    pending_join_count,
    process_pending_join_requests,
)
from .channels import owned_channel

router = Router(name="members")


async def render_member_channels(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        channels = await get_active_channels(session, workspace.id) if workspace else []
        counts = (
            dict(
                (
                    await session.execute(
                        select(
                            JoinRequestEvent.channel_id,
                            func.count(JoinRequestEvent.id),
                        )
                        .join(Channel, Channel.telegram_chat_id == JoinRequestEvent.channel_id)
                        .where(
                            Channel.workspace_id == workspace.id,
                            JoinRequestEvent.approved.is_(False),
                            JoinRequestEvent.outcome.in_(
                                PENDING_APPROVAL_OUTCOMES | {"approval_processing"}
                            ),
                        )
                        .group_by(JoinRequestEvent.channel_id)
                    )
                ).all()
            )
            if workspace
            else {}
        )
    text = (
        "👥 <b>Miembros</b>\n\n"
        "Configura cómo se aprobarán las nuevas solicitudes de cada canal o grupo. "
        "Los lotes procesan hasta <b>200 solicitudes</b> por ejecución."
    )
    if not channels:
        text += "\n\nTodavía no hay canales o grupos vinculados."
    await callback.message.edit_text(
        text,
        reply_markup=members_channels_menu(channels, counts),
    )


async def render_member_settings(callback: CallbackQuery, channel_id: int) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        channel = await owned_channel(session, channel_id, callback.from_user.id)
        pending = await pending_join_count(session, channel_id) if channel else 0
    if channel is None or workspace is None:
        await callback.answer("Canal o grupo no encontrado.", show_alert=True)
        return
    next_run = "No programada"
    if channel.join_approval_next_run_at is not None:
        local_time = channel.join_approval_next_run_at.astimezone(ZoneInfo(workspace.timezone))
        next_run = local_time.strftime("%d/%m/%Y %H:%M")
    permission = "✅ Disponible" if channel.can_invite_users else "⚠️ Falta Invitar usuarios"
    text = (
        f"👥 <b>Miembros · {escape(channel.title)}</b>\n\n"
        f"Modo: <b>{member_approval_label(channel)}</b>\n"
        f"Pendientes conocidos: <b>{pending}</b>\n"
        f"Próxima ejecución: <b>{next_run}</b>\n"
        f"Permiso: <b>{permission}</b>\n\n"
        "• <b>Inmediato:</b> acepta cada solicitud nueva al recibirla.\n"
        "• <b>Por intervalos:</b> acepta hasta 200 en cada ejecución.\n"
        "• <b>Manual:</b> las deja pendientes hasta que uses Aprobar ahora u otro "
        "administrador actúe desde Telegram.\n\n"
        "Los filtros de escritura y la unión obligatoria se evalúan antes de cualquier "
        "aprobación."
    )
    await callback.message.edit_text(
        text,
        reply_markup=member_settings_menu(channel, pending),
    )


@router.callback_query(F.data.in_({"members:channels", "settings:show"}))
async def show_member_channels(callback: CallbackQuery) -> None:
    await render_member_channels(callback)
    await callback.answer()


@router.callback_query(F.data == "settings:auto_approve")
async def explain_legacy_setting(callback: CallbackQuery) -> None:
    await callback.answer(
        "Esta opción ahora se configura por canal desde Miembros.",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("members:chat:"))
async def show_member_settings(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    await render_member_settings(callback, channel_id)
    await callback.answer()


@router.callback_query(F.data.startswith("members:mode:"))
async def set_member_mode(callback: CallbackQuery) -> None:
    _, _, mode, channel_text = callback.data.split(":", 3)
    if mode not in {"manual", "immediate"}:
        await callback.answer("Modo inválido.", show_alert=True)
        return
    channel_id = int(channel_text)
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
        if channel is None:
            await callback.answer("Canal o grupo no encontrado.", show_alert=True)
            return
        if mode == "immediate" and not channel.can_invite_users:
            await callback.answer(
                "Concede primero al bot el permiso Invitar usuarios.", show_alert=True
            )
            return
        channel.join_approval_mode = mode
        channel.join_approval_interval_hours = None
        channel.join_approval_next_run_at = None
        session.add(
            AuditLog(
                workspace_id=channel.workspace_id,
                actor_user_id=callback.from_user.id,
                action="members.approval_mode_changed",
                details=f"chat_id={channel_id};mode={mode}",
            )
        )
        await session.commit()
    await render_member_settings(callback, channel_id)
    await callback.answer("Modo de aprobación actualizado")


@router.callback_query(F.data.startswith("members:intervals:"))
async def show_member_intervals(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal o grupo no encontrado.", show_alert=True)
        return
    await callback.message.edit_text(
        f"🕒 <b>Intervalo · {escape(channel.title)}</b>\n\n"
        "En cada ejecución se aprobarán como máximo 200 solicitudes pendientes. "
        "Si quedan más, continuarán en el siguiente intervalo.",
        reply_markup=member_interval_menu(channel_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("members:interval:"))
async def set_member_interval(callback: CallbackQuery) -> None:
    _, _, hours_text, channel_text = callback.data.split(":", 3)
    hours, channel_id = int(hours_text), int(channel_text)
    if hours not in APPROVAL_INTERVALS:
        await callback.answer("Intervalo inválido.", show_alert=True)
        return
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
        if channel is None:
            await callback.answer("Canal o grupo no encontrado.", show_alert=True)
            return
        if not channel.can_invite_users:
            await callback.answer(
                "Concede primero al bot el permiso Invitar usuarios.", show_alert=True
            )
            return
        channel.join_approval_mode = "scheduled"
        channel.join_approval_interval_hours = hours
        channel.join_approval_next_run_at = utcnow() + timedelta(hours=hours)
        session.add(
            AuditLog(
                workspace_id=channel.workspace_id,
                actor_user_id=callback.from_user.id,
                action="members.approval_interval_changed",
                details=f"chat_id={channel_id};hours={hours}",
            )
        )
        await session.commit()
    await render_member_settings(callback, channel_id)
    await callback.answer("Aprobación por intervalos activada")


@router.callback_query(F.data.startswith("members:approve:"))
async def approve_pending_now(callback: CallbackQuery, bot: Bot) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal o grupo no encontrado.", show_alert=True)
        return
    if not channel.can_invite_users:
        await callback.answer(
            "Concede primero al bot el permiso Invitar usuarios.", show_alert=True
        )
        return
    await callback.answer("Procesando hasta 200 solicitudes…")
    summary = await process_pending_join_requests(bot, channel_id)
    await render_member_settings(callback, channel_id)
    await callback.message.answer(
        "✅ <b>Lote finalizado</b>\n\n"
        f"Aprobadas: <b>{summary.approved}</b>\n"
        f"Ya no disponibles: <b>{summary.unavailable}</b>\n"
        f"Pendientes por error temporal: <b>{summary.failed}</b>"
    )
