from dataclasses import dataclass

from app.shared.auth.models import AuthSession
from app.shared.users.models import User


@dataclass
class Principal:
    """The logged-in user for the current request."""

    user: User
    session: AuthSession
    permissions: frozenset[str]

    @property
    def is_admin(self) -> bool:
        return self.user.is_admin

    def can(self, code: str) -> bool:
        return self.is_admin or code in self.permissions
