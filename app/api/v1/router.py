"""Агрегатор роутеров API v1. Префикс /api/v1 добавляется в main.py."""

from fastapi import APIRouter

from app.api.v1 import auth

api_router = APIRouter()
api_router.include_router(auth.router)

__all__ = ["api_router"]
