# Фаза 18 — финальный QA

Дата прогона: 2026-09-14. Product code не изменялся. Полный сырой вывод curl, import, build, ruff, файловых проверок и логов: [phase18_raw.txt](phase18_raw.txt).

## Итог

**FAIL**: интеграционный auth-flow не проходит: уникальная регистрация возвращает `500 Internal Server Error` (`sqlite3.OperationalError: no such table: user`), поэтому login/account/authorized protected/logout-flow не может быть завершён. Retained order endpoint также возвращает `500` (`no such table: orders`). При этом import/OpenAPI, anonymous boundaries, demo endpoint, удалённый blog API, SPA fallback и frontend build проверены.

Дополнительная проверка окружения показала: после запуска документированной команды Alembic в `fastapi-application/` SQLite содержит только `alembic_version`; `alembic/versions/` пуст. Это не меняет наблюдаемый результат контракта: на чистом штатном запуске требуемый auth-flow и order endpoint недоступны.

## Критерии успеха

| # | Критерий | Результат | Доказательство |
|---|---|---|---|
| 1 | Backend импортируется без blog package: OpenAPI paths = 23, protected есть, blog и `/users/{id}` отсутствуют | **PASS** | `phase18_raw.txt`: `path_count 23`, `protected_present True`, `blog_present False`, `users_id_present False`, import exit 0 |
| 2 | Blog routes удалены, auth routes сохранены | **PASS** | `phase18_raw.txt`: `/auth/register` validation `422` JSON; `/api/blog/articles` `404` JSON; OpenAPI содержит auth paths |
| 3 | Anonymous `/users/me` и `/api/v1/auth/protected` возвращают JSON 401 | **PASS** | `phase18_raw.txt`: оба `HTTP/1.1 401 Unauthorized`, `content-type: application/json`, `{"detail":"Unauthorized"}` |
| 4 | Registration/login/logout flow | **FAIL** | `phase18_raw.txt`: register `500`, login `500`, cookie jar пуст; причина в приложении — `sqlite3.OperationalError: no such table: user`; authorized me/protected не достигнуты |
| 5 | Account multipart и avatar contract | **FAIL** | `phase18_raw.txt`: account получает `401`, так как регистрация/login не выдали cookie; avatar feasibility check получает `404` для отсутствующего файла. Положительный authorized account-flow не может быть доказан |
| 6 | `/docs`, demo API и order domain | **FAIL** | `/docs` `200` и demo `200` PASS; `/orders/get_all_orders?params=id` `500` с `no such table: orders`, поэтому критерий целиком FAIL |
| 7 | Blog/UserPost code/data удалены и runtime references отсутствуют | **PASS** | `phase18_raw.txt`: `md_articles`, `content_art`, `ex_user_post` absent; `no_runtime_refs`; dependency markers сохранены/удалены согласно manifest |
| 8 | Frontend собирается без blog code | **PASS** | `phase18_raw.txt`: `npm run build`, `✓ built`, `frontend_build_exit=0`; forbidden frontend marker search без совпадений |
| 9 | Frontend routes/auth guard и SPA fallback | **PASS** | `phase18_raw.txt`: `/`, `/login`, `/register`, `/account`, `/protected` возвращают `200` HTML index; `/api/nope` возвращает JSON `404`; build зелёный |
| 10 | Единый avatar URL source of truth | **PASS (ограниченно)** | `phase18_raw.txt`: OpenAPI multipart содержит field `picture`, UserRead содержит `image_file`; static mount отсутствующего avatar отвечает JSON `404`, не blog HTML. Положительный upload не доказан из-за FAIL критерия 4 |

## Дополнительные проверки

- `GET /auth/register` с невалидным email: `422` JSON.
- `/orders/get_all_orders` без `params`: `422` JSON, что подтверждает наличие маршрута и validation boundary.
- Application uvicorn log сохранён в raw evidence: регистрация и order endpoint logged as `500`, tracebacks содержат точные `no such table` причины.
- Узкий backend ruff для изменённых backend-файлов: **PASS**, `All checks passed!`.
- Полный `uv run ruff check .`: **FAIL**, существующие unrelated findings (включая `api/dependencies/*` и pre-existing `auth_users/account.py`, `auth_users/helpers.py`); не заведён как дефект текущего задания согласно инструкции.
- Frontend build: **PASS**.
- Adversarial-прогон не выполнялся: исключён спецификацией.

## Ограничение среды

Для воспроизведения использовались серверы, запущенные строго из `fastapi-application/` с `../.venv/bin/uvicorn main:main_app --host 127.0.0.1 --port 8000`; каждый поднятый QA-процесс остановлен, порт 8000 после прогона свободен. Для диагностики применялась только документированная команда `../.venv/bin/alembic upgrade heads`; она завершилась с exit 0, но создала только `alembic_version`, а таблицы `user` и `orders` отсутствуют.
