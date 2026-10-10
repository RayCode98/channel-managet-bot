import secrets
from html import escape
from urllib.parse import urlparse

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from ..database import SessionFactory
from ..keyboards import (
    back_home,
    campaign_channels_menu,
    campaign_link_detail_menu,
    campaign_links_menu,
)
from ..models import CampaignClick, CampaignLink, Channel, ChannelStatus
from ..repository import get_active_channels, get_workspace
from ..states import CampaignLinkFlow

router = Router(name="campaigns")


def valid_campaign_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"https", "http", "tg"} and bool(parsed.netloc)


async def owned_link(session, token: str, user_id: int) -> CampaignLink | None:
    workspace = await get_workspace(session, user_id)
    if workspace is None:
        return None
    return await session.scalar(
        select(CampaignLink).where(
            CampaignLink.token == token,
            CampaignLink.workspace_id == workspace.id,
        )
    )


@router.callback_query(F.data == "campaign:list")
async def list_campaign_links(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        rows = (
            list(
                await session.execute(
                    select(
                        CampaignLink.token,
                        CampaignLink.name,
                        CampaignLink.enabled,
                        func.count(CampaignClick.id),
                    )
                    .outerjoin(
                        CampaignClick,
                        CampaignClick.campaign_link_token == CampaignLink.token,
                    )
                    .where(CampaignLink.workspace_id == workspace.id)
                    .group_by(CampaignLink.token, CampaignLink.name, CampaignLink.enabled)
                    .order_by(CampaignLink.created_at.desc())
                    .limit(30)
                )
            )
            if workspace
            else []
        )
    links = [(token, name, enabled, clicks) for token, name, enabled, clicks in rows]
    text = (
        "🔗 <b>Enlaces de campaña</b>\n\n"
        "Crea enlaces rastreables para medir cuántas personas abren el bot desde cada campaña. "
        "Al entrar, el bot registra la visita y ofrece el enlace de destino."
    )
    if not links:
        text += "\n\nTodavía no tienes enlaces."
    await callback.message.edit_text(text, reply_markup=campaign_links_menu(links))
    await callback.answer()


@router.callback_query(F.data == "campaign:new")
async def new_campaign_link(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CampaignLinkFlow.waiting_name)
    await callback.message.edit_text(
        "🔗 <b>Nuevo enlace de campaña</b>\n\n"
        "Escribe un nombre corto para identificarlo, por ejemplo: <i>Instagram octubre</i>.",
        reply_markup=back_home(),
    )
    await callback.answer()


@router.message(CampaignLinkFlow.waiting_name, F.text)
async def receive_campaign_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not 1 <= len(name) <= 100:
        await message.answer("El nombre debe tener entre 1 y 100 caracteres.")
        return
    await state.update_data(campaign_name=name)
    await state.set_state(CampaignLinkFlow.waiting_target_url)
    await message.answer(
        "Ahora envía el enlace de destino que se mostrará al visitante:\n"
        "<code>https://ejemplo.com/landing</code>"
    )


@router.message(CampaignLinkFlow.waiting_target_url, F.text)
async def receive_campaign_target(message: Message, state: FSMContext) -> None:
    target_url = message.text.strip()
    if not valid_campaign_url(target_url):
        await message.answer("El enlace debe comenzar por https://, http:// o tg://.")
        return
    async with SessionFactory() as session:
        workspace = await get_workspace(session, message.from_user.id)
        channels = await get_active_channels(session, workspace.id) if workspace else []
    if not channels:
        await state.clear()
        await message.answer("Primero conecta al menos un canal o grupo.", reply_markup=back_home())
        return
    await state.update_data(campaign_target_url=target_url)
    await state.set_state(CampaignLinkFlow.waiting_channel)
    await message.answer(
        "Selecciona el canal o grupo al que corresponde esta campaña:",
        reply_markup=campaign_channels_menu(channels),
    )


@router.callback_query(
    CampaignLinkFlow.waiting_channel, F.data.startswith("campaign:channel:")
)
async def save_campaign_link(callback: CallbackQuery, state: FSMContext) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    data = await state.get_data()
    name = data.get("campaign_name")
    target_url = data.get("campaign_target_url")
    if not name or not target_url:
        await state.clear()
        await callback.answer(
            "La configuración expiró; inicia el enlace otra vez.",
            show_alert=True,
        )
        return
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        channel = await session.scalar(
            select(Channel).where(
                Channel.telegram_chat_id == channel_id,
                Channel.workspace_id == workspace.id,
                Channel.status == ChannelStatus.active,
            )
        ) if workspace else None
        if workspace is None or channel is None:
            await callback.answer("Ese chat no pertenece a tu espacio.", show_alert=True)
            return
        token = secrets.token_hex(12)
        link = CampaignLink(
            token=token,
            workspace_id=workspace.id,
            channel_id=channel_id,
            name=name,
            target_url=target_url,
            created_by_user_id=callback.from_user.id,
        )
        session.add(link)
        await session.commit()
    await state.clear()
    bot_user = await callback.bot.get_me()
    deep_link = f"https://t.me/{bot_user.username}?start=trk_{token}"
    await callback.message.edit_text(
        "✅ <b>Enlace de campaña creado</b>\n\n"
        f"Nombre: <b>{escape(name)}</b>\n"
        f"Chat: <b>{escape(channel.title)}</b>\n\n"
        "Copia este enlace y úsalo en tu publicación, anuncio o red social:\n"
        f"<code>{deep_link}</code>\n\n"
        "La métrica registra cuando una persona abre el bot desde este enlace. Las visitas "
        "repetidas también quedan registradas y el panel muestra clics totales y únicos.",
        reply_markup=campaign_link_detail_menu(token, True),
    )
    await callback.answer("Enlace creado")


@router.callback_query(F.data.startswith("campaign:open:"))
async def open_campaign_link(callback: CallbackQuery) -> None:
    token = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        link = await owned_link(session, token, callback.from_user.id)
        if link is None:
            await callback.answer("Enlace no encontrado.", show_alert=True)
            return
        channel = await session.get(Channel, link.channel_id)
        clicks = await session.scalar(
            select(func.count()).where(CampaignClick.campaign_link_token == token)
        )
        unique = await session.scalar(
            select(func.count(func.distinct(CampaignClick.user_id))).where(
                CampaignClick.campaign_link_token == token
            )
        )
    await callback.message.edit_text(
        "🔗 <b>Detalle del enlace</b>\n\n"
        f"Nombre: <b>{escape(link.name)}</b>\n"
        f"Chat: <b>{escape(channel.title if channel else 'No disponible')}</b>\n"
        f"Destino: <code>{escape(link.target_url)}</code>\n\n"
        f"Clics totales: <b>{clicks or 0}</b>\n"
        f"Personas únicas: <b>{unique or 0}</b>",
        reply_markup=campaign_link_detail_menu(token, link.enabled),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("campaign:toggle:"))
async def toggle_campaign_link(callback: CallbackQuery) -> None:
    token = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        link = await owned_link(session, token, callback.from_user.id)
        if link is None:
            await callback.answer("Enlace no encontrado.", show_alert=True)
            return
        link.enabled = not link.enabled
        enabled = link.enabled
        await session.commit()
    await callback.message.edit_reply_markup(reply_markup=campaign_link_detail_menu(token, enabled))
    await callback.answer("Enlace actualizado")


@router.callback_query(F.data.startswith("campaign:delete:"))
async def delete_campaign_link(callback: CallbackQuery) -> None:
    token = callback.data.rsplit(":", 1)[1]
    async with SessionFactory() as session:
        link = await owned_link(session, token, callback.from_user.id)
        if link is None:
            await callback.answer("Enlace no encontrado.", show_alert=True)
            return
        await session.delete(link)
        await session.commit()
    await callback.message.edit_text("✅ Enlace eliminado.", reply_markup=campaign_links_menu([]))
    await callback.answer("Enlace eliminado")
