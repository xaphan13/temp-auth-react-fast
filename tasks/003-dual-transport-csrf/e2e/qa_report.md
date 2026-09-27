# Финальный QA-прогон

Дата: 2026-09-27. Сервер запускался из `fastapi-application/` на `127.0.0.1:8017`; после прогона остановлен, `pgrep -x uvicorn` пуст.

## Критерии

| # | Результат | Фактическое доказательство |
|---|---|---|
| 1 | PASS | Register 201; cookie login 204; `Set-Cookie: auth=` и `csrf_token=` в `qa_runtime.txt`. |
| 2 | PASS | Bearer login 200, JSON `access_token` и `token_type: bearer`. |
| 3 | PASS | Cookie `/users/me` 200, JSON содержит `id`, `email`. |
| 4 | PASS | Bearer `/users/me` 200, JSON содержит `id`, `email`. |
| 5 | PASS | Cookie PATCH без CSRF: 403, `CSRF validation failed`. |
| 6 | PASS | Cookie PATCH с `invalid`: 403, `CSRF validation failed`. |
| 7 | PASS | Cookie PATCH с валидным токеном: 200. |
| 8 | PASS | Cookie logout 204; `Set-Cookie: csrf_token=""; Max-Age=0`. |
| 9a | PASS | Mixed cookie+Bearer без CSRF: 403. |
| 9b | PASS | Mixed cookie+Bearer с CSRF: 200. |
| 10 | PASS | `/docs` 200; тело содержит `Swagger UI`. |
| 11 | PASS | Anonymous `/users/me`: 401, `Unauthorized`. |
| 12 | FAIL | `/orders/get_all_orders?params=id`: 500 вместо 200. DEF-002. |
| 13 | FAIL | `/api/v1/dep_examples/header_name` с `foobar`: 404 вместо 200. DEF-001. |
| 14 | PASS | `/auth/account`: без CSRF 403; с валидным токеном 200. |
| 15 | PASS | `/orders/add_order`: без CSRF 403; с валидным токеном и валидным телом `{"promocode":"QA"}` 200. Валидационная ошибка/500 с `{}` в первом общем прогоне не использована как CSRF-оценка; targeted-проверка с валидным телом подтверждает middleware. |
| 16 | PASS | Authenticated Bearer logout без cookie и CSRF: 204. Неаутентифицированный вызов отдельно дал ожидаемый 401. |
| 17 | PASS | Register → cookie login → `/users/me` → `/api/v1/auth/protected` → cookie logout: все шаги успешны. |
| 18 | PASS | OpenAPI `paths=25`. |
| 19 | PASS | `APIKeyCookie` и `OAuth2PasswordBearer` присутствуют в `components.securitySchemes`. |
| 20 | PASS | `npm run build`: exit 0; `dist/index.html` создан. |
| 21 | FAIL (baseline) | `ruff check .`: единственный `I001` в `auth_users/user_manager.py`; focused ruff на том же файле воспроизвёл тот же I001. Изменений этого файла нет, дефект не заведен. |

## Артефакты

- `qa_runtime.txt` — сырые curl-запросы и ответы, включая targeted-проверку валидного order body и authenticated Bearer logout.
- `qa_commands.txt` — OpenAPI, frontend build, backend ruff, application log tail и traceback.

## Сознательно не применялось

UI-скриншоты не делались: задание требует API/runtime, `/docs` проверен curl-ответом, а не визуальным изменением Swagger UI. Нагрузочные проверки, path traversal и XSS не применялись как нерелевантные этому auth/CSRF контракту. Граница invalid/empty order payload сознательно не использовалась для оценки CSRF: валидное `{"promocode":"QA"}` проверено отдельно.

## Дефекты

- DEF-001 — OPEN, HIGH: отсутствует требуемый `/api/v1/dep_examples/header_name`.
- DEF-002 — OPEN, HIGH: `GET /orders/get_all_orders?params=id` возвращает 500.
