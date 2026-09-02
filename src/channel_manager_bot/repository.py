import uuid
from datetime import UTC, datetime

from aiogram.types import User as TelegramUser
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import Channel, ChannelStatus, Membership, Role, User, Workspace


async def ensure_user_workspace(session: AsyncSession, tg_user: TelegramUser) -> Workspace:
    user = await session.get(User, tg_user.id)
    if user is None:
        user = User(
            telegram_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
        )
        session.add(user)
        await session.flush()
    else:
        user.username = tg_user.username
        user.full_name = tg_user.full_name

    workspace = await session.scalar(
        select(Workspace)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == tg_user.id)
        .order_by(Workspace.created_at)
    )
    if workspace is None:
        workspace = Workspace(
            id=uuid.uuid4(),
            name=f"Canales de {tg_user.full_name}"[:100],
            owner_user_id=tg_user.id,
            timezone=get_settings().default_timezone,
        )
        session.add(workspace)
        await session.flush()
        session.add(Membership(workspace_id=workspace.id, user_id=tg_user.id, role=Role.owner))
    await session.commit()
    return workspace


async def get_workspace(session: AsyncSession, user_id: int) -> Workspace | None:
    return await session.scalar(
        select(Workspace)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user_id)
        .order_by(Workspace.created_at)
    )


async def get_active_channels(session: AsyncSession, workspace_id) -> list[Channel]:
    rows = await session.scalars(
        select(Channel)
        .where(Channel.workspace_id == workspace_id, Channel.status == ChannelStatus.active)
        .order_by(Channel.title)
    )
    return list(rows)


async def can_add_channel(session: AsyncSession, workspace_id) -> bool:
    total = await session.scalar(
        select(func.count())
        .select_from(Channel)
        .where(
            Channel.workspace_id == workspace_id,
            Channel.status != ChannelStatus.removed,
        )
    )
    return (total or 0) < get_settings().max_channels_per_workspace


def utcnow() -> datetime:
    return datetime.now(UTC)
