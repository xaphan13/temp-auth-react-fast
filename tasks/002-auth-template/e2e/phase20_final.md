# Фаза 20 — повторный финальный QA после миграции

Дата прогона: 2026-09-14. Product code не изменялся; QA-артефакты записаны в `tasks/current/e2e/`. Выполнен один финальный раннер `tasks/current/e2e/phase20_run.py`; скрипт запускал команды из `fastapi-application/`, выбирал отдельную SQLite через `APP__DB__URL=sqlite+aiosqlite:////tmp/.../one_simple.db`, поднимал один `uvicorn`, ждал `openapi` и очищал свои временные файлы/сервер/dist после прогона.

## Итог

**PASS по runtime-критериям и миграционному blocker.** На чистой временной SQLite `alembic upgrade heads` создал ровно `alembic_version`, `user`, `orders`, `products`, `order_product_association`. OpenAPI/auth/account/logout/order/demo/SPA проверки прошли с ожидаемыми статусами и JSON/HTML-телами. DEF-001 и DEF-002 успешно перетестированы и закрыты в `../DEFECTS.md`.

Полный сырой вывод, включая команды, тела ответов, статусы, SQL-инспекцию, build и лог ruff: [phase20_raw.txt](phase20_raw.txt).

## Результаты

| Область | Результат | Доказательство |
|---|---|---|
| Чистая миграция SQLite | PASS | `alembic upgrade heads` exit 0; таблицы ровно `['alembic_version', 'order_product_association', 'orders', 'products', 'user']`; `sqlite_schema_check=PASS` |
| OpenAPI 23 и границы маршрутов | PASS | `openapi_path_count=23`, protected присутствует, blog отсутствует, `/users/{id}` отсутствует |
| Docs | PASS | `/docs` HTTP 200 |
| Anonymous me/protected | PASS | оба HTTP 401, `application/json`, JSON body |
| Registration | PASS | HTTP 201, JSON UserRead с email, без password |
| Login | PASS | HTTP 204, cookie jar непустой |
| Authorized me/protected | PASS | оба HTTP 200; protected содержит `authenticated: true` и user без password |
| Account | PASS | multipart username/email без picture HTTP 200; `{message, category, user}`, обновлённые email/username подтверждены через `/users/me` |
| Logout | PASS | HTTP 204; после очистки cookie protected HTTP 401 JSON |
| Retained demo/order | PASS | demo с обязательным `foobar` HTTP 200; `/orders/get_all_orders?params=id` HTTP 200 и JSON `[]` |
| Blog/API fallback | PASS | `/api/blog/articles` HTTP 404 JSON; `/api/nope` HTTP 404 JSON |
| SPA fallback | PASS | `/protected` HTTP 200 `text/html`, содержит `<div id="root">` |
| Удаление backend blog/UserPost | PASS | `md_articles`, `content_art`, `ex_user_post`, `docs/06_blog.md` отсутствуют; runtime reference hits отсутствуют в code tokens |
| Frontend build/source/bundle | PASS | `npm run build` exit 0; `frontend_code_marker_hits=[]`, `frontend_bundle_marker_hits=[]`; локальный dist удалён cleanup-ом |
| Application logs | PASS | прочитаны `fastapi-application/log/` и uvicorn log; в успешном runtime-прогоне ошибок/traceback нет |
| Runtime DB guard | PASS | SHA-256 до и после: `ddacef2b5b715b7578d9a076a5d80dc40a18ff6cf3aecb147cb2edaf5b83ec10`; сервер остановлен, порт 8000 свободен |

## Нерелевантные/ограниченные проверки

- Adversarial-прогон не выполнялся: он прямо исключён текущей спецификацией.
- Фото не загружалось: сценарий критерия требует multipart без picture; сохранность avatar/static подтверждена контрактом и раздачей SPA, отдельный upload не был необходим для закрытия обнаруженных blocker-дефектов.
- Полный `ruff check .` не выполнялся; требовался narrow ruff для migration/backend. Он был запущен, но завершился с pre-existing/style findings в `auth_users` (`B008`, `SIM102`, `BLE001`), поэтому это честно отмечено как **FAIL/ограничение** в сыром выводе. Product code QA не менял.

## Дефекты

DEF-001 и DEF-002: **CLOSED** после успешного ретеста; записи и History находятся в [../DEFECTS.md](../DEFECTS.md).
