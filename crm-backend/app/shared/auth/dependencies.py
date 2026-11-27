from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import api_error
from app.core.security import safe_equal
from app.shared.auth import service
from app.shared.auth.principal import Principal
from app.shared.rbac.service import effective_permissions
from app.shared.users.models import User

settings = get_settings()
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def client_ip(request: Request) -> str | None:
    # Behind Nginx, run uvicorn with --proxy-headers so this is the real client IP.
    return request.client.host if request.client else None


async def get_principal(request: Request, db: AsyncSession = Depends(get_db)) -> Principal:
    """Resolve the session cookie to a user. Use directly for routes that must work even
    while a password change is pending (me, change-password, logout)."""
    raw = request.cookies.get(settings.cookie_name)
    if not raw:
        raise api_error(401, "not_authenticated", "Please log in")

    session = await service.load_session(db, raw)
    if session is None:
        raise api_error(401, "session_expired", "Session expired. Please log in again")

    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise api_error(401, "not_authenticated", "Please log in")
    if user.organization_id and user.organization and not user.organization.is_active:
        raise api_error(403, "organization_disabled", "This organization is disabled")

    # CSRF: unsafe methods must echo the token we gave the client at login / on /auth/me
    if request.method not in SAFE_METHODS:
        sent = request.headers.get("X-CSRF-Token", "")
        if not sent or not safe_equal(sent, session.csrf_token):
            raise api_error(403, "csrf_failed", "Missing or invalid CSRF token")

    await service.touch_session(db, session)
    return Principal(user=user, session=session, permissions=effective_permissions(user))


async def get_active_principal(p: Principal = Depends(get_principal)) -> Principal:
    """Like get_principal, but blocks users who still have to change their password."""
    if p.user.must_change_password:
        raise api_error(403, "password_change_required", "You must change your password first")
    return p


def require(*codes: str):
    """Route guard:  Depends(require('crm.lead.create'))  -> returns the Principal."""

    async def checker(p: Principal = Depends(get_active_principal)) -> Principal:
        missing = [c for c in codes if not p.can(c)]
        if missing:
            raise api_error(403, "forbidden", "You do not have permission for this action", missing)
        return p

    return checker


async def require_admin(p: Principal = Depends(get_active_principal)) -> Principal:
    if not p.is_admin:
        raise api_error(403, "forbidden", "Admin only")
    return p
