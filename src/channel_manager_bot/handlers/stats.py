from html import escape
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select

from ..database import SessionFactory
from ..keyboards import (
    back_home,
    growth_channels_menu,
    stats_menu,
    stats_period_menu,
)
from ..models import Channel, ChannelMetricSnapshot, ChannelStatus
from ..repository import get_active_channels, get_workspace
from ..services.channel_sync import refresh_channels
from ..services.growth_stats import (
    best_posting_hours,
    channel_growth,
    member_metrics,
    publication_metrics,
    top_publications,
    workspace_summary,
)

router = Router(name="stats")


def _period_title(days: int) -> str:
    return {7: "7 días", 30: "30 días", 90: "90 días"}.get(days, f"{days} días")


def _signed(value: int | None) -> str:
    return "—" if value is None else f"{value:+,}"


async def _workspace(callback: CallbackQuery):
    async with SessionFactory() as session:
        return await get_workspace(session, callback.from_user.id)


@router.callback_query(F.data == "stats:show")
async def show_stats_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "📊 <b>Crecimiento y estadísticas</b>\n\n"
        "Consulta la evolución de tus chats, el rendimiento de publicaciones, solicitudes, "
        "reenvíos y enlaces de campaña. Todo se calcula por espacio de trabajo y se puede "
        "revisar desde Telegram.",
        reply_markup=stats_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "stats:period")
async def choose_stats_period(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "📊 <b>Resumen de crecimiento</b>\n\nElige el periodo que quieres comparar:",
        reply_markup=stats_period_menu(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("stats:overview:"))
async def show_stats_overview(callback: CallbackQuery, bot: Bot) -> None:
    days = int(callback.data.rsplit(":", 1)[1])
    workspace = await _workspace(callback)
    if workspace is None:
        await callback.message.edit_text("No se encontró tu cuenta.", reply_markup=back_home())
        await callback.answer()
        return
    await callback.answer("Actualizando estadísticas…")
    refresh = await refresh_channels(bot, workspace_id=workspace.id)
    async with SessionFactory() as session:
        summary = await workspace_summary(session, workspace.id, days)
    growth = summary["growth"]
    current_total = sum(item.current or 0 for item in growth)
    changes = [item.change for item in growth if item.change is not None]
    change_total = sum(changes) if changes else None
    publications = summary["publications"]
    members = summary["members"]
    lines = [
        f"📊 <b>Resumen · últimos {_period_title(days)}</b>",
        "",
        f"👥 Comunidad actual: <b>{current_total:,}</b>",
        f"📈 Cambio estimado: <b>{_signed(change_total)}</b>",
        f"📝 Publicaciones entregadas: <b>{publications.publications}</b>",
        f"✅ Entregas correctas: <b>{publications.successful:,}</b> "
        f"({publications.success_rate:.1f}%)",
        f"🙋 Solicitudes recibidas: <b>{members.received:,}</b>",
        f"✅ Solicitudes aprobadas: <b>{members.approved:,}</b>",
        f"⏳ Pendientes reales actuales: <b>{members.active_pending:,}</b>",
        f"↪️ Reenvíos correctos: <b>{summary['relay_successful']:,}</b>",
        f"⚠️ Reenvíos fallidos: <b>{summary['relay_failed']:,}</b>",
        "",
        "El cambio se basa en capturas históricas tomadas durante la sincronización de chats.",
    ]
    if refresh.failed:
        lines.append(f"⚠️ {refresh.failed} chat(s) no pudieron actualizarse ahora.")
    await callback.message.edit_text("\n".join(lines), reply_markup=stats_menu())


@router.callback_query(F.data == "stats:growth")
async def show_growth_channels(callback: CallbackQuery) -> None:
    await _render_growth_channels(callback, 30)
    await callback.answer()


@router.callback_query(F.data.startswith("stats:growth:"))
async def change_growth_period(callback: CallbackQuery) -> None:
    days = int(callback.data.rsplit(":", 1)[1])
    await _render_growth_channels(callback, days)
    await callback.answer()


async def _render_growth_channels(callback: CallbackQuery, days: int) -> None:
    workspace = await _workspace(callback)
    if workspace is None:
        await callback.message.edit_text("No se encontró tu cuenta.", reply_markup=back_home())
        return
    async with SessionFactory() as session:
        channels = await get_active_channels(session, workspace.id)
    await callback.message.edit_text(
        f"📈 <b>Crecimiento por chat · {_period_title(days)}</b>\n\n"
        "Selecciona un canal o grupo para ver su línea de crecimiento.",
        reply_markup=growth_channels_menu(channels, days),
    )


@router.callback_query(F.data.startswith("stats:channel:"))
async def show_channel_growth(callback: CallbackQuery) -> None:
    _, _, channel_text, days_text = callback.data.split(":", 3)
    channel_id, days = int(channel_text), int(days_text)
    workspace = await _workspace(callback)
    if workspace is None:
        await callback.answer("No se encontró tu cuenta.", show_alert=True)
        return
    async with SessionFactory() as session:
        channel = await session.scalar(
            select(Channel).where(
                Channel.telegram_chat_id == channel_id,
                Channel.workspace_id == workspace.id,
                Channel.status == ChannelStatus.active,
            )
        )
        snapshots = (
            list(
                await session.scalars(
                    select(ChannelMetricSnapshot)
                    .where(ChannelMetricSnapshot.channel_id == channel_id)
                    .order_by(ChannelMetricSnapshot.captured_at.desc())
                    .limit(8)
                )
            )
            if channel
            else []
        )
        metric = await channel_growth(session, channel, days) if channel else None
    if channel is None or metric is None:
        await callback.answer("Chat no encontrado.", show_alert=True)
        return
    lines = [
        f"📈 <b>{escape(metric.title)}</b>",
        f"Periodo: últimos {_period_title(days)}",
        "",
        f"Actual: <b>{metric.current or 0:,}</b>",
        (
            f"Base del periodo: <b>{metric.baseline:,}</b>"
            if metric.baseline is not None
            else "Base del periodo: <b>sin datos</b>"
        ),
        f"Cambio: <b>{_signed(metric.change)}</b>"
        + (f" ({metric.percent:+.1f}%)" if metric.percent is not None else ""),
        "",
        "Últimas capturas:",
    ]
    if snapshots:
        timezone = ZoneInfo(workspace.timezone)
        for snapshot in reversed(snapshots):
            local = snapshot.captured_at.astimezone(timezone)
            lines.append(f"• {local:%d/%m %H:%M} · {snapshot.member_count:,}")
    else:
        lines.append("• Todavía no hay capturas históricas; espera la próxima sincronización.")
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=growth_channels_menu([channel], days),
    )
    await callback.answer()


@router.callback_query(F.data == "stats:publications")
async def show_publication_stats(callback: CallbackQuery) -> None:
    workspace = await _workspace(callback)
    if workspace is None:
        await callback.answer("No se encontró tu cuenta.", show_alert=True)
        return
    async with SessionFactory() as session:
        metrics = await publication_metrics(session, workspace.id, 30)
        top = await top_publications(session, workspace.id, 30)
        hours = await best_posting_hours(session, workspace.id, workspace.timezone, 30)
    lines = [
        "📝 <b>Rendimiento de publicaciones · 30 días</b>",
        "",
        f"Publicaciones con entrega: <b>{metrics.publications}</b>",
        f"Entregas correctas: <b>{metrics.successful}</b>",
        f"Entregas fallidas: <b>{metrics.failed}</b>",
        f"Tasa de éxito: <b>{metrics.success_rate:.1f}%</b>",
        "",
        "🏆 <b>Mayor alcance por publicación</b>",
    ]
    if top:
        lines.extend(
            f"• {escape(preview.replace(chr(10), ' ')[:55])} · {deliveries} entrega(s)"
            for preview, deliveries in top
        )
    else:
        lines.append("• Todavía no hay entregas en este periodo.")
    lines.extend(["", "⏰ <b>Horas con más entregas</b>"])
    if hours:
        lines.extend(f"• {hour:02d}:00 · {count} entrega(s)" for hour, count in hours)
    else:
        lines.append("• Aún no hay suficiente historial.")
    await callback.message.edit_text("\n".join(lines), reply_markup=stats_menu())
    await callback.answer()


@router.callback_query(F.data == "stats:members")
async def show_member_stats(callback: CallbackQuery) -> None:
    workspace = await _workspace(callback)
    if workspace is None:
        await callback.answer("No se encontró tu cuenta.", show_alert=True)
        return
    async with SessionFactory() as session:
        metrics = await member_metrics(session, workspace.id, 30)
    conversion = metrics.approved / metrics.received * 100 if metrics.received else 0
    await callback.message.edit_text(
        "🙋 <b>Miembros y solicitudes · 30 días</b>\n\n"
        f"Solicitudes recibidas: <b>{metrics.received}</b>\n"
        f"Aprobadas: <b>{metrics.approved}</b> ({conversion:.1f}%)\n"
        f"Pendientes reales actuales: <b>{metrics.active_pending}</b>\n\n"
        "El contador pendiente toma solo el último estado conocido por usuario y chat; "
        "los reintentos y estados ya resueltos no inflan la cifra.",
        reply_markup=stats_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "stats:report")
async def send_stats_report(callback: CallbackQuery) -> None:
    workspace = await _workspace(callback)
    if workspace is None:
        await callback.answer("No se encontró tu cuenta.", show_alert=True)
        return
    async with SessionFactory() as session:
        summary = await workspace_summary(session, workspace.id, 30)
        top = await top_publications(session, workspace.id, 30)
    growth = summary["growth"]
    members = summary["members"]
    publications = summary["publications"]
    current_total = sum(item.current or 0 for item in growth)
    change_total = sum(item.change or 0 for item in growth if item.change is not None)
    lines = [
        "📄 <b>Reporte de crecimiento · últimos 30 días</b>",
        "",
        f"👥 Comunidad actual: <b>{current_total:,}</b>",
        f"📈 Variación estimada: <b>{change_total:+,}</b>",
        f"📝 Publicaciones: <b>{publications.publications}</b>",
        f"✅ Entregas correctas: <b>{publications.successful}</b>",
        f"🙋 Solicitudes: <b>{members.received}</b> · aprobadas <b>{members.approved}</b>",
        f"⏳ Pendientes reales: <b>{members.active_pending}</b>",
        "",
        "🏆 <b>Publicaciones con más entregas</b>",
    ]
    lines.extend(
        f"• {escape(preview.replace(chr(10), ' ')[:60])} · {deliveries}"
        for preview, deliveries in top
    )
    await callback.message.answer("\n".join(lines))
    await callback.answer("Reporte enviado")
