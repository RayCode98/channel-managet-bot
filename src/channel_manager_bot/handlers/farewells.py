import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message
from sqlalchemy import select

from ..database import SessionFactory
from ..keyboards import farewell_buttons_menu, farewell_menu
from ..models import Channel, ChannelStatus, FarewellButton
from ..repository import get_workspace
from ..services.welcome import (
    content_from_message,
    is_voluntary_channel_departure,
    parse_welcome_buttons,
    send_channel_farewell,
)
from ..states import ChannelFarewellFlow

router = Router(name="farewells")
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


@router.callback_query(F.data.startswith("farewell:menu:"))
async def show_farewell_menu(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    status = "Activa" if channel.farewell_enabled else "Desactivada"
    await callback.message.edit_text(
        f"🚪 <b>Despedida de {escape(channel.title)}</b>\n\n"
        f"Estado: <b>{status}</b>\n"
        f"Botones: <b>{len(channel.farewell_buttons)}</b>\n\n"
        "Se intentará enviar por privado cuando Telegram informe que el propio usuario salió. "
        "Solo llegará si esa persona ya inició una conversación con el bot y no lo bloqueó.",
        reply_markup=farewell_menu(channel),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("farewell:content:"))
async def ask_farewell_content(callback: CallbackQuery, state: FSMContext) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    await state.set_state(ChannelFarewellFlow.waiting_content)
    await state.update_data(channel_id=channel_id)
    await callback.message.answer(
        f"🚪 Envía la despedida para <b>{escape(channel.title)}</b>.\n\n"
        "Puede ser texto enriquecido, foto, video, animación, audio, voz o documento.\n\n"
        "Variables disponibles:\n"
        "• <code>{nombre}</code>: nombre de la persona que salió.\n"
        "• <code>{canal}</code>: nombre del canal.\n\n"
        "Ejemplo: <code>Hasta pronto, {nombre}. Gracias por haber formado parte de {canal}.</code>"
    )
    await callback.answer()


@router.message(ChannelFarewellFlow.waiting_content, F.chat.type == ChatType.PRIVATE)
async def save_farewell_content(message: Message, state: FSMContext) -> None:
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
        channel.farewell_source_chat_id = message.chat.id
        channel.farewell_source_message_id = message.message_id
        channel.farewell_content_type = content_type
        channel.farewell_text_template = text_template
        channel.farewell_file_id = file_id
        channel.farewell_enabled = True
        await session.commit()
    await state.clear()
    await message.answer(
        "✅ Despedida guardada y activada. Recuerda que el envío privado depende de que el "
        "usuario haya iniciado el bot.",
        reply_markup=farewell_menu(channel),
    )


@router.callback_query(F.data.startswith("farewell:buttons:"))
async def ask_farewell_buttons(callback: CallbackQuery, state: FSMContext) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    if not channel.farewell_source_message_id:
        await callback.answer("Primero configura el contenido de despedida.", show_alert=True)
        return
    await state.set_state(ChannelFarewellFlow.waiting_buttons)
    await state.update_data(channel_id=channel_id)
    await callback.message.answer(
        "🔗 Envía todos los botones en un solo mensaje, uno por línea:\n\n"
        "<code>nombre botón - url - color</code>\n\n"
        "Ejemplo:\n"
        "<code>Volver al canal - https://t.me/mi_canal - verde\n"
        "Conocer más - https://example.com - azul</code>\n\n"
        "Colores: <b>azul, verde, rojo o normal</b>. Envía <code>quitar</code> para eliminarlos."
    )
    await callback.answer()


@router.message(ChannelFarewellFlow.waiting_buttons, F.text)
async def save_farewell_buttons(message: Message, state: FSMContext) -> None:
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
        channel.farewell_buttons.clear()
        for row_index, button in enumerate(parsed_buttons):
            channel.farewell_buttons.append(
                FarewellButton(
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
        f"✅ Botones de despedida actualizados: <b>{len(parsed_buttons)}</b>.",
        reply_markup=farewell_menu(channel),
    )


@router.callback_query(F.data.startswith("farewell:manage:"))
async def manage_farewell_buttons(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    if not channel.farewell_buttons:
        await callback.answer("La despedida no tiene botones.", show_alert=True)
        return
    await callback.message.edit_text(
        f"🧹 <b>Botones de despedida de {escape(channel.title)}</b>\n\n"
        "Pulsa el botón que deseas eliminar.",
        reply_markup=farewell_buttons_menu(channel.telegram_chat_id, channel.farewell_buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("farewell:bdel:"))
async def delete_farewell_button(callback: CallbackQuery) -> None:
    try:
        button_id = int(callback.data.rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("Botón inválido.", show_alert=True)
        return
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        if workspace is None:
            await callback.answer("Cuenta no encontrada.", show_alert=True)
            return
        button = await session.scalar(
            select(FarewellButton)
            .join(Channel, Channel.telegram_chat_id == FarewellButton.channel_id)
            .where(
                FarewellButton.id == button_id,
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
                select(FarewellButton)
                .where(FarewellButton.channel_id == channel_id)
                .order_by(FarewellButton.row_index, FarewellButton.position)
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
    if channel.farewell_buttons:
        await callback.message.edit_reply_markup(
            reply_markup=farewell_buttons_menu(channel.telegram_chat_id, channel.farewell_buttons)
        )
    else:
        await callback.message.edit_text(
            f"🚪 <b>{escape(channel.title)}</b>\n\nLa despedida quedó sin botones.",
            reply_markup=farewell_menu(channel),
        )
    await callback.answer("Botón eliminado")


@router.callback_query(F.data.startswith("farewell:preview:"))
async def preview_farewell(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
    if channel is None:
        await callback.answer("Canal no encontrado.", show_alert=True)
        return
    if not channel.farewell_source_message_id:
        await callback.answer("Primero configura el contenido de despedida.", show_alert=True)
        return
    try:
        await send_channel_farewell(
            callback.bot,
            chat_id=callback.from_user.id,
            channel=channel,
            user_name=callback.from_user.full_name,
        )
    except TelegramAPIError as exc:
        logger.warning("Could not render farewell preview for %s: %s", channel_id, exc)
        await callback.answer("Telegram no pudo generar la vista previa.", show_alert=True)
        return
    await callback.answer("Vista previa enviada")


@router.callback_query(F.data.startswith("farewell:toggle:"))
async def toggle_farewell(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
        if channel is None:
            await callback.answer("Canal no encontrado.", show_alert=True)
            return
        if not channel.farewell_source_message_id:
            await callback.answer("Primero configura el contenido de despedida.", show_alert=True)
            return
        channel.farewell_enabled = not channel.farewell_enabled
        await session.commit()
    await callback.message.edit_reply_markup(reply_markup=farewell_menu(channel))
    await callback.answer("Despedida actualizada")


@router.callback_query(F.data.startswith("farewell:clear:"))
async def clear_farewell(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        channel = await owned_channel(session, channel_id, callback.from_user.id)
        if channel is None:
            await callback.answer("Canal no encontrado.", show_alert=True)
            return
        channel.farewell_enabled = False
        channel.farewell_source_chat_id = None
        channel.farewell_source_message_id = None
        channel.farewell_content_type = None
        channel.farewell_text_template = None
        channel.farewell_file_id = None
        channel.farewell_buttons.clear()
        await session.commit()
    await callback.message.edit_text(
        f"🚪 <b>{escape(channel.title)}</b>\n\nLa despedida personalizada fue eliminada.",
        reply_markup=farewell_menu(channel),
    )
    await callback.answer()


@router.chat_member(F.chat.type == ChatType.CHANNEL)
async def member_left_channel(event: ChatMemberUpdated, bot: Bot) -> None:
    departed_user = event.new_chat_member.user
    if not is_voluntary_channel_departure(event):
        return

    async with SessionFactory() as session:
        channel = await session.get(Channel, event.chat.id)
    if not (
        channel
        and channel.status == ChannelStatus.active
        and channel.farewell_enabled
        and channel.farewell_source_message_id
    ):
        return
    try:
        await send_channel_farewell(
            bot,
            chat_id=departed_user.id,
            channel=channel,
            user_name=departed_user.full_name,
        )
    except TelegramAPIError as exc:
        logger.info(
            "Could not send farewell for channel %s to user %s: %s",
            channel.telegram_chat_id,
            departed_user.id,
            exc,
        )
