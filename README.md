# СППР ОРМ — Backend

## Стек

- Python 3.14, менеджер пакетов `uv`
- FastAPI + Pydantic V2
- SQLAlchemy 2.0 (async) + asyncpg + PostgreSQL
- Alembic (async-миграции)
- Redis (сессии, кэш)
- Auth: сессии в Redis + HttpOnly cookie `sid` + CSRF double-submit cookie (без JWT)
- Пароли: Argon2id (pwdlib) для новых хэшей; bcrypt — legacy-схема верификации старых хэшей

## Зависимости (PostgreSQL, Redis)

Перед запуском поднимите зависимости в Docker. Порты и учётные данные
совпадают с дефолтами из `.env.example` / `app/core/config.py`.

```bash
# PostgreSQL (user=app, password=app_secret, db=sppr_orm, порт 5432)
docker run -d --name sppr-orm-postgres \
  -e POSTGRES_USER=app \
  -e POSTGRES_PASSWORD=app_secret \
  -e POSTGRES_DB=sppr_orm \
  -p 5432:5432 \
  postgres:16

# Redis (порт 6379)
docker run -d --name sppr-orm-redis \
  -p 6379:6379 \
  redis:7
```

Повторный запуск контейнеров после перезагрузки машины:

```bash
docker start sppr-orm-postgres sppr-orm-redis
```

## Быстрый старт

```bash
# 1. Зависимости
uv sync

# 2. Конфигурация
cp .env.example .env

# 3. Миграции
uv run alembic upgrade head

# 4. Запуск
uv run fastapi dev app/main.py
```

Swagger: <http://127.0.0.1:8000/docs>

## Структура

Домен-ориентированная структура (по образцу Netflix Dispatch / FastAPI Best
Practices): один домен — одна папка со всем необходимым (router, schemas,
models, repository, service, dependencies) внутри.

```text
app/
├── main.py               # app factory, CORS, exception handlers, CSRF middleware
├── core/                 # общее: config, exceptions, security, csrf, pagination,
│                         # messages (i18n), routing (ApiRouter), deps (db/redis),
│                         # envelope-схемы {"data"/"meta"}, {"error"}
├── db/                   # async engine, session, Base — общее
├── auth/                 # домен аутентификации (api.md, раздел 2)
│   ├── router.py         # эндпоинты /auth
│   ├── schemas.py        # Pydantic V2
│   ├── models.py         # SQLAlchemy ORM (User, UserRole)
│   ├── repository.py     # CRUD-запросы к БД
│   ├── service.py        # бизнес-логика (Redis-сессии)
│   └── dependencies.py   # get_current_user, require_roles
├── checks/               # каркас: проверка по 14 критериям (ТЗ 3.1)
├── documents/            # каркас: генератор документов (ТЗ 3.4)
├── knowledge_base/       # каркас: база знаний (ТЗ 3.3)
├── audit/                # каркас: логирование/аудит (ТЗ 3.5)
├── api/
│   └── v1/
│       └── router.py     # агрегатор роутеров доменов
├── workers/              # фоновые задачи (ARQ/Celery) — следующий этап
└── templates/            # Jinja2 (отчёты, письма)
```

## Auth-флоу (frontend)

1. Перед любой формой: `GET /api/v1/auth/csrf-token` → cookie `csrf_token`
   (НЕ HttpOnly) + значение в `data.csrf_token`.
2. Каждый мутирующий запрос (POST/PUT/PATCH/DELETE): заголовок
   `X-CSRF-Token: <значение>` + `credentials: 'include'`.
3. `POST /api/v1/auth/login` ставит HttpOnly `sid` (TTL 30 мин, скользящее
   продление; жёсткий лимит 12 ч) и обновляет `csrf_token`.
4. Проверка сессии: `GET /api/v1/auth/me` (вызывается при старте SPA).

## Форматы ответов

```json
{"data": { ... }, "meta": {"page": 1, "per_page": 20, "total": 134}}
{"error": {"code": "VALIDATION_ERROR", "message": "...", "details": [{"field": "...", "issue": "..."}]}}
```

## Проверка типов

```bash
uv run mypy app
```
