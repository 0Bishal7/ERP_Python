import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import api_error
from app.core.schemas import Page
from app.shared.audit import service as audit
from app.shared.auth.dependencies import client_ip, require, require_admin
from app.shared.auth.principal import Principal
from app.shared.users import service
from app.shared.users.models import Department, Organization
from app.shared.users.schemas import (
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    PasswordResetIn,
    UserCreate,
    UserOut,
    UserUpdate,
    OrganizationCreate,
    OrganizationOut,
    OrganizationUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])
departments_router = APIRouter(prefix="/departments", tags=["departments"])
organizations_router = APIRouter(prefix="/organizations", tags=["organizations"])


@organizations_router.get("", response_model=list[OrganizationOut])
async def list_organizations(p: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(Organization).order_by(Organization.name))).all()


# @organizations_router.post("", response_model=OrganizationOut, status_code=201)
# async def create_organization(body: OrganizationCreate, request: Request,
#                               p: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
#     exists = await db.scalar(select(Organization.id).where(
#         (Organization.code == body.code) | (Organization.name == body.name.strip())))
#     if exists:
#         raise api_error(409, "organization_exists", "An organization with this name or code exists")
#     org = Organization(name=body.name.strip(), code=body.code)
#     db.add(org)
#     await db.flush()
#     audit.record(db, action="organization.create", user_id=p.user.id, entity="organization",
#                  entity_id=org.id, details={"code": org.code}, ip=client_ip(request))
#     await db.commit()
#     return org


# @organizations_router.patch("/{organization_id}", response_model=OrganizationOut)
# async def update_organization(organization_id: uuid.UUID, body: OrganizationUpdate, request: Request,
#                               p: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
#     org = await db.get(Organization, organization_id)
#     if org is None:
#         raise api_error(404, "organization_not_found", "Organization not found")
#     changes = body.model_dump(exclude_unset=True)
#     for key, value in changes.items():
#         if value is not None:
#             setattr(org, key, value.strip() if isinstance(value, str) else value)
#     audit.record(db, action="organization.update", user_id=p.user.id, entity="organization",
#                  entity_id=org.id, details=changes, ip=client_ip(request))
#     await db.commit()
#     return org


@organizations_router.post("", response_model=OrganizationOut, status_code=201)
async def create_organization(
    body: OrganizationCreate,
    request: Request,
    p: Principal = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    # Normalize input
    name = body.name.strip()
    code = body.code.strip()
    address = body.address.strip() if body.address else None
    gst_number = body.gst_number.strip().upper() if body.gst_number else None
    email = str(body.email).strip().lower() if body.email else None

    # Check duplicate organization name or code
    conditions = [
        Organization.name == name,
        Organization.code == code
    ]

    if gst_number:
        conditions.append(Organization.gst_number == gst_number)

    if email:
        conditions.append(Organization.email == email)

    exists = await db.scalar(
        select(Organization.id).where(
            or_(*conditions)
        )
    )

    if exists:
        raise api_error(
            409,
            "organization_exists",
            "An organization with this name, code, GST number, or email already exists"
        )

    # Create organization
    org = Organization(
        name=name,
        code=code,
        address=address,
        gst_number=gst_number,
        email=email
    )

    db.add(org)
    await db.flush()

    # Audit log
    audit.record(
        db,
        action="organization.create",
        user_id=p.user.id,
        entity="organization",
        entity_id=org.id,
        details={
            "code": org.code,
            "name": org.name,
            "gst_number": org.gst_number,
            "email": org.email
        },
        ip=client_ip(request)
    )

    await db.commit()
    await db.refresh(org)

    return org


@organizations_router.patch("/{organization_id}", response_model=OrganizationOut)
async def update_organization(
    organization_id: uuid.UUID,
    body: OrganizationUpdate,
    request: Request,
    p: Principal = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    org = await db.get(Organization, organization_id)

    if org is None:
        raise api_error(
            404,
            "organization_not_found",
            "Organization not found"
        )

    # Get only supplied fields
    changes = body.model_dump(exclude_unset=True)

    # Normalize values
    for key, value in changes.items():
        if isinstance(value, str):
            value = value.strip()

            if key == "gst_number":
                value = value.upper()

            elif key == "email":
                value = value.lower()

        changes[key] = value

    # Check duplicate values against other organizations
    conditions = []

    for key in ("name", "gst_number", "email"):
        value = changes.get(key)

        if value:
            conditions.append(
                getattr(Organization, key) == value
            )

    if "code" in changes and changes["code"]:
        conditions.append(
            Organization.code == changes["code"]
        )

    if conditions:
        exists = await db.scalar(
            select(Organization.id).where(
                Organization.id != organization_id,
                or_(*conditions)
            )
        )

        if exists:
            raise api_error(
                409,
                "organization_exists",
                "Another organization with this name, code, GST number, or email already exists"
            )

    # Apply updates
    for key, value in changes.items():
        setattr(org, key, value)

    # Audit log
    audit.record(
        db,
        action="organization.update",
        user_id=p.user.id,
        entity="organization",
        entity_id=org.id,
        details=changes,
        ip=client_ip(request)
    )

    await db.commit()
    await db.refresh(org)

    return org



# ---- users -------------------------------------------------------------------------------------


@router.get("", response_model=Page[UserOut])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    is_active: bool | None = None,
    department_id: uuid.UUID | None = None,
    p: Principal = Depends(require("core.user.view")),
    db: AsyncSession = Depends(get_db),
):
    users, total = await service.list_users(db, page, page_size, q, is_active, department_id,
                                            None if p.is_admin else p.user.organization_id)
    return Page[UserOut](
        items=[UserOut.model_validate(u) for u in users], total=total, page=page, page_size=page_size
    )


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    request: Request,
    p: Principal = Depends(require("core.user.create")),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_user(db, p, body, client_ip(request))


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    p: Principal = Depends(require("core.user.view")),
    db: AsyncSession = Depends(get_db),
):
    user = await service.get_user_or_404(db, user_id)
    if not p.is_admin and user.organization_id != p.user.organization_id:
        raise api_error(404, "user_not_found", "User not found")
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    request: Request,
    p: Principal = Depends(require("core.user.update")),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_user(db, p, user_id, body, client_ip(request))


@router.post("/{user_id}/reset-password", status_code=204)
async def reset_password(
    user_id: uuid.UUID,
    body: PasswordResetIn,
    request: Request,
    p: Principal = Depends(require("core.user.reset_password")),
    db: AsyncSession = Depends(get_db),
):
    await service.reset_password(
        db, p, user_id, body.new_password, body.must_change_password, client_ip(request)
    )


# ---- departments -------------------------------------------------------------------------------


@departments_router.get("", response_model=list[DepartmentOut])
async def list_departments(
    p: Principal = Depends(require("core.department.view")), db: AsyncSession = Depends(get_db)
):
    stmt = select(Department).order_by(Department.name)
    if not p.is_admin:
        stmt = stmt.where(Department.organization_id == p.user.organization_id)
    return (await db.scalars(stmt)).all()


@departments_router.post("", response_model=DepartmentOut, status_code=201)
async def create_department(
    body: DepartmentCreate,
    request: Request,
    p: Principal = Depends(require("core.department.manage")),
    db: AsyncSession = Depends(get_db),
):
    org_id = body.organization_id if p.is_admin else p.user.organization_id
    exists = await db.scalar(select(Department.id).where(
        Department.organization_id == org_id,
        (Department.code == body.code) | (Department.name == body.name.strip())))
    if exists:
        raise api_error(409, "department_exists", "A department with this name or code exists")
    dept = Department(organization_id=org_id, name=body.name.strip(), code=body.code)
    db.add(dept)
    await db.flush()
    audit.record(db, action="department.create", user_id=p.user.id, entity="department",
                 entity_id=dept.id, details={"code": dept.code}, ip=client_ip(request))
    await db.commit()
    return dept


@departments_router.patch("/{department_id}", response_model=DepartmentOut)
async def update_department(
    department_id: uuid.UUID,
    body: DepartmentUpdate,
    request: Request,
    p: Principal = Depends(require("core.department.manage")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Department).where(Department.id == department_id)
    if not p.is_admin:
        stmt = stmt.where(Department.organization_id == p.user.organization_id)
    dept = await db.scalar(stmt)
    if dept is None or (not p.is_admin and dept.organization_id != p.user.organization_id):
        raise api_error(404, "department_not_found", "Department not found")
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if value is not None:
            setattr(dept, key, value.strip() if isinstance(value, str) else value)
    audit.record(db, action="department.update", user_id=p.user.id, entity="department",
                 entity_id=dept.id, details=changes, ip=client_ip(request))
    await db.commit()
    return dept
