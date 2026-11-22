import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import api_error
from app.core.schemas import Page
from app.shared.audit import service as audit
from app.shared.auth.dependencies import client_ip, require
from app.shared.auth.principal import Principal
from app.shared.users import service
from app.shared.users.models import Department
from app.shared.users.schemas import (
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    PasswordResetIn,
    UserCreate,
    UserOut,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])
departments_router = APIRouter(prefix="/departments", tags=["departments"])


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
    users, total = await service.list_users(db, page, page_size, q, is_active, department_id)
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
    return await service.get_user_or_404(db, user_id)


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
    return (await db.scalars(select(Department).order_by(Department.name))).all()


@departments_router.post("", response_model=DepartmentOut, status_code=201)
async def create_department(
    body: DepartmentCreate,
    request: Request,
    p: Principal = Depends(require("core.department.manage")),
    db: AsyncSession = Depends(get_db),
):
    exists = await db.scalar(
        select(Department.id).where((Department.code == body.code) | (Department.name == body.name))
    )
    if exists:
        raise api_error(409, "department_exists", "A department with this name or code exists")
    dept = Department(name=body.name.strip(), code=body.code)
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
    dept = await db.get(Department, department_id)
    if dept is None:
        raise api_error(404, "department_not_found", "Department not found")
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if value is not None:
            setattr(dept, key, value.strip() if isinstance(value, str) else value)
    audit.record(db, action="department.update", user_id=p.user.id, entity="department",
                 entity_id=dept.id, details=changes, ip=client_ip(request))
    await db.commit()
    return dept
