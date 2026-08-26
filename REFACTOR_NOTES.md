# Заметки о рефакторинге backend СППР ОРМ (2026-08-26)

Ревью-фиксы выполнены пошагово, каждый — отдельным коммитом
(`git log --oneline` в репозитории):

1. `test` — тестовая инфраструктура + dev-зависимости + fix Makefile.
2. `refactor(security)` — passlib → pwdlib.
3. `security(csrf)` — подписанный double-submit CSRF.
4. `refactor(auth)` — DRY для логики Redis-сессий.
5. `feat(i18n)` — локализация сообщений об ошибках.
6. `refactor` — переход на domain-based структуру.

## Что сделано

- **Тесты и инструменты**: в `[dependency-groups].dev` добавлены
  `pytest`, `pytest-asyncio`, `httpx`, `ruff` (+ `aiosqlite`, `fakeredis`
  для фикстур); `uv sync` на чистой машине ставит всё для
  `make lint`/`make test`. `Makefile run` исправлен: `src.main:app` →
  `app.main:app`.
- **Хэширование**: `pwdlib[argon2,bcrypt]` вместо `passlib`; Argon2id для
  новых хэшей, bcrypt — legacy-верификация старых. Сигнатуры
  `hash_password`/`verify_password` сохранены.
- **CSRF**: наивный double-submit заменён на подписанный
  (OWASP): `csrf_token = HMAC-SHA256(secret_key, sid)`, сравнения только
  через `secrets.compare_digest`; `secret_key` из Settings теперь
  используется. До логина (`sid` отсутствует) токен = `HMAC(secret_key, b"")`.
- **DRY сессий**: парсинг Redis-сессии + проверка `hard_expire_at` живут
  только в `AuthService.get_session_payload` (чистит просроченные/битые
  ключи); `get_current_user` и `logout` работают через сервис.
- **Локализация**: `app/core/messages.py` — `{ErrorCode: {"ru": "...",
  "en": "..."}}` + `get_message`/`resolve_locale` (заголовок
  `Accept-Language`, fallback «ru»). `AppException` принимает `ErrorCode`
  и `**format_kwargs`; текст резолвится в handler'ах `app/main.py`.
  Специфичные сообщения получили отдельные коды
  (`EMAIL_ALREADY_REGISTERED`, `INVALID_CREDENTIALS`, `SESSION_NOT_FOUND`
  и др.).
- **Структура**: переход на domain-based (Netflix Dispatch / FastAPI
  Best Practices):

  ```text
  app/
  ├── main.py               # app factory, CORS, CSRF, exception handlers
  ├── core/                 # config, exceptions, security, csrf, pagination,
  │                         # messages (i18n), routing (ApiRouter),
  │                         # deps (DbSession/RedisClient), schemas (envelope)
  ├── db/                   # engine, session, Base
  ├── auth/                 # router, schemas, models, repository, service,
  │                         # dependencies (get_current_user, require_roles)
  ├── checks/               # каркас (ТЗ 3.1)
  ├── documents/            # каркас (ТЗ 3.4)
  ├── knowledge_base/       # каркас (ТЗ 3.3)
  ├── audit/                # каркас (ТЗ 3.5)
  └── api/v1/router.py      # агрегатор роутеров
  ```

  `alembic/env.py` регистрирует модели явным импортом
  (`from app.auth.models import User`); `autogenerate` проверен: пустой
  diff против накатанной БД.

## Тесты (36 шт., `make test`)

- `tests/test_auth.py` — интеграция: register (дубль email, запрет
  admin-регистрации), login (неверный пароль, неактивный), сессии (TTL
  выдачи и скользящее продление, `hard_expire_at` → 401 + удаление ключа,
  битая сессия), logout, локализация по `Accept-Language`.
- `tests/test_auth_service.py` — unit: правила register/authenticate,
  payload сессии, hard-expire, битый payload.
- `tests/test_csrf.py` — привязка токена к `sid`, отклонение подменённой
  пары cookie+header (403 `CSRF_TOKEN_INVALID`), отсутствие заголовка.
- `tests/test_rbac.py` — `require_roles` (lawyer → 403, admin → 200).
- `tests/test_security.py` — Argon2id + верификация legacy-bcrypt.
- `tests/test_messages.py` — словарь сообщений, fallback локали.
- Инфраструктура: `tests/conftest.py` — sqlite in-memory (StaticPool) +
  fakeredis + httpx `AsyncClient` через `app.dependency_overrides`.

## TODO / каркасы без логики

- `app/checks/` — модуль «Проверка по 14 критериям» (ТЗ 3.1): пустой
  `ApiRouter` + заглушки schemas/service; подключение закомментировано
  в `app/api/v1/router.py`.
- `app/documents/` (ТЗ 3.4), `app/knowledge_base/` (ТЗ 3.3),
  `app/audit/` (ТЗ 3.5) — только `__init__.py`.
- `app/workers/`, `app/templates/` — по-прежнему следующий этап.

## Ограничения локальной проверки

- В окружении нет PostgreSQL/Redis/Docker: интеграционные тесты и
  smoke-проверка миграций (`alembic upgrade head`, `autogenerate`)
  выполнены на sqlite+aiosqlite. Диалект-специфика Postgres
  (native enum `user_role`) локально не проверялась — миграция
  `dc9c85a65f26` не менялась.
- `make lint`/`typecheck`/`test` — зелёные на Python 3.14.2.
