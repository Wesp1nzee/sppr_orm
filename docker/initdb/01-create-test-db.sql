-- Создаёт тестовую БД для интеграционных тестов (make test-integration).
-- Выполняется docker-entrypoint-initdb.d только при первом старте (свежий volume).
CREATE DATABASE sppr_orm_test;
