"""CRM module placeholder. Shows how a business module plugs into the shared core.

Real endpoints (leads, quotes, ...) will follow the same two lines:
    p: Principal = Depends(require("crm.lead.view"))          # who may call it
    stmt = apply_scope(select(Lead), Lead.owner_id, p)        # which rows they see
"""
from fastapi import APIRouter, Depends

from app.shared.auth.dependencies import require
from app.shared.auth.principal import Principal
from app.shared.rbac.scope import scope_for

router = APIRouter(prefix="/crm", tags=["crm"])


@router.get("/ping")
async def ping(p: Principal = Depends(require("crm.lead.view"))):
    return {"module": "crm", "user": p.user.email, "scope": scope_for(p)}
