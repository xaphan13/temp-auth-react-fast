# Пособие по авторизации: Cookie/Bearer и JWT/Database/Redis

Это отдельное учебное пособие только о двух независимых решениях:

1. **транспорт** — как credential передаётся между клиентом и сервером:
   `CookieTransport` или `BearerTransport`;
2. **стратегия** — где находится состояние credential и как сервер его проверяет:
   `JWTStrategy`, `DatabaseStrategy` или `RedisStrategy`.

Примеры написаны для `fastapi-users 15.0.5`, который используется в этом проекте.
Реальные фрагменты отмечены как **текущий код проекта**. Остальные примеры —
**варианты развития**: они показывают архитектуру и требуют подключения таблицы,
миграции, Redis или дополнительного backend.

---

## 1. Самый короткий ответ на собеседовании

> Cookie и Bearer — это не две стратегии, а два транспорта. Cookie кладёт credential
> в `Set-Cookie`, после чего браузер автоматически отправляет его в `Cookie`. Bearer
> возвращает credential в JSON, а клиент сам добавляет `Authorization: Bearer ...`.
>
> Cookie удобнее и безопаснее для браузерной сессии с `HttpOnly`, потому что JavaScript
> не может прочитать токен. Но автоматическая отправка cookie создаёт CSRF-риск.
> Bearer удобнее для мобильного приложения, CLI и внешнего API-клиента: CSRF от cookie
> нет, но клиент сам отвечает за хранение токена, и XSS/утечки storage становятся его
> проблемой.
>
> JWTStrategy — stateless: JWT проверяется подписью, отдельное хранилище токенов не
> нужно, но уже выданный токен нельзя мгновенно отозвать. DatabaseStrategy хранит
> случайный токен в БД: каждый запрос проверяется через БД, зато logout и revoke
> настоящие. RedisStrategy делает то же в Redis: быстрый `GET`/`DEL` и TTL, но появляется
> обязательная зависимость от Redis.
>
> Для браузера по умолчанию я выбираю `CookieTransport`; для mobile/CLI/API-клиента —
> `BearerTransport`. Стратегию выбираю отдельно: JWT — если важны stateless и простое
> масштабирование, Database/Redis — если нужен мгновенный отзыв и управление сессиями.

Это хороший ответ, потому что он сразу разделяет **как токен едет** и **как он проверяется**.

---

## 2. Не путать транспорт и стратегию

Представим пропуск в здание:

- **транспорт** — кто несёт пропуск: курьер в конверте или предъявляет его вручную;
- **стратегия** — что записано в пропуске и где охрана проверяет его действительность.

В `fastapi-users` это выражено объектом `AuthenticationBackend`:

```python
AuthenticationBackend(
    name="backend-name",
    transport=transport,
    get_strategy=get_strategy,
)
```

Логика login концептуально выглядит так:

```python
async def login(user):
    token = await strategy.write_token(user)
    return await transport.get_login_response(token)
```

Логика защищённого запроса:

```python
async def authenticate(request):
    token = await transport.scheme(request)
    user = await strategy.read_token(token, user_manager)
    return user
```

Поэтому можно составить матрицу:

| | `CookieTransport` | `BearerTransport` |
|---|---|---|
| `JWTStrategy` | текущий проект | вариант для мобильного/API-клиента |
| `DatabaseStrategy` | серверная сессия в cookie с настоящим revoke | токен в JSON + stateful API-сессия |
| `RedisStrategy` | cookie-сессия с быстрым TTL/revoke | API-клиент с Redis-backed токеном |

**Смена транспорта не превращает JWT в DatabaseStrategy.**
**Смена стратегии не превращает cookie в Bearer.** Это независимые настройки.

---

## 3. Что сейчас реально реализовано в проекте

### 3.1. Backend

Файл `fastapi-application/auth_users/auth_backend.py` собирает ровно такую пару:

```python
from core.config import settings
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy import JWTStrategy

cookie_transport = CookieTransport(
    cookie_name=settings.auth_users.cookie_name,
    cookie_max_age=settings.auth_users.cookie_max_age,
    cookie_secure=settings.auth_users.cookie_secure,
    cookie_httponly=settings.auth_users.cookie_httponly,
    cookie_samesite=settings.auth_users.cookie_samesite,
)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.web.secret_key,
        lifetime_seconds=settings.auth_users.jwt_lifetime_seconds,
        algorithm=settings.auth_users.jwt_algorithm,
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)
```

Итог:

```text
CookieTransport + JWTStrategy
```

### 3.2. Маршруты

В `fastapi-application/auth_users/router.py` backend подключается под префиксом:

```python
router.include_router(auth_router, prefix="/auth/jwt", tags=["auth-jwt"])
```

Отсюда реальные endpoints:

```text
POST /auth/jwt/login
POST /auth/jwt/logout
```

`name="jwt"` — имя backend внутри `fastapi-users`; оно само по себе не добавляет
`/jwt` в URL. URL задаёт `prefix` в `include_router`.

### 3.3. Frontend

В текущем `frontend/src/api/client.ts` запросы используют:

```typescript
async function request(path: string, init: RequestInit = {}): Promise<Response> {
    return fetch(path, { credentials: 'include', ...init });
}
```

Frontend не читает JWT и не добавляет `Authorization`. Браузер принимает `Set-Cookie`
после login и сам отправляет cookie дальше.

---

## 4. CookieTransport: как работает и почему это удобно в браузере

### 4.1. Поток login

```text
1. Browser → POST /auth/jwt/login
2. Server проверяет login/password
3. Strategy создаёт token
4. CookieTransport отвечает Set-Cookie
5. Browser сохраняет cookie
6. Browser автоматически добавляет Cookie к /users/me
```

Пример HTTP:

```http
POST /auth/jwt/login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=correct-password
```

Для текущей пары `CookieTransport + JWTStrategy` ответ содержит примерно:

```http
HTTP/1.1 204 No Content
Set-Cookie: auth=<JWT>; Max-Age=86400; HttpOnly; SameSite=Lax; Path=/
```

Следующий запрос:

```http
GET /users/me
Cookie: auth=<JWT>
```

### 4.2. Флаги cookie

- `HttpOnly` — JavaScript не прочитает значение через `document.cookie`;
- `Secure` — браузер отправит cookie только по HTTPS; в production должен быть `True`;
- `SameSite=Lax` — ограничивает cross-site отправку и снижает CSRF-риск;
- `Max-Age` — время жизни cookie в браузере;
- `Path=/` — область действия cookie.

`HttpOnly` защищает от **кражи значения** cookie через XSS, но не от выполнения
действия от имени пользователя: вредоносный скрипт всё ещё может вызвать `fetch`.
Поэтому XSS всё равно нужно устранять.

### 4.3. Плюсы

- браузер сам управляет отправкой credential;
- токен не нужно хранить в `localStorage`;
- `HttpOnly` ограничивает кражу credential JavaScript-кодом;
- frontend-клиент получается простым;
- logout cookie-транспорта удаляет cookie.

### 4.4. Минусы

- cookie отправляется автоматически, поэтому возникает CSRF-риск;
- cross-origin frontend требует CORS с credentials;
- для `SameSite=None` нужен `Secure`, а CSRF-защиту нужно продумать отдельно;
- CLI и мобильному приложению неудобно вручную поддерживать cookie jar;
- если стратегия JWT, удаление cookie не отзывает уже скопированный JWT.

### 4.5. Когда выбирать

`CookieTransport` — естественный выбор для:

- SSR-приложения;
- браузерного приложения и API на одном origin;
- BFF, когда браузер общается только с backend-for-frontend;
- web-сессии, которую не должен читать JavaScript.

---

## 5. BearerTransport: как работает и почему удобнее для клиента

### 5.1. Поток login

`BearerTransport` возвращает token в JSON:

```http
POST /auth/bearer/login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=correct-password
```

Ответ:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "access_token": "<TOKEN>",
  "token_type": "bearer"
}
```

Дальше клиент сам прикладывает token:

```http
GET /users/me
Authorization: Bearer <TOKEN>
```

### 5.2. Backend: Bearer + JWTStrategy

Это **вариант развития**, в текущем проекте второй backend не подключён:

```python
from fastapi_users.authentication import AuthenticationBackend, BearerTransport
from fastapi_users.authentication.strategy import JWTStrategy

bearer_transport = BearerTransport(
    tokenUrl="auth/bearer/login",
)


def get_bearer_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.web.secret_key,
        lifetime_seconds=900,
        algorithm="HS256",
    )


bearer_backend = AuthenticationBackend(
    name="bearer-jwt",
    transport=bearer_transport,
    get_strategy=get_bearer_jwt_strategy,
)
```

`tokenUrl` — подсказка для OpenAPI/Swagger UI. Сам путь задаётся там, где auth-router
подключается:

```python
bearer_auth_router = fastapi_users.get_auth_router(bearer_backend)
router.include_router(
    bearer_auth_router,
    prefix="/auth/bearer",
    tags=["auth-bearer"],
)
```

Если bearer backend добавляется в список `FastAPIUsers`, защищённые dependencies
могут принимать backend'ы согласно конфигурации authenticator:

```python
fastapi_users = FastAPIUsers[User, UUID](
    get_user_manager,
    [auth_backend, bearer_backend],
)
```

В реальном проекте это потребует согласованной правки `auth_users` и проверки
OpenAPI-маршрутов; пример здесь показывает принцип, а не утверждает, что код уже
подключён.

### 5.3. Frontend/API-клиент для Bearer

Минимальный TypeScript-клиент:

```typescript
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
    accessToken = token;
}

export async function requestWithBearer(
    path: string,
    init: RequestInit = {},
): Promise<Response> {
    const headers = new Headers(init.headers);
    if (accessToken !== null) {
        headers.set('Authorization', `Bearer ${accessToken}`);
    }

    return fetch(path, { ...init, headers });
}

export async function loginWithBearer(
    email: string,
    password: string,
): Promise<void> {
    const response = await fetch('/auth/bearer/login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
            username: email,
            password,
        }),
    });

    if (!response.ok) {
        throw new Error(`Login failed: HTTP ${response.status}`);
    }

    const data = (await response.json()) as {
        access_token: string;
        token_type: string;
    };
    setAccessToken(data.access_token);
}
```

В учебном примере token хранится в памяти. Это лучше, чем `localStorage`, с точки
зрения долгого хранения, но после перезагрузки страницы token исчезает. Production-
решение обычно строит короткий access token и отдельный refresh flow; где хранить
refresh token — отдельное security-решение.

Для мобильного приложения token помещают в системное защищённое хранилище:
Keychain на iOS, Keystore/Secure Storage на Android. Для CLI — в системный keychain
или файл с ограниченными правами, а не в исходный код.

### 5.4. Logout Bearer

Bearer-транспорт не может «стереть» token из браузера серверным `Set-Cookie`, потому
что token хранится у клиента. Logout клиента:

```typescript
setAccessToken(null);
```

Это только удаление локальной копии. При `JWTStrategy` скопированный token продолжает
работать до истечения срока. Для настоящего revoke нужна DatabaseStrategy, RedisStrategy,
introspection/revocation store или короткий access token с защищённым refresh flow.

### 5.5. Когда выбирать

`BearerTransport` — естественный выбор для:

- мобильного приложения;
- desktop-клиента;
- CLI;
- Postman/curl и внешнего API-клиента;
- frontend и API на разных origin, если выбран token-based flow;
- service-to-service клиента.

Главное правило: не хранить bearer token в URL и не писать его в логи.

---

## 6. JWTStrategy: «подписал и проверил без token store»

### 6.1. Что лежит внутри

`JWTStrategy` создаёт подписанный JWT с данными вроде:

```json
{
  "sub": "user-id",
  "aud": ["fastapi-users:auth"],
  "exp": 1780000900
}
```

Схема работы:

```text
login:
  user → JWTStrategy.write_token(user) → signed JWT

request:
  signed JWT → verify signature + exp → user id (sub) → загрузить user
```

Сервер не обязан хранить каждый выданный JWT. Поэтому стратегия stateless.

### 6.2. Реальный код проекта

```python
def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.web.secret_key,
        lifetime_seconds=settings.auth_users.jwt_lifetime_seconds,
        algorithm=settings.auth_users.jwt_algorithm,
    )
```

Та же стратегия может быть передана и `CookieTransport`, и `BearerTransport`:

```python
cookie_jwt_backend = AuthenticationBackend(
    name="cookie-jwt",
    transport=CookieTransport(cookie_name="auth"),
    get_strategy=get_jwt_strategy,
)

bearer_jwt_backend = AuthenticationBackend(
    name="bearer-jwt",
    transport=BearerTransport(tokenUrl="auth/bearer/login"),
    get_strategy=get_jwt_strategy,
)
```

JWT одинакового типа, различается только конверт доставки.

### 6.3. Плюсы

- не нужен token store;
- проверка подписи быстрая и локальная;
- удобно горизонтально масштабировать несколько экземпляров API;
- любой сервис с доверенным публичным ключом может проверить JWT;
- нет запроса в Redis/таблицу для поиска самого token.

### 6.4. Минусы

- JWT нельзя мгновенно отозвать только силами подписи;
- logout при cookie удаляет cookie, но не инвалидирует JWT;
- украденный JWT работает до `exp`;
- изменение роли пользователя не обязательно отражается в уже выданном JWT;
- payload JWT читаем, если это не JWE: подпись не означает шифрование;
- компрометация секрета подписи компрометирует все токены, подписанные этим секретом.

### 6.5. Когда выбирать

Выбирайте `JWTStrategy`, когда:

- нужен stateless API;
- важны простое горизонтальное масштабирование и отсутствие token table;
- TTL можно сделать коротким;
- мгновенный revoke не является обязательным или реализован отдельным механизмом;
- токен может проверяться несколькими сервисами.

---

## 7. DatabaseStrategy: «случайный token и запись в БД»

### 7.1. Как работает

`DatabaseStrategy` не кодирует user ID в подписанный JWT. Она создаёт случайный
token и сохраняет запись примерно такого вида:

```text
access_token
------------
token       = random-url-safe-string
user_id     = 42
created_at  = now
```

Поток:

```text
login:
  user → random token → INSERT access_token

request:
  token → SELECT access_token WHERE token=?
        → проверить lifetime
        → user_id → загрузить пользователя

logout:
  token → DELETE access_token
```

Logout и revoke здесь настоящие: удалённая запись больше не подтверждает token.
Цена — обращение к БД при проверке каждого запроса и необходимость миграции.

### 7.2. Пример с SQLAlchemy

Ниже учебный пример для UUID-пользователя и SQLAlchemy-адаптера `fastapi-users`.
Имена импортов и базовые типы зависят от установленной версии адаптера:

```python
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy import DatabaseStrategy
from fastapi_users.authentication.strategy.db import AccessTokenDatabase
from fastapi_users_db_sqlalchemy.access_token import (
    SQLAlchemyAccessTokenDatabase,
    SQLAlchemyBaseAccessTokenTableUUID,
)

from db_core.db_async import CurrentSession
from db_core.model_base import Base


class AccessToken(SQLAlchemyBaseAccessTokenTableUUID, Base):
    __tablename__ = "access_token"


async def get_access_token_database(
    session: CurrentSession,
) -> AsyncGenerator[SQLAlchemyAccessTokenDatabase[AccessToken], None]:
    yield SQLAlchemyAccessTokenDatabase(session, AccessToken)


async def get_database_strategy(
    access_token_database: Annotated[
        AccessTokenDatabase[AccessToken], Depends(get_access_token_database)
    ],
) -> DatabaseStrategy:
    return DatabaseStrategy(
        database=access_token_database,
        lifetime_seconds=3600,
    )


database_backend = AuthenticationBackend(
    name="database-cookie",
    transport=CookieTransport(cookie_name="database_session"),
    get_strategy=get_database_strategy,
)
```

В реальном приложении `access_token_database` и `AsyncSession` подключаются через
FastAPI dependency injection. Перед использованием понадобятся:

1. модель access token в metadata;
2. импорт модели в registry проекта;
3. Alembic migration для `access_token`;
4. корректный `get_access_token_database` с текущей async-сессией;
5. передача database dependency в `get_strategy` по правилам версии библиотеки.

Главный смысл примера — не копировать его вслепую, а увидеть границу:
`DatabaseStrategy` получает объект `AccessTokenDatabase`, а не просто строку URL базы.

### 7.3. Cookie или Bearer с DatabaseStrategy

Транспорт меняется независимо:

```python
# Cookie + DatabaseStrategy: web-сессия с настоящим revoke.
database_cookie_backend = AuthenticationBackend(
    name="database-cookie",
    transport=CookieTransport(cookie_name="session"),
    get_strategy=get_database_strategy,
)

# Bearer + DatabaseStrategy: API/mobile token, который можно удалить на сервере.
database_bearer_backend = AuthenticationBackend(
    name="database-bearer",
    transport=BearerTransport(tokenUrl="auth/database-bearer/login"),
    get_strategy=get_database_strategy,
)
```

### 7.4. Плюсы и минусы

Плюсы:

- настоящий logout и мгновенный revoke;
- можно показать пользователю список устройств и удалить одну сессию;
- можно завершить все сессии пользователя;
- состояние сессии контролируется сервером.

Минусы:

- запрос к БД при проверке token;
- таблица, индексы, миграция и очистка протухших записей;
- дополнительная нагрузка и зависимость от доступности БД;
- при большом количестве запросов БД становится частью каждого auth-check.

---

## 8. RedisStrategy: «token в Redis с быстрым TTL»

### 8.1. Как работает

`RedisStrategy` использует случайный token и хранит связь token → user ID в Redis:

```text
SET fastapi_users_token:<token> <user_id> EX 3600
```

Проверка:

```text
GET fastapi_users_token:<token>
```

Logout/revoke:

```text
DEL fastapi_users_token:<token>
```

Истечение срока выполняет Redis через TTL. В отличие от JWT, сервер знает каждую
активную сессию и может немедленно удалить её.

### 8.2. Пример RedisStrategy

```python
import redis.asyncio
from fastapi_users.authentication import AuthenticationBackend, BearerTransport

# Этот импорт доступен только при установленной зависимости redis.
from fastapi_users.authentication.strategy.redis import RedisStrategy


redis_client = redis.asyncio.Redis(
    host="localhost",
    port=6379,
    decode_responses=True,
)


def get_redis_strategy() -> RedisStrategy:
    return RedisStrategy(
        redis=redis_client,
        lifetime_seconds=3600,
        key_prefix="auth:token:",
    )


redis_bearer_backend = AuthenticationBackend(
    name="redis-bearer",
    transport=BearerTransport(tokenUrl="auth/redis/login"),
    get_strategy=get_redis_strategy,
)
```

Для cookie-варианта меняется только транспорт:

```python
redis_cookie_backend = AuthenticationBackend(
    name="redis-cookie",
    transport=CookieTransport(cookie_name="redis_session"),
    get_strategy=get_redis_strategy,
)
```

В production Redis client должен управляться lifespan приложения, закрываться при
shutdown и конфигурироваться через секреты/настройки. Нельзя создавать новые
неограниченные подключения к Redis на каждый запрос.

### 8.3. Плюсы и минусы

Плюсы:

- быстрые `GET`/`DEL`;
- TTL удаляет протухшие записи;
- простой настоящий revoke;
- удобно для нескольких экземпляров API;
- не нужно нагружать основную SQL-БД каждым auth-check.

Минусы:

- Redis становится обязательной частью auth-path;
- нужно продумать availability и persistence Redis;
- нужен lifecycle connection pool;
- поиск «всех сессий пользователя» требует дополнительного индекса или структуры
  ключей, потому что обычный ключ token → user не равен списку user → tokens.

### 8.4. Когда выбирать

`RedisStrategy` подходит, когда:

- нужен stateful token и быстрый access check;
- несколько экземпляров API должны видеть одни сессии;
- TTL и revoke важнее полного stateless;
- Redis уже есть в инфраструктуре.

---

## 9. Сравнение трёх стратегий

| Вопрос | `JWTStrategy` | `DatabaseStrategy` | `RedisStrategy` |
|---|---|---|---|
| Где истина? | внутри подписанного JWT | запись в БД | ключ/значение в Redis |
| Token | JWT | случайная строка | случайная строка |
| Проверка | подпись + claims | SELECT | GET |
| Нужен token store? | нет | да | да |
| Настоящий revoke? | не самим JWT | DELETE записи | DEL ключа |
| Logout | удалить token у клиента; JWT ещё живёт до exp | удалить запись и cookie/локальный token | DEL и удалить cookie/локальный token |
| Нагрузка | CPU и загрузка user | БД на auth-check | Redis на auth-check |
| Горизонтальное масштабирование | простое | общая БД обязательна | общий Redis обязательный |
| TTL | `exp` в JWT | lifetime при чтении/очистке | Redis `EX` |
| Изменение прав | новые права не всегда в старом JWT | видно после чтения user/записи | видно после чтения user/записи |
| Главный риск | украденный token живёт до exp | недоступность БД | недоступность Redis |
| Главная причина выбрать | stateless | управляемые сессии | быстрые управляемые сессии |

---

## 10. Что применять: браузер или клиент

### 10.1. Браузер на том же origin

Рекомендуемая базовая комбинация:

```text
CookieTransport + JWTStrategy
```

Почему:

- browser автоматически работает с cookie;
- `HttpOnly` не даёт обычному JavaScript прочитать JWT;
- не нужен `localStorage`;
- JWT не требует token store;
- для небольшого приложения настройка проста.

Но нужно честно помнить: это не настоящий revoke. Если требуются управление сессиями,
logout на всех устройствах и мгновенное закрытие украденной сессии:

```text
CookieTransport + DatabaseStrategy
или
CookieTransport + RedisStrategy
```

### 10.2. SPA на другом origin

Возможны две схемы:

```text
CookieTransport + stateful strategy
```

Тогда нужны `credentials`, точный CORS origin, `Allow-Credentials`, корректные
`SameSite=None; Secure` и CSRF-защита.

Или:

```text
BearerTransport + JWTStrategy
```

Тогда нет автоматической cookie и CSRF от неё, но token нужно хранить и защищать
от XSS/утечек. Для сложного frontend часто выбирают BFF, чтобы вернуть browser-
сессию в HttpOnly cookie и не держать access token в JavaScript.

### 10.3. Mobile / desktop / CLI

Базовый выбор:

```text
BearerTransport + JWTStrategy
```

или при обязательном revoke:

```text
BearerTransport + DatabaseStrategy
BearerTransport + RedisStrategy
```

Почему Bearer:

- у клиента есть явный token;
- нет браузерной cookie-механики;
- клиент может хранить token в Keychain/Keystore/keyring;
- удобно обращаться к API без cookie jar.

### 10.4. Сводная таблица

| Клиент | Транспорт | Стратегия по умолчанию | Если нужен мгновенный revoke |
|---|---|---|---|
| Браузер same-origin | Cookie | JWT | Database или Redis |
| Браузер cross-origin | Cookie или Bearer | зависит от threat model | Database или Redis |
| SPA без BFF | Bearer | JWT с коротким TTL | Redis/Database + refresh design |
| Mobile | Bearer | JWT | Redis/Database |
| CLI | Bearer | JWT с коротким TTL | Redis/Database |
| Внешний API-клиент | Bearer | JWT или opaque stateful token | Database/Redis |

---

## 11. Как объяснить студенту на одном примере

Пусть Alice входит в интернет-магазин.

### Вариант A: Cookie + JWT

```text
login → server подписывает JWT → Set-Cookie
GET /orders → browser сам отправляет cookie
server проверяет подпись JWT
```

Если Alice нажала logout, browser забыл cookie. Но если JWT заранее скопировали,
он технически может работать до `exp`.

### Вариант B: Cookie + Database

```text
login → server создаёт random token → INSERT в БД → Set-Cookie
GET /orders → browser отправляет cookie → SELECT token в БД
logout → DELETE token из БД + удалить cookie
```

Скопированный token после DELETE больше не работает.

### Вариант C: Bearer + Redis

```text
login → server создаёт random token → Redis SET с TTL → JSON
GET /orders → client добавляет Authorization: Bearer token → Redis GET
logout → client удаляет token + server делает Redis DEL
```

Здесь transport — Bearer, а стратегия — Redis. Эти понятия не конфликтуют.

---

## 12. Готовые ответы на вопросы собеседования

### «Почему Cookie безопаснее Bearer?»

Неполный ответ. Cookie с `HttpOnly` лучше защищает **от чтения token JavaScript**,
но автоматическая отправка cookie создаёт CSRF. Bearer не отправляется браузером
сам и поэтому не подвержен этой форме CSRF, но token нужно где-то хранить, а
`localStorage` уязвим для XSS. Правильный выбор зависит от клиента и threat model.

### «Почему Bearer для мобильного приложения?»

У мобильного клиента нет обычной браузерной cookie-модели, зато есть Keychain/Keystore.
Bearer явно передаётся в `Authorization`, легко используется в API, а credential можно
хранить в системном secure storage.

### «JWTStrategy и DatabaseStrategy — чем отличаются?»

JWTStrategy хранит необходимые для проверки claims внутри подписанного token и не
требует token store. DatabaseStrategy хранит случайную строку и связь с пользователем
в БД. JWT проще масштабировать, DatabaseStrategy даёт мгновенный revoke и управление
сессиями ценой запроса к БД.

### «RedisStrategy — это просто быстрый JWT?»

Нет. RedisStrategy не проверяет подпись JWT. Она хранит случайный token в Redis и
делает `GET`/`DEL`. Это stateful strategy, а не разновидность JWTStrategy.

### «Можно ли использовать CookieTransport с DatabaseStrategy?»

Да. Транспорт и стратегия независимы. Это cookie-based server session с token state
в БД и настоящим revoke.

### «Можно ли использовать BearerTransport с JWTStrategy?»

Да. Это обычный bearer JWT: JSON на login, `Authorization: Bearer` на каждом запросе.

### «Что делает logout с JWT?»

CookieTransport стирает cookie, Bearer-клиент удаляет локальный token. Но сама JWT
Strategy не может сделать уже подписанный token недействительным без дополнительного
server-side механизма. Он живёт до `exp`.

### «Что выбрать, если нужно выйти со всех устройств?»

DatabaseStrategy или RedisStrategy, потому что сервер хранит активные tokens и может
удалить их. С чистым JWT придётся использовать короткий TTL, version/revocation check
или отдельный blacklist/session version.

---

## 13. Итоговая формула выбора

```text
Сначала спросить: кто клиент?

Browser:
  CookieTransport
  + JWTStrategy для stateless простоты
  + Database/RedisStrategy для revoke и управления сессиями

Mobile / desktop / CLI / внешний API-клиент:
  BearerTransport
  + JWTStrategy для stateless и короткого TTL
  + Database/RedisStrategy для server-side revoke
```

И ещё раз главное:

> **Cookie/Bearer отвечают на вопрос «как token приехал».**
> **JWT/Database/Redis отвечают на вопрос «где token проверяется и как его отозвать».**

---

## 14. Источники и привязанные к ним рекомендации

- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) — cookie flags, session IDs и опасность хранения credential в `localStorage`/`sessionStorage`.
- [OWASP Cross-Site Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) — CSRF tokens, SameSite и отличие CSRF от XSS.
- [OWASP OAuth 2.0 Protocol Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html) — bearer tokens, token leakage и sender-constrained tokens.
- [RFC 6750 — OAuth 2.0 Bearer Token Usage](https://www.rfc-editor.org/rfc/rfc6750.html) — правила использования `Authorization: Bearer`.
- [RFC 7519 — JSON Web Token](https://www.rfc-editor.org/rfc/rfc7519.html) — формат JWT и claims.
- [RFC 9700 — Best Current Practice for OAuth 2.0 Security](https://www.rfc-editor.org/rfc/rfc9700.html) — актуальные рекомендации OAuth; использован здесь для общей модели access token, ограничения privilege и различий stateful/stateless подходов.
- [fastapi-users 15.0.5 — Authentication strategies](https://github.com/fastapi-users/fastapi-users/tree/master/fastapi_users/authentication/strategy) — API классов, соответствующий установленной версии проекта.
- Текущий проект: `fastapi-application/auth_users/auth_backend.py`, `auth_users/router.py`, `frontend/src/api/client.ts`.
