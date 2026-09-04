from html import escape

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import func, select

from ..database import SessionFactory
from ..keyboards import back_home
from ..models import Channel, JoinRequestEvent, Publication, PublicationStatus, PublishedMessage
from ..repository import get_active_channels, get_workspace
from ..services.channel_sync import refresh_channels

router = Router(name="stats")


@router.callback_query(F.data == "stats:show")
async def show_stats(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer("Actualizando estadísticas…")
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
    if workspace is None:
        await callback.message.edit_text("No se encontró tu cuenta.", reply_markup=back_home())
        return
    summary = await refresh_channels(bot, workspace_id=workspace.id)
    async with SessionFactory() as session:
        channels = await get_active_channels(session, workspace.id)
        lines = ["📊 <b>Estadísticas actuales</b>", ""]
        total_members = 0
        for channel in channels:
            if channel.member_count is None:
                lines.append(f"• <b>{escape(channel.title)}</b>: no disponible")
                continue
            total_members += channel.member_count
            change = (
                channel.member_count - channel.previous_member_count
                if channel.previous_member_count is not None
                else None
            )
            change_text = f" ({change:+d})" if change is not None else ""
            lines.append(f"• <b>{escape(channel.title)}</b>: {channel.member_count:,}{change_text}")

        published = await session.scalar(
            select(func.count())
            .select_from(Publication)
            .where(
                Publication.workspace_id == workspace.id,
                Publication.status.in_([PublicationStatus.published, PublicationStatus.partial]),
            )
        )
        successful_deliveries = await session.scalar(
            select(func.count())
            .select_from(PublishedMessage)
            .join(Publication, Publication.id == PublishedMessage.publication_id)
            .where(Publication.workspace_id == workspace.id, PublishedMessage.succeeded.is_(True))
        )
        joins = await session.scalar(
            select(func.count())
            .select_from(JoinRequestEvent)
            .join(Channel, Channel.telegram_chat_id == JoinRequestEvent.channel_id)
            .where(Channel.workspace_id == workspace.id)
        )
    lines.extend(
        [
            "",
            f"👥 <b>Total visible:</b> {total_members:,}",
            f"📝 <b>Publicaciones terminadas:</b> {published or 0}",
            f"✅ <b>Entregas exitosas:</b> {successful_deliveries or 0}",
            f"🙋 <b>Solicitudes registradas:</b> {joins or 0}",
            "",
            "El cambio entre paréntesis se calcula desde la sincronización anterior.",
        ]
    )
    if summary.failed:
        lines.append(f"⚠️ {summary.failed} canal(es) no pudieron actualizarse temporalmente.")
    await callback.message.edit_text("\n".join(lines), reply_markup=back_home())
