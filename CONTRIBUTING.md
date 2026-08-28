# Contributing

## Подготовка окружения

```bash
# 1. Зависимости
uv sync

# 2. Конфигурация
cp .env.example .env

# 3. Инфраструктура (PostgreSQL + Redis)
docker compose up -d
```

Перед первым коммитом установите pre-commit-хуки:

```bash
pre-commit install
```

## Workflow разработки

```bash
# Форматирование + линт + типы
make all

# Тесты (с coverage, порог 85%)
make test
```

Полный список команд — `make help` или `Makefile`. Кратко:

| Команда | Действие |
|---------|----------|
| `make run` | запуск uvicorn с `--reload` |
| `make format` | `ruff format` |
| `make lint` | `ruff check` |
| `make typecheck` | `mypy` |
| `make all` | format + lint + typecheck |
| `make test` | pytest + coverage |
| `make mm m="..."` | автогенерация миграции Alembic |

## Стиль коммитов

Используется [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <описание>

type: feat | fix | refactor | docs | test | chore | security | data | ci
scope: auth | checks | documents | knowledge_base | core | db | ...
```

Примеры из истории проекта:

- `feat(documents): generate procedural documents from ORM checks`
- `security: rate limiting on auth, CORS narrowing, secrets placeholder`
- `refactor(checks): resolve legal_references from knowledge base`

## Правила

- **Типы обязательны**: проект использует `mypy --strict`, все функции
  типизированы.
- **Тесты обязательны** для новой логики; coverage не должен падать ниже 85%.
- **Бизнес-ошибки** поднимайте как `AppException(ErrorCode, ...)` — тексты
  локализуются через `app/core/messages.py`, а не зашиваются в код.
- **Новые домены** создавайте по единому шаблону (`router`, `schemas`,
  `models`, `repository`, `service`, `dependencies`) — см.
  [docs/architecture.md](docs/architecture.md).
- **Архитектурные решения** фиксируйте ADR в `docs/adr/`.
- **Секреты** в код не коммитим — только плейсхолдеры в `.env.example`.
