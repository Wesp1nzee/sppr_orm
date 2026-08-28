# СППР ОРМ — Backend

[![CI](https://github.com/Wesp1nzee/sppr_orm/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/Wesp1nzee/sppr_orm/actions)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/)
[![Coverage](https://img.shields.io/badge/coverage-85%25-green.svg)](#тестирование)
[![License](https://img.shields.io/badge/license-proprietary-red.svg)](#лицензия)

REST API системы поддержки принятия решений при проведении оперативно-розыскных
мероприятий (ОРМ): автоматизирует оценку законности ОРМ по 14 критериям и
генерацию процессуальных документов на основе результатов проверки.

## Содержание

- [Возможности](#возможности)
- [Стек](#стек)
- [Архитектура](#архитектура)
- [Быстрый старт](#быстрый-старт)
- [Запуск в Docker](#запуск-в-docker)
- [Конфигурация](#конфигурация)
- [Аутентификация и роли](#аутентификация-и-роли)
- [Формат ответов и ошибки](#формат-ответов-и-ошибки)
- [Структура проекта](#структура-проекта)
- [Разработка](#разработка)
- [Тестирование](#тестирование)
- [Документация](#документация)
- [Дорожная карта](#дорожная-карта)
- [Лицензия](#лицензия)

## Возможности

- **Проверка законности ОРМ** — движок правил по 14 критериям с ролевыми
  приоритетами и ссылками на нормы из базы знаний.
- **Генерация документов** — процессуальные документы (ходатайства, жалобы,
  чек-листы, план легализации) в DOCX и PDF из результатов проверки.
- **База знаний** — нормативные материалы (ФЗ «Об ОРД», статьи УПК РФ,
  определения КС РФ, постановления Пленума ВС РФ) с версионированием.
- **Роли и RBAC** — четыре роли (`lawyer`, `investigator`, `officer`, `admin`)
  с разграничением доступа и приоритизацией критериев.
- **Безопасная аутентификация** — серверные сессии в Redis + подписанный
  double-submit CSRF (без JWT), Argon2id для паролей, rate limiting на вход.
- **Единый формат ответов** — envelope `{"data"}` / `{"error"}` + локализация
  сообщений (`ru`/`en`).
- **Событийная шина** — домены общаются через `EventBus` (слабая связность).
- **Аудит** — журнал событий (`/api/v1/audit/*`): запись событий `EventBus` в БД,
  admin-просмотр журнала с фильтрами, сводный отчёт по проверке с экспортом в
  DOCX/PDF и ретеншен журнала ≥ 1 года.

## Стек

| Компонент | Технология |
|-----------|------------|
| Язык | Python 3.14 |
| Пакетный менеджер | [uv](https://docs.astral.sh/uv/) |
| Web-фреймворк | FastAPI + Pydantic V2 |
| ORM | SQLAlchemy 2.0 (async) + asyncpg |
| База данных | PostgreSQL 16 |
| Миграции | Alembic (async) |
| Кэш / сессии | Redis 7 |
| Аутентификация | Redis-сессии + HttpOnly cookie `sid` + CSRF double-submit |
| Хэширование паролей | Argon2id (`pwdlib`), bcrypt — legacy-верификация |
| Генерация документов | Jinja2 + python-docx + ReportLab |

## Архитектура

Домен-ориентированная структура (по образцу Netflix Dispatch / FastAPI Best
Practices): один домен — одна папка со всем необходимым (`router`, `schemas`,
`models`, `repository`, `service`, `dependencies`). Общее поведение вынесено в
`app/core`, `app/db`, `app/api`.

Подробнее — [docs/architecture.md](docs/architecture.md) и
[ADR](docs/adr/README.md).

## Быстрый старт

Требования: Python 3.14, `uv`, Docker (для PostgreSQL и Redis).

```bash
# 1. Зависимости
uv sync

# 2. Конфигурация
cp .env.example .env

# 3. Инфраструктура (PostgreSQL + Redis)
docker compose up -d

# 4. Миграции
uv run alembic upgrade head

# 5. Создание администратора (опционально)
make createadmin EMAIL=admin@example.com PASSWORD=secret

# 6. Запуск
uv run fastapi dev app/main.py
```

Swagger: <http://127.0.0.1:8000/docs>

> Альтернатива `docker compose` — отдельные контейнеры PostgreSQL и Redis,
> см. `docker-compose.yml` для учётных данных (совпадают с дефолтами из
> `.env.example`).

## Запуск в Docker

Production-образ собирается в два этапа (`Dockerfile`): зависимости ставятся в
билдере на базе `uv`, в рантайм попадает только `python:3.14-slim` без dev-пакетов.

```bash
docker build -t sppr-orm .
docker run --rm -p 8000:8000 sppr-orm
```

Секреты (`SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`) в проде передаются через
переменные окружения процесса, а не через `.env` внутри контейнера — см.
[Секреты в production](#секреты-в-production).

## Конфигурация

Настройки читаются из переменных окружения и `.env` (приоритет: env > `.env`).
Полный список с дефолтами — в `.env.example` и `app/core/config.py`.

| Переменная | Назначение | Дефолт |
|-----------|-----------|--------|
| `APP_NAME` | Название сервиса | `СППР ОРМ` |
| `APP_ENV` | Окружение (`development` / `testing` / `production`) | `development` |
| `DEBUG` | Режим отладки FastAPI | `false` |
| `SECRET_KEY` | Ключ для HMAC CSRF и подписи | `insecure-dev-key-change-me` |
| `CORS_ORIGINS` | Разрешённые origins (JSON-массив) | `localhost:3000/5173` |
| `DATABASE_URL` | DSN PostgreSQL (async) | `postgresql+asyncpg://app:app_secret@localhost:5432/sppr_orm` |
| `DB_ECHO` | Логирование SQL | `false` |
| `REDIS_URL` | DSN Redis | `redis://localhost:6379/0` |
| `SESSION_TTL_SECONDS` | Скользящий TTL сессии | `1800` (30 мин) |
| `SESSION_HARD_EXPIRE_SECONDS` | Жёсткий лимит сессии | `43200` (12 ч) |
| `COOKIE_SECURE` | Флаг `Secure` для cookie | `false` |
| `COOKIE_SAMESITE` | SameSite-политика | `lax` |

### Секреты в production

В проде `SECRET_KEY`, `DATABASE_URL` и `REDIS_URL` **не читаются из `.env`-файла
внутри контейнера**. Они подставляются через секрет-менеджер окружения (Vault,
AWS Secrets Manager, Kubernetes Secret и т.п.) как переменные окружения
процесса. `pydantic-settings` уже поддерживает чтение из env без `.env` — менять
код не нужно.

Генерация `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Аутентификация и роли

Аутентификация — серверные сессии в Redis: клиент получает HttpOnly-cookie `sid`,
состояние сессии хранится в Redis под ключом `session:{sid}`.

Auth-флоу для frontend:

1. Перед любой формой: `GET /api/v1/auth/csrf-token` → cookie `csrf_token`
   (НЕ HttpOnly) + значение в `data.csrf_token`.
2. Каждый мутирующий запрос (POST/PUT/PATCH/DELETE): заголовок
   `X-CSRF-Token: <значение>` + `credentials: 'include'`.
3. `POST /api/v1/auth/login` ставит HttpOnly `sid` (TTL 30 мин, скользящее
   продление; жёсткий лимит 12 ч) и обновляет `csrf_token`.
4. Проверка сессии: `GET /api/v1/auth/me` (вызывается при старте SPA).

### Роли

| Роль | Кто | Доступ |
|------|-----|--------|
| `lawyer` | адвокат | ходатайства, жалоба; свои проверки и документы |
| `investigator` | следователь | служебные документы; свои проверки и документы |
| `officer` | оперативный сотрудник | чек-лист, план легализации; свои проверки |
| `admin` | администратор | все проверки/документы, управление базой знаний |

Роли определяют приоритетные критерии проверки и допустимые типы документов —
подробнее в [docs/api.md](docs/api.md#роли-и-права).

## Формат ответов и ошибки

```json
{"data": { ... }, "meta": {"page": 1, "per_page": 20, "total": 134}}
{"error": {"code": "VALIDATION_ERROR", "message": "...", "details": [{"field": "...", "issue": "..."}]}}
```

`meta` присутствует только в пагинированных ответах. Полный каталог кодов
ошибок (27 кодов с HTTP-статусами) — в [docs/api.md](docs/api.md#каталог-кодов-ошибок).

## Структура проекта

```text
app/
├── main.py               # app factory, CORS, exception handlers, CSRF middleware
├── core/                 # общее: config, exceptions, security, csrf, pagination,
│                         # messages (i18n), routing (ApiRouter), deps (db/redis),
│                         # events (EventBus), rate_limit, envelope-схемы
├── db/                   # async engine, session, Base (UUID PK + timestamps)
├── auth/                 # домен аутентификации
│   ├── router.py         # эндпоинты /auth
│   ├── schemas.py        # Pydantic V2
│   ├── models.py         # SQLAlchemy ORM (User, UserRole)
│   ├── repository.py     # CRUD-запросы к БД
│   ├── service.py        # бизнес-логика (Redis-сессии)
│   └── dependencies.py   # get_current_user, require_roles
├── checks/               # проверка по 14 критериям + движок правил (rules/)
├── documents/            # генерация документов (Jinja2-шаблоны, export DOCX/PDF)
├── knowledge_base/       # база знаний (версионируемые нормативные документы)
├── audit/                # журнал аудита: подписчики EventBus, API журнала/отчёта
├── api/
│   └── v1/
│       └── router.py     # агрегатор роутеров доменов
├── workers/              # каркас: контракт фоновой очереди (ARQ/Redis)
└── templates/            # (зарезервировано)
```

## Разработка

Команды через `Makefile` (`make <target>`):

| Команда | Действие |
|---------|----------|
| `make sync` | `uv sync` |
| `make run` | запуск uvicorn с `--reload` |
| `make format` | `ruff format` |
| `make lint` | `ruff check` |
| `make typecheck` | `mypy` |
| `make all` | format + lint + typecheck |
| `make test` | pytest + coverage |
| `make mm m="..."` | автогенерация миграции |
| `make migrate` / `make rollback` | применить / откатить миграцию |
| `make createadmin` | создать администратора |

Перед коммитом отрабатывает pre-commit (ruff format/check + mypy). Инструкции
по внесению изменений и стиль коммитов — [CONTRIBUTING.md](CONTRIBUTING.md).

## Тестирование

Тесты используют in-memory SQLite (`aiosqlite`) с включённой проверкой внешних
ключей и `fakeredis`, без внешних сервисов. Порог покрытия — 85%
(`.coverage` / `pyproject.toml`).

```bash
make test
```

Интеграционные тесты на реальном PostgreSQL 18 (весь набор + миграции Alembic,
включая регрессию FK для `UserRegistered`):

```bash
# создать тестовую БД
docker exec sppr-orm-postgres psql -U app -d postgres -c "CREATE DATABASE sppr_orm_test"
make test-integration
```

## Ретеншен журнала аудита

ТЗ (раздел 4) требует хранить журнал действий пользователей не менее 1 года.
Устаревшие записи удаляются вручную или по cron/systemd-таймеру снаружи
приложения (бэкенд сам не планирует задачи):

```bash
# удалить записи старше 365 дней (дефолт)
uv run python -m scripts.purge_audit_log

# другой срок хранения
uv run python -m scripts.purge_audit_log --retention-days 730
```

## Документация

- [docs/api.md](docs/api.md) — конвенции API, каталог ошибок, auth-флоу, пагинация.
- [docs/architecture.md](docs/architecture.md) — архитектура и поток запроса.
- [docs/adr/README.md](docs/adr/README.md) — записи об архитектурных решениях.
- [app/workers/README.md](app/workers/README.md) — контракт фоновой очереди.

Интерактивная схема API — Swagger UI (`/docs`) и ReDoc (`/redoc`).

## Дорожная карта

- [x] Аутентификация (Redis-сессии, CSRF, RBAC, rate limiting)
- [x] Проверка по 14 критериям
- [x] База знаний (CRUD + версионирование)
- [x] Генерация документов (DOCX/PDF)
- [x] Аудит — запись событий `EventBus` в БД, журнал и сводный отчёт
- [ ] Фоновые задачи — реализация очереди ARQ (зафиксирован контракт)

## Лицензия

Проприетарное ПО. Все права защищены.
