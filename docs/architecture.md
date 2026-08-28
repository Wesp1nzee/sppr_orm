# Архитектура

## 1. Принципы

- **Домен-ориентированная структура** — один домен = одна папка (обоснование —
  [ADR 0002](adr/0002-domain-oriented-structure.md)).
- **Слабая связность доменов** — домены-источники публикуют события в `EventBus`
  вместо прямых импортов подписчиков.
- **Единый формат ответов** — envelope `{"data"}` / `{"error"}` через
  `app/core/routing.ApiRouter` и `app/core/schemas`.
- **Конфигурация через env** — `pydantic-settings`, приоритет env > `.env`.

## 2. Структура домена

Каждый домен (`auth`, `checks`, `knowledge_base`, `documents`, `audit`) следует
одинаковому внутреннему шаблону:

| Модуль | Ответственность |
|--------|-----------------|
| `router.py` | HTTP-слой: эндпоинты, валидация входов, status-коды |
| `schemas.py` | Pydantic-схемы запросов/ответов |
| `models.py` | SQLAlchemy-модели |
| `repository.py` | CRUD-запросы к БД |
| `service.py` | бизнес-логика, транзакционные границы |
| `dependencies.py` | FastAPI-зависимости (`get_current_user`, `require_roles`) |
| `constants.py` | доменные константы (опционально) |

## 3. Поток запроса

```
HTTP → CSRFMiddleware → CORS → Router (app/api/v1)
        → ApiRouter (домен) → Dependencies (DbSession, RedisClient, CurrentUser)
        → Service (бизнес-логика) → Repository → SQLAlchemy → PostgreSQL
        → Response (envelope)
```

Ошибки бизнес-логики поднимаются как `AppException(ErrorCode, ...)` и
перехватываются глобальными обработчиками в `app/main.py`, которые резолвят
текст по коду и локали (`app/core/messages.py`) и сериализуют в
`{"error": {...}}`.

## 4. Сквозные механики (`app/core`)

| Модуль | Назначение |
|--------|------------|
| `config.py` | `Settings` (`pydantic-settings`) + кэш-синглтон `get_settings` |
| `exceptions.py` | `ErrorCode`, `AppException`, соответствие кодов HTTP-статусам |
| `messages.py` | локализация сообщений об ошибках (ru/en) |
| `schemas.py` | envelope-схемы `DataResponse`, `ErrorResponse`, `PageMeta` |
| `routing.py` | `ApiRouter` (общие дефолты, `exclude_none`) |
| `pagination.py` | `PageParams`, `get_page_params` |
| `csrf.py` | генерация и проверка CSRF-токена (HMAC) |
| `security.py` | хэширование паролей (Argon2id / bcrypt legacy) |
| `rate_limit.py` | rate limiting на Redis |
| `deps.py` | типизированные зависимости `DbSession`, `RedisClient` |
| `events.py` | `EventBus` — событийная шина доменов |

## 5. Инфраструктурные слои

- **`app/db`** — async engine (`create_async_engine`), `sessionmaker`, `Base`
  (общие колонки: UUID PK, `created_at`, `updated_at`).
- **`app/api/v1`** — агрегатор роутеров доменов; health check в `main.py`.
- **`app/main.py`** — `create_app()` (app factory), lifespan (подключение Redis,
  регистрация audit-подписчиков), middleware (CSRF, CORS), exception handlers.

## 6. Событийная шина и аудит

Домены публикуют доменные события (`UserRegistered`, `UserLoggedIn`,
`UserLoggedOut`, `LoginFailed`, `CheckCreated`, `DocumentCreated`,
`DocumentFinalized`, `DocumentExported`, `DocumentContentUpdated`,
`NormativeDocumentCreated`, `NormativeDocumentVersionCreated`) в `EventBus`.
Домен `audit` регистрирует подписчиков в `lifespan` и сохраняет события в
`audit_log_entries` (append-only, без `updated_at`).

Запись аудита выполняется синхронно внутри обработчика `EventBus` под
собственную `AsyncSession` (`async_session_factory`), а не в HTTP request-scope:
подписчик не находится внутри запроса и не может переиспользовать `DbSession`.
`EventBus.publish` — fire-and-forget (глотает и логирует исключения
обработчиков), поэтому ошибка записи аудита не роняет источник события.
Интерфейс `AuditWriter` (`app/audit/subscribers.py`) оставляет seam для будущей
асинхронной записи через очередь (контракт — [app/workers/README.md](../app/workers/README.md)).

Связь между доменами — только через `EventBus` и типы событий, объявленные в
доменах-источниках. Сводный отчёт по проверке (`app/audit/service.py`)
переиспользует `app/documents/export.py` для рендера DOCX/PDF.

## 7. База данных

- Миграции — Alembic (async), каталог `alembic/versions`.
- `normative_documents` — версионируемые документы БЗ: обновление создаёт новую
  строку (`code` + `version`, уникальность `uq_normdoc_code_version`), а не
  переписывает существующую; `is_current` помечает актуальную версию.
- `generated_documents` — документы хранятся как структурированный JSONB
  (`content`), экспорт в DOCX/PDF выполняется на лету из финализированного
  содержимого (`app/documents/export.py`).
- `audit_log_entries` — журнал аудита (append-only): событие, снимок роли,
  `payload` (JSONB), `ip_address`. `user_id` — `ON DELETE SET NULL` (запись не
  исчезает при удалении пользователя). Ретеншен ≥ 1 года обеспечивается
  скриптом `scripts/purge_audit_log.py` (запуск вручную или по cron/systemd-
  таймеру), см. `README.md`.

## 8. Тестирование

Тесты (`tests/`) строят приложение через `app.main:create_app` и подменяют
реальные БД/Redis через `dependency_overrides` (in-memory SQLite + `fakeredis`).
Это позволяет гонять полный стек HTTP без внешних сервисов.
