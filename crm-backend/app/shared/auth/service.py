import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import api_error
from app.core.security import (
    adummy_verify,
    ahash_password,
    averify_password,
    hash_token,
    needs_rehash,
    new_token,
    password_problems,
)
from app.core.utils import ensure_utc, utcnow
from app.shared.audit import service as audit
from app.shared.auth.models import AuthSession
from app.shared.users.models import User

settings = get_settings()

_INVALID = ("invalid_credentials", "Incorrect email or password")


async def login(
    db: AsyncSession, email: str, password: str, ip: str | None, user_agent: str | None
) -> tuple[User, str, AuthSession]:
    """Check credentials, create a session. Returns (user, raw_token, session)."""
    email = email.strip().lower()
    now = utcnow()
    user = await db.scalar(select(User).where(User.email == email))

    if user is None:
        await adummy_verify(password)  # same timing as a real check
        audit.record(db, action="auth.login_failed", details={"email": email}, ip=ip)
        await db.commit()
        raise api_error(401, *_INVALID)

    locked_until = ensure_utc(user.locked_until)
    if locked_until and locked_until > now:
        audit.record(db, action="auth.login_blocked", user_id=user.id, ip=ip)
        await db.commit()
        raise api_error(429, "account_locked", "Too many failed attempts. Try again later.")

    if not await averify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        details = {"attempts": user.failed_login_attempts}
        if user.failed_login_attempts >= settings.max_failed_logins:
            user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
            user.failed_login_attempts = 0
            details["locked"] = True
        audit.record(db, action="auth.login_failed", user_id=user.id, details=details, ip=ip)
        await db.commit()
        raise api_error(401, *_INVALID)

    if not user.is_active:
        audit.record(db, action="auth.login_disabled", user_id=user.id, ip=ip)
        await db.commit()
        raise api_error(403, "account_disabled", "This account is disabled. Contact an admin.")

    # Success
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    if needs_rehash(user.password_hash):
        user.password_hash = await ahash_password(password)

    raw_token = new_token()
    session = AuthSession(
        token_hash=hash_token(raw_token),
        csrf_token=new_token(),
        user_id=user.id,
        last_seen_at=now,
        expires_at=now + timedelta(hours=settings.session_absolute_hours),
        ip_address=ip,
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(session)
    audit.record(db, action="auth.login", user_id=user.id, ip=ip)
    await db.commit()
    return user, raw_token, session


async def load_session(db: AsyncSession, raw_token: str) -> AuthSession | None:
    """Find a valid session for a cookie token, or None."""
    session = await db.scalar(
        select(AuthSession).where(AuthSession.token_hash == hash_token(raw_token))
    )
    if session is None or session.revoked_at is not None:
        return None
    now = utcnow()
    if ensure_utc(session.expires_at) <= now:
        return None
    idle_limit = ensure_utc(session.last_seen_at) + timedelta(minutes=settings.session_idle_minutes)
    if idle_limit <= now:
        return None
    return session


async def touch_session(db: AsyncSession, session: AuthSession) -> None:
    """Slide the idle timeout, at most once a minute to avoid a write on every request."""
    now = utcnow()
    if now - ensure_utc(session.last_seen_at) > timedelta(seconds=60):
        session.last_seen_at = now
        await db.commit()


async def revoke_session(db: AsyncSession, session: AuthSession, ip: str | None) -> None:
    session.revoked_at = utcnow()
    audit.record(db, action="auth.logout", user_id=session.user_id, ip=ip)
    await db.commit()


async def revoke_all_sessions(
    db: AsyncSession, user_id: uuid.UUID, except_session_id: uuid.UUID | None = None
) -> None:
    """Mark every active session of a user as revoked. The caller commits."""
    stmt = (
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    if except_session_id:
        stmt = stmt.where(AuthSession.id != except_session_id)
    await db.execute(stmt)


async def change_password(
    db: AsyncSession,
    user: User,
    session: AuthSession,
    current_password: str,
    new_password: str,
    ip: str | None,
) -> None:
    if not await averify_password(current_password, user.password_hash):
        audit.record(db, action="auth.password_change_failed", user_id=user.id, ip=ip)
        await db.commit()
        raise api_error(400, "wrong_password", "Current password is incorrect")
    problems = password_problems(new_password, settings.min_password_length, user.email)
    if problems:
        raise api_error(422, "weak_password", "New password is too weak", problems)
    if current_password == new_password:
        raise api_error(422, "same_password", "New password must be different")

    user.password_hash = await ahash_password(new_password)
    user.password_changed_at = utcnow()
    user.must_change_password = False
    await revoke_all_sessions(db, user.id, except_session_id=session.id)
    audit.record(db, action="auth.password_changed", user_id=user.id, ip=ip)
    await db.commit()
