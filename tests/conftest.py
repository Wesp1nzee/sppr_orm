"""Общая инфраструктура тестов.

БД: in-memory SQLite (aiosqlite) с единственным общим соединением (StaticPool)
— простейший вариант для async SQLAlchemy без внешних сервисов.
Redis: fakeredis.

Приложение строится через ``app.main:create_app``; реальные зависимости
БД/Redis подменяются через ``app.dependency_overrides`` (без monkeypatch
``app.state.redis`` — работает только override).
"""

from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.auth.models import User, UserRole
from app.auth.repository import UserRepository
from app.core.deps import get_redis
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app

UserFactory = Callable[..., Awaitable[User]]


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """In-memory SQLite: одно общее соединение на весь тест (StaticPool)."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(
    db_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[FakeAsyncRedis]:
    redis = FakeAsyncRedis(decode_responses=True)
    yield redis
    await redis.aclose()


@pytest_asyncio.fixture
async def app(
    session_factory: async_sessionmaker[AsyncSession],
    fake_redis: FakeAsyncRedis,
) -> FastAPI:
    application = create_app()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            else:
                await session.commit()

    def override_get_redis() -> FakeAsyncRedis:
        return fake_redis

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_redis] = override_get_redis
    return application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def csrf_headers(client: httpx.AsyncClient) -> dict[str, str]:
    """Получает CSRF-cookie и токен, возвращает заголовок для мутирующих запросов."""
    response = await client.get("/api/v1/auth/csrf-token")
    assert response.status_code == 200
    token = response.json()["data"]["csrf_token"]
    return {"X-CSRF-Token": token}


@pytest.fixture
def user_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> UserFactory:
    """Фабрика пользователей напрямую в БД (минуя API-регистрацию)."""

    async def _make(
        email: str,
        password: str,
        role: UserRole,
        *,
        is_active: bool = True,
    ) -> User:
        async with session_factory() as session:
            user = await UserRepository(session).create(
                email=email,
                hashed_password=hash_password(password),
                full_name="Тест Тестов",
                role=role,
            )
            user.is_active = is_active
            await session.commit()
        return user

    return _make
