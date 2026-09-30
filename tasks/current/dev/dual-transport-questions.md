# Вопросы и решения: dual-transport auth + CSRF

Документ для обсуждения ДО запуска spec-writer. Не спека, не план фаз — только
вопросы, варианты ответов и принятые решения.

Дата создания: 2026-09-26

---

## Контекст (что уже известно)

- fastapi-users 15 **штатно** поддерживает список бэкендов: `FastAPIUsers(get_user_manager, [backend1, backend2])`.
- `current_user()` / `active_user()` автоматически перебирают backend'ы по порядку: первый валидный побеждает. Кастомный composite-Depends **не нужен**.
- Встроенный `BearerTransport(tokenUrl="...")` при login отдаёт `{"access_token": "...", "token_type": "bearer"}` в JSON-теле — это ровно то, что нужно клиенту. Кастомный BearerTransport **не нужен**.
- Документация проекта (`docs/09_auth_transports_and_api_keys.md`, раздел 3.1) уже описывает эту архитектуру с примерами кода.
- Текущий код: один `auth_backend` в `auth_users/auth_backend.py`, подключён через `/auth/jwt/*` в `auth_users/router.py`, экземпляр `fastapi_users` в `auth_users/fastapi_users_obj.py`.

---

## Вопрос 1: Именование путей login/logout

### Варианты

| # | Browser | Client (Bearer) | Плюсы | Минусы |
|---|---------|-----------------|-------|--------|
| A | `/auth/cookie/login` | `/auth/bearer/login` | Совпадает с docs/09, явно указывает на транспорт | Длиннее текущего |
| B | `/auth/browser/login` | `/auth/client/login` | Говорящие имена по типу потребителя | Менее технично |
| C | Оставить `/auth/jwt/login` для cookie, добавить `/auth/bearer/login` | Минимум изменений | Асимметрия имён |

### Решение
**Принято: вариант A** — `/auth/cookie/login` и `/auth/bearer/login`. Совпадает с существующей документацией, технически точно, prefix'ы router'ов задаются при `include_router`.

---

## Вопрос 2: Регистрация — общая или раздельная?

### Суть
Сейчас `register_router = fastapi_users.get_register_router(UserRead, UserCreate)` подключается один раз с prefix `/auth`. При двух backend'ах registration endpoint не привязан к транспорту — он создаёт пользователя в БД и не выдаёт токен.

### Варианты

| # | Подход | Описание |
|---|--------|----------|
| A | Один `/auth/register` | Регистрация не зависит от транспорта. После register клиент сам вызывает свой login. |
| B | Два пути `/auth/cookie/register` и `/auth/bearer/register` | Избыточно — регистрация одна и та же. |

### Решение
**Принято: вариант A** — один `/auth/register`, без дублирования. Это штатное поведение fastapi-users: `get_register_router` не привязан к backend.

---

## Вопрос 3: CSRF-защита — какой паттерн?

### Варианты

| # | Паттерн | Как работает | Плюсы | Минусы |
|---|---------|-------------|-------|--------|
| A | Double Submit Cookie (рекомендация OWASP 2025-2026 для SPA) | Сервер ставит cookie `csrf_token=<random>` (не httpOnly). JS читает cookie, шлёт заголовок `X-CSRF-Token`. Middleware сверяет. | Stateless, не нужна сессия на сервере, прост для SPA | Атакующий может установить свою cookie если контролирует поддомен |
| B | Signed Double Submit Cookie (OWASP RECOMMENDED) | То же, но токен подписан серверным ключом и привязан к session/auth cookie | Защита от cookie injection | Нужен секретный ключ для подписи |
| C | Custom Header Only | Клиент всегда шлёт `X-Requested-With: XMLHttpRequest` или произвольный заголовок. Браузер не позволяет cross-origin запросам ставить кастомные заголовки без CORS preflight. | Простейшая реализация | Не работает если CORS настроен слишком широко |

### Решение
**Принято: вариант B** — Signed Double Submit Cookie. Привязка к auth-cookie через HMAC/signature. Для учебного проекта достаточно простой подписи через `settings.web.secret_key`.

### Подвопрос 3.1: Где жить CSRF-middleware?

| # | Вариант | Описание |
|---|---------|----------|
| A | Starlette middleware (`app.add_middleware`) | Глобальный, с whitelist исключений (`/auth/bearer/*`, `/docs`, `/openapi.json`, `/assets/*`, SPA catch-all) |
| B | Dependency на cookie-роутах | Точечный, но каждый роут должен знать про CSRF |
| C | Отдельный модуль `auth_users/csrf.py`, подключаемый как middleware | Изолированный, легко тестировать |

**Принято: вариант C** — отдельный модуль, подключается как middleware в `main.py` после API-роутов но до SPA catch-all. Исключения по path-prefix конфигурируются.

### Подвопрос 3.2: Когда генерировать CSRF-токен?

| # | Момент | Описание |
|---|--------|----------|
| A | При login | Токен живёт столько же, сколько auth-cookie |
| B | При каждом запросе (ротация) | Максимальная безопасность, но сложнее |
| C | Один раз при первом обращении (GET /) | Простой, но токен долгоживущий |

**Принято: вариант A** — CSRF-токен генерируется и ставится при успешном `/auth/cookie/login`, очищается при `/auth/cookie/logout`. Время жизни совпадает с auth-cookie.

---

## Вопрос 4: Передача Bearer-токена клиенту при login

### Суть
Клиент (CLI, мобильное приложение, скрипт) вызывает `POST /auth/bearer/login` с email/password. Что приходит в ответе?

### Факт
Встроенный `BearerTransport` из fastapi-users уже возвращает:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```
Это стандарт OAuth2 Token Response (RFC 6749 section 5.1). Ничего кастомного делать не нужно.

### Подвопрос 4.1: Как клиент хранит токен?

Это зона ответственности клиента, не сервера. Но для документации:

| Клиент | Хранение | Передача |
|--------|----------|----------|
| curl | Shell-переменная `$TOKEN` | `-H "Authorization: Bearer $TOKEN"` |
| Python httpx/requests | Переменная / `.env` | `headers={"Authorization": f"Bearer {token}"}` |
| CLI-утилита | Файл `~/.config/app/token` (chmod 600) | Читает файл, ставит header |
| Мобильное приложение | Keychain / EncryptedSharedPreferences | SDK добавляет header |

**Решение:** сервер просто отдаёт JSON. Документация проекта опишет примеры для curl и httpx.

---

## Вопрос 5: Порядок перебора backend'ов в current_user()

### Суть
`Authenticator._authenticate` пробует backend'ы по порядку. Какой первым?

### Варианты

| # | Порядок | Обоснование |
|---|---------|-------------|
| A | Cookie → Bearer | Большинство запросов из браузера; cookie проверяется быстрее (нет парсинга заголовка Authorization) |
| B | Bearer → Cookie | Bearer stateless, нет CSRF-проверки; чуть дешевле |

### Решение
**Принято: вариант A** — cookie первым. В учебном проекте основной потребитель — браузер React SPA. Разница в производительности несущественна.

---

## Вопрос 6: OpenAPI security schemes

### Суть
При двух backend'ах Swagger UI должен показывать оба варианта авторизации: cookie и Bearer. fastapi-users генерирует security schemes автоматически для каждого transport.

### Проверено
Поиск подтвердил: "Full OpenAPI schema support, even with several authentication backends" — fastapi-users регистрирует обе схемы. Swagger UI покажет кнопку Authorize с выбором.

**Решение:** ручная настройка `security_schemes` не нужна. Проверить после реализации: `curl localhost:8000/openapi.json | python -m json.tool` должен содержать обе схемы.

---

## Вопрос 7: Logout для Bearer-транспорта

### Суть
JWT stateless — сервер не может "отозвать" токен. Что делает `/auth/bearer/logout`?

### Варианты

| # | Подход | Описание |
|---|--------|----------|
| A | Пустой 204 No Content | Клиент забывает токен сам. Сервер ничего не делает. |
| B | Blacklist в БД | Тяжело, не для учебного проекта |
| C | Короткий TTL (5-15 мин) | Токен быстро протухает сам |

### Решение
**Принято: вариант A** — `BearerTransport` штатно возвращает пустой ответ при logout. Документировать, что клиент обязан безопасно хранить токен и удалять его при logout на своей стороне.

---

## Вопрос 8: Обновление фронтенда (React SPA)

### Суть
Текущий frontend обращается к `/auth/jwt/login`. После переименования в `/auth/cookie/login` — сломается.

### Варианты

| # | Подход | Описание |
|---|--------|----------|
| A | Обновить `frontend/src/api/client.ts` в том же задании | Единый PR, но увеличивает scope |
| B | Оставить `/auth/jwt/*` как alias (deprecated) | Обратная совместимость, но мусор в роутах |
| C | Обновить фронтенд отдельным заданием после | Чище, но временно сломано |

### Решение
**Принято: вариант A** — обновить фронтенд в рамках того же задания. Файлы: `frontend/src/api/client.ts` и любые компоненты, где захардкожен путь `/auth/jwt/login`. Scope небольшой (поиск по `auth/jwt` в frontend/).

---

## Вопрос 9: Влияние на счётчик маршрутов

### Текущее состояние
23 path-ключа OpenAPI.

### Ожидаемые изменения

| Действие | Пути | Delta |
|----------|------|-------|
| Переименование `/auth/jwt/login` → `/auth/cookie/login` | 0 (замена) | 0 |
| Добавление `/auth/bearer/login`, `/auth/bearer/logout` | +2 | +2 |
| **Итого** | | **25** |

**Решение:** обновить эталон в AGENTS.md и QWEN.md с 23 на 25 после реализации.

---

## Вопрос 10: CSRF для GET-запросов?

### Суть
CSRF имеет смысл только для state-changing методов (POST, PUT, DELETE, PATCH). GET-запросы не должны менять состояние.

### Решение
**Принято:** CSRF-middleware проверяет только POST/PUT/PATCH/DELETE. GET-запросы пропускаются без проверки. Это стандартная практика (OWASP).

---

## Итоговая таблица решений

| # | Вопрос | Решение | Статус |
|---|--------|---------|--------|
| 1 | Именование путей | `/auth/cookie/*` + `/auth/bearer/*` | Принято |
| 2 | Регистрация | Одна `/auth/register` | Принято |
| 3 | CSRF-паттерн | Signed Double Submit Cookie | Принято |
| 3.1 | Где CSRF-middleware | Отдельный модуль `auth_users/csrf.py` | Принято |
| 3.2 | Когда CSRF-токен | При `/auth/cookie/login` | Принято |
| 4 | Bearer-ответ клиенту | Штатный `BearerTransport` (JSON body) | Принято |
| 5 | Порядок backend'ов | Cookie → Bearer | Принято |
| 6 | OpenAPI schemes | Автоматически от fastapi-users | Принято |
| 7 | Bearer logout | Пустой 204, клиент забывает сам | Принято |
| 8 | Фронтенд | Обновить в том же задании | Принято |
| 9 | Счётчик маршрутов | 23 → 25 | Принято |
| 10 | CSRF для GET | Не проверять | Принято |

---

## Файлы, которые будут затронуты (предварительно)

| Файл | Изменение |
|------|-----------|
| `auth_users/auth_backend.py` | Добавить `bearer_transport`, `bearer_backend`; изменить имя cookie-backend на `cookie_backend` |
| `auth_users/fastapi_users_obj.py` | Передать `[cookie_backend, bearer_backend]` вместо `[auth_backend]` |
| `auth_users/router.py` | Два `include_router` для auth_router с разными prefix'ами |
| `auth_users/csrf.py` | **Новый файл** — CSRF middleware |
| `main.py` | Подключить CSRF-middleware |
| `core/config.py` | Возможно: настройки CSRF (имя cookie, secret) |
| `frontend/src/api/client.ts` | Обновить URL логина |
| `AGENTS.md`, `QWEN.md` | Счётчик 23 → 25 |
| `docs/09_auth_transports_and_api_keys.md` | Актуализировать примеры под реальные пути |

</content>