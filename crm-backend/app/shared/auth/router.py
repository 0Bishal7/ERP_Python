from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.utils import ensure_utc, utcnow
from app.shared.auth import service
from app.shared.auth.dependencies import client_ip, get_principal
from app.shared.auth.principal import Principal
from app.shared.auth.schemas import ChangePasswordIn, LoginIn, MeOut
from app.shared.rbac.scope import scope_for_user
from app.shared.rbac.service import effective_permissions, modules_for
from app.shared.users.models import User
from app.shared.users.schemas import UserOut

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


def _me(user: User, csrf_token: str) -> MeOut:
    perms = effective_permissions(user)
    return MeOut(
        user=UserOut.model_validate(user),
        permissions=sorted(perms),
        modules=modules_for(perms),
        scope=scope_for_user(user),
        csrf_token=csrf_token,
    )


@router.post("/login", response_model=MeOut)
async def login(
    body: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    user, raw_token, session = await service.login(
        db, body.email, body.password, client_ip(request), request.headers.get("user-agent")
    )
    max_age = int((ensure_utc(session.expires_at) - utcnow()).total_seconds())
    response.set_cookie(
        key=settings.cookie_name,
        value=raw_token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
    )
    return _me(user, session.csrf_token)


@router.get("/me", response_model=MeOut)
async def me(p: Principal = Depends(get_principal)):
    return _me(p.user, p.session.csrf_token)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    p: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    await service.revoke_session(db, p.session, client_ip(request))
    response.delete_cookie(settings.cookie_name, domain=settings.cookie_domain, path="/")


@router.post("/logout-all", status_code=204)
async def logout_all(
    request: Request,
    response: Response,
    p: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    await service.revoke_all_sessions(db, p.user.id)
    await db.commit()
    response.delete_cookie(settings.cookie_name, domain=settings.cookie_domain, path="/")


@router.post("/change-password", status_code=204)
async def change_password(
    body: ChangePasswordIn,
    request: Request,
    p: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    await service.change_password(
        db, p.user, p.session, body.current_password, body.new_password, client_ip(request)
    )
