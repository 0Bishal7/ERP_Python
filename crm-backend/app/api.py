from fastapi import APIRouter

from app.modules.crm.router import router as crm_router
from app.shared.audit.router import router as audit_router
from app.shared.auth.router import router as auth_router
from app.shared.rbac.router import router as rbac_router
from app.shared.users.router import departments_router
from app.shared.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(departments_router)
api_router.include_router(rbac_router)
api_router.include_router(audit_router)
api_router.include_router(crm_router)  # later: hrms, accounts, inventory
