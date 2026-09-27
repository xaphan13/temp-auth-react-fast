# Cookie, Bearer и API-ключи: где живут, как ездят, что выбрать

Документ отвечает на четыре конкретных вопроса, которые остаются после чтения
[`docs/08_jwt_transport_options.md`](08_jwt_transport_options.md). Написан так, чтобы
его можно было использовать **как шпаргалку к собеседованию** и как практический гайд.

Актуальность: сентябрь 2026. Источники — RFC 6265 (Cookie), RFC 6750 (Bearer),
OWASP Authentication Cheat Sheet, документация OpenAI / Anthropic / fastapi-users 15,
статьи wempe.dev (2026 revision), Okta, Tyk, Zuplo.

---

## Вопрос 1. Где передаются, где хранятся в браузере и где хранятся в клиенте

Главная ошибка — смешивать три разных решения. Это **три независимые оси**:

| # | Решение | Варианты | Пример |
|---|---------|----------|--------|
| A | **Где состояние?** | Сервер (сессия) vs Токен (stateless) | Session ID в Redis vs JWT |
| B | **Где credential на клиенте?** | Cookie vs localStorage vs память vs SecureStore | `document.cookie` vs React state |
| C | **Как credential едет по сети?** | Заголовок `Cookie` vs заголовок `Authorization` | Браузер сам vs `fetch(headers)` |

JWT — это формат токена (ось A). Cookie и Bearer — это транспорт (ось C).
localStorage — это хранилище (ось B). Их можно комбинировать почти свободно.

### 1.1. Cookie-транспорт

```text
Сервер ──Set-Cookie: auth=<JWT>; HttpOnly──> Браузер
Браузер сохраняет cookie в своём cookie-jar (недоступно JS при HttpOnly)
Браузер ──Cookie: auth=<JWT>──> Сервер (автоматически, каждый same-origin запрос)
```

**В браузере:**
- Хранится в cookie-jar браузера (отдельное защищённое хранилище, не localStorage).
- При флаге `HttpOnly` JavaScript **не может** прочитать значение через `document.cookie`.
- При флаге `Secure` отправляется только по HTTPS.
- `SameSite=Lax/Strict/None` управляет cross-site отправкой.
- Ограничение размера: ~4 KB на одну cookie.

**В не-браузерном клиенте (curl, Python requests, мобильное приложение):**
- Cookie-jar'а "из коробки" нет. Нужно вручную:
  - curl: `-c cookies.txt` (сохранить) и `-b cookies.txt` (отправить).
  - Python `httpx` / `requests`: объект `Session` или `Client` ведёт jar автоматически.
  - Мобильное приложение: нужно реализовать cookie-менеджер или использовать библиотеку.
- В этом проекте для таких клиентов предусмотрен `BearerTransport`: `POST /auth/bearer/login`
  возвращает JSON с токеном, а не-браузерный клиент явно передаёт его как
  `Authorization: Bearer <token>`. Cookie остаётся поддерживаемым вариантом, но обычно менее удобна.

**В нашем проекте** (`fastapi-application/auth_users/auth_backend.py`):
```python
cookie_transport = CookieTransport(
    cookie_name="auth",
    cookie_max_age=86400,       # 24 часа
    cookie_httponly=True,       # JS не читает
    cookie_secure=False,        # Локальная разработка по HTTP; в проде True
    cookie_samesite="lax",      # Защита от cross-site POST
)
```

Frontend (`frontend/src/api/client.ts`) просто включает отправку:
```ts
fetch(path, { credentials: 'include', ...init })
// Никакого ручного добавления токена — браузер делает сам
```

### 1.2. Bearer-транспорт (Authorization header)

```text
Сервер ──{"access_token": "<JWT>", "token_type": "bearer"}──> Клиент
Клиент сохраняет токен куда решит (память, localStorage, файл)
Клиент ──Authorization: Bearer <JWT>──> Сервер (вручную, каждый запрос)
```

**В браузере (SPA):**

| Место хранения | Переживает перезагрузку F5 | Читается любым JS | Безопасность при XSS |
|----------------|:-:|:-:|---|
| `localStorage` | да | **да** | **нулевая** — одна инъекция уносит токен |
| `sessionStorage` | до закрытия вкладки | **да** | нулевая |
| Память (React state, closure) | **нет** | нет (только пока страница открыта) | лучше: перезагрузка сбрасывает |
| `HttpOnly` cookie | да | нет | **лучший вариант для SPA** |

OWASP (2025-2026) прямо говорит: **не храните access/refresh tokens в localStorage**.
Любой скрипт, загруженный на страницу (сторонняя аналитика, CDN-библиотека, XSS-инъекция),
выполняет `localStorage.getItem('access_token')` и отправляет злоумышленнику.

Рекомендуемый паттерн для SPA:
- Access token — **в памяти** (переменная модуля, React state).
- Refresh token — в `HttpOnly` cookie (сервер ставит, JS не читает).
- При перезагрузке страницы: silent refresh через cookie → новый access в память.

**В не-браузерном клиенте:**

| Клиент | Где хранит | Как передаёт |
|--------|-----------|-------------|
| curl | В переменной shell `$TOKEN` | `-H "Authorization: Bearer $TOKEN"` |
| Python httpx | В переменной / `.env` | `headers={"Authorization": f"Bearer {token}"}` |
| Мобильное приложение | Keychain (iOS) / EncryptedSharedPreferences (Android) | SDK добавляет header |
| CLI-утилита | Файл `~/.config/myapp/token` с правами 600 | Читает файл, ставит header |

Это **родной сценарий** для Bearer — любой код умеет ставить HTTP-заголовок.

### 1.3. Сводная таблица вопроса 1

| | Cookie | Bearer |
|---|---|---|
| **Кто прикладывает к запросу** | Браузер автоматически | Клиент вручную |
| **Где живёт в браузере** | Cookie-jar (HttpOnly = невидимо JS) | Зависит от разработчика (память / localStorage) |
| **Где живёт в CLI / мобильном** | Ручной cookie-jar (неудобно) | Переменная / файл / Keychain (удобно) |
| **Размер** | ~4 KB ограничение | Практически без ограничений |
| **Отправка** | Только matching domain/path | Любой URL, любой origin |

---

## Вопрос 2. Можно ли Bearer в браузере? Можно ли cookie в клиенте?

Короткий ответ: **оба варианта возможны, но один из них мучительный**.

### 2.1. Bearer в браузере — да, но осторожно

Технически: `fetch('/api/data', { headers: { Authorization: 'Bearer ${token}' } })`
работает в любом браузере. Проблемы не в совместимости, а в **безопасности хранения**.

Если положить токен в `localStorage` — любая XSS-уязвимость (а они есть почти везде)
означает утечку токена. Если держать в памяти — пользователь жмёт F5, токен пропадает,
нужен повторный вход или refresh-механизм.

**Паттерн "лучшее из двух миров" для SPA + API:**

```text
1. POST /login → сервер возвращает:
   - access_token в теле JSON (короткоживущий, 5-15 минут)
   - refresh_token в HttpOnly cookie (долгоживущий, 7-30 дней)

2. SPA кладёт access_token в память (НЕ localStorage)

3. Каждый fetch:
   headers: { Authorization: `Bearer ${accessToken}` }

4. Получили 401 → silent POST /refresh (cookie прикладывается сама) →
   новый access_token в память

5. F5 → access_token потерян → при первой загрузке вызываем /refresh →
   получаем новый access_token без ввода пароля
```

Это именно то, что делают современные SPA в production.

### 2.2. Cookie в не-браузерном клиенте — да, но неудобно

curl умеет cookie-jar:
```bash
curl -c jar.txt -X POST https://api/login --data 'user=x&pass=y'
curl -b jar.txt https://api/orders   # cookie из jar.txt приложена
```

Python `httpx.Client()` ведёт cookie автоматически между запросами.

Но проблемы:
1. **Нет встроенного механизма** в большинстве мобильных SDK — приходится писать свой.
2. **CSRF** — state-changing запрос с auth-cookie требует Signed Double Submit Cookie:
   совпадающие cookie/header `csrf_token` и `X-CSRF-Token`. Чистый Bearer-запрос без
   auth-cookie CSRF не требует.
3. **Смешанный credential** — наличие `Authorization: Bearer` не отменяет CSRF-проверку,
   если тот же запрос содержит auth-cookie.
4. **SameSite** — если клиент не браузер, `SameSite` не имеет смысла, но сервер не знает,
   кто клиент.
5. **Сложнее отлаживать** — в логах мобильного приложения не видно cookie так же легко,
   как HTTP-заголовки.

Итог: cookie в не-браузерном клиенте работают, но **это нестандартный путь**.
Нормальная практика: браузер → cookie, всё остальное → Bearer.

### 2.3. Блок для собеседования

> **Вопрос:** "Можно ли использовать Bearer token в браузере?"
>
> **Ответ:** Да, технически `fetch` поддерживает любые заголовки. Проблема не в
> транспорте, а в хранении. Если токен лежит в `localStorage`, он уязвим к XSS.
> Рекомендуемый подход для SPA — короткий access token в памяти плюс refresh token
> в `HttpOnly` cookie. Это даёт защиту от XSS (токен нельзя украсть из cookie) и
> удобство (refresh работает автоматически).
>
> **Вопрос:** "А cookie в мобильном приложении?"
>
> **Ответ:** Работает, но неудобно. Мобильные SDK не имеют встроенного cookie-jar
> уровня браузера. Приходится управлять вручную, плюс появляется CSRF-риск, который
> для нативного приложения не типичен. Поэтому для мобильных клиентов используют
> Bearer + Keychain/EncryptedStorage.

---

## Вопрос 3. Что делать, если к одному API ходят и браузер, и клиент

Это самый частый реальный сценарий: SPA для пользователей + мобильное приложение +
CLI-скрипты для админов + server-to-server интеграции.

### 3.1. Решение: несколько authentication backend'ов

Сервер принимает **оба** транспорта на одних и тех же защищённых маршрутах.
fastapi-users 15 это поддерживает штатно:

```python
# auth_users/auth_backend.py
from fastapi_users.authentication import (
    AuthenticationBackend, CookieTransport, BearerTransport, JWTStrategy
)

# Backend 1: для браузера
cookie_transport = CookieTransport(cookie_name="auth", cookie_httponly=True)
cookie_backend = AuthenticationBackend(
    name="jwt-cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

# Backend 2: для мобильных / CLI / серверов
bearer_transport = BearerTransport(tokenUrl="/auth/bearer/login")
bearer_backend = AuthenticationBackend(
    name="jwt-bearer",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,  # тот же JWT, меняется только доставка
)

# Регистрация обоих
fastapi_users = FastAPIUsers[User, UUID](
    get_user_manager,
    [cookie_backend, bearer_backend],  # список!
)
```

Маршруты login/logout становятся разными путями:
```python
router.include_router(
    fastapi_users.get_auth_router(cookie_backend),
    prefix="/auth/cookie", tags=["auth-cookie"]
)
router.include_router(
    fastapi_users.get_auth_router(bearer_backend),
    prefix="/auth/bearer", tags=["auth-bearer"]
)
```

А **защищённые маршруты** (`current_user`, `active_user`) принимают оба credential'а
автоматически — `Authenticator._authenticate` перебирает backend'ы по порядку:

```python
@router.get("/orders")
async def get_orders(user: User = Depends(current_active_user)):
    # Работает и с cookie, и с Bearer — зависит от того, что прислал клиент
    ...
```

### 3.2. Архитектурная схема

```text
                    ┌────────────────────┐
                    │     API Server     │
                    │                    │
Browser ──cookie ──>│  /auth/cookie/*    │
  (SPA)             │  /auth/bearer/*    │<── Mobile App ──Bearer──
                    │                    │<── CLI/curl   ──Bearer──
                    │  current_user()    │<── Server     ──Bearer/API-key──
                    │  принимает оба     │
                    └────────────────────┘
```

### 3.3. Альтернатива: BFF-паттерн

Если SPA на другом домене и CORS с cookie становится болью:

```text
Browser ──cookie──> BFF (same origin) ──Bearer──> API
```

BFF (Backend For Frontend) — лёгкий прокси, который:
- Принимает cookie от браузера (same-origin, нет CORS-проблем).
- Делает запрос к основному API с Bearer-токеном.
- Возвращает результат браузеру.

Это устраняет необходимость в `SameSite=None`, `Allow-Credentials` и CSRF-токенах
для cross-origin cookie.

### 3.4. Чего НЕ делать

- **Не класть токен в URL** (`?token=xxx`) — попадёт в логи, историю, Referer.
- **Не использовать один endpoint `/login` с query-параметром `?transport=cookie`** —
  усложняет OpenAPI-документацию и Swagger UI.
- **Не мешать user-auth и service-auth в одном middleware** — сервисные ключи
  проверяются отдельно (см. вопрос 4).

### 3.5. Блок для собеседования

> **Вопрос:** "У нас веб-приложение и мобильное приложение, оба ходят к одному API.
> Как авторизовать?"
>
> **Ответ:** Два authentication backend'а на сервере: cookie для веба, Bearer для
> мобильных. Оба используют один и тот же JWT (одна стратегия подписи), отличаются
> только способом доставки. Защищённые маршруты принимают оба типа credential.
> Альтернативно — BFF-паттерн, если SPA на другом домене.

---

## Вопрос 4. Как работают API-ключи (OpenAI, Anthropic и т.д.)

API-ключ — это **не JWT и не OAuth-токен**. Это совершенно другой механизм,
предназначенный для других сценариев.

### 4.1. Что такое API-ключ

API-ключ — длинная случайная строка (обычно 32-128 символов), которая:
- Идентифицирует **аккаунт / проект / приложение** (не пользователя!).
- Выдаётся через dashboard провайдера (не через login/password flow).
- Живёт долго (месяцы, годы) — пока не отзовут вручную.
- Проверяется сервером простым поиском в БД / кэше (не криптографической подписью).

Примеры форматов:
```text
OpenAI:     sk-proj-abc123def456...
Anthropic:  sk-ant-api03-xyz789...
Stripe:     sk_live_51ABC...
```

### 4.2. Как передаётся

Провайдеры используют разные заголовки:

```bash
# OpenAI — стандартный Bearer (API key как значение Bearer token)
curl https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o","messages":[...]}'

# Anthropic — кастомный заголовок x-api-key
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-sonnet-4-20250514","messages":[...]}'
```

Обратите внимание: OpenAI использует `Authorization: Bearer`, но значение — **не JWT**,
а статический API-ключ. Это иллюстрация того, что "Bearer" описывает **способ доставки**
(заголовок `Authorization: Bearer <что-то>`), а не **тип credential**.

### 4.3. Жизненный цикл API-ключа

```text
1. Пользователь заходит в dashboard провайдера (console.anthropic.com, platform.openai.com)
2. Нажимает "Create API Key"
3. Провайдер генерирует случайную строку, показывает ЕДИНСТВЕННЫЙ РАЗ
4. Пользователь сохраняет ключ в .env / vault / secret manager
5. Приложение читает ключ из переменной окружения
6. Каждый запрос: ключ в заголовке → сервер ищет его в БД → находит account → проверяет
   лимиты, scope, IP-whitelist → обрабатывает запрос
7. Если ключ скомпрометирован → пользователь идёт в dashboard → Revoke → ключ удаляется
   из БД → все запросы с ним отклоняются
```

### 4.4. API-ключ vs JWT vs OAuth — принципиальные отличия

| | API-ключ | JWT (access token) | OAuth token |
|---|---|---|---|
| **Кого идентифицирует** | Аккаунт / проект | Пользователя | Делегированный доступ клиента |
| **Как выдаётся** | Dashboard, вручную | После login (password/OAuth) | Через OAuth flow |
| **Срок жизни** | Месяцы-годы (пока не отзовут) | Минуты-часы (`exp` в payload) | Часы (access) + дни (refresh) |
| **Проверка** | Поиск в БД / кэше | Криптографическая подпись | Интроспекция или подпись |
| **Содержит claims?** | Нет (просто opaque строка) | Да (sub, aud, scope, exp) | Зависит от реализации |
| **Можно отозвать?** | Да, мгновенно (удалить из БД) | Сложно (нужен blacklist/introspection) | Да (revoke refresh token) |
| **Типичный клиент** | Сервер, скрипт, CI/CD | SPA, мобильное приложение | Third-party приложение |
| **Где хранить** | `.env`, Vault, Secret Manager | Память, HttpOnly cookie | Память + refresh в HttpOnly |

### 4.5. Безопасность API-ключей (best practices 2026)

1. **Никогда не хардкодить в коде.** Только переменные окружения или secret manager.
   ```python
   # ПЛОХО
   client = OpenAI(api_key="sk-proj-abc123...")

   # ХОРОШО
   client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
   ```

2. **Никогда не отправлять из браузера.** API-ключ в frontend-коде = публичный ключ.
   Если SPA нужно обращаться к AI API — делайте прокси через свой backend:
   ```text
   Browser ──fetch──> Your Backend (/api/ai-chat) ──API key──> OpenAI
                       ↑ ключ в .env на сервере
   ```

3. **IP-whitelist.** OpenAI, Anthropic, Google Cloud позволяют ограничить IP-адреса,
   с которых принимается ключ.

4. **Usage limits.** Установите максимальный месячный расход (OpenAI позволяет это
   в dashboard), чтобы утечка ключа не привела к счету на $10,000.

5. **Ротация.** Регулярно создавайте новые ключи и удаляйте старые.

6. **Разные ключи для разных сред.** Dev / staging / prod — отдельные ключи с
   разными лимитами.

7. **Мониторинг.** GitGuardian, TruffleHog сканируют репозитории на утечки ключей.
   GitHub Secret Scanning автоматически обнаруживает ключи OpenAI/Anthropic.

### 4.6. История с Anthropic (февраль 2026) — важный кейс

В феврале 2026 Anthropic обновила ToS: OAuth-токены от подписки (Claude Max)
**разрешено использовать только в claude.ai и Claude Code**. Использование этих
токенов в сторонних инструментах — нарушение ToS. Для любых интеграций нужно
генерировать API-ключ через console.anthropic.com.

Это иллюстрирует разницу:
- **OAuth-токен подписки** — для интерактивного использования человеком.
- **API-ключ** — для программной интеграции.
- Смешивать их — нарушение условий провайдера.

### 4.7. Когда использовать API-ключ, а когда OAuth/JWT

| Сценарий | Выбор | Почему |
|----------|-------|--------|
| Ваш backend вызывает AI API | API-ключ | Нет пользователя, server-to-server |
| Пользователь входит в ваше SPA | JWT в cookie или OAuth | Нужна сессия, logout, отзыв |
| Стороннее приложение хочет доступ к вашему API | OAuth 2.0 | Делегирование, scope, consent |
| CI/CD pipeline деплоит через ваш API | API-ключ или Service Account | Нет интерактивного пользователя |
| Мобильное приложение вашего сервиса | OAuth PKCE + Bearer | Пользователь логинится, нужны короткие токены |
| IoT-устройство шлёт данные | API-ключ или mTLS | Долгоживущий credential, нет браузера |

### 4.8. Блок для собеседования

> **Вопрос:** "Чем API-ключ отличается от токена?"
>
> **Ответ:** API-ключ — это статический opaque-идентификатор аккаунта или проекта.
> Он живёт долго, проверяется поиском в базе, не содержит claims о пользователе.
> Токен (JWT, OAuth access token) — короткоживущий credential, выданный после
> аутентификации конкретного пользователя, содержащий claims (sub, scope, exp) и
> проверяемый криптографически. API-ключ подходит для server-to-server и интеграций,
> токен — для пользовательских сессий.
>
> **Вопрос:** "Почему нельзя отправить API-ключ из браузера напрямую к OpenAI?"
>
> **Ответ:** Потому что API-ключ окажется в клиентском коде, который виден любому
> пользователю. Кто угодно скопирует ключ и потратит вашу квоту. Правильная
> архитектура: браузер обращается к вашему backend, ваш backend (где ключ хранится
> в переменной окружения) обращается к OpenAI и возвращает результат браузеру.

---

## Шпаргалка для собеседования: 17 тезисов

1. **Аутентификация** = "кто ты?", **авторизация** = "что тебе можно?".
2. **JWT** — формат токена, не протокол входа.
3. **Cookie** и **Bearer** — способы доставки credential, не стратегии.
4. **localStorage** — плохое место для токенов: читается любым JS, уязвим к XSS.
5. **HttpOnly cookie** — лучшее хранилище в браузере: JS не читает, кража затруднена.
6. **Bearer** — лучший транспорт для не-браузерных клиентов: curl, мобильные, CLI.
7. **CSRF** — state-changing запрос с auth-cookie требует `X-CSRF-Token`, равный подписанной cookie `csrf_token`; чистый Bearer без auth-cookie CSRF не требует.
8. **XSS** — проблема localStorage. HttpOnly cookie защищает от кражи, но не от
   session riding (скрипт может делать запросы, пока страница открыта).
9. **CORS** — политика браузера, не защита API. curl её игнорирует.
10. **API-ключ** — для server-to-server, не для пользовательских сессий.
11. **OAuth** — делегирование доступа, не аутентификация. Для identity нужен OIDC.
12. **Logout ≠ revoke** для JWT. Без серверного blacklist JWT живёт до `exp`.
13. **Refresh token** опаснее access token: живёт дольше, даёт новые access.
    Хранить в HttpOnly cookie, ротировать при каждом использовании.
14. **Несколько клиентов** = несколько backend'ов (cookie для веба, Bearer для остальных).
15. **Нельзя передавать credential в URL** — логи, история, Referer.
16. **API-ключ никогда не хардкодится** — только `.env` / vault / secret manager.
17. **BFF-паттерн** решает проблему cross-origin cookie для SPA.

---

## Источники

- RFC 6265 (HTTP State Management Mechanism — Cookie)
- RFC 6750 (The OAuth 2.0 Authorization Framework: Bearer Token Usage)
- RFC 9700 (OAuth 2.0 Security Best Current Practice, 2025)
- OWASP Authentication Cheat Sheet (2025)
- wempe.dev, "Web Authentication: Three Decisions You're Conflating" (rev. Jan 2026)
- Okta Developer Blog, "Cookies vs Tokens" (2022, updated)
- Tyk Learning Center, "API Keys vs Tokens" (2025)
- Zuplo, "Top 7 API Authentication Methods Compared" (Jan 2025, updated 2026)
- OpenAI API Reference, "Authentication" (2026)
- Anthropic Platform Docs, "API Overview" (2026)
- Anthropic ToS update on OAuth token usage (Feb 2026)
- fastapi-users 15.0.5 source code (`site-packages/fastapi_users/`)
- Проект: `docs/08_jwt_transport_options.md`, `auth_users/auth_backend.py`
