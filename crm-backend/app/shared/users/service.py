import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import api_error
from app.core.security import ahash_password, password_problems
from app.core.utils import utcnow
from app.shared.audit import service as audit
from app.shared.auth.principal import Principal
from app.shared.auth.service import revoke_all_sessions
from app.shared.rbac.models import Role
from app.shared.users.models import Department, Organization, User
from app.shared.users.schemas import UserCreate, UserUpdate

settings = get_settings()


async def reload_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    """Fresh copy with department and roles loaded (needed after writes in async mode)."""
    stmt = select(User).where(User.id == user_id).execution_options(populate_existing=True)
    return (await db.scalars(stmt)).one()


async def get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise api_error(404, "user_not_found", "User not found")
    return user


async def list_users(
    db: AsyncSession,
    page: int,
    page_size: int,
    q: str | None,
    is_active: bool | None,
    department_id: uuid.UUID | None,
    organization_id: uuid.UUID | None,
) -> tuple[list[User], int]:
    stmt, count = select(User), select(func.count()).select_from(User)
    filters = []
    if organization_id is not None:
        filters.append(User.organization_id == organization_id)
    if q:
        like = f"%{q.strip().lower()}%"
        filters.append(or_(func.lower(User.email).like(like), func.lower(User.full_name).like(like)))
    if is_active is not None:
        filters.append(User.is_active == is_active)
    if department_id:
        filters.append(User.department_id == department_id)
    for f in filters:
        stmt, count = stmt.where(f), count.where(f)
    total = await db.scalar(count) or 0
    rows = await db.scalars(
        stmt.order_by(User.full_name).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.unique().all()), total


# ---- helpers -----------------------------------------------------------------------------------


async def _load_roles(db: AsyncSession, role_ids: list[uuid.UUID]) -> list[Role]:
    ids = set(role_ids)
    if not ids:
        return []
    roles = list((await db.scalars(select(Role).where(Role.id.in_(ids)))).all())
    if len(roles) != len(ids):
        raise api_error(400, "role_not_found", "One or more roles do not exist")
    return roles


def _assert_can_grant_roles(actor: Principal, roles: list[Role]) -> None:
    """Stop privilege escalation: you cannot give a role holding permissions you lack."""
    if actor.is_admin:
        return
    for role in roles:
        if {p.code for p in role.permissions} - actor.permissions:
            raise api_error(403, "role_not_grantable", f"You cannot assign the role '{role.name}'")


async def _check_department(db: AsyncSession, department_id: uuid.UUID | None) -> None:
    if department_id and await db.get(Department, department_id) is None:
        raise api_error(400, "department_not_found", "Department does not exist")


async def _check_manager(
    db: AsyncSession, manager_id: uuid.UUID | None, user_id: uuid.UUID | None
) -> None:
    if manager_id is None:
        return
    if manager_id == user_id:
        raise api_error(400, "invalid_manager", "A user cannot be their own manager")
    manager = await db.get(User, manager_id)
    if manager is None:
        raise api_error(400, "manager_not_found", "Manager does not exist")
    # no reporting loops: walk up the chain and make sure we never meet the user
    seen = {manager_id}
    current = manager
    while current.manager_id is not None:
        if current.manager_id == user_id or current.manager_id in seen:
            raise api_error(400, "invalid_manager", "This would create a reporting loop")
        seen.add(current.manager_id)
        current = await db.get(User, current.manager_id)
        if current is None:
            break


async def _other_active_admins(db: AsyncSession, user_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(User).where(
        User.user_type == "admin", User.is_active.is_(True), User.id != user_id
    )
    return await db.scalar(stmt) or 0


# ---- create / update ---------------------------------------------------------------------------


async def create_user(db: AsyncSession, actor: Principal, data: UserCreate, ip: str | None) -> User:
    email = data.email.strip().lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise api_error(409, "email_taken", "A user with this email already exists")
    if data.user_type == "admin" and not actor.is_admin:
        raise api_error(403, "forbidden", "Only an admin can create another admin")
    if data.role_ids and not actor.can("core.user.manage_roles"):
        raise api_error(403, "forbidden", "You cannot assign roles", ["core.user.manage_roles"])
    problems = password_problems(data.password, settings.min_password_length, email)
    if problems:
        raise api_error(422, "weak_password", "Password is too weak", problems)

    org_id = actor.user.organization_id
    if actor.is_admin:
        org_id = data.organization_id
    elif data.organization_id and data.organization_id != org_id:
        raise api_error(403, "organization_forbidden", "You cannot create users for another organization")
    if org_id and await db.get(Organization, org_id) is None:
        raise api_error(400, "organization_not_found", "Organization does not exist")
    await _check_department(db, data.department_id)
    if data.department_id:
        dept = await db.get(Department, data.department_id)
        if dept and dept.organization_id != org_id:
            raise api_error(400, "department_not_found", "Department does not exist in this organization")
    await _check_manager(db, data.manager_id, None)
    roles = await _load_roles(db, data.role_ids)
    if any(role.organization_id != org_id for role in roles):
        raise api_error(400, "role_not_found", "One or more roles do not exist in this organization")
    _assert_can_grant_roles(actor, roles)

    user = User(
        email=email,
        full_name=data.full_name.strip(),
        password_hash=await ahash_password(data.password),
        organization_id=org_id,
        user_type=data.user_type,
        department_id=data.department_id,
        manager_id=data.manager_id,
        must_change_password=data.must_change_password,
        password_changed_at=utcnow(),
        roles=roles,
    )
    db.add(user)
    await db.flush()
    audit.record(
        db, action="user.create", user_id=actor.user.id, entity="user", entity_id=user.id,
        details={"email": email, "user_type": data.user_type, "roles": [r.name for r in roles]},
        ip=ip,
    )
    await db.commit()
    return await reload_user(db, user.id)


async def update_user(
    db: AsyncSession, actor: Principal, user_id: uuid.UUID, data: UserUpdate, ip: str | None
) -> User:
    user = await get_user_or_404(db, user_id)
    if not actor.is_admin and user.organization_id != actor.user.organization_id:
        raise api_error(404, "user_not_found", "User not found")
    fields = data.model_fields_set
    changed: dict = {}

    if user.is_admin and not actor.is_admin:
        raise api_error(403, "forbidden", "Only an admin can modify an admin")
    if data.user_type in {"admin", "org_admin"} and not actor.is_admin:
        raise api_error(403, "forbidden", "Only an admin can make someone an admin")

    # never leave the system without an active admin, never lock yourself out
    demoting = (
        user.is_admin
        and (("user_type" in fields and data.user_type != "admin")
             or ("is_active" in fields and data.is_active is False))
    )
    if demoting and await _other_active_admins(db, user.id) == 0:
        raise api_error(409, "last_admin", "There must be at least one active admin")
    if "is_active" in fields and data.is_active is False and user.id == actor.user.id:
        raise api_error(409, "self_deactivation", "You cannot deactivate your own account")

    if "full_name" in fields and data.full_name is not None:
        user.full_name = data.full_name.strip()
        changed["full_name"] = True
    if "user_type" in fields and data.user_type is not None:
        user.user_type = data.user_type
        changed["user_type"] = data.user_type
    if "department_id" in fields:
        await _check_department(db, data.department_id)
        if data.department_id:
            department = await db.get(Department, data.department_id)
            if department and department.organization_id != user.organization_id:
                raise api_error(400, "department_not_found", "Department does not exist in this organization")
        user.department_id = data.department_id
        changed["department_id"] = str(data.department_id) if data.department_id else None
    if "manager_id" in fields:
        await _check_manager(db, data.manager_id, user.id)
        if data.manager_id:
            manager = await db.get(User, data.manager_id)
            if manager and manager.organization_id != user.organization_id:
                raise api_error(400, "manager_not_found", "Manager does not exist in this organization")
        user.manager_id = data.manager_id
        changed["manager_id"] = str(data.manager_id) if data.manager_id else None
    if "is_active" in fields and data.is_active is not None:
        user.is_active = data.is_active
        changed["is_active"] = data.is_active
        if not data.is_active:
            await revoke_all_sessions(db, user.id)  # kick them out immediately
    if "role_ids" in fields and data.role_ids is not None:
        if not actor.can("core.user.manage_roles"):
            raise api_error(403, "forbidden", "You cannot assign roles", ["core.user.manage_roles"])
        roles = await _load_roles(db, data.role_ids)
        if any(role.organization_id != user.organization_id for role in roles):
            raise api_error(400, "role_not_found", "One or more roles do not exist in this organization")
        _assert_can_grant_roles(actor, roles)
        user.roles = roles
        changed["roles"] = [r.name for r in roles]

    audit.record(
        db, action="user.update", user_id=actor.user.id, entity="user", entity_id=user.id,
        details=changed, ip=ip,
    )
    await db.commit()
    return await reload_user(db, user.id)


async def reset_password(
    db: AsyncSession,
    actor: Principal,
    user_id: uuid.UUID,
    new_password: str,
    must_change: bool,
    ip: str | None,
) -> None:
    user = await get_user_or_404(db, user_id)
    if not actor.is_admin and user.organization_id != actor.user.organization_id:
        raise api_error(404, "user_not_found", "User not found")
    if user.is_admin and not actor.is_admin:
        raise api_error(403, "forbidden", "Only an admin can reset an admin's password")
    problems = password_problems(new_password, settings.min_password_length, user.email)
    if problems:
        raise api_error(422, "weak_password", "Password is too weak", problems)

    user.password_hash = await ahash_password(new_password)
    user.password_changed_at = utcnow()
    user.must_change_password = must_change
    user.failed_login_attempts = 0
    user.locked_until = None
    await revoke_all_sessions(db, user.id)
    audit.record(
        db, action="user.password_reset", user_id=actor.user.id, entity="user",
        entity_id=user.id, ip=ip,
    )
    await db.commit()
