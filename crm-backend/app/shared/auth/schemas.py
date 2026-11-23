from pydantic import BaseModel, EmailStr, Field

from app.shared.users.schemas import UserOut


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class MeOut(BaseModel):
    user: UserOut
    permissions: list[str]
    modules: list[str]
    scope: str  # own | team | all
    csrf_token: str


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)
