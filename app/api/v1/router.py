"""Агрегатор роутеров API v1. Префикс /api/v1 добавляется в main.py."""

from fastapi import APIRouter

from app.auth.router import router as auth_router

# Каркасы доменов созданы, но роутов пока нет — подключаются по мере
# реализации модулей из ТЗ:
# TODO(checks): подключить router домена «14 критериев» (ТЗ, раздел 3.1)
# from app.checks.router import router as checks_router
# TODO(documents): генератор документов (ТЗ, раздел 3.4)
# TODO(knowledge_base): база знаний (ТЗ, раздел 3.3)
# TODO(audit): логирование/аудит (ТЗ, раздел 3.5)

api_router = APIRouter()
api_router.include_router(auth_router)

__all__ = ["api_router"]
