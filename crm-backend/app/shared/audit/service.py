import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.audit.models import AuditLog


def record(
    db: AsyncSession,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
    entity: str | None = None,
    entity_id: str | uuid.UUID | None = None,
    details: dict | None = None,
    ip: str | None = None,
) -> None:
    """Add an audit row to the current transaction. The caller commits."""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id else None,
            details=details,
            ip_address=ip,
        )
    )
