"""Record scope: which rows a user may see.  staff = own, manager = own + team, admin = all.

Modules use it like:
    stmt = apply_scope(select(Lead), Lead.owner_id, principal)
"""
from sqlalchemy import Select, or_, select

from app.shared.auth.principal import Principal
from app.shared.users.models import User


def scope_for_user(user: User) -> str:
    if user.user_type == "admin":
        return "all"
    if user.user_type == "manager":
        return "team"
    return "own"


def scope_for(p: Principal) -> str:
    return scope_for_user(p.user)


def apply_scope(stmt: Select, owner_col, p: Principal) -> Select:
    scope = scope_for(p)
    if scope == "all":
        return stmt
    if scope == "own":
        return stmt.where(owner_col == p.user.id)
    team_ids = select(User.id).where(User.manager_id == p.user.id)
    return stmt.where(or_(owner_col == p.user.id, owner_col.in_(team_ids)))
