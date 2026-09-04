from html import escape

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from ..database import SessionFactory
from ..keyboards import channel_post_text_menu
from ..models import Channel, ChannelStatus
from ..repository import get_workspace
from ..services.post_text import MAX_CHANNEL_TEXT_LENGTH, telegram_text_length
from ..states import ChannelPostTextFlow

router = Router(name="channel_texts")
VALID_KINDS = {"auto", "signature"}


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


def callback_target(data: str) -> tuple[str, int] | None:
    try:
        _, _, kind, channel_id_text = data.split(":", 3)
        channel_id = int(channel_id_text)
    except (ValueError, AttributeError):
        return None
    if kind not in VALID_KINDS:
        return None
    return kind, channel_id


def kind_values(channel: Channel, kind: str) -> tuple[str, bool, str]:
    if kind == "auto":
        return "Autocompletado", channel.autocomplete_enabled, channel.autocomplete_text or ""
    return "Firma", channel.signature_enabled, channel.signature_text or ""


def channel_text_menu_text(channel: Channel, kind: str) -> str:
    title, enabled, configured_text = kind_values(channel, kind)
    if kind == "auto":
        explanation = (
            "Se coloca únicamente cuando la publicación no trae texto o descripción. "
            "Si ya tiene descripción, se conserva sin agregar este contenido."
        )
    else:
        explanation = (
            "Se agrega siempre al final de cada publicación. Si ya existe texto, se separa "
            "con una línea en blanco."
        )
    current = configured_text if configured_text else "<i>Sin texto configurado.</i>"
    return (
        f"{'🪄' if kind == 'auto' else '✍️'} <b>{title} de {escape(channel.title)}</b>\n\n"
        f"Estado: <b>{'Activo' if enabled else 'Desactivado'}</b>\n\n"
        f"{explanation}\n\n"
        f"<b>Texto actual:</b>\n{current}"
    )


@router.callback_query(F.data.startswith("posttext:menu:"))
async def show_channel_text_menu(callback: CallbackQuery) -> None:
    target = callback_target(callback.data)
    if target is None:
        await callback.answer("Opción inválida.", show_alert=True)
        return
    kind, channel_id = target
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    await callback.message.edit_text(
        channel_text_menu_text(channel, kind),
        reply_markup=channel_post_text_menu(channel, kind),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("posttext:set:"))
async def ask_channel_text(callback: CallbackQuery, state: FSMContext) -> None:
    target = callback_target(callback.data)
    if target is None:
        await callback.answer("Opción inválida.", show_alert=True)
        return
    kind, channel_id = target
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    await state.set_state(ChannelPostTextFlow.waiting_text)
    await state.update_data(channel_id=channel_id, post_text_kind=kind)
    if kind == "auto":
        detail = "Se usará solamente en publicaciones que lleguen sin descripción."
    else:
        detail = "Se agregará al final de todas las publicaciones de este canal."
    await callback.message.answer(
        f"Envía el nuevo texto para <b>{escape(channel.title)}</b>.\n\n"
        f"{detail}\n"
        f"Puedes utilizar formato de Telegram. Máximo: <b>{MAX_CHANNEL_TEXT_LENGTH}</b> caracteres."
    )
    await callback.answer()


@router.message(ChannelPostTextFlow.waiting_text, F.chat.type == ChatType.PRIVATE, F.text)
async def save_channel_text(message: Message, state: FSMContext) -> None:
    plain_text = message.text.strip()
    if not 1 <= telegram_text_length(plain_text) <= MAX_CHANNEL_TEXT_LENGTH:
        await message.answer(f"El texto debe tener entre 1 y {MAX_CHANNEL_TEXT_LENGTH} caracteres.")
        return
    data = await state.get_data()
    kind = data.get("post_text_kind")
    if kind not in VALID_KINDS:
        await state.clear()
        await message.answer("La configuración ya no está disponible.")
        return
    async with SessionFactory() as session:
        channel = await owned_channel(session, int(data["channel_id"]), message.from_user.id)
        if channel is None:
            await state.clear()
            await message.answer("Canal no encontrado.")
            return
        rich_text = message.html_text.strip()
        if kind == "auto":
            channel.autocomplete_text = rich_text
            channel.autocomplete_enabled = True
        else:
            channel.signature_text = rich_text
            channel.signature_enabled = True
        await session.commit()
    await state.clear()
    label = "Autocompletado" if kind == "auto" else "Firma"
    await message.answer(
        f"✅ {label} guardado y activado.",
        reply_markup=channel_post_text_menu(channel, kind),
    )


@router.message(ChannelPostTextFlow.waiting_text, F.chat.type == ChatType.PRIVATE)
async def reject_non_text_channel_text(message: Message) -> None:
    await message.answer("Esta configuración solo acepta un mensaje de texto.")


@router.callback_query(F.data.startswith("posttext:preview:"))
async def preview_channel_text(callback: CallbackQuery) -> None:
    target = callback_target(callback.data)
    if target is None:
        await callback.answer("Opción inválida.", show_alert=True)
        return
    kind, channel_id = target
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    _, _, configured_text = kind_values(channel, kind)
    if not configured_text:
        await callback.answer("Primero configura el texto.", show_alert=True)
        return
    if kind == "auto":
        parts = [configured_text]
        if channel.signature_enabled and channel.signature_text:
            parts.append(channel.signature_text)
    else:
        parts = ["Este es un ejemplo de publicación con descripción.", configured_text]
    rendered = "\n\n".join(parts)
    await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text=rendered,
    )
    await callback.answer("Vista previa enviada")


@router.callback_query(F.data.startswith("posttext:toggle:"))
async def toggle_channel_text(callback: CallbackQuery) -> None:
    target = callback_target(callback.data)
    if target is None:
        await callback.answer("Opción inválida.", show_alert=True)
        return
    kind, channel_id = target
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
        if channel is None:
            await callback.answer("Canal no encontrado.", show_alert=True)
            return
        _, _, configured_text = kind_values(channel, kind)
        if not configured_text:
            await callback.answer("Primero configura el texto.", show_alert=True)
            return
        if kind == "auto":
            channel.autocomplete_enabled = not channel.autocomplete_enabled
        else:
            channel.signature_enabled = not channel.signature_enabled
        await session.commit()
    await callback.message.edit_text(
        channel_text_menu_text(channel, kind),
        reply_markup=channel_post_text_menu(channel, kind),
    )
    await callback.answer("Estado actualizado")


@router.callback_query(F.data.startswith("posttext:clear:"))
async def clear_channel_text(callback: CallbackQuery) -> None:
    target = callback_target(callback.data)
    if target is None:
        await callback.answer("Opción inválida.", show_alert=True)
        return
    kind, channel_id = target
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
        if channel is None:
            await callback.answer("Canal no encontrado.", show_alert=True)
            return
        if kind == "auto":
            channel.autocomplete_enabled = False
            channel.autocomplete_text = None
        else:
            channel.signature_enabled = False
            channel.signature_text = None
        await session.commit()
    label = "autocompletado" if kind == "auto" else "firma"
    await callback.message.edit_text(
        f"✅ Se eliminó el texto de {label} de <b>{escape(channel.title)}</b>.",
        reply_markup=channel_post_text_menu(channel, kind),
    )
    await callback.answer()
