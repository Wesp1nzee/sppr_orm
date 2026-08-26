# СППР ОРМ — Backend

## Стек

- Python 3.14, менеджер пакетов `uv`
- FastAPI + Pydantic V2
- SQLAlchemy 2.0 (async) + asyncpg + PostgreSQL
- Alembic (async-миграции)
- Redis (сессии, кэш)
- Auth: сессии в Redis + HttpOnly cookie `sid` + CSRF double-submit cookie (без JWT)

## Быстрый старт

```bash
# 1. Зависимости
uv sync

# 2. Конфигурация
cp .env.example .env      # поправить при необходимости

# 4. Миграции
uv run alembic upgrade head

# 5. Запуск
uv run fastapi dev app/main.py      # dev-режим с auto-reload
# или
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Swagger: <http://127.0.0.1:8000/docs>

## Структура

```text
app/
├── main.py              # app factory, CORS, exception handlers, CSRF middleware
├── core/                # config (.env), exceptions, security, CSRF, pagination
├── db/                  # async engine, session, Base
├── models/              # SQLAlchemy ORM (User, UserRole)
├── schemas/             # Pydantic V2: envelope {"data"/"meta"}, {"error"}
├── repositories/        # CRUD-запросы к БД
├── services/            # бизнес-логика (auth, Redis-сессии)
├── api/
│   ├── deps.py          # get_db, get_redis, get_current_user, require_roles
│   └── v1/              # роутеры по доменам
├── workers/             # фоновые задачи (ARQ/Celery) — следующий этап
└── templates/           # Jinja2 (отчёты, письма)
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
