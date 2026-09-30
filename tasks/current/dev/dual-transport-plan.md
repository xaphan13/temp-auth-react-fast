# План реализации dual-transport auth (Cookie + Bearer) с CSRF

Дата: 2026-09-26
Статус: черновик для обсуждения, не спека

---

## 1. Текущее состояние

- `auth_backend.py`: один `AuthenticationBackend(name="jwt", transport=cookie_transport, get_strategy=get_jwt_strategy)`
- `fastapi_users_obj.py`: `FastAPIUsers[User, UUID](get_user_manager, [auth_backend])` — список из одного backend'а
- `router.py`: `get_auth_router(auth_backend)` включён с prefix `/auth/jwt` → даёт `/auth/jwt/login`, `/auth/jwt/logout`
- Фронтенд: `fetch(path, { credentials: 'include' })` — полагается на cookie
- Счётчик OpenAPI: 23 path-ключа

## 2. Что говорит документация fastapi-users (проверено tavily + исходники)

**Официальная дока** (fastapi-users.github.io, все версии 10.x–latest):

> You can have several authentication methods, e.g. a cookie authentication for browser-based queries and a JWT token authentication for pure API queries. When checking authentication, each method is run one after the other. The first method yielding a user wins. If no method yields a user, an HTTPException is raised.

**BearerTransport** (`fastapi_users.authentication.BearerTransport`):
- Принимает `tokenUrl` (путь к login-endpoint для OpenAPI).
- При login возвращает JSON: `{ "access_token": "<JWT>", "token_type": "bearer" }`.
- При logout — пустой ответ.
- Извлекает токен из заголовка `Authorization: Bearer <token>`.
- Встроен в библиотеку, кастомного писать не нужно.

**Множественные backend'ы**: передаются списком в `FastAPIUsers(get_user_manager, [backend1, backend2])`. `Authenticator._authenticate` перебирает их по порядку. `current_user()` / `active_user()` работают со всеми зарегистрированными backend'ами автоматически.

**GitHub discussion #989, #960**: подтверждено — `current_user` dependency handles several backends, tries one by one until one matches.

**Вывод:** кастомный composite-Depends не нужен. Штатный механизм полностью закрывает задачу.

## 3. Архитектура после изменений

```
Browser (React SPA)          Client (curl / CLI / мобильное)
       |                              |
  POST /auth/cookie/login        POST /auth/bearer/login
  ← Set-Cookie: auth=<JWT>       ← { "access_token": "<JWT>", "token_type": "bearer" }
       |                              |
  GET /users/me                  GET /users/me
  Cookie: auth=<JWT>             Authorization: Bearer <JWT>
  X-CSRF-Token: <token>          (CSRF не нужен)
       |                              |
       └──────────┬───────────────────┘
                  │
         Authenticator._authenticate
         пробует cookie → bearer → первый валидный побеждает
                  │
            current_user() / active_user()
```

## 4. Пошаговый план

### Шаг 1: Добавить BearerTransport в `auth_backend.py`

- Импортировать `BearerTransport` из `fastapi_users.authentication`.
- Создать `bearer_transport = BearerTransport(tokenUrl="/auth/bearer/login")`.
- Создать `bearer_backend = AuthenticationBackend(name="jwt-bearer", transport=bearer_transport, get_strategy=get_jwt_strategy)`.
- Экспортировать оба backend'а.

Файл: `fastapi-application/auth_users/auth_backend.py` (edit, добавить ~10 строк).

### Шаг 2: Зарегистрировать оба backend'а в `fastapi_users_obj.py`

- Заменить `[auth_backend]` на `[cookie_backend, bearer_backend]`.
- Переименовать `auth_backend` → `cookie_backend` (или оставить alias для обратной совместимости).

Файл: `fastapi-application/auth_users/fastapi_users_obj.py` (edit, 1 строка).

### Шаг 3: Развести роутеры логина в `router.py`

- `get_auth_router(cookie_backend)` → prefix `/auth/cookie`
- `get_auth_router(bearer_backend)` → prefix `/auth/bearer`
- Удалить старый prefix `/auth/jwt` (или оставить как redirect/alias на время перехода).
- Register router остаётся без изменений: `/auth/register`.

Файл: `fastapi-application/auth_users/router.py` (edit, ~5 строк).

### Шаг 4: CSRF middleware (Double Submit Cookie)

**Паттерн** (рекомендован OWASP 2025, подтверждён tavily-поиском):

1. Middleware при каждом запросе проверяет наличие cookie `csrf_token`.
   - Если нет — генерирует `secrets.token_urlsafe(32)`, ставит cookie `csrf_token` (не httpOnly, SameSite=Lax, Secure=False в dev).
2. Для state-changing методов (POST, PUT, PATCH, DELETE) на маршрутах, где используется cookie-auth:
   - Читает заголовок `X-CSRF-Token`.
   - Сравнивает с значением cookie `csrf_token`.
   - Не совпадает или отсутствует → 403.
3. Исключения (не проверять CSRF):
   - `/auth/bearer/*` — клиентский транспорт.
   - `/docs`, `/openapi.json`, `/redoc` — Swagger UI.
   - `/assets/*` — статика Vite.
   - SPA catch-all `/{full_path:path}` — GET-запросы к HTML.
   - Маршруты, где аутентификация прошла через Bearer (нет cookie `auth`).

**Реализация:** Starlette middleware (класс `CSRFMiddleware(BaseHTTPMiddleware)` или чистый ASGI middleware).

Файл: новый `fastapi-application/core/csrf_middleware.py` (~40–60 строк).
Подключение: `main.py` → `app.add_middleware(CSRFMiddleware)`.

**Альтернатива: пакет `starlette-csrf`** — но для учебного проекта лучше показать ручную реализацию (понятнее для обучения).

### Шаг 5: Обновить фронтенд

- Изменить URL логина: `/auth/jwt/login` → `/auth/cookie/login`.
- Добавить чтение cookie `csrf_token` и отправку заголовка `X-CSRF-Token` в каждом fetch.
- Функция-обёртка в `frontend/src/api/client.ts`:
  ```ts
  function getCsrfToken(): string | null {
    return document.cookie.split('; ').find(r => r.startsWith('csrf_token='))?.split('=')[1] ?? null;
  }
  // В каждый fetch добавлять headers: { 'X-CSRF-Token': getCsrfToken() }
  ```

Файлы: `frontend/src/api/client.ts`, возможно компоненты логина.

### Шаг 6: Обновить счётчик маршрутов и документацию

- Было: 23 OpenAPI path-ключа.
- Добавятся: `/auth/bearer/login`, `/auth/bearer/logout` (+2).
- Старые `/auth/jwt/login`, `/auth/jwt/logout` уйдут (-2), если переименовываем.
- Net: 23 или 25 (зависит от того, оставляем ли `/auth/jwt/*` как alias).
- Обновить AGENTS.md, QWEN.md, docs/04_authorization.md, docs/07_auth_token_flow_code.md.

## 5. Клиентский flow (как передать токен)

```text
1. curl -X POST http://localhost:8000/auth/bearer/login \
     -H "Content-Type: application/json" \
     -d '{"email":"user@test.com","password":"12345678"}'

2. Ответ: {"access_token":"eyJ...","token_type":"bearer"}

3. Клиент сохраняет токен (переменная shell, файл, Keychain).

4. Каждый запрос:
   curl http://localhost:8000/users/me \
     -H "Authorization: Bearer eyJ..."

5. CSRF не проверяется (нет cookie auth → middleware пропускает).
```

## 6. Что НЕ меняется

- `JWTStrategy` — одна и та же для обоих транспортов, payload идентичен.
- `get_jwt_strategy()` — без изменений.
- Модели, схемы, CRUD, Alembic — не трогаются.
- `/auth/register` — остаётся один (регистрация общая).
- Защищённые роуты (`/users/me`, `/api/v1/auth/protected`) — Depends `active_user` работает как есть, fastapi-users сам попробует оба backend'а.
