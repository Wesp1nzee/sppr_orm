"""Общие FastAPI-зависимости: БД-сессия, Redis-клиент."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


RedisClient = Annotated[Redis, Depends(get_redis)]
