## DEF-001: Регистрация возвращает 500 из-за отсутствующей таблицы user

- Status: CLOSED
- Severity: HIGH
- Found by: qa
- Task: FastAPI-шаблон для изучения авторизации без блогового слоя

Steps to reproduce:
1. Перейти в каталог приложения: `cd fastapi-application`.
2. Запустить приложение: `../.venv/bin/uvicorn main:main_app --host 127.0.0.1 --port 8000`.
3. Дождаться ответа `200` от `GET http://127.0.0.1:8000/openapi.json`.
4. Отправить `POST http://127.0.0.1:8000/auth/register` с `Content-Type: application/json` и уникальным телом `{"email":"qa.phase18.<unique>@example.com","password":"Phase18-password-Valid"}`.

Expected: HTTP `201`, JSON `UserRead` с полями пользователя (email/password в запросе; пароль не возвращается).
Actual: Исправлено: на чистой временной SQLite после `alembic upgrade heads` регистрация вернула HTTP `201` и JSON с email без password; полный auth-flow, account и retained endpoint прогнаны регрессионно.
Screenshot: не применимо.

History:
- qa: opened; воспроизведено в финальном прогоне фазы 18, raw evidence: `tasks/current/e2e/phase18_raw.txt`
- qa: CLOSED после ретеста фазы 20 на чистой временной SQLite и регрессии auth-flow/order/demo/SPA; raw evidence: `tasks/current/e2e/phase20_raw.txt`

## DEF-002: Retained order endpoint возвращает 500 из-за отсутствующей таблицы orders

- Status: CLOSED
- Severity: HIGH
- Found by: qa
- Task: FastAPI-шаблон для изучения авторизации без блогового слоя

Steps to reproduce:
1. Перейти в каталог приложения: `cd fastapi-application`.
2. Запустить приложение: `../.venv/bin/uvicorn main:main_app --host 127.0.0.1 --port 8000`.
3. Дождаться ответа `200` от `GET http://127.0.0.1:8000/openapi.json`.
4. Отправить `GET http://127.0.0.1:8000/orders/get_all_orders?params=id`.

Expected: Зарегистрированный retained order endpoint отвечает штатным успешным ответом приложения (для пустого списка — JSON-массивом), а не `500`.
Actual: Исправлено: на чистой временной SQLite после `alembic upgrade heads` endpoint вернул HTTP `200` и JSON `[]`.
Screenshot: не применимо.

History:
- qa: opened; воспроизведено в финальном прогоне фазы 18, raw evidence: `tasks/current/e2e/phase18_raw.txt`
- qa: CLOSED после ретеста фазы 20 на чистой временной SQLite; raw evidence: `tasks/current/e2e/phase20_raw.txt`
