# ADR 0002: Подписанный double-submit cookie для CSRF

- Статус: принято
- Дата: 2026-08-26

## Контекст

SPA использует cookie-аутентификацию, поэтому мутирующие запросы
(POST/PUT/PATCH/DELETE) уязвимы к CSRF. Рассматривались: `SameSite=Strict`
без отдельного токена и подписанный double-submit cookie.

## Решение

Использовать **подписанный double-submit cookie** (OWASP, вариант «Signed
Double-Submit Cookie»): cookie `csrf_token` хранит `HMAC-SHA256(secret_key,
sid)`, фронт дублирует его в заголовок `X-CSRF-Token`, middleware проверяет
`cookie == header` и `cookie == HMAC(secret_key, sid)`
(`app/core/csrf.py`).

## Обоснование

- **`SameSite=Strict` недостаточно**: он не защищает от cookie-injection через
  поддомен/MITM, при котором атакующий подсовывает свою пару cookie+header.
  Привязка токена к `sid` через HMAC закрывает эту атаку — `secret_key`
  атакующему неизвестен.
- **SPA-совместимость**: `SameSite=Lax` не ломает кросс-сайтовую навигацию, а
  CSRF-токен читается фронтом (cookie не HttpOnly) и шлётся в заголовке.
- Все сравнения токенов — через `secrets.compare_digest` (константное время).

## Последствия

- Фронт обязан получать CSRF-токен (`GET /auth/csrf-token`) и слать заголовок
  `X-CSRF-Token` на каждый мутирующий запрос (`README.md`, раздел «Auth-флоу»).
- Валидация CSRF требует `secret_key` (тот же, что и для сессий).
