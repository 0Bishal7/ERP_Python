from app.shared.rbac.registry import PERMISSIONS, module_of
from app.shared.users.models import User


def effective_permissions(user: User) -> frozenset[str]:
    """Admins hold every permission. Everyone else gets the union of their roles."""
    if user.is_admin:
        return frozenset(PERMISSIONS)
    return frozenset(p.code for role in user.roles for p in role.permissions)


def modules_for(permissions: frozenset[str] | set[str]) -> list[str]:
    return sorted({module_of(code) for code in permissions})
