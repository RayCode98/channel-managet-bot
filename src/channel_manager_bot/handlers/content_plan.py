import math
import uuid
from collections import defaultdict
from html import escape
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, select

from ..database import SessionFactory
from ..keyboards import recurrence_label, ttl_label
from ..models import Publication, PublicationChannel, PublicationStatus
from ..repository import get_workspace

router = Router(name="content_plan")
PAGE_SIZE = 8


async def render_plan(callback: CallbackQuery, page: int) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        total = (
            await session.scalar(
                select(func.count())
                .select_from(Publication)
                .where(
                    Publication.workspace_id == workspace.id,
                    Publication.status == PublicationStatus.scheduled,
                    Publication.scheduled_at.is_not(None),
                )
            )
            or 0
        )
        total_pages = max(1, math.ceil(total / PAGE_SIZE))
        page = min(max(page, 0), total_pages - 1)
        publications = list(
            await session.scalars(
                select(Publication)
                .where(
                    Publication.workspace_id == workspace.id,
                    Publication.status == PublicationStatus.scheduled,
                    Publication.scheduled_at.is_not(None),
                )
                .order_by(Publication.scheduled_at)
                .offset(page * PAGE_SIZE)
                .limit(PAGE_SIZE)
            )
        )
        channel_counts = {}
        for publication in publications:
            channel_counts[publication.id] = (
                await session.scalar(
                    select(func.count())
                    .select_from(PublicationChannel)
                    .where(PublicationChannel.publication_id == publication.id)
                )
                or 0
            )

    grouped = defaultdict(list)
    timezone = ZoneInfo(workspace.timezone)
    for publication in publications:
        local_time = publication.scheduled_at.astimezone(timezone)
        grouped[local_time.strftime("%d/%m/%Y")].append((publication, local_time))

    lines = ["🗓 <b>Plan de contenido</b>", ""]
    if not publications:
        lines.append("No tienes publicaciones programadas.")
    for date, items in grouped.items():
        lines.append(f"📅 <b>{date}</b>")
        for publication, local_time in items:
            preview = escape(
                (publication.preview or "Contenido multimedia").replace("\n", " ")[:70]
            )
            channels = channel_counts[publication.id]
            ttl = ttl_label(publication.delete_after_minutes)
            recurrence = (
                f" · 🔁 {recurrence_label(publication.recurrence_interval_days)}"
                if publication.recurrence_interval_days
                else ""
            )
            lines.append(
                f"• {local_time:%H:%M} · {channels} canal(es) · elimina: {ttl}{recurrence}\n"
                f"  {preview}"
            )
        lines.append("")
    lines.append(f"Página {page + 1}/{total_pages} · {total} programada(s)")

    rows = [
        [
            InlineKeyboardButton(
                text=(
                    f"{'⏹' if publication.recurrence_interval_days else '❌'} "
                    f"{local_time:%d/%m %H:%M} · "
                    f"{(publication.preview or 'Multimedia').replace(chr(10), ' ')[:24]}"
                ),
                callback_data=f"plan:cancel:{publication.id}:{page}",
            )
        ]
        for publication, local_time in [
            (item, item.scheduled_at.astimezone(timezone)) for item in publications
        ]
    ]
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(text="⬅️ Anterior", callback_data=f"plan:page:{page - 1}")
        )
    if page + 1 < total_pages:
        navigation.append(
            InlineKeyboardButton(text="Siguiente ➡️", callback_data=f"plan:page:{page + 1}")
        )
    if navigation:
        rows.append(navigation)
    rows.extend(
        [
            [InlineKeyboardButton(text="🔄 Actualizar", callback_data=f"plan:page:{page}")],
            [InlineKeyboardButton(text="⬅️ Menú principal", callback_data="home")],
        ]
    )
    await callback.message.edit_text(
        "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )


@router.callback_query(F.data.startswith("plan:page:"))
async def show_plan(callback: CallbackQuery) -> None:
    page = int(callback.data.rsplit(":", 1)[1])
    await render_plan(callback, page)
    await callback.answer()


@router.callback_query(F.data.startswith("plan:cancel:"))
async def cancel_planned(callback: CallbackQuery) -> None:
    _, _, publication_id, page_text = callback.data.split(":", 3)
    try:
        parsed_id = uuid.UUID(publication_id)
    except ValueError:
        await callback.answer("Publicación inválida.", show_alert=True)
        return
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        publication = await session.scalar(
            select(Publication).where(
                Publication.id == parsed_id,
                Publication.workspace_id == workspace.id,
                Publication.status == PublicationStatus.scheduled,
            )
        )
        if publication is None:
            await callback.answer("La publicación ya no está programada.", show_alert=True)
            return
        was_recurring = bool(publication.recurrence_interval_days)
        publication.status = PublicationStatus.cancelled
        await session.commit()
    await render_plan(callback, int(page_text))
    await callback.answer("Recurrencia detenida" if was_recurring else "Publicación cancelada")
