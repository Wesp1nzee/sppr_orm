from fastapi import APIRouter

from app.audit.router import router as audit_router
from app.auth.router import router as auth_router
from app.case_materials.router import router as case_materials_router
from app.checks.router import router as checks_router
from app.documents.router import router as documents_router
from app.knowledge_base.router import router as knowledge_base_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(checks_router)
api_router.include_router(knowledge_base_router)
api_router.include_router(documents_router)
api_router.include_router(case_materials_router)
api_router.include_router(audit_router)

__all__ = ["api_router"]
