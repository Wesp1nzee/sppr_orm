.PHONY: lint format typecheck all run sync mm migrate rollback history current test createadmin

# Запуск линтера
lint:
	uv run ruff check . --fix

# Форматирование кода
format:
	uv run ruff format .

# Проверка типов
typecheck:
	uv run mypy .

# Запуск всего сразу
all: format lint typecheck

# Запуск FastAPI в режиме разработки
run:
	uv run uvicorn app.main:app --reload

# Запуск тестов
test:
	uv run pytest tests/ -v

# Синхронизация зависимостей
sync:
	uv sync

# Создать новую миграцию
# Использование: make mm m="описание миграции"
mm:
	uv run alembic revision --autogenerate -m "$(m)"

# Применить все миграции
migrate:
	uv run alembic upgrade head

# Откатить последнюю миграцию на 1 шаг назад
rollback:
	uv run alembic downgrade -1

# Посмотреть историю миграций
history:
	uv run alembic history --verbose

# Посмотреть текущий статус
current:
	uv run alembic current

# Создать пустую миграцию
revision:
	uv run alembic revision -m "$(m)"

# Создать администратора
# Использование: make createadmin EMAIL=admin@example.com PASSWORD=secret
createadmin:
	uv run python -m scripts.create_admin --email "$(EMAIL)" --password "$(PASSWORD)"
