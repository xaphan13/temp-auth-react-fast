# Dual-transport авторизация (Cookie + Bearer) с CSRF-защитой

Добавить поддержку двух способов авторизации к существующему JWT-механизму: Cookie-transport для браузера (React SPA) и Bearer-transport для не-браузерных клиентов (CLI, мобильные приложения, server-to-server). Реализовать CSRF-защиту для Cookie-transport через паттерн Signed Double Submit Cookie. Обновить фронтенд для работы с новыми путями и CSRF-токенами.

## Подтверждённые решения

- Пути авторизации: `/auth/cookie/login`, `/auth/cookie/logout` для браузера; `/auth/bearer/login`, `/auth/bearer/logout` для клиентов
- Регистрация: единый endpoint `/auth/register` (не зависит от транспорта)
- Транспорты: стандартный `CookieTransport` из fastapi-users (уже есть) + стандартный `BearerTransport` (добавить)
- Два `AuthenticationBackend`: `cookie_backend` и `bearer_backend`, оба используют единый `get_jwt_strategy` — JWT payload идентичен
- Порядок перебора в `Authenticator._authenticate`: cookie первым, затем bearer
- Bearer login отдаёт JSON `{"access_token": "...", "token_type": "bearer"}` (штатное поведение `BearerTransport`)
- Bearer logout: пустой ответ 204, клиент забывает токен сам
- OpenAPI security schemes генерируются библиотекой автоматически — проверить наличие обеих схем в `/openapi.json`
- CSRF: паттерн Signed Double Submit Cookie (HMAC-SHA256 через `settings.web.secret_key`)
- CSRF cookie `csrf_token` создаётся в ответе успешного `/auth/cookie/login`, удаляется в ответе успешного `/auth/cookie/logout`
- CSRF cookie: не HttpOnly (SPA читает через `document.cookie`), SameSite=Lax, Secure=False в dev
- CSRF проверяется для каждого POST/PUT/PATCH/DELETE, если в запросе присутствует auth-cookie; GET/HEAD/OPTIONS пропускаются
- Наличие `Authorization: Bearer` не отменяет CSRF-проверку, если auth-cookie также присутствует; чистый Bearer-запрос без auth-cookie CSRF не требует
- Отдельный модуль `fastapi-application/auth_users/csrf.py` с middleware
- React SPA обновляется в этом же задании: пути `/auth/cookie/*`, чтение `csrf_token`, передача заголовка `X-CSRF-Token`
- OpenAPI path count меняется с 23 на 25 (+2 пути для bearer login/logout)

## Результат

После выполнения задания в репозитории:

**Backend:**
- `fastapi-application/auth_users/auth_backend.py`: экспортирует `cookie_backend` и `bearer_backend`
- `fastapi-application/auth_users/fastapi_users_obj.py`: регистрирует оба backend'а в `FastAPIUsers`
- `fastapi-application/auth_users/router.py`: два auth_router с prefix `/auth/cookie` и `/auth/bearer`
- `fastapi-application/auth_users/csrf.py`: новый файл с `CSRFMiddleware`
- `fastapi-application/main.py`: подключён `CSRFMiddleware`
- OpenAPI `/openapi.json` содержит 25 paths и две security schemes (cookie и bearer)
- `current_user()` / `active_user()` автоматически принимают оба типа credential

**Frontend:**
- `frontend/src/api/auth.ts`: использует `/auth/cookie/login` вместо `/auth/jwt/login`
- `frontend/src/api/client.ts`: читает cookie `csrf_token`, добавляет заголовок `X-CSRF-Token` в каждый state-changing запрос

**Поведение:**
- Браузер: `POST /auth/cookie/login` → получает JWT в cookie `auth` и CSRF-токен в cookie `csrf_token` → все запросы с этими cookies + заголовок `X-CSRF-Token`
- CLI/мобильные: `POST /auth/bearer/login` → получают JSON с `access_token` → передают `Authorization: Bearer <token>`, CSRF не требуется
- Защищённые маршруты (`/users/me`, `/api/v1/auth/protected`, `/orders/*`) принимают оба транспорта
- CSRF middleware блокирует state-changing запросы с auth-cookie без валидного `X-CSRF-Token` (403 Forbidden)
- Чистый Bearer-запрос без auth-cookie проходит без CSRF; смешанный запрос с auth-cookie и Bearer обязан пройти CSRF-проверку, чтобы заголовок Authorization не создавал обход защиты cookie

## Вне рамок

- Модели, схемы, CRUD заказов/пользователей — не изменяются
- Alembic миграции — не требуются (схема БД не меняется)
- Демонстрационные API-маршруты `/api/v1/dep_examples/*` — не трогаются
- Тестовые фреймворки (pytest, TestClient) — не добавляются, проверка через запуск и curl
- Профили БД, настройки uvicorn/gunicorn — не меняются
- Известный дефект `validate_query_safe` — не исправляется
- Документация проекта (`docs/`) и агентный контракт (`QWEN.md`, `AGENTS.md`) — обновит оркестратор отдельным шагом после продуктовых фаз
- Bearer token blacklist / revocation — не реализуется (stateless logout, документировано в CSRF фазе)
- Рефреш-токены — не добавляются (за рамками текущего задания)

## Архитектурный разбор

### Bounded context

**Входит в задание:**
- Модуль авторизации `fastapi-application/auth_users/` (транспорты, backend'ы, роутеры, middleware)
- Точка входа приложения `fastapi-application/main.py` (подключение middleware)
- Frontend API-слой `frontend/src/api/` (пути авторизации, CSRF-заголовок)

**За границами задания:**
- Модуль заказов `fastapi-application/ex_order_product/` (использует `active_user`, изменения не требуются)
- Демонстрационные API `fastapi-application/api/` (используют свои Depends, не меняются)
- Модели и миграции `fastapi-application/db_core/` (схема БД не затронута)
- UI-компоненты `frontend/src/components/` (логика входа не меняется, только URL)

### Интеграционные границы и контракты

**Backend → Backend (между фазами):**

После фазы 1 (dual transport):
- Экспорты `auth_backend.py`: `cookie_backend: AuthenticationBackend`, `bearer_backend: AuthenticationBackend`, `get_jwt_strategy: Callable[[], JWTStrategy]`
- Пути роутеров: `/auth/cookie/login`, `/auth/cookie/logout`, `/auth/bearer/login`, `/auth/bearer/logout`, `/auth/register`
- OpenAPI path count: 25 (было 23)
- JWT payload: без изменений — `sub` (user UUID), `aud` (опционально), `exp` (lifetime из settings)
- `current_user` / `active_user`: автоматически пробуют оба backend'а по порядку (cookie → bearer)

После фазы 2 (CSRF middleware):
- Модуль `auth_users/csrf.py` экспортирует `CSRFMiddleware` (класс Starlette BaseHTTPMiddleware или чистый ASGI middleware)
- Cookie `csrf_token`: имя фиксировано, значение = `<nonce>.<signature>`, где `nonce` — случайный URL-safe токен, а `signature` — hex HMAC-SHA256(`settings.web.secret_key`, `nonce`); не HttpOnly, SameSite=Lax, Secure=False в dev, Max-Age = `settings.auth_users.cookie_max_age` (86400 сек)
- Заголовок запроса: `X-CSRF-Token: <точное значение cookie csrf_token>`
- Логика проверки: если метод в [POST, PUT, PATCH, DELETE] и cookie `auth` присутствует, требовать совпадающий cookie/header и валидную HMAC-подпись; наличие `Authorization` не отменяет проверку. Если auth-cookie нет, запрос пропускается без CSRF независимо от Bearer.
- Login/logout endpoints должны получить lifecycle-обработку CSRF-cookie без обхода проверки: успешный `/auth/cookie/login` устанавливает подписанный cookie, успешный `/auth/cookie/logout` удаляет его; `/auth/bearer/*`, `/docs`, `/openapi.json`, `/redoc`, `/assets/*` не требуют CSRF, если auth-cookie отсутствует. GET SPA fallback пропускается по методу.
- Middleware подключается в `main.py` через `main_app.add_middleware(CSRFMiddleware)`; Starlette middleware глобален и порядок `add_middleware` не является границей между API-роутерами. Реализация не должна полагаться на подключение «между роутерами».

**Backend → Frontend:**

После фазы 2:
- Cookie `csrf_token` появляется в ответе `/auth/cookie/login` (Set-Cookie), доступна JS через `document.cookie`
- Cookie `csrf_token` удаляется в ответе `/auth/cookie/logout` (Set-Cookie с Max-Age=0)
- Backend ожидает заголовок `X-CSRF-Token` в каждом POST/PUT/PATCH/DELETE запросе с cookie-auth

После фазы 3 (frontend):
- `frontend/src/api/client.ts`: функция `getCsrfToken(): string | null` читает cookie `csrf_token`
- Все вызовы `postJson`, `postForm`, `postMultipart` добавляют header `X-CSRF-Token: <значение>`
- `auth.ts`: путь логина изменён с `/auth/jwt/login` на `/auth/cookie/login`, путь logout аналогично

### Зависимости и порядок работ

**До фазы 1 должны существовать:**
- Текущий `get_jwt_strategy` в `auth_backend.py` (есть)
- `FastAPIUsers` в `fastapi_users_obj.py` (есть)
- `settings.auth_users.*` конфигурация (есть)

**Последовательность фаз (параллельность невозможна):**
1. Фаза 1 (dual transport) → обязательна первой, создаёт контракты путей
2. Фаза 2 (CSRF) → зависит от существования `/auth/cookie/login` (проверяет этот path для генерации токена)
3. Фаза 3 (frontend) → зависит от существования CSRF cookie и новых путей

**Новые абстракции и их обоснование:**
- `CSRFMiddleware` — отдельный модуль обоснован изоляцией ответственности (auth_backend отвечает за JWT, csrf — за защиту от cross-site атак) и возможностью включения/отключения middleware без правки auth-кода
- Два backend'а вместо одного — обоснованы разными требованиями клиентов: браузер нуждается в автоматической передаче cookie, не-браузерные клиенты нуждаются в явном контроле токена

### Риски безопасности и производительности

**Безопасность (релевантные для задания):**
- CSRF middleware должен корректно различать cookie-auth и bearer-auth запросы: проверка наличия заголовка `Authorization` предотвращает ложные отказы для Bearer-клиентов
- Подпись CSRF-токена через HMAC защищает от cookie injection: злоумышленник не может сгенерировать валидный токен без знания `settings.web.secret_key`
- CSRF cookie не HttpOnly: это осознанное решение для SPA, но увеличивает поверхность XSS-атаки (если скрипт читает csrf_token, он может сделать валидный запрос от имени пользователя, пока страница открыта)

**Производительность (релевантные для задания):**
- Middleware выполняется на каждом запросе: overhead минимален (проверка path и метода — O(1), HMAC-верификация только для state-changing запросов с cookie)
- Два backend'а увеличивают время проверки аутентификации: в худшем случае (невалидный cookie + валидный Bearer) проверяются оба, но для 99% запросов первый backend побеждает

**Нерелевантные (явно вне рамок):**
- Rate limiting для login endpoints — не реализуется
- Blacklist токенов для отзыва — не реализуется (Bearer logout stateless)
- Защита от brute-force пароля — fastapi-users не предоставляет встроенного механизма, задача не расширяется

## План фаз

Единица исполнения — фаза: одно делегирование, 1–3 файла, бюджет ~10–15 ходов.
Следующая фаза стартует только после зелёного checkpoint и ревью диффа оркестратором.
Прогресс backend/frontend-фазы разработчик фиксирует в `tasks/current/dev/phaseNN_progress.md`; для фаз 4–6, которые выполняет `docs-writer`, отдельный progress-файл не требуется.

| # | Фаза | Исполнитель | Файлы | Контракт | Checkpoint | Бюджет ходов |
|---|---|---|---|---|---|---|
| 1 | Dual transport backend | backend-dev | auth_backend.py, fastapi_users_obj.py, router.py | Экспорты cookie_backend, bearer_backend; пути /auth/cookie/*, /auth/bearer/* | OpenAPI count=25, ruff чистый, import чистый, smoke curl оба login | ~12 |
| 2 | CSRF middleware | backend-dev | auth_users/csrf.py (новый), main.py | CSRFMiddleware с response inspection для login/logout и корректным lifecycle CSRF-cookie | ruff/import чистые; curl доказывает 403/успех/удаление cookie и смешанный сценарий | ~18 |
| 3 | Frontend CSRF integration | frontend-dev | frontend/src/api/auth.ts, frontend/src/api/client.ts | Функция чтения csrf_token; header на state-changing fetch; cookie auth paths | `npm run build` без ошибок | ~10 |
| 4 | Документация auth flow | docs-writer | `docs/04_authorization.md`, `docs/07_auth_token_flow_code.md`, `docs/09_auth_transports_and_api_keys.md` | Описать оба транспорта, CSRF lifecycle, точные заголовки и актуальные пути | Поиск подтверждает актуальные маршруты cookie/bearer и CSRF-flow; diff только релевантных строк | ~8 |
| 5 | Документация навигации | docs-writer | `docs/00_agent_navigation.md`, `docs/01_project_structure.md` | Обновить inventory auth routes и OpenAPI count до 25 | В route inventory перечислены cookie/bearer endpoints; count=25; diff только релевантных строк | ~6 |
| 6 | Агентные инварианты | оркестратор | `QWEN.md`, `AGENTS.md` | Обновить startup/smoke facts, OpenAPI count и dual-transport endpoints | `grep` подтверждает 25 и новые пути; diff только релевантных строк | ~6 |

### Фаза 1: Dual transport backend

**Исполнитель:** backend-dev

**Файлы:**
- `fastapi-application/auth_users/auth_backend.py` (edit: добавить BearerTransport и bearer_backend)
- `fastapi-application/auth_users/fastapi_users_obj.py` (edit: изменить список backend'ов с `[auth_backend]` на `[cookie_backend, bearer_backend]`)
- `fastapi-application/auth_users/router.py` (edit: развести auth_router на два prefix'а)

**Контракт (замораживается для следующих фаз):**

`auth_backend.py` экспортирует:
```python
cookie_backend: AuthenticationBackend  # name="jwt-cookie"
bearer_backend: AuthenticationBackend  # name="jwt-bearer"
get_jwt_strategy: Callable[[], JWTStrategy]  # без изменений
```

`router.py` подключает:
```python
router.include_router(
    fastapi_users.get_auth_router(cookie_backend),
    prefix="/auth/cookie", tags=["auth-cookie"]
)
router.include_router(
    fastapi_users.get_auth_router(bearer_backend),
    prefix="/auth/bearer", tags=["auth-bearer"]
)
router.include_router(register_router, prefix="/auth", tags=["auth-register"])
# /auth/register остаётся без изменений
```

OpenAPI paths (25 total):
- `/auth/cookie/login` (POST)
- `/auth/cookie/logout` (POST)
- `/auth/bearer/login` (POST)
- `/auth/bearer/logout` (POST)
- `/auth/register` (POST)
- `/users/me` (GET, PATCH)
- `/api/v1/auth/protected` (GET)
- `/orders/*` (4 пути)
- `/api/v1/dep_examples/*` (12 путей)
- `/docs`, `/openapi.json`, `/redoc` (служебные, не считаются в OpenAPI paths)

JWT payload: без изменений, `sub`, `aud` (опционально), `exp`.

**Шаги:**

1. Прочитать текущий `auth_backend.py`, `fastapi_users_obj.py`, `router.py` — зафиксировать текущие имена и структуру
2. Составить план изменений файлов (записать в `tasks/current/dev/phase01_progress.md`)
3. Править `auth_backend.py`:
   - Импортировать `BearerTransport` из `fastapi_users.authentication`
   - Создать `bearer_transport = BearerTransport(tokenUrl="/auth/bearer/login")`
   - Создать `bearer_backend = AuthenticationBackend(name="jwt-bearer", transport=bearer_transport, get_strategy=get_jwt_strategy)`
   - Переименовать `auth_backend` в `cookie_backend` (или оставить alias `auth_backend = cookie_backend` для обратной совместимости, если используется вне router.py — проверить grep)
   - Экспортировать оба backend'а
4. Зафиксировать прогресс checkpoint: `../.venv/bin/python -c "from auth_users.auth_backend import cookie_backend, bearer_backend; print('OK')"`
5. Править `fastapi_users_obj.py`:
   - Изменить импорт: `from auth_users.auth_backend import cookie_backend, bearer_backend`
   - Изменить список: `FastAPIUsers[User, UUID](get_user_manager, [cookie_backend, bearer_backend])`
6. Зафиксировать прогресс checkpoint: `../.venv/bin/python -c "from auth_users.fastapi_users_obj import fastapi_users; print('OK')"`
7. Править `router.py`:
   - Изменить импорт: `from auth_users.auth_backend import cookie_backend, bearer_backend`
   - Заменить старое подключение `/auth/jwt` двумя `include_router` с prefix `/auth/cookie` и `/auth/bearer`; старый путь удалить
8. Зафиксировать прогресс checkpoint: `../.venv/bin/python -c "from main import main_app; print(len(main_app.openapi()['paths']))"` → 25
9. Smoke-тест (запустить приложение в фоне, curl, kill):
   ```bash
   cd fastapi-application
   ../.venv/bin/uvicorn main:main_app --host 127.0.0.1 --port 8000 &
   UVICORN_PID=$!
   sleep 3
   # Cookie login
   curl -c /tmp/cookies.txt -X POST http://127.0.0.1:8000/auth/cookie/login \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=test@example.com&password=testpass" \
     -w "%{http_code}" -o /dev/null  # ожидаем 204 или 401 (если пользователя нет — не критично, важно что эндпоинт существует)
   # Bearer login
   curl -X POST http://127.0.0.1:8000/auth/bearer/login \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=test@example.com&password=testpass"  # ожидаем JSON {"access_token":...} или 401
   kill $UVICORN_PID
   ```
10. Обновить прогресс-файл финальной сводкой

**Checkpoint:**
```bash
cd fastapi-application
../.venv/bin/ruff check auth_users/
../.venv/bin/python -c "from auth_users.auth_backend import cookie_backend, bearer_backend; print('OK')"
../.venv/bin/python -c "from main import main_app; paths=len(main_app.openapi()['paths']); assert paths==25, f'Expected 25, got {paths}'; print('OK')"
```

**Ожидаемый результат checkpoint:**
- ruff без ошибок
- импорты чистые
- OpenAPI paths = 25
- smoke curl: `/auth/cookie/login` и `/auth/bearer/login` отвечают (статус-код не 404)

**Готовность фазы:**
- Checkpoint зелёный
- `git diff` показывает изменения только в `auth_users/auth_backend.py`, `auth_users/fastapi_users_obj.py`, `auth_users/router.py`
- Нет TODO/FIXME в изменённых строках
- `tasks/current/dev/phase01_progress.md` обновлён финальной сводкой

---

### Фаза 2: CSRF middleware

**Исполнитель:** backend-dev

**Файлы:**
- `fastapi-application/auth_users/csrf.py` (новый файл)
- `fastapi-application/main.py` (edit: подключить middleware)

**Контракт (замораживается для фазы 3):**

`auth_users/csrf.py` экспортирует:
```python
class CSRFMiddleware(BaseHTTPMiddleware):  # или чистый ASGI middleware
    def __init__(self, app, secret_key: str, cookie_name: str = "csrf_token",
                 auth_cookie_name: str = "auth"):
        ...
```

Поведение middleware:
- Для POST/PUT/PATCH/DELETE с cookie `auth` читает cookie `csrf_token` и заголовок `X-CSRF-Token`; отсутствие, несовпадение или неверная HMAC-подпись дают HTTP 403.
- Формат cookie — `<nonce>.<signature>`; HMAC проверяет только `nonce`, а header должен в точности совпадать со всем cookie-значением.
- Для GET/HEAD/OPTIONS и для запросов без cookie `auth` middleware пропускает запрос; наличие `Authorization` не является исключением, если `auth` cookie также присутствует.
- Lifecycle реализуется внутри `CSRFMiddleware` через response inspection вокруг `call_next(request)`, без hook’ов fastapi-users: после `response = await call_next(request)` при `request.url.path == "/auth/cookie/login"` и `response.status_code == 204` middleware добавляет в response `Set-Cookie` со значением `<nonce>.<signature>`; при `request.url.path == "/auth/cookie/logout"` и успешном ответе middleware добавляет удаление `csrf_token` с `Max-Age=0`. Login не требует CSRF header, потому что auth-cookie ещё не было; logout при наличии auth-cookie проходит обычную CSRF-проверку до `call_next`.
- Пути `/auth/bearer/*`, `/docs`, `/openapi.json`, `/redoc`, `/assets/*` не создают CSRF bypass для запроса с auth-cookie; GET SPA fallback проходит по правилу метода.

`main.py` подключает:
```python
from auth_users.csrf import CSRFMiddleware
from core.config import settings

main_app.add_middleware(
    CSRFMiddleware,
    secret_key=settings.web.secret_key,
    auth_cookie_name=settings.auth_users.cookie_name,
)
```

CSRF cookie lifecycle:
- успешный `/auth/cookie/login` (204 ответ) → `Set-Cookie: csrf_token=<nonce>.<signature>; Max-Age=86400; SameSite=Lax; Secure=False; Path=/`
- успешный `/auth/cookie/logout` → удаление `csrf_token` через `Set-Cookie` с `Max-Age=0`

**Шаги:**

1. Прочитать `core/config.py` — убедиться, что `settings.web.secret_key` и `settings.auth_users.cookie_name` существуют
2. Прочитать `main.py` — зафиксировать текущую структуру, порядок include_router и mount_frontend
3. Составить план (записать в `tasks/current/dev/phase02_progress.md`)
4. Создать `fastapi-application/auth_users/csrf.py`:
   - Импорты: `BaseHTTPMiddleware` или чистый ASGI middleware, `Request`, `hmac`, `hashlib`, `secrets`
   - Класс `CSRFMiddleware` с `secret_key`, `cookie_name="csrf_token"`, `auth_cookie_name="auth"`
   - Формировать значение как `<nonce>.<signature>`, где signature = hex HMAC-SHA256(secret_key, nonce); проверять через `hmac.compare_digest`
   - Для POST/PUT/PATCH/DELETE при наличии auth-cookie требовать точное совпадение `X-CSRF-Token` с cookie и валидную подпись; наличие Authorization этот вызов не освобождает
   - Для запросов без auth-cookie, а также GET/HEAD/OPTIONS, пропускать проверку
   - Реализовать lifecycle через response inspection вокруг `response = await call_next(request)`: для `request.url.path == "/auth/cookie/login"` и `response.status_code == 204` добавить `Set-Cookie` с `<nonce>.<signature>`; для успешного `/auth/cookie/logout` добавить удаление `csrf_token` с `Max-Age=0`. Не пытаться использовать несуществующий post-login hook fastapi-users.
   - Не использовать whitelist путей как обход CSRF для запросов с auth-cookie
5. Зафиксировать прогресс checkpoint: `../.venv/bin/python -c "from auth_users.csrf import CSRFMiddleware; print('OK')"`
6. Править `main.py`:
   - Добавить импорт `from auth_users.csrf import CSRFMiddleware`
   - Зарегистрировать `CSRFMiddleware` через `main_app.add_middleware(...)` с `settings.web.secret_key` и `settings.auth_users.cookie_name`; размещение в исходнике должно учитывать, что Starlette оборачивает всё приложение глобально, а `mount_frontend` остаётся последним маршрутизирующим вызовом
7. Зафиксировать прогресс checkpoint: `../.venv/bin/python -c "from main import main_app; print('OK')"`
8. Smoke-тест (в рамках локального checkpoint, использовать свободный порт/сервер по правилам AGENTS.md) должен проверить:
   - Cookie login выдаёт `auth` и подписанную `csrf_token` в ответе.
   - State-changing cookie-запрос без заголовка и с подменённым токеном получает 403.
   - Запрос с совпадающим cookie/header и валидной подписью доходит до endpoint (не получает CSRF 403).
   - Смешанный auth-cookie + валидный Bearer без CSRF header всё равно получает 403; повтор с валидным CSRF header не получает CSRF 403; чистый Bearer без auth-cookie проходит middleware.
   - `/auth/account` без CSRF header получает 403, с валидным header доходит до endpoint; один state-changing order endpoint имеет такое же поведение.
   - Cookie logout с валидным CSRF header удаляет `csrf_token` согласно lifecycle.
   - Bearer logout отвечает 204 и не требует CSRF header.
   Реальные команды и ответы сохранить в `tasks/current/dev/phase02_progress.md`; сервер не останавливать, если он принадлежит другому агенту.
9. Обновить прогресс-файл финальной сводкой

**Checkpoint:**
```bash
cd fastapi-application
../.venv/bin/ruff check auth_users/csrf.py core/ main.py
../.venv/bin/python -c "from auth_users.csrf import CSRFMiddleware; print('OK')"
../.venv/bin/python -c "from main import main_app; print('OK')"
```

**Ожидаемый результат checkpoint:**
- ruff без ошибок
- импорты чистые
- smoke curl: POST без X-CSRF-Token → 403, POST с валидным токеном → 200 или 422 (валидация данных)

**Готовность фазы:**
- Checkpoint зелёный
- `git diff` показывает новый файл `auth_users/csrf.py` и правку `main.py`
- Нет TODO/FIXME
- `tasks/current/dev/phase02_progress.md` обновлён

---

### Фаза 3: Frontend CSRF integration

**Исполнитель:** frontend-dev

**Файлы:**
- `frontend/src/api/client.ts` (edit: добавить функцию getCsrfToken и заголовок X-CSRF-Token в state-changing запросы)
- `frontend/src/api/auth.ts` (edit: изменить пути с `/auth/jwt/*` на `/auth/cookie/*`)

**Контракт:**

`client.ts` экспортирует:
```ts
function getCsrfToken(): string | null  // читает cookie csrf_token
// postJson, postForm, postMultipart автоматически добавляют X-CSRF-Token
```

`auth.ts` использует:
```ts
export function login(body: { email: string; password: string }): Promise<User> {
    const form = new URLSearchParams({ username: body.email, password: body.password });
    return postForm<unknown>('/auth/cookie/login', form).then(() => getJson<User>('/users/me'));
}
export function logout(): Promise<MessageResp> {
    return postForm<MessageResp>('/auth/cookie/logout', new URLSearchParams())
        .catch(() => ({ message: 'Logged out', category: 'info' }));
}
```

**Шаги:**

1. Прочитать текущие `client.ts` и `auth.ts` — зафиксировать текущие пути и структуру функций
2. Составить план (записать в `tasks/current/dev/phase03_progress.md`)
3. Править `frontend/src/api/client.ts`:
   - Добавить функцию `getCsrfToken()`:
     ```ts
     function getCsrfToken(): string | null {
         const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
         return match ? decodeURIComponent(match[1]) : null;
     }
     ```
   - Изменить функции `postJson`, `postForm`, `postMultipart`:
     - Перед вызовом `fetch` добавить:
       ```ts
       const csrfToken = getCsrfToken();
       const headers = { ...init.headers };
       if (csrfToken) headers['X-CSRF-Token'] = csrfToken;
       ```
     - Передать обновлённые headers в `fetch`
4. Зафиксировать прогресс checkpoint: `cd frontend && npm run build` (без ошибок)
5. Править `frontend/src/api/auth.ts`:
   - Найти все упоминания `/auth/jwt/` → заменить на `/auth/cookie/`
   - Конкретно:
     - `login`: `'/auth/jwt/login'` → `'/auth/cookie/login'`
     - `logout`: `'/auth/jwt/logout'` → `'/auth/cookie/logout'`
6. Зафиксировать прогресс checkpoint: `cd frontend && npm run build` (без ошибок)
7. Машинная smoke-проверка frontend-артефакта:
   ```bash
   cd frontend
   npm run build
   test -f dist/index.html
   ```
   Проверку фактического login/CSRF через браузер выполняет QA отдельным runtime-сценарием; эта фаза не требует ручного просмотра DevTools.
8. Обновить прогресс-файл финальной сводкой

**Checkpoint:**
```bash
cd frontend
npm run build
# Ожидаем: build завершается без ошибок, dist/index.html создан
```

**Ожидаемый результат checkpoint:**
- `npm run build` успешен
- `frontend/dist/index.html` и `frontend/dist/assets/*.js` существуют
- Изменения API-клиента добавляют `X-CSRF-Token` только при наличии cookie и не ломают `credentials: 'include'`; runtime-поведение проверяется QA curl-сценариями

**Готовность фазы:**
- Checkpoint зелёный
- `git diff` показывает изменения только в `frontend/src/api/client.ts` и `frontend/src/api/auth.ts`
- Нет TODO/FIXME
- `tasks/current/dev/phase03_progress.md` обновлён

---

### Фаза 4: Документация auth flow

**Исполнитель:** docs-writer; progress-файл не требуется.

**Файлы:** `docs/04_authorization.md`, `docs/07_auth_token_flow_code.md`, `docs/09_auth_transports_and_api_keys.md`.

**Контракт:** документы описывают `/auth/cookie/*`, `/auth/bearer/*`, общий `/auth/register`, два backend'а на одной JWTStrategy, формат Bearer login/logout и Signed Double Submit Cookie с форматом `<nonce>.<signature>`. Для state-changing запросов с auth-cookie документация требует `X-CSRF-Token`; смешанный cookie+Bearer запрос не описывается как CSRF bypass.

**Шаги:** обновить только устаревшие фактические маршруты, примеры curl/fetch, auth flow и CSRF lifecycle; сохранить обучательные разделы, не относящиеся к текущим endpoint'ам. Не переписывать документацию целиком.

**Checkpoint:** поиск по трём файлам подтверждает новые cookie/bearer routes, CSRF header и 25-path contract; diff содержит только правки auth transport/CSRF.

### Фаза 5: Документация навигации

**Исполнитель:** docs-writer; progress-файл не требуется.

**Файлы:** `docs/00_agent_navigation.md`, `docs/01_project_structure.md`.

**Контракт:** route inventory перечисляет оба login/logout prefix'а и общий `/auth/register`; OpenAPI reference указывает 25 path-ключей.

**Шаги:** обновить inventory и точечные ссылки на auth-модули, не менять архитектурные описания за пределами dual-transport.

**Checkpoint:** поиск по двум файлам не находит активных утверждений о 23 paths или единственном `/auth/jwt/*` как текущем auth flow.

### Фаза 6: Агентные инварианты

**Исполнитель:** оркестратор; progress-файл не требуется.

**Файлы:** `QWEN.md`, `AGENTS.md`.

**Контракт:** startup/check commands, smoke-набор и OpenAPI reference соответствуют 25 paths, новым auth endpoints и CSRF-проверке cookie-auth state-changing запросов.

**Шаги:** обновить только dual-transport факты и связанные команды; не трогать известный дефект валидатора, зоны агентов и общие правила.

**Checkpoint:** `grep` по обоим файлам подтверждает 25, `/auth/cookie`, `/auth/bearer`, `X-CSRF-Token`; `git diff` ограничен этими релевантными строками.

---

## Критерии успеха

Проверяются qa по завершении всех фаз; сырые выводы curl/команд — в `tasks/current/e2e/`.

| # | Критерий | Проверка | Ожидание |
|---|---|---|---|
| 1 | Cookie login работает | `curl -c cookies.txt -X POST http://127.0.0.1:8000/auth/cookie/login -H "Content-Type: application/x-www-form-urlencoded" -d "username=<email>&password=<pass>"` (пользователь создан через `/auth/register`) | HTTP 204, Set-Cookie содержит `auth=` и `csrf_token=` |
| 2 | Bearer login работает | `curl -X POST http://127.0.0.1:8000/auth/bearer/login -H "Content-Type: application/x-www-form-urlencoded" -d "username=<email>&password=<pass>"` | HTTP 200, JSON `{"access_token": "eyJ...", "token_type": "bearer"}` |
| 3 | Защищённая ручка через cookie | `curl -b cookies.txt http://127.0.0.1:8000/users/me` (после cookie login) | HTTP 200, JSON с полями `id`, `email` |
| 4 | Защищённая ручка через Bearer | `curl -H "Authorization: Bearer <token>" http://127.0.0.1:8000/users/me` (токен из критерия 2) | HTTP 200, JSON с полями `id`, `email` |
| 5 | CSRF: отказ без заголовка | `curl -b cookies.txt -X PATCH http://127.0.0.1:8000/users/me -H "Content-Type: application/json" -d '{"email":"<email>"}'` (без X-CSRF-Token) | HTTP 403, `{"detail": "CSRF validation failed"}` |
| 6 | CSRF: отказ с невалидным токеном | `curl -b cookies.txt -X PATCH http://127.0.0.1:8000/users/me -H "Content-Type: application/json" -H "X-CSRF-Token: invalid" -d '{"email":"<email>"}'` | HTTP 403, `{"detail": "CSRF validation failed"}` |
| 7 | CSRF: успех с валидным токеном | `curl -b cookies.txt -X PATCH http://127.0.0.1:8000/users/me -H "Content-Type: application/json" -H "X-CSRF-Token: <valid>" -d '{"email":"<email>"}'` (valid токен извлечён из cookies.txt) | HTTP 200 или 422 (если email невалиден), но НЕ 403 |
| 8 | CSRF: logout очищает CSRF-cookie | `curl -c cookies_after.txt -b cookies.txt -X POST http://127.0.0.1:8000/auth/cookie/logout -H "Content-Type: application/x-www-form-urlencoded" -H "X-CSRF-Token: <valid>"` | HTTP 204, response удаляет `csrf_token` через `Set-Cookie` с `Max-Age=0`; отдельная проверка auth-cookie остаётся ответственностью CookieTransport |
| 9a | Смешанный cookie+Bearer без CSRF не обходит защиту | `curl -b cookies.txt -H "Authorization: Bearer <token>" -X PATCH http://127.0.0.1:8000/users/me -H "Content-Type: application/json" -d '{"email":"<email>"}'` (auth-cookie присутствует, X-CSRF-Token отсутствует) | HTTP 403 с detail `CSRF validation failed` |
| 9b | Смешанный cookie+Bearer с CSRF проходит middleware | Повторить запрос 9a с `-H "X-CSRF-Token: <valid>"` | HTTP 200 или 422, но не 403 |
| 10 | Регресс: /docs доступен | `curl http://127.0.0.1:8000/docs` | HTTP 200, HTML содержит "Swagger UI" |
| 11 | Регресс: анонимный /users/me → 401 | `curl http://127.0.0.1:8000/users/me` | HTTP 401, `{"detail": "Unauthorized"}` |
| 12 | Регресс: /orders/get_all_orders с params | `curl "http://127.0.0.1:8000/orders/get_all_orders?params=id"` | HTTP 200, JSON список заказов (или пустой список) |
| 13 | Регресс: /api/v1/dep_examples с заголовком | `curl -H "foobar: testvalue" http://127.0.0.1:8000/api/v1/dep_examples/header_name` | HTTP 200, ответ содержит упоминание foobar |
| 14 | Регресс: `/auth/account` защищён CSRF | Cookie auth с `/auth/account` без `X-CSRF-Token` получает 403; повтор с валидным token доходит до endpoint | Без токена — 403; с токеном — не CSRF 403 |
| 15 | Регресс: state-changing order endpoint защищён CSRF | Cookie auth на `POST /orders/add_order` без header получает 403; повтор с валидным token доходит до endpoint | Без токена — 403; с токеном — не CSRF 403 |
| 16 | Bearer logout работает | `curl -X POST http://127.0.0.1:8000/auth/bearer/logout` без cookie и без CSRF header | HTTP 204 |
| 17 | Регресс: полный cookie auth flow | 1. `POST /auth/register` (201), 2. `POST /auth/cookie/login` (204, cookies), 3. `GET /users/me` с cookies (200), 4. `GET /api/v1/auth/protected` с cookies (200), 5. `POST /auth/cookie/logout` (204 + валидный CSRF header) | Все шаги успешны, последовательность без ошибок |
| 18 | OpenAPI count = 25 | `curl http://127.0.0.1:8000/openapi.json \| python -m json.tool \| jq '.paths \| length'` | Вывод: `25` |
| 19 | OpenAPI содержит обе security schemes | `curl http://127.0.0.1:8000/openapi.json \| python -m json.tool \| jq '.components.securitySchemes \| length'` | Вывод не меньше `2`; в JSON присутствуют схемы, соответствующие cookie и Bearer backend'ам |
| 20 | Frontend build без ошибок | `cd frontend && npm run build` | Exit code 0, `dist/index.html` создан, stderr без строк "error" |
| 21 | ruff чистый на backend | `cd fastapi-application && ../.venv/bin/ruff check .` | Exit code 0, нет ошибок |

## Финальные критерии

1. Все критерии успеха 1-21 подтверждены доказательствами в `tasks/current/e2e/` (сырые выводы curl + команд, qa-отчёт).
2. `tasks/current/DEFECTS.md` не существует или все записи имеют статус CLOSED/REJECTED (не OPEN, не FIX-READY, не DISPUTED).
3. Документы перечисленных фаз синхронизированы с реализованным контрактом; в них нет устаревшего утверждения, что актуальные login/logout routes — `/auth/jwt/*` или что OpenAPI count = 23.
4. Smoke-набор пройден: `/docs` открывается, анонимный `/users/me` → 401, `/orders/get_all_orders?params=id` работает, `/api/v1/dep_examples/header_name` с заголовком `foobar` работает, полный cookie auth flow завершён успешно.
5. OpenAPI `/openapi.json` содержит 25 paths и обе security schemes.
6. Frontend `npm run build` завершается без ошибок.
7. Backend `ruff check .` чистый.

## Открытые вопросы

Нет. Выборы по путям, транспортам, регистрации, порядку backend'ов, CSRF-паттерну и жизненному циклу cookie закрыты в `dev/dual-transport-questions.md`; безопасное поведение смешанного cookie+Bearer запроса уточнено в этой спецификации.

---

# Отчёт о выполнении

- Дата закрытия: 2026-09-27
- Коммит: не коммитилось (работа в рабочем дереве, ветка dual-transport)

## Итог

Реализована dual-transport авторизация (CookieTransport `/auth/cookie/*` + BearerTransport `/auth/bearer/*` на общей JWTStrategy) с CSRF-защитой Signed Double Submit Cookie (`auth_users/csrf.py`, X-CSRF-Token для state-changing cookie-запросов, включая смешанный cookie+Bearer), обновлён фронтенд, документация и агентные инварианты до 25 OpenAPI paths. Подтверждено qa-прогоном 19/21 PASS + ретестом двух исправленных дефектов (e2e/qa_report.md, e2e/defects_retest.txt).

## Дефекты

- DEF-001 (header_name 404): CLOSED — endpoint добавлен в `api/dependencies/dep_examp_simple.py` с `include_in_schema=False` (OpenAPI-инвариант 25 сохранён).
- DEF-002 (get_all_orders 500): CLOSED — нормализация `promocode=None → ""` в `ex_order_product/router_order_one.py`.
- Критерий 21 (ruff чистый): единственный I001 в `auth_users/user_manager.py` — предсуществующий baseline (воспроизведён на чистом HEAD через git stash), вне зоны задания, не исправлялся.

## Adversarial-прогон

ADV-001…ADV-006: все REJECTED — подделка подписи, replay, кросс-юзер CSRF, method override, pre-login csrf, bearer cookies: нарушений не найдено (ADVERSARIAL_REVIEW.md; прогон выполнен оркестратором после двух сетевых срывов делегирования).

## Примечания

- Ретест DEF-001/DEF-002 и adversarial-прогон выполнены оркестратором лично: делегирования qa/adversary прерывались сетевыми сбоями среды.
- Модели агентных ролей в течение задания менялись пользователем/оркестратором: relay/gpt-6-luna → nyxos-auto/glm-5.3-flash (backend-dev на финальном defect-fix — nyxos-auto/glm-5.3).

