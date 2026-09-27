# Фаза 1: Dual transport backend — прогресс

Задание: Dual-transport авторизация (Cookie + Bearer) с CSRF-защитой.
Исполнитель: backend-dev. Дата: 2026-09-27.

## План (до правок)

Текущее состояние (зафиксировано чтением файлов):
- `auth_backend.py`: единственный `auth_backend = AuthenticationBackend(name="jwt", transport=cookie_transport, ...)`
- `fastapi_users_obj.py`: `FastAPIUsers[User, UUID](get_user_manager, [auth_backend])`
- `router.py`: один `auth_router = get_auth_router(auth_backend)` под `prefix="/auth/jwt"`
- `auth_backend` используется вне router.py: `auth_users/__init__.py` (импорт + `__all__`) — файл вне зоны фазы → alias `auth_backend = cookie_backend` обязателен
- `BearerTransport` доступен в установленной fastapi-users 15 (проверено импортом)

Изменения:

1. `auth_backend.py` (edit):
   - импорт `BearerTransport` из `fastapi_users.authentication`
   - `bearer_transport = BearerTransport(tokenUrl="/auth/bearer/login")`
   - `auth_backend` → `cookie_backend` с `name="jwt-cookie"` (по контракту спеки)
   - новый `bearer_backend = AuthenticationBackend(name="jwt-bearer", transport=bearer_transport, get_strategy=get_jwt_strategy)`
   - alias `auth_backend = cookie_backend` (обратная совместимость с `__init__.py`)
   - `get_jwt_strategy` без изменений — единая стратегия для обоих backend
   - обновить docstring
2. `fastapi_users_obj.py` (edit): импорт обоих backend, список `[cookie_backend, bearer_backend]`
3. `router.py` (edit):
   - импорт `cookie_backend, bearer_backend`
   - `cookie_auth_router = fastapi_users.get_auth_router(cookie_backend)` → `prefix="/auth/cookie", tags=["auth-cookie"]`
   - `bearer_auth_router = fastapi_users.get_auth_router(bearer_backend)` → `prefix="/auth/bearer", tags=["auth-bearer"]`
   - удалить подключение `/auth/jwt/*`
   - `/auth/register`, `/users/*`, account, protected — без изменений
4. Checkpoint: ruff, импорты, OpenAPI paths == 25, smoke curl оба login (не 404), сервер погасить

## Прогресс

| Дата | Файл | Что сделано | Проверки | Статус |
|---|---|---|---|---|
| 2026-09-27 | tasks/current/dev/phase01_progress.md | план зафиксирован до правок | — | done |
| 2026-09-27 | auth_users/auth_backend.py | добавлен BearerTransport(tokenUrl="/auth/bearer/login"), bearer_backend (name="jwt-bearer"); auth_backend переименован в cookie_backend (name="jwt-cookie"); alias auth_backend = cookie_backend (нужен: auth_users/__init__.py импортирует auth_backend); get_jwt_strategy без изменений | ruff на файле чист, `from auth_users.auth_backend import cookie_backend, bearer_backend` → OK (jwt-cookie, jwt-bearer) | done |
| 2026-09-27 | auth_users/fastapi_users_obj.py | FastAPIUsers[User, UUID](get_user_manager, [cookie_backend, bearer_backend]) — порядок cookie -> bearer по контракту | ruff чист, импорт fastapi_users OK | done |
| 2026-09-27 | auth_users/router.py | два auth_router: /auth/cookie (tags=auth-cookie) и /auth/bearer (tags=auth-bearer); старый /auth/jwt/* удалён; register/users/account/protected без изменений | ruff чист; OpenAPI paths = 25 | done |
| 2026-09-27 | tasks/current/dev/ | smoke-прогон (raw — phase01_smoke_curl.txt, phase01_smoke_server.txt), сервер погашен | см. сводку | done |

## Финальная сводка (фактические проверки)

### Checkpoint спеки

1. `cd fastapi-application && ../.venv/bin/ruff check auth_users/` — 1 ошибка I001 в
   `auth_users/user_manager.py` (сортировка импортов). Проверено через `git stash`:
   ошибка воспроизводится на чистом HEAD — предсуществующая, вне зоны фазы, не чинилась.
   На трёх изменённых файлах фазы (`auth_backend.py`, `fastapi_users_obj.py`,
   `router.py`) — `ruff check` поимённо: All checks passed.
2. `../.venv/bin/python -c "from auth_users.auth_backend import cookie_backend, bearer_backend"` → OK,
   имена: jwt-cookie, jwt-bearer. Импорт `fastapi_users_obj.fastapi_users` → OK.
3. `../.venv/bin/python -c "from main import main_app; ..."` → OpenAPI paths = **25**
   (было 23). Auth-пути: `/auth/account`, `/auth/bearer/login`, `/auth/bearer/logout`,
   `/auth/cookie/login`, `/auth/cookie/logout`, `/auth/register`. Security schemes:
   `APIKeyCookie`, `OAuth2PasswordBearer` — обе присутствуют.

### Smoke (uvicorn 127.0.0.1:8000, raw в phase01_smoke_curl.txt)

- `POST /auth/register` (phase01@example.com) → **201**, JSON UserRead
- `POST /auth/cookie/login` → **204**, Set-Cookie `auth=<JWT>` (HttpOnly), JWT в jar
- `POST /auth/bearer/login` → **200**, `{"access_token": "<JWT>", "token_type": "bearer"}`
  (JWT совпадает с cookie-вариантом — единый get_jwt_strategy)
- `POST /auth/bearer/login` неверный пароль → **400**
- `POST /auth/jwt/login` (старый путь) → **405** (путь больше не существует; 405 из-за
  SPA catch-all, не 404 — ожидаемо для FastAPI с catch-all)
- `GET /users/me` с cookie jar → **200** (cookie-транспорт работает)
- Сервер погашен, `ps aux | grep uvicorn` пусто.

### Замечания

- `auth_backend` alias оставлен: действительно используется в
  `auth_users/__init__.py` (строки 24–25, 52) — вне зоны фазы.
- OpenAPI count 23→25 зафиксирован: сменились фазы 5–6 (docs/инварианты) — им знать.

## Фаза завершена

Checkpoint зелёный (с оговоркой о предсуществующем I001 в user_manager.py),
`git diff` — только три файла фазы + прогресс-файл, TODO/FIXME не добавлялись.

