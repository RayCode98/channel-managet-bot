import uuid
from datetime import UTC, datetime

from aiogram.types import User as TelegramUser
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import (
    AuditLog,
    Channel,
    ChannelStatus,
    Membership,
    Role,
    User,
    Workspace,
    WorkspaceInvite,
)


async def ensure_user_record(session: AsyncSession, tg_user: TelegramUser) -> User:
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
    return user


async def ensure_user_workspace(session: AsyncSession, tg_user: TelegramUser) -> Workspace:
    user = await ensure_user_record(session, tg_user)

    workspace = None
    if user.active_workspace_id is not None:
        workspace = await session.scalar(
            select(Workspace)
            .join(Membership, Membership.workspace_id == Workspace.id)
            .where(
                Workspace.id == user.active_workspace_id,
                Membership.user_id == tg_user.id,
            )
        )
    if workspace is None:
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
    user.active_workspace_id = workspace.id
    await session.commit()
    return workspace


async def get_workspace(session: AsyncSession, user_id: int) -> Workspace | None:
    user = await session.get(User, user_id)
    if user is not None and user.active_workspace_id is not None:
        active = await session.scalar(
            select(Workspace)
            .join(Membership, Membership.workspace_id == Workspace.id)
            .where(
                Workspace.id == user.active_workspace_id,
                Membership.user_id == user_id,
            )
        )
        if active is not None:
            return active
    return await session.scalar(
        select(Workspace)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user_id)
        .order_by(Workspace.created_at)
    )


async def get_user_workspaces(session: AsyncSession, user_id: int) -> list[Workspace]:
    rows = await session.scalars(
        select(Workspace)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user_id)
        .order_by(Workspace.created_at)
    )
    return list(rows)


async def get_active_channels(session: AsyncSession, workspace_id) -> list[Channel]:
    rows = await session.scalars(
        select(Channel)
        .where(Channel.workspace_id == workspace_id, Channel.status == ChannelStatus.active)
        .order_by(Channel.title)
    )
    return list(rows)


async def get_managed_channels(session: AsyncSession, workspace_id) -> list[Channel]:
    rows = await session.scalars(
        select(Channel)
        .where(Channel.workspace_id == workspace_id, Channel.status != ChannelStatus.removed)
        .order_by(Channel.title)
    )
    return list(rows)


async def get_membership(
    session: AsyncSession, workspace_id, user_id: int
) -> Membership | None:
    return await session.scalar(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user_id,
        )
    )


async def can_manage_workspace(session: AsyncSession, workspace_id, user_id: int) -> bool:
    membership = await get_membership(session, workspace_id, user_id)
    return membership is not None and membership.role in {Role.owner, Role.admin}


async def accept_workspace_invite(
    session: AsyncSession,
    tg_user: TelegramUser,
    token: str,
) -> tuple[WorkspaceInvite | None, str]:
    invite = await session.get(WorkspaceInvite, token)
    if invite is None:
        return None, "invalid"
    if invite.used_at is not None:
        return invite, "used"
    if invite.expires_at <= utcnow():
        return invite, "expired"

    user = await ensure_user_record(session, tg_user)
    membership = await get_membership(session, invite.workspace_id, tg_user.id)
    if membership is None:
        session.add(
            Membership(
                workspace_id=invite.workspace_id,
                user_id=tg_user.id,
                role=invite.role,
            )
        )
    elif membership.role == Role.editor and invite.role == Role.admin:
        membership.role = Role.admin
    invite.used_by_user_id = tg_user.id
    invite.used_at = utcnow()
    user.active_workspace_id = invite.workspace_id
    session.add(
        AuditLog(
            workspace_id=invite.workspace_id,
            actor_user_id=tg_user.id,
            action="workspace.invite_accepted",
            details=f"role={invite.role.value};token={token[:8]}",
        )
    )
    await session.commit()
    return invite, "accepted"


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
