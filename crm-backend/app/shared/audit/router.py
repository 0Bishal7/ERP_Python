import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schemas import Page
from app.shared.audit.models import AuditLog
from app.shared.auth.dependencies import require
from app.shared.auth.principal import Principal

router = APIRouter(prefix="/audit-logs", tags=["audit"])


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    entity: str | None
    entity_id: str | None
    details: dict | None
    ip_address: str | None
    created_at: datetime


@router.get("", response_model=Page[AuditOut])
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    entity: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    p: Principal = Depends(require("core.audit.view")),
    db: AsyncSession = Depends(get_db),
):
    stmt, count = select(AuditLog), select(func.count()).select_from(AuditLog)
    filters = []
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if action:
        filters.append(AuditLog.action == action)
    if entity:
        filters.append(AuditLog.entity == entity)
    if date_from:
        filters.append(AuditLog.created_at >= date_from)
    if date_to:
        filters.append(AuditLog.created_at <= date_to)
    for f in filters:
        stmt, count = stmt.where(f), count.where(f)
    total = await db.scalar(count) or 0
    rows = await db.scalars(
        stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return Page[AuditOut](
        items=[AuditOut.model_validate(r) for r in rows.all()],
        total=total, page=page, page_size=page_size,
    )
