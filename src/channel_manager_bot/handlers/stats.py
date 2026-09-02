from datetime import UTC, datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery
from sqlalchemy import func, select

from ..database import SessionFactory
from ..keyboards import back_home
from ..models import Channel, JoinRequestEvent, Publication, PublicationStatus, PublishedMessage
from ..repository import get_active_channels, get_workspace

router = Router(name="stats")


@router.callback_query(F.data == "stats:show")
async def show_stats(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer("Actualizando estadísticas…")
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        channels = await get_active_channels(session, workspace.id)
        lines = ["📊 <b>Estadísticas actuales</b>", ""]
        total_members = 0
        for channel in channels:
            try:
                current = await bot.get_chat_member_count(channel.telegram_chat_id)
                previous = channel.member_count
                channel.previous_member_count = previous
                channel.member_count = current
                channel.last_checked_at = datetime.now(UTC)
                total_members += current
                change = current - previous if previous is not None else None
                change_text = f" ({change:+d})" if change is not None else ""
                lines.append(f"• <b>{channel.title}</b>: {current:,}{change_text}")
            except TelegramAPIError:
                lines.append(f"• <b>{channel.title}</b>: no disponible")

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
        await session.commit()

    lines.extend(
        [
            "",
            f"👥 <b>Total visible:</b> {total_members:,}",
            f"📝 <b>Publicaciones terminadas:</b> {published or 0}",
            f"✅ <b>Entregas exitosas:</b> {successful_deliveries or 0}",
            f"🙋 <b>Solicitudes registradas:</b> {joins or 0}",
            "",
            "El cambio entre paréntesis se calcula desde la consulta anterior.",
        ]
    )
    await callback.message.edit_text("\n".join(lines), reply_markup=back_home())
