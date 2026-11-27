"""Add organization ownership to administration data.

Revision ID: 8a3f2c6d1b70
Revises: 24d3974a19ec
"""
from alembic import op
import sqlalchemy as sa

revision = "8a3f2c6d1b70"
down_revision = "24d3974a19ec"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("name", name=op.f("uq_organizations_name")),
        sa.UniqueConstraint("code", name=op.f("uq_organizations_code")),
    )
    op.add_column("users", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_users_organization_id_organizations", "users", "organizations", ["organization_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.add_column("departments", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_departments_organization_id_organizations", "departments", "organizations", ["organization_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_departments_organization_id", "departments", ["organization_id"])
    op.drop_constraint("uq_departments_name", "departments", type_="unique")
    op.drop_constraint("uq_departments_code", "departments", type_="unique")
    op.create_unique_constraint("uq_departments_organization_name", "departments", ["organization_id", "name"])
    op.create_unique_constraint("uq_departments_organization_code", "departments", ["organization_id", "code"])
    op.add_column("roles", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_roles_organization_id_organizations", "roles", "organizations", ["organization_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_roles_organization_id", "roles", ["organization_id"])
    op.drop_constraint("uq_roles_name", "roles", type_="unique")
    op.create_unique_constraint("uq_roles_organization_name", "roles", ["organization_id", "name"])


def downgrade() -> None:
    op.drop_constraint("uq_roles_organization_name", "roles", type_="unique")
    op.create_unique_constraint("uq_roles_name", "roles", ["name"])
    op.drop_index("ix_roles_organization_id", table_name="roles")
    op.drop_constraint("fk_roles_organization_id_organizations", "roles", type_="foreignkey")
    op.drop_column("roles", "organization_id")
    op.drop_constraint("uq_departments_organization_code", "departments", type_="unique")
    op.drop_constraint("uq_departments_organization_name", "departments", type_="unique")
    op.create_unique_constraint("uq_departments_code", "departments", ["code"])
    op.create_unique_constraint("uq_departments_name", "departments", ["name"])
    op.drop_index("ix_departments_organization_id", table_name="departments")
    op.drop_constraint("fk_departments_organization_id_organizations", "departments", type_="foreignkey")
    op.drop_column("departments", "organization_id")
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_constraint("fk_users_organization_id_organizations", "users", type_="foreignkey")
    op.drop_column("users", "organization_id")
    op.drop_table("organizations")
