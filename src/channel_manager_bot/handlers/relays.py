import asyncio
import logging
import uuid
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from ..database import SessionFactory
from ..keyboards import relay_rule_menu, relay_sources_menu, relay_targets_menu
from ..models import (
    AuditLog,
    Channel,
    ChannelStatus,
    RelayDelivery,
    RelayDestination,
    RelayRule,
)
from ..repository import get_active_channels, get_workspace
from ..services.relay import (
    is_copyable_content_type,
    remember_relayed_message,
    url_only_markup,
    was_recently_relayed,
    would_create_cycle,
)
from .channels import owned_channel

router = Router(name="relays")
logger = logging.getLogger(__name__)

_album_lock = asyncio.Lock()
_album_messages: dict[tuple[int, str], set[int]] = {}
_album_markups: dict[tuple[int, str], InlineKeyboardMarkup] = {}


async def load_rule(session, source_chat_id: int, workspace_id=None) -> RelayRule | None:
    query = (
        select(RelayRule)
        .options(selectinload(RelayRule.destinations))
        .where(RelayRule.source_chat_id == source_chat_id)
    )
    if workspace_id is not None:
        query = query.where(RelayRule.workspace_id == workspace_id)
    return await session.scalar(query)


def rule_text(
    source: Channel,
    rule: RelayRule | None,
    destinations: list[Channel],
    successful: int,
    failed: int,
) -> str:
    status = "Activo" if rule and rule.enabled and destinations else "Desactivado"
    mode = (
        "Con etiqueta «Reenviado de»"
        if rule and rule.preserve_forward_header
        else "Copia limpia, sin etiqueta"
    )
    destination_lines = (
        "\n".join(
            f"• {'👥' if item.chat_type in {'group', 'supergroup'} else '📢'} "
            f"{escape(item.title)}"
            for item in destinations
        )
        if destinations
        else "Ninguno"
    )
    return (
        f"↪️ <b>Reenvío · {escape(source.title)}</b>\n\n"
        f"Estado: <b>{status}</b>\n"
        f"Formato: <b>{mode}</b>\n"
        f"Entregas: <b>{successful} correctas</b> · <b>{failed} fallidas</b>\n\n"
        f"<b>Destinos:</b>\n{destination_lines}\n\n"
        "La copia limpia conserva botones URL. Al mostrar el origen, Telegram controla el "
        "formato y puede omitir los botones del mensaje original."
    )


@router.callback_query(F.data == "relay:sources")
async def show_relay_sources(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        channels = await get_active_channels(session, workspace.id) if workspace else []
        rules = (
            list(
                await session.scalars(
                    select(RelayRule)
                    .options(selectinload(RelayRule.destinations))
                    .where(RelayRule.workspace_id == workspace.id)
                )
            )
            if workspace
            else []
        )
    text = (
        "↪️ <b>Reenvío automático</b>\n\n"
        "Selecciona el canal o grupo principal del que se copiarán las publicaciones nuevas."
    )
    if not channels:
        text += "\n\nTodavía no hay canales o grupos vinculados."
    await callback.message.edit_text(
        text,
        reply_markup=relay_sources_menu(
            channels, {rule.source_chat_id: rule for rule in rules}
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("relay:menu:"))
async def show_relay_rule(callback: CallbackQuery) -> None:
    source_chat_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        source = await owned_channel(session, source_chat_id, callback.from_user.id)
        rule = await load_rule(session, source_chat_id, workspace.id) if workspace else None
        destination_ids = (
            [item.destination_chat_id for item in rule.destinations] if rule else []
        )
        destinations = (
            list(
                await session.scalars(
                    select(Channel)
                    .where(Channel.telegram_chat_id.in_(destination_ids))
                    .order_by(Channel.title)
                )
            )
            if destination_ids
            else []
        )
        successful = failed = 0
        if rule:
            successful = (
                await session.scalar(
                    select(func.count())
                    .select_from(RelayDelivery)
                    .where(
                        RelayDelivery.relay_rule_id == rule.id,
                        RelayDelivery.succeeded.is_(True),
                    )
                )
                or 0
            )
            failed = (
                await session.scalar(
                    select(func.count())
                    .select_from(RelayDelivery)
                    .where(
                        RelayDelivery.relay_rule_id == rule.id,
                        RelayDelivery.succeeded.is_(False),
                        RelayDelivery.error.is_not(None),
                    )
                )
                or 0
            )
    if source is None:
        await callback.answer("Chat no encontrado.", show_alert=True)
        return
    await callback.message.edit_text(
        rule_text(source, rule, destinations, successful, failed),
        reply_markup=relay_rule_menu(source_chat_id, rule),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("relay:targets:"))
async def show_relay_targets(callback: CallbackQuery) -> None:
    source_chat_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        source = await owned_channel(session, source_chat_id, callback.from_user.id)
        channels = await get_active_channels(session, workspace.id) if workspace else []
        rule = await load_rule(session, source_chat_id, workspace.id) if workspace else None
        selected = {item.destination_chat_id for item in rule.destinations} if rule else set()
    if source is None:
        await callback.answer("Chat no encontrado.", show_alert=True)
        return
    text = (
        f"🎯 <b>Destinos de {escape(source.title)}</b>\n\n"
        "Selecciona uno o varios canales o grupos. El origen no puede ser su propio destino."
    )
    if len(channels) < 2:
        text += "\n\nVincula al menos otro canal o grupo para continuar."
    await callback.message.edit_text(
        text,
        reply_markup=relay_targets_menu(
            source_chat_id,
            channels,
            selected,
            bool(rule and rule.preserve_forward_header),
        ),
    )
    await callback.answer()


async def active_relay_edges(session, workspace_id, excluding_rule_id=None) -> set[tuple[int, int]]:
    rules = list(
        await session.scalars(
            select(RelayRule)
            .options(selectinload(RelayRule.destinations))
            .where(
                RelayRule.workspace_id == workspace_id,
                RelayRule.enabled.is_(True),
            )
        )
    )
    return {
        (rule.source_chat_id, destination.destination_chat_id)
        for rule in rules
        if rule.id != excluding_rule_id
        for destination in rule.destinations
    }


@router.callback_query(F.data.startswith("relay:dest:"))
async def toggle_relay_destination(callback: CallbackQuery) -> None:
    _, _, source_text, destination_text = callback.data.split(":", 3)
    source_chat_id, destination_chat_id = int(source_text), int(destination_text)
    if source_chat_id == destination_chat_id:
        await callback.answer("El origen no puede ser su propio destino.", show_alert=True)
        return
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        source = await owned_channel(session, source_chat_id, callback.from_user.id)
        destination = (
            await session.scalar(
                select(Channel).where(
                    Channel.telegram_chat_id == destination_chat_id,
                    Channel.workspace_id == workspace.id,
                    Channel.status == ChannelStatus.active,
                )
            )
            if workspace
            else None
        )
        if workspace is None or source is None or destination is None:
            await callback.answer("Origen o destino no disponible.", show_alert=True)
            return
        rule = await load_rule(session, source_chat_id, workspace.id)
        existing = (
            next(
                (
                    item
                    for item in rule.destinations
                    if item.destination_chat_id == destination_chat_id
                ),
                None,
            )
            if rule
            else None
        )
        if existing:
            rule.destinations.remove(existing)
            if not rule.destinations:
                rule.enabled = False
            action = "removed"
        else:
            if rule is None:
                rule = RelayRule(
                    id=uuid.uuid4(),
                    workspace_id=workspace.id,
                    source_chat_id=source_chat_id,
                    creator_user_id=callback.from_user.id,
                    enabled=True,
                )
                session.add(rule)
            elif not rule.destinations:
                rule.enabled = True
            edges = await active_relay_edges(session, workspace.id, excluding_rule_id=rule.id)
            if would_create_cycle(edges, source_chat_id, destination_chat_id):
                await callback.answer(
                    "Esa relación formaría un ciclo de reenvíos.", show_alert=True
                )
                return
            rule.destinations.append(
                RelayDestination(destination_chat_id=destination_chat_id)
            )
            action = "added"
        session.add(
            AuditLog(
                workspace_id=workspace.id,
                actor_user_id=callback.from_user.id,
                action=f"relay.destination_{action}",
                details=(
                    f"source_chat_id={source_chat_id};"
                    f"destination_chat_id={destination_chat_id}"
                ),
            )
        )
        await session.commit()
        channels = await get_active_channels(session, workspace.id)
        selected = {item.destination_chat_id for item in rule.destinations}
    await callback.message.edit_reply_markup(
        reply_markup=relay_targets_menu(
            source_chat_id,
            channels,
            selected,
            rule.preserve_forward_header,
        )
    )
    await callback.answer("Destino actualizado")


@router.callback_query(F.data.startswith("relay:mode:"))
async def toggle_relay_mode(callback: CallbackQuery) -> None:
    source_chat_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        source = await owned_channel(session, source_chat_id, callback.from_user.id)
        if workspace is None or source is None:
            await callback.answer("Chat no encontrado.", show_alert=True)
            return
        rule = await load_rule(session, source_chat_id, workspace.id)
        if rule is None:
            rule = RelayRule(
                id=uuid.uuid4(),
                workspace_id=workspace.id,
                source_chat_id=source_chat_id,
                creator_user_id=callback.from_user.id,
                enabled=False,
                preserve_forward_header=True,
            )
            session.add(rule)
        else:
            rule.preserve_forward_header = not rule.preserve_forward_header
        session.add(
            AuditLog(
                workspace_id=workspace.id,
                actor_user_id=callback.from_user.id,
                action="relay.forward_header_toggled",
                details=(
                    f"source_chat_id={source_chat_id};"
                    f"enabled={rule.preserve_forward_header}"
                ),
            )
        )
        await session.commit()
        channels = await get_active_channels(session, workspace.id)
        selected = {item.destination_chat_id for item in rule.destinations}
    await callback.message.edit_reply_markup(
        reply_markup=relay_targets_menu(
            source_chat_id,
            channels,
            selected,
            rule.preserve_forward_header,
        )
    )
    await callback.answer("Formato de reenvío actualizado")


@router.callback_query(F.data.startswith("relay:toggle:"))
async def toggle_relay_rule(callback: CallbackQuery) -> None:
    source_chat_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        source = await owned_channel(session, source_chat_id, callback.from_user.id)
        rule = await load_rule(session, source_chat_id, workspace.id) if workspace else None
        if source is None or rule is None or not rule.destinations:
            await callback.answer("Selecciona al menos un destino.", show_alert=True)
            return
        enabling = not rule.enabled
        if enabling:
            edges = await active_relay_edges(session, workspace.id, excluding_rule_id=rule.id)
            pending_edges = set(edges)
            for destination in rule.destinations:
                if would_create_cycle(
                    pending_edges, source_chat_id, destination.destination_chat_id
                ):
                    await callback.answer(
                        "No se puede activar porque formaría un ciclo.", show_alert=True
                    )
                    return
                pending_edges.add((source_chat_id, destination.destination_chat_id))
        rule.enabled = enabling
        session.add(
            AuditLog(
                workspace_id=workspace.id,
                actor_user_id=callback.from_user.id,
                action="relay.toggled",
                details=f"source_chat_id={source_chat_id};enabled={enabling}",
            )
        )
        await session.commit()
    await callback.message.edit_reply_markup(reply_markup=relay_rule_menu(source_chat_id, rule))
    await callback.answer("Reenvío actualizado")


async def is_relay_output(chat_id: int, message_id: int) -> bool:
    if was_recently_relayed(chat_id, message_id):
        return True
    async with SessionFactory() as session:
        return bool(
            await session.scalar(
                select(RelayDelivery.id).where(
                    RelayDelivery.destination_chat_id == chat_id,
                    RelayDelivery.telegram_message_id == message_id,
                    RelayDelivery.succeeded.is_(True),
                )
            )
        )


async def relay_source_messages(
    bot: Bot,
    *,
    source_chat_id: int,
    message_ids: list[int],
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    async with SessionFactory() as session:
        rule = await session.scalar(
            select(RelayRule)
            .join(Channel, Channel.telegram_chat_id == RelayRule.source_chat_id)
            .options(selectinload(RelayRule.destinations))
            .where(
                RelayRule.source_chat_id == source_chat_id,
                RelayRule.enabled.is_(True),
                Channel.status == ChannelStatus.active,
            )
        )
        if rule is None or not rule.destinations:
            return
        destination_ids = [item.destination_chat_id for item in rule.destinations]
        active_ids = set(
            await session.scalars(
                select(Channel.telegram_chat_id).where(
                    Channel.telegram_chat_id.in_(destination_ids),
                    Channel.status == ChannelStatus.active,
                    Channel.can_post_messages.is_(True),
                )
            )
        )

        for destination_chat_id in active_ids:
            claimed: dict[int, uuid.UUID] = {}
            for message_id in message_ids:
                delivery_id = uuid.uuid4()
                statement = (
                    pg_insert(RelayDelivery)
                    .values(
                        id=delivery_id,
                        relay_rule_id=rule.id,
                        source_message_id=message_id,
                        destination_chat_id=destination_chat_id,
                        succeeded=False,
                    )
                    .on_conflict_do_nothing(
                        constraint="uq_relay_delivery_message_destination"
                    )
                    .returning(RelayDelivery.id)
                )
                if await session.scalar(statement):
                    claimed[message_id] = delivery_id
            await session.commit()

            # Solamente la instancia que insertó la entrega puede publicarla. Esto
            # evita duplicados si Telegram repite una actualización o hay dos procesos.
            pending_ids = [message_id for message_id in message_ids if message_id in claimed]
            if not pending_ids:
                continue
            deliveries = list(
                await session.scalars(
                    select(RelayDelivery).where(RelayDelivery.id.in_(claimed.values()))
                )
            )
            by_source = {item.source_message_id: item for item in deliveries}

            try:
                if rule.preserve_forward_header and len(pending_ids) == 1:
                    sent = await bot.forward_message(
                        chat_id=destination_chat_id,
                        from_chat_id=source_chat_id,
                        message_id=pending_ids[0],
                    )
                    sent_ids = [sent.message_id]
                elif rule.preserve_forward_header:
                    sent = await bot.forward_messages(
                        chat_id=destination_chat_id,
                        from_chat_id=source_chat_id,
                        message_ids=pending_ids,
                    )
                    sent_ids = [item.message_id for item in sent]
                elif len(pending_ids) == 1:
                    sent = await bot.copy_message(
                        chat_id=destination_chat_id,
                        from_chat_id=source_chat_id,
                        message_id=pending_ids[0],
                        reply_markup=url_only_markup(reply_markup),
                    )
                    sent_ids = [sent.message_id]
                else:
                    sent = await bot.copy_messages(
                        chat_id=destination_chat_id,
                        from_chat_id=source_chat_id,
                        message_ids=pending_ids,
                    )
                    sent_ids = [item.message_id for item in sent]
                    copied_markup = url_only_markup(reply_markup)
                    if copied_markup and sent_ids:
                        try:
                            await bot.edit_message_reply_markup(
                                chat_id=destination_chat_id,
                                message_id=sent_ids[0],
                                reply_markup=copied_markup,
                            )
                        except TelegramAPIError as exc:
                            logger.info(
                                "Could not copy album URL buttons to %s: %s",
                                destination_chat_id,
                                exc,
                            )
            except TelegramAPIError as exc:
                logger.warning(
                    "Could not relay messages from %s to %s: %s",
                    source_chat_id,
                    destination_chat_id,
                    exc,
                )
                for message_id in pending_ids:
                    by_source[message_id].succeeded = False
                    by_source[message_id].error = str(exc)[:2000]
                await session.commit()
                continue

            for position, message_id in enumerate(pending_ids):
                delivery = by_source[message_id]
                if position < len(sent_ids):
                    delivery.telegram_message_id = sent_ids[position]
                    delivery.succeeded = True
                    delivery.error = None
                    remember_relayed_message(destination_chat_id, sent_ids[position])
                else:
                    delivery.succeeded = False
                    delivery.error = "Telegram omitió este elemento al copiar el lote."
            await session.commit()


async def process_relay_message(message: Message, bot: Bot) -> None:
    if not is_copyable_content_type(message.content_type):
        return
    if await is_relay_output(message.chat.id, message.message_id):
        return
    if not message.media_group_id:
        await relay_source_messages(
            bot,
            source_chat_id=message.chat.id,
            message_ids=[message.message_id],
            reply_markup=message.reply_markup,
        )
        return

    key = (message.chat.id, message.media_group_id)
    async with _album_lock:
        is_first = key not in _album_messages
        _album_messages.setdefault(key, set()).add(message.message_id)
        if message.reply_markup is not None:
            _album_markups[key] = message.reply_markup
    if not is_first:
        return
    await asyncio.sleep(1)
    async with _album_lock:
        message_ids = sorted(_album_messages.pop(key, set()))
        reply_markup = _album_markups.pop(key, None)
    if message_ids:
        await relay_source_messages(
            bot,
            source_chat_id=message.chat.id,
            message_ids=message_ids,
            reply_markup=reply_markup,
        )


@router.channel_post()
async def relay_channel_post(message: Message, bot: Bot) -> None:
    await process_relay_message(message, bot)


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def relay_group_message(message: Message, bot: Bot) -> None:
    await process_relay_message(message, bot)
