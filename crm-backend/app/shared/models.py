"""Import every model once so Alembic and Base.metadata see all tables."""
from app.shared.audit.models import AuditLog  # noqa: F401
from app.shared.auth.models import AuthSession  # noqa: F401
from app.shared.rbac.models import Permission, Role, role_permissions, user_roles  # noqa: F401
from app.shared.users.models import Department, User  # noqa: F401
