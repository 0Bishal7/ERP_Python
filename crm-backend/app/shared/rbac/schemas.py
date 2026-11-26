import uuid

from pydantic import BaseModel, ConfigDict, Field


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    module: str
    description: str


class RoleBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class RoleOut(RoleBrief):
    organization_id: uuid.UUID | None = None
    description: str
    is_system: bool
    permissions: list[PermissionOut]


class RoleCreate(BaseModel):
    organization_id: uuid.UUID | None = None
    name: str = Field(min_length=2, max_length=100)
    description: str = ""
    permission_codes: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = None


class RolePermissionsIn(BaseModel):
    permission_codes: list[str]
