"""Idempotent bootstrap. Safe to run on every deploy:

    python -m app.scripts.seed

* syncs the permission table with app/shared/rbac/registry.py
* creates starter departments and roles (existing roles are never overwritten)
* creates the first admin from FIRST_ADMIN_EMAIL / FIRST_ADMIN_PASSWORD if no admin exists
"""
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password, password_problems
from app.core.utils import utcnow
from app.shared.rbac.defaults import DEFAULT_DEPARTMENTS, DEFAULT_ROLES
from app.shared.rbac.models import Permission, Role
from app.shared.rbac.registry import PERMISSIONS, module_of
from app.shared.users.models import Department, User


async def seed_all(
    db: AsyncSession,
    admin_email: str | None = None,
    admin_password: str | None = None,
    admin_name: str = "System Admin",
) -> None:
    # 1) permissions
    existing = {p.code: p for p in (await db.scalars(select(Permission))).all()}
    for code, description in PERMISSIONS.items():
        if code in existing:
            existing[code].description = description
        else:
            db.add(Permission(code=code, module=module_of(code), description=description))
    await db.flush()
    perms = {p.code: p for p in (await db.scalars(select(Permission))).all()}

    # 2) departments
    have = {d.code for d in (await db.scalars(select(Department))).all()}
    for name, code in DEFAULT_DEPARTMENTS:
        if code not in have:
            db.add(Department(name=name, code=code))

    # 3) roles (only created, never overwritten, so admin edits survive deploys)
    role_names = {r.name for r in (await db.scalars(select(Role))).all()}
    for name, (description, codes) in DEFAULT_ROLES.items():
        if name not in role_names:
            db.add(Role(name=name, description=description, is_system=True,
                        permissions=[perms[c] for c in codes]))

    # 4) first admin
    has_admin = await db.scalar(select(User.id).where(User.user_type == "admin").limit(1))
    if not has_admin:
        if admin_email and admin_password:
            settings = get_settings()
            problems = password_problems(admin_password, settings.min_password_length, admin_email)
            if problems:
                raise SystemExit(f"FIRST_ADMIN_PASSWORD is too weak: {', '.join(problems)}")
            db.add(User(
                email=admin_email.strip().lower(), full_name=admin_name,
                password_hash=hash_password(admin_password), user_type="admin",
                password_changed_at=utcnow(),
            ))
            print(f"Created first admin: {admin_email}")
        else:
            print("No admin exists. Set FIRST_ADMIN_EMAIL and FIRST_ADMIN_PASSWORD and run again.")
    await db.commit()


async def main() -> None:
    s = get_settings()
    async with SessionLocal() as db:
        await seed_all(db, s.first_admin_email, s.first_admin_password, s.first_admin_name)
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
