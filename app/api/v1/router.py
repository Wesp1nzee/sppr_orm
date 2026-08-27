from fastapi import APIRouter

from app.auth.router import router as auth_router
from app.checks.router import router as checks_router
from app.documents.router import router as documents_router
from app.knowledge_base.router import router as knowledge_base_router

# TODO(audit): логирование/аудит (ТЗ, раздел 3.5)

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(checks_router)
api_router.include_router(knowledge_base_router)
api_router.include_router(documents_router)

__all__ = ["api_router"]
