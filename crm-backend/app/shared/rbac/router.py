import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import api_error
from app.shared.audit import service as audit
from app.shared.auth.dependencies import client_ip, require
from app.shared.auth.principal import Principal
from app.shared.rbac.models import Permission, Role, user_roles
from app.shared.rbac.schemas import (
    PermissionOut,
    RoleCreate,
    RoleOut,
    RolePermissionsIn,
    RoleUpdate,
)

router = APIRouter(tags=["roles"])


async def _get_role(db: AsyncSession, role_id: uuid.UUID) -> Role:
    role = await db.get(Role, role_id)
    if role is None:
        raise api_error(404, "role_not_found", "Role not found")
    return role


def _org_roles(stmt, p: Principal):
    # Platform admins can inspect all tenants; organization members see their tenant only.
    return stmt if p.is_admin else stmt.where(Role.organization_id == p.user.organization_id)


async def _load_permissions(
    db: AsyncSession, actor: Principal, codes: list[str]
) -> list[Permission]:
    wanted = set(codes)
    perms = list((await db.scalars(select(Permission).where(Permission.code.in_(wanted)))).all())
    unknown = wanted - {p.code for p in perms}
    if unknown:
        raise api_error(400, "unknown_permission", "Unknown permission codes", sorted(unknown))
    # no privilege escalation: you can only grant permissions you hold yourself
    not_held = [p.code for p in perms if not actor.can(p.code)]
    if not_held:
        raise api_error(403, "permission_not_grantable", "You cannot grant these permissions", not_held)
    return perms


@router.get("/permissions", response_model=list[PermissionOut])
async def list_permissions(
    p: Principal = Depends(require("core.role.view")), db: AsyncSession = Depends(get_db)
):
    return (await db.scalars(select(Permission).order_by(Permission.code))).all()


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    p: Principal = Depends(require("core.role.view")), db: AsyncSession = Depends(get_db)
):
    return (await db.scalars(_org_roles(select(Role), p).order_by(Role.name))).all()


@router.get("/roles/{role_id}", response_model=RoleOut)
async def get_role(
    role_id: uuid.UUID,
    p: Principal = Depends(require("core.role.view")),
    db: AsyncSession = Depends(get_db),
):
    role = await _get_role(db, role_id)
    if not p.is_admin and role.organization_id != p.user.organization_id:
        raise api_error(404, "role_not_found", "Role not found")
    return role


@router.post("/roles", response_model=RoleOut, status_code=201)
async def create_role(
    body: RoleCreate,
    request: Request,
    p: Principal = Depends(require("core.role.manage")),
    db: AsyncSession = Depends(get_db),
):
    org_id = body.organization_id if p.is_admin else p.user.organization_id
    if await db.scalar(select(Role.id).where(Role.name == body.name.strip(), Role.organization_id == org_id)):
        raise api_error(409, "role_exists", "A role with this name already exists")
    perms = await _load_permissions(db, p, body.permission_codes)
    role = Role(organization_id=org_id, name=body.name.strip(), description=body.description, permissions=perms)
    db.add(role)
    await db.flush()
    audit.record(db, action="role.create", user_id=p.user.id, entity="role", entity_id=role.id,
                 details={"name": role.name, "permissions": body.permission_codes},
                 ip=client_ip(request))
    await db.commit()
    return role


@router.patch("/roles/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: uuid.UUID,
    body: RoleUpdate,
    request: Request,
    p: Principal = Depends(require("core.role.manage")),
    db: AsyncSession = Depends(get_db),
):
    role = await _get_role(db, role_id)
    if not p.is_admin and role.organization_id != p.user.organization_id:
        raise api_error(404, "role_not_found", "Role not found")
    if body.name is not None and body.name.strip() != role.name:
        if role.is_system:
            raise api_error(409, "system_role", "System roles cannot be renamed")
        if await db.scalar(select(Role.id).where(Role.name == body.name.strip())):
            raise api_error(409, "role_exists", "A role with this name already exists")
        role.name = body.name.strip()
    if body.description is not None:
        role.description = body.description
    audit.record(db, action="role.update", user_id=p.user.id, entity="role", entity_id=role.id,
                 details=body.model_dump(exclude_unset=True), ip=client_ip(request))
    await db.commit()
    return role


@router.put("/roles/{role_id}/permissions", response_model=RoleOut)
async def set_role_permissions(
    role_id: uuid.UUID,
    body: RolePermissionsIn,
    request: Request,
    p: Principal = Depends(require("core.role.manage")),
    db: AsyncSession = Depends(get_db),
):
    role = await _get_role(db, role_id)
    if not p.is_admin and role.organization_id != p.user.organization_id:
        raise api_error(404, "role_not_found", "Role not found")
    # a non-admin must not be able to strip or change permissions they do not hold
    current = {perm.code for perm in role.permissions}
    if not p.is_admin and (current - p.permissions):
        raise api_error(403, "forbidden", "This role holds permissions you do not have")
    role.permissions = await _load_permissions(db, p, body.permission_codes)
    audit.record(db, action="role.set_permissions", user_id=p.user.id, entity="role",
                 entity_id=role.id, details={"permissions": sorted(body.permission_codes)},
                 ip=client_ip(request))
    await db.commit()
    return role


@router.delete("/roles/{role_id}", status_code=204)
async def delete_role(
    role_id: uuid.UUID,
    request: Request,
    p: Principal = Depends(require("core.role.manage")),
    db: AsyncSession = Depends(get_db),
):
    role = await _get_role(db, role_id)
    if not p.is_admin and role.organization_id != p.user.organization_id:
        raise api_error(404, "role_not_found", "Role not found")
    if role.is_system:
        raise api_error(409, "system_role", "System roles cannot be deleted")
    in_use = await db.scalar(select(user_roles.c.user_id).where(user_roles.c.role_id == role.id).limit(1))
    if in_use:
        raise api_error(409, "role_in_use", "Remove this role from all users first")
    audit.record(db, action="role.delete", user_id=p.user.id, entity="role", entity_id=role.id,
                 details={"name": role.name}, ip=client_ip(request))
    await db.delete(role)
    await db.commit()
