import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.shared.rbac.schemas import RoleBrief

UserType = Literal["admin", "manager", "staff"]


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    code: str
    is_active: bool


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    code: str = Field(min_length=2, max_length=30, pattern=r"^[a-z0-9_]+$")


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    is_active: bool | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    full_name: str
    user_type: str
    is_active: bool
    must_change_password: bool
    manager_id: uuid.UUID | None
    department: DepartmentOut | None
    roles: list[RoleBrief]
    last_login_at: datetime | None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(max_length=128)
    user_type: UserType = "staff"
    department_id: uuid.UUID | None = None
    manager_id: uuid.UUID | None = None
    role_ids: list[uuid.UUID] = []
    must_change_password: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    user_type: UserType | None = None
    department_id: uuid.UUID | None = None
    manager_id: uuid.UUID | None = None
    is_active: bool | None = None
    role_ids: list[uuid.UUID] | None = None


class PasswordResetIn(BaseModel):
    new_password: str = Field(max_length=128)
    must_change_password: bool = True
