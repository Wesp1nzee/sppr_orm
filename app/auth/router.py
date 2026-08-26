"""Эндпоинты аутентификации (api.md, раздел 2.2)."""

from __future__ import annotations

from fastapi import Request, Response, status

from app.auth.dependencies import CurrentUser, DbSession, RedisClient
from app.auth.schemas import (
    CsrfData,
    LoginData,
    LoginRequest,
    LogoutData,
    RegisterRequest,
    UserOut,
)
from app.auth.service import AuthService
from app.core.config import get_settings
from app.core.csrf import generate_csrf_token
from app.core.routing import ApiRouter
from app.core.schemas import DataResponse

settings = get_settings()

router = ApiRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, sid: str) -> None:
    """sid: HttpOnly; Secure; SameSite=Lax; Max-Age=1800 (api.md, 2.1)."""
    response.set_cookie(
        key=settings.session_cookie_name,
        value=sid,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path=settings.cookie_path,
        domain=settings.cookie_domain,
    )


def _set_csrf_cookie(response: Response, token: str) -> None:
    """csrf_token: НЕ HttpOnly (фронт должен читать), Secure, SameSite=Lax."""
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path=settings.cookie_path,
        domain=settings.cookie_domain,
    )


def _delete_cookie(response: Response, key: str) -> None:
    response.delete_cookie(
        key=key,
        path=settings.cookie_path,
        domain=settings.cookie_domain,
        secure=settings.cookie_secure,
    )


@router.post(
    "/register",
    response_model=DataResponse[UserOut],
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    db: DbSession,
    redis: RedisClient,
) -> DataResponse[UserOut]:
    service = AuthService(db, redis)
    user = await service.register(payload)
    return DataResponse[UserOut](data=UserOut.model_validate(user))


@router.post("/login", response_model=DataResponse[LoginData])
async def login(
    payload: LoginRequest,
    response: Response,
    db: DbSession,
    redis: RedisClient,
) -> DataResponse[LoginData]:
    service = AuthService(db, redis)
    user = await service.authenticate(payload.email, payload.password)
    sid = await service.create_session(user)

    # CSRF-токен привязан к сессии: HMAC(secret_key, sid).
    csrf_token = generate_csrf_token(sid)
    _set_session_cookie(response, sid)
    _set_csrf_cookie(response, csrf_token)

    return DataResponse[LoginData](
        data=LoginData(
            id=user.id,
            email=user.email,
            role=user.role,
            full_name=user.full_name,
            csrf_token=csrf_token,
        )
    )


@router.post("/logout", response_model=DataResponse[LogoutData])
async def logout(
    request: Request,
    response: Response,
    db: DbSession,
    redis: RedisClient,
) -> DataResponse[LogoutData]:
    sid = request.cookies.get(settings.session_cookie_name)
    if sid:
        await AuthService(db, redis).destroy_session(sid)
    _delete_cookie(response, settings.session_cookie_name)
    _delete_cookie(response, settings.csrf_cookie_name)
    return DataResponse[LogoutData](data=LogoutData())


@router.get("/me", response_model=DataResponse[UserOut])
async def me(user: CurrentUser) -> DataResponse[UserOut]:
    return DataResponse[UserOut](data=UserOut.model_validate(user))


@router.get("/csrf-token", response_model=DataResponse[CsrfData])
async def csrf_token(request: Request, response: Response) -> DataResponse[CsrfData]:
    """Выдаёт/обновляет CSRF-токен, привязанный к текущей сессии.

    Если пользователь уже вошёл — токен = HMAC(secret_key, sid); до логина
    sid отсутствует, токен = HMAC(secret_key, b"").
    """
    sid = request.cookies.get(settings.session_cookie_name)
    token = generate_csrf_token(sid)
    _set_csrf_cookie(response, token)
    return DataResponse[CsrfData](data=CsrfData(csrf_token=token))
