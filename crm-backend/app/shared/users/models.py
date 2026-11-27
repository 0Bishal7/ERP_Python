import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin, uuid_pk

USER_TYPES = ("admin", "org_admin", "manager", "staff")


# class Organization(Base, TimestampMixin):
#     __tablename__ = "organizations"

#     id: Mapped[uuid.UUID] = uuid_pk()
#     name: Mapped[str] = mapped_column(String(150), unique=True)
#     code: Mapped[str] = mapped_column(String(40), unique=True)
#     is_active: Mapped[bool] = mapped_column(Boolean, default=True)
class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = uuid_pk()

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)

    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    gst_number: Mapped[str | None] = mapped_column(
        String(15),
        unique=True,
        nullable=True
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )


class Department(Base, TimestampMixin):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("organization_id", "name"), UniqueConstraint("organization_id", "code"))

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    organization: Mapped[Organization | None] = relationship(lazy="joined")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # admin = sees everything, manager = own team, staff = own records
    user_type: Mapped[str] = mapped_column(String(20), default="staff")
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Eager loading: async SQLAlchemy cannot lazy load, so we load these with the user.
    department: Mapped[Department | None] = relationship(lazy="joined")
    organization: Mapped[Organization | None] = relationship(lazy="joined")
    roles: Mapped[list["Role"]] = relationship(  # noqa: F821
        secondary="user_roles", back_populates="users", lazy="selectin"
    )

    @property
    def is_admin(self) -> bool:
        return self.user_type == "admin"


# Make sure the Role / Permission tables are registered whenever User is imported.
from app.shared.rbac import models as _rbac_models  # noqa: E402,F401
