# Фаза 2: CSRF middleware — прогресс

Задание: Dual-transport авторизация (Cookie + Bearer) с CSRF-защитой.
Исполнитель: backend-dev. Дата: 2026-09-27.

## План (до правок)

Текущее состояние (зафиксировано чтением файлов):
- `core/config.py`: `settings.web.secret_key` существует (WebConfig),
  `settings.auth_users.cookie_name = "auth"`, `cookie_max_age = 86400` существуют
- `main.py`: create_app -> include_router x3 -> mount_frontend последним; middleware не подключён
- Фаза 1 завершена и проверена: cookie/bearer backend'ы, пути `/auth/cookie/*`, `/auth/bearer/*`, OpenAPI paths=25
- В БД есть пользователь phase01@example.com (smoke фазы 1); для фазы 2 регистрирую своего phase02@example.com

Изменения:

1. `auth_users/csrf.py` (новый, один write_file):
   - `CSRFMiddleware(BaseHTTPMiddleware)` с сигнатурой по контракту:
     `__init__(self, app, secret_key: str, cookie_name: str = "csrf_token", auth_cookie_name: str = "auth")`
   - Токен: `<nonce>.<hex HMAC-SHA256(secret_key, nonce)>`, nonce = `secrets.token_urlsafe(32)`
   - dispatch: если метод в {POST, PUT, PATCH, DELETE} И cookie auth присутствует —
     требовать `X-CSRF-Token == csrf_token cookie` (точное совпадение) И валидную HMAC
     (`hmac.compare_digest`); иначе 403 `{"detail": "CSRF validation failed"}`.
     Наличие `Authorization` НЕ освобождает при наличии auth-cookie. GET/HEAD/OPTIONS и
     запросы без auth-cookie пропускаются. Никаких whitelist-путей.
   - Lifecycle через response inspection вокруг `call_next`:
     - `path == "/auth/cookie/login"` и `status_code == 204` →
       `Set-Cookie: csrf_token=<nonce>.<sig>; Max-Age=<settings.auth_users.cookie_max_age>; Path=/; SameSite=Lax` (secure=False, без HttpOnly)
     - `path == "/auth/cookie/logout"` и успешный статус (<400) → удаление csrf_token (`max_age=0`, Path=/)
   - Max-Age берётся из `settings.auth_users.cookie_max_age` (импорт core.config внутри модуля — сигнатура контракта остаётся точной)
2. `main.py` (точечный edit):
   - импорт `from auth_users.csrf import CSRFMiddleware`
   - после `create_app(...)`, до include_router'ов: `main_app.add_middleware(CSRFMiddleware, secret_key=settings.web.secret_key, auth_cookie_name=settings.auth_users.cookie_name)`
   - `mount_frontend(main_app)` остаётся строго последним
3. Checkpoint: ruff (csrf.py, core/, main.py) с учётом предсуществующего I001 в
   `auth_users/user_manager.py` (зафиксирован в фазе 1, чужой файл — не чинить);
   импорты csrf/main; OpenAPI paths остаётся 25
4. Smoke (свободный порт 8010, свой сервер, в конце погасить):
   - login Set-Cookie auth + csrf_token
   - 403 без X-CSRF-Token и с подменённым токеном (state-changing cookie-запрос)
   - успех с валидным токеном (не 403)
   - смешанный cookie+Bearer без CSRF → 403, с CSRF → не 403
   - чистый Bearer без cookie проходит middleware
   - /auth/account без CSRF → 403
   - cookie logout удаляет csrf_token (Max-Age=0)
   - bearer logout без CSRF → 204

## Прогресс

| Дата | Файл | Что сделано | Проверки | Статус |
|---|---|---|---|---|
| 2026-09-27 | tasks/current/dev/phase02_progress.md | план зафиксирован до правок | — | done |
| 2026-09-27 | auth_users/csrf.py | создан CSRFMiddleware (BaseHTTPMiddleware): signed double-submit cookie, 403 CSRF validation failed, lifecycle login(204)->set / logout(success)->delete; I001 сортировки импортов исправлен (core.config первым) | ruff поимённо чист | done |
| 2026-09-27 | main.py | add_middleware(CSRFMiddleware, secret_key, auth_cookie_name) после create_app, до include_router; mount_frontend остался последним | ruff чист; `from main import main_app` OK; OpenAPI paths = 25 | done |
| 2026-09-27 | статический checkpoint | ruff csrf.py+main.py+core/ → All checks passed; `auth_users/` целиком → только предсуществующий I001 в user_manager.py (чужой файл, из фазы 1, не чинился) | — | done |

## Финальная сводка (фактические проверки)

### Checkpoint спеки (статический)

1. `cd fastapi-application && ../.venv/bin/ruff check auth_users/csrf.py core/ main.py`
   → All checks passed (наZone-файлах фазы ошибок нет).
   `../.venv/bin/ruff check auth_users/` → единственная ошибка I001 в
   `auth_users/user_manager.py` — предсуществующая (зафиксирована ещё в фазе 1
   через `git stash`), чужой файл зоны фазы, не исправлялась.
2. `../.venv/bin/python -c "from auth_users.csrf import CSRFMiddleware"` → OK.
3. `../.venv/bin/python -c "from main import main_app; ..."` → OK, OpenAPI paths = 25
   (не изменилось: middleware не добавляет маршрутов).

### Smoke (uvicorn 127.0.0.1:8010, свой сервер, raw в phase02_smoke_curl.txt; скрипт прогона — phase02_smoke.sh, лог сервера — phase02_smoke_server.txt)

Зарегистрирован phase02@example.com (201). Все ответы — дословно в phase02_smoke_curl.txt:

- S1 cookie login → **204**, `Set-Cookie: auth=<JWT>; HttpOnly; Max-Age=86400; Path=/; SameSite=lax`
  + `Set-Cookie: csrf_token=<nonce>.<sig>; Max-Age=86400; Path=/; SameSite=lax` (без HttpOnly — как задано)
- S2 GET /users/me (cookie) → **200** (GET без CSRF)
- S3 POST /auth/account без X-CSRF-Token → **403** `{"detail":"CSRF validation failed"}`
- S4 POST /auth/account с подменённым nonce при валидной чужой подписи → **403**;
  S4b с `abc.def` (битая подпись) → **403**
- S5 POST /auth/account с валидным X-CSRF-Token → **422** (endpoint достигнут:
  fastapi-users-схема требует username/email — это валидация endpoint'а, не CSRF;
  спека допускает «200 или 422»)
- S6 смешанный (auth-cookie + Bearer) без X-CSRF-Token → **403**
- S7 смешанный (auth-cookie + Bearer) с валидным X-CSRF-Token → **422** (не 403,
  endpoint достигнут — Bearer не обошёл проверку, но и не заблокировал валидный запрос)
- S8 чистый Bearer (без auth-cookie) без X-CSRF-Token → middleware пропустил:
  с пустым телом `add_order` дал 500 (IntegrityError самого endpoint'а — `Order()`
  без значений, известное поведение endpoint'а), с валидным телом
  `{"promocode":"PHASE02"}` → **200** `{"id":2,...}` (S8-fix в raw)
- S9 POST /orders/add_order c cookie без CSRF → **403**
- S10 cookie logout с валидным X-CSRF-Token → **204**,
  `Set-Cookie: csrf_token=""; Max-Age=0; Path=/; SameSite=lax` — удаление по lifecycle
  (вместе с удалением auth-cookie самим fastapi-users)
- S10b после logout POST /auth/account со старым csrf → **401** Unauthorized
  (auth-cookie удалён — middleware корректно пропустил, отказ от auth)
- S11 bearer logout без auth-cookie и без CSRF-заголовка → **204**
- Сервер погашен после прогона: `kill <pid>`, `pgrep -af "uvicorn.*main:main_app"`
  пусто, порт 8010 закрыт.

### Замечания

- S5/S7: `/auth/account` с валидным CSRF-токеном возвращает 422 — endpoint
  требует поля username/email (схема fastapi-users), middleware при этом пропустил
  запрос. 422 ≠ CSRF-403, спека допускает «200 или 422».
- S8: пустое тело `add_order` → 500 от самого endpoint'а (NOT NULL в БД), не от
  middleware; повтор с валидным телом дал 200 — проход middleware чистым Bearer
  доказан кодом ответа.
- Max-Age CSRF-cookie берётся из settings.auth_users.cookie_max_age (86400) внутри
  csrf.py: контракт сигнатуры middleware зафиксирован спекой без этого параметра.
- Cookie logout удаляет csrf_token при любом статусе <400; logout с невалидным CSRF
  и auth-cookie до call_next не доходит (403) — bypass не создаётся.

## Фаза завершена

Checkpoint зелёный, git diff — только auth_users/csrf.py (новый) и main.py +
прогресс/raw-файлы. TODO/FIXME не добавлялись. Сервер не оставлен запущенным.
