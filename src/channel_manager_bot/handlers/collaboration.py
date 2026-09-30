import secrets
from datetime import timedelta
from html import escape
from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select

from ..database import SessionFactory
from ..keyboards import (
    collaboration_menu,
    collaborator_detail_menu,
    invite_role_menu,
    workspace_switch_menu,
)
from ..models import AuditLog, Membership, Role, User, WorkspaceInvite
from ..repository import (
    can_manage_workspace,
    get_membership,
    get_user_workspaces,
    get_workspace,
    utcnow,
)

router = Router(name="collaboration")


ROLE_LABELS = {
    Role.owner: "👑 Propietario",
    Role.admin: "🛠 Administrador",
    Role.editor: "✍️ Editor",
}


async def _workspace_view(session, user_id: int):
    workspace = await get_workspace(session, user_id)
    if workspace is None:
        return None, False, [], []
    membership = await get_membership(session, workspace.id, user_id)
    rows = await session.execute(
        select(Membership, User)
        .join(User, User.telegram_id == Membership.user_id)
        .where(Membership.workspace_id == workspace.id)
        .order_by(Membership.role, User.full_name)
    )
    members = [
        (membership_row.user_id, user.full_name, ROLE_LABELS.get(membership_row.role, "Editor"))
        for membership_row, user in rows.all()
    ]
    can_manage = membership is not None and membership.role in {Role.owner, Role.admin}
    workspaces = await get_user_workspaces(session, user_id)
    return workspace, can_manage, members, workspaces


def _collaboration_text(workspace, members: list[tuple[int, str, str]]) -> str:
    lines = [
        "🤝 <b>Colaboración</b>",
        "",
        f"Espacio: <b>{escape(workspace.name)}</b>",
        "Comparte un enlace para que otra persona administre tus canales y grupos.",
        "",
        f"<b>Miembros ({len(members)}):</b>",
    ]
    lines.extend(f"• {escape(role)} · {escape(name)}" for _, name, role in members)
    return "\n".join(lines)


@router.callback_query(F.data == "collab:menu")
async def show_collaboration(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace, can_manage, members, workspaces = await _workspace_view(
            session, callback.from_user.id
        )
    if workspace is None:
        await callback.answer("Cuenta no encontrada.", show_alert=True)
        return
    await callback.message.edit_text(
        _collaboration_text(workspace, members),
        reply_markup=collaboration_menu(can_manage, members, len(workspaces)),
    )
    await callback.answer()


@router.callback_query(F.data == "collab:workspaces")
async def choose_workspace(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        current = await get_workspace(session, callback.from_user.id)
        workspaces = await get_user_workspaces(session, callback.from_user.id)
    if len(workspaces) < 2:
        await callback.answer("Solo tienes un espacio de trabajo.", show_alert=True)
        return
    await callback.message.edit_text(
        "🔄 <b>Cambiar espacio de trabajo</b>\n\nSelecciona el espacio que deseas administrar.",
        reply_markup=workspace_switch_menu(
            [(workspace.id, workspace.name, workspace.id == current.id) for workspace in workspaces]
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("collab:switch:"))
async def switch_workspace(callback: CallbackQuery) -> None:
    try:
        workspace_id = UUID(callback.data.rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("Espacio inválido.", show_alert=True)
        return
    async with SessionFactory() as session:
        user = await session.get(User, callback.from_user.id)
        membership = await session.scalar(
            select(Membership).where(
                Membership.workspace_id == workspace_id,
                Membership.user_id == callback.from_user.id,
            )
        )
        if user is None or membership is None:
            await callback.answer("No tienes acceso a ese espacio.", show_alert=True)
            return
        user.active_workspace_id = workspace_id
        await session.commit()
    await show_collaboration(callback)


@router.callback_query(F.data == "collab:invite")
async def choose_invite_role(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        allowed = workspace is not None and await can_manage_workspace(
            session, workspace.id, callback.from_user.id
        )
    if not allowed:
        await callback.answer("Solo un propietario o administrador puede invitar colaboradores.", show_alert=True)
        return
    await callback.message.edit_text(
        "🤝 <b>Invitar colaborador</b>\n\n"
        "Elige el nivel de acceso. El enlace caducará en 7 días y solo podrá usarse una vez.",
        reply_markup=invite_role_menu(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("collab:invite:"))
async def create_invite(callback: CallbackQuery, bot: Bot) -> None:
    role_value = callback.data.rsplit(":", 1)[1]
    if role_value not in {Role.admin.value, Role.editor.value}:
        await callback.answer("Rol inválido.", show_alert=True)
        return
    role = Role(role_value)
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        if workspace is None or not await can_manage_workspace(
            session, workspace.id, callback.from_user.id
        ):
            await callback.answer("No tienes permiso para invitar colaboradores.", show_alert=True)
            return
        token = secrets.token_urlsafe(32)[:48]
        session.add(
            WorkspaceInvite(
                token=token,
                workspace_id=workspace.id,
                created_by_user_id=callback.from_user.id,
                role=role,
                expires_at=utcnow() + timedelta(days=7),
            )
        )
        session.add(
            AuditLog(
                workspace_id=workspace.id,
                actor_user_id=callback.from_user.id,
                action="workspace.invite_created",
                details=f"role={role.value};token={token[:8]}",
            )
        )
        await session.commit()
    me = await bot.get_me()
    if not me.username:
        await callback.answer("El bot no tiene username para crear el enlace.", show_alert=True)
        return
    link = f"https://t.me/{me.username}?start=ws_{token}"
    await callback.message.edit_text(
        "✅ <b>Invitación creada</b>\n\n"
        f"Rol: <b>{escape(ROLE_LABELS[role])}</b>\n"
        "Comparte este enlace con la persona invitada:\n\n"
        f"<code>{escape(link)}</code>\n\n"
        "Cuando lo abra y pulse Start, aparecerá en tu equipo automáticamente.",
        reply_markup=collaboration_menu(True),
    )
    await callback.answer("Enlace listo")


@router.callback_query(F.data.startswith("collab:member:"))
async def show_member(callback: CallbackQuery) -> None:
    try:
        target_id = int(callback.data.rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("Miembro inválido.", show_alert=True)
        return
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        actor = (
            await get_membership(session, workspace.id, callback.from_user.id)
            if workspace
            else None
        )
        target = (
            await get_membership(session, workspace.id, target_id) if workspace else None
        )
        user = await session.get(User, target_id) if target else None
    if workspace is None or actor is None or target is None or user is None:
        await callback.answer("Miembro no encontrado.", show_alert=True)
        return
    can_manage = actor.role == Role.owner or (
        actor.role == Role.admin and target.role == Role.editor
    )
    await callback.message.edit_text(
        "🤝 <b>Colaborador</b>\n\n"
        f"Nombre: <b>{escape(user.full_name)}</b>\n"
        f"Usuario: <b>{escape('@' + user.username if user.username else 'sin username')}</b>\n"
        f"Rol: <b>{escape(ROLE_LABELS.get(target.role, target.role.value))}</b>",
        reply_markup=collaborator_detail_menu(target_id, target.role.value, can_manage),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("collab:setrole:"))
async def change_member_role(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    if len(parts) != 4 or parts[3] not in {Role.admin.value, Role.editor.value}:
        await callback.answer("Rol inválido.", show_alert=True)
        return
    target_id = int(parts[2])
    new_role = Role(parts[3])
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        actor = (
            await get_membership(session, workspace.id, callback.from_user.id)
            if workspace
            else None
        )
        target = await get_membership(session, workspace.id, target_id) if workspace else None
        if workspace is None or actor is None or target is None:
            allowed = False
        else:
            allowed = actor.role == Role.owner or (
                actor.role == Role.admin
                and target.role == Role.editor
                and new_role == Role.editor
            )
        if not allowed or target.role == Role.owner:
            await callback.answer("No tienes permiso para cambiar este rol.", show_alert=True)
            return
        old_role = target.role
        target.role = new_role
        session.add(
            AuditLog(
                workspace_id=workspace.id,
                actor_user_id=callback.from_user.id,
                action="workspace.role_changed",
                details=f"user_id={target_id};from={old_role.value};to={new_role.value}",
            )
        )
        await session.commit()
    await show_collaboration(callback)


@router.callback_query(F.data.startswith("collab:remove:"))
async def remove_member(callback: CallbackQuery) -> None:
    target_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        actor = (
            await get_membership(session, workspace.id, callback.from_user.id)
            if workspace
            else None
        )
        target = await get_membership(session, workspace.id, target_id) if workspace else None
        allowed = bool(
            workspace
            and actor
            and target
            and target.role != Role.owner
            and (actor.role == Role.owner or (actor.role == Role.admin and target.role == Role.editor))
        )
        if not allowed:
            await callback.answer("No tienes permiso para quitar este acceso.", show_alert=True)
            return
        await session.delete(target)
        session.add(
            AuditLog(
                workspace_id=workspace.id,
                actor_user_id=callback.from_user.id,
                action="workspace.member_removed",
                details=f"user_id={target_id}",
            )
        )
        await session.commit()
    await show_collaboration(callback)


@router.callback_query(F.data == "collab:logs")
async def show_audit_logs(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        workspace = await get_workspace(session, callback.from_user.id)
        if workspace is None:
            await callback.answer("Cuenta no encontrada.", show_alert=True)
            return
        rows = await session.execute(
            select(AuditLog, User)
            .outerjoin(User, User.telegram_id == AuditLog.actor_user_id)
            .where(AuditLog.workspace_id == workspace.id)
            .order_by(AuditLog.created_at.desc())
            .limit(15)
        )
    lines = ["📜 <b>Actividad reciente</b>", ""]
    for event, actor in rows.all():
        when = event.created_at.strftime("%d/%m %H:%M") if event.created_at else "ahora"
        actor_name = actor.full_name if actor else "sistema"
        details = f" · {event.details}" if event.details else ""
        lines.append(
            f"• <code>{escape(when)}</code> · {escape(actor_name)} · "
            f"<b>{escape(event.action)}</b>{escape(details)}"
        )
    if len(lines) == 2:
        lines.append("Todavía no hay eventos registrados.")
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=collaboration_menu(False),
    )
    await callback.answer()
