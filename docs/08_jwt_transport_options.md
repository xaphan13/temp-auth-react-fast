# 08. Способы передачи JWT: cookie, Bearer и кастомный заголовок

Документ — про **транспорт токена**: каким способом выданный credential попадает от клиента
обратно на сервер. Текущая реализация (cookie `auth` + `CookieTransport` + `JWTStrategy`) —
в [`docs/04_authorization.md`](04_authorization.md), диаграммы и рантайм-граф — в
[`docs/06_auth_visual.md`](06_auth_visual.md), список невыполненного — в
[`docs/05_authorization_upgrade.md`](05_authorization_upgrade.md).
Пошаговый разбор текущего cookie-потока с полным кодом фронта и бэка —
[`docs/07_auth_token_flow_code.md`](07_auth_token_flow_code.md).

Прицел документа: у API планируется **отдельное клиентское приложение** (другой origin или
вообще не браузер), которое тоже должно авторизоваться. Поэтому сравнение ведётся не «что лучше
вообще», а «что выбрать под несколько клиентов».

Имена классов, параметры и дефолты в разделах 1–2, 5 и 7.2 проверены чтением установленного
пакета `.venv/lib/python3.12/site-packages/fastapi_users/` (**fastapi-users 15.0.5**). Где
утверждение опирается только на внешнюю документацию — это указано явно (раздел 9).

---

## 1. Транспорт, стратегия и хранение — три независимых решения

| # | Вопрос | Чем задаётся в fastapi-users |
|---|---|---|
| а | **Как токен выдаётся** (тело ответа, заголовки) | `Transport.get_login_response()` |
| б | **Чем токен едет обратно** (`Cookie`, `Authorization: Bearer`, свой заголовок) | `Transport.scheme` |
| в | **Что лежит в токене и как он проверяется** | `Strategy`: `JWTStrategy` / `DatabaseStrategy` / `RedisStrategy` |

`AuthenticationBackend` — это пара «транспорт + стратегия» (`authentication/backend.py`):
`login()` = `strategy.write_token(user)` → `transport.get_login_response(token)`, а `logout()`
вызывает `strategy.destroy_token(...)`, **глотая** `StrategyDestroyNotSupportedError`, и затем
`transport.get_logout_response()`, **глотая** `TransportLogoutNotSupportedError`.

Отсюда три следствия, которые обычно ошибочно приписывают «JWT»:

- **`logout` не равен отзыву.** `JWTStrategy.destroy_token()` бросает
  `JWTStrategyDestroyNotSupportedError` с текстом `"A JWT can't be invalidated: it's valid
  until it expires."`, и backend проглатывает исключение. Cookie-вариант просто стирает cookie.
- **Смена транспорта не меняет токен**, **смена стратегии не меняет транспорт** — это
  независимые решения (тот же JWT можно отдавать cookie'й или в JSON без правок стратегии;
  переход на серверное состояние с настоящим отзывом делается отдельно).

В проекте выбрано: `CookieTransport` + `JWTStrategy`, `name="jwt"`
(`auth_users/auth_backend.py`), а путь `/auth/jwt` задаётся **вручную** в `auth_users/router.py`:
`router.include_router(auth_router, prefix="/auth/jwt", tags=["auth-jwt"])`. Имя backend'а в
путь не попадает — это важно для раздела 7.2.

---

## 2. Штатные транспорты и стратегии fastapi-users 15.0.5

### 2.1. Транспорты

Пакет экспортирует ровно три имени (`transport/__init__.py`): `BearerTransport`,
`CookieTransport`, `Transport` (плюс `TransportLogoutNotSupportedError`). `Transport` — это
`Protocol`, не базовый класс; он требует ровно `scheme: SecurityBase`,
`get_login_response(self, token)`, `get_logout_response(self)` и две статические функции
OpenAPI-ответов. Это и делает расширение тривиальным (раздел 5).

**`CookieTransport`** — параметры и дефолты из `transport/cookie.py` и их значения здесь:

| Параметр | Дефолт | В проекте |
|---|---|---|
| `cookie_name` | `"fastapiusersauth"` | `"auth"` |
| `cookie_max_age` | `None` | `86400` |
| `cookie_path` | `"/"` | не переопределён |
| `cookie_domain` | `None` | не переопределён |
| `cookie_secure` | `True` | `False` |
| `cookie_httponly` | `True` | `True` |
| `cookie_samesite` | `"lax"` (`Literal["lax","strict","none"]`) | `"lax"` |

Чтение запроса — `APIKeyCookie(name=self.cookie_name, auto_error=False)`; `auto_error=False`
значит, что отсутствие cookie не даёт 401 само — решение принимает `Authenticator`. Выдача и
удаление — `Response(204)` + `set_cookie(...)`, при logout значение пустое и `max_age=0`.

**`BearerTransport`** — параметр ровно один, без дефолта: `BearerTransport(tokenUrl: str)`,
который создаёт `OAuth2PasswordBearer(tokenUrl, auto_error=False)`. `tokenUrl` — подсказка
Swagger UI. Ответ login — `BearerResponse(access_token, token_type)` =
`{"access_token": "<JWT>", "token_type": "bearer"}` со статусом 200.
`get_logout_response()` бросает `TransportLogoutNotSupportedError()`.

**Своего `HeaderTransport` в пакете нет** — в `transport/` только `base.py`, `bearer.py`,
`cookie.py`. Любой нестандартный заголовок — свой класс (раздел 5).

### 2.2. Стратегии

| Класс | Параметры конструктора | Свойства |
|---|---|---|
| `JWTStrategy` | `secret`, `lifetime_seconds`, `token_audience=["fastapi-users:auth"]`, `algorithm="HS256"`, `public_key=None` | stateless; payload `{"sub": str(user.id), "aud": ...}` + `exp`; `destroy_token` не реализован |
| `DatabaseStrategy` | `database: AccessTokenDatabase`, `lifetime_seconds=None` | токен `secrets.token_urlsafe()`; `destroy_token` реально удаляет строку |
| `RedisStrategy` | `redis: redis.asyncio.Redis`, `lifetime_seconds=None`, `key_prefix="fastapi_users_token:"` | токен в Redis (`set(..., ex=...)`); `destroy_token` — `redis.delete` |

Redis-стратегия действительно есть в установленной версии, но импортируется в try/except
(`try: ... except ImportError: pass`), поэтому появляется только при наличии `redis.asyncio`.
В этом окружении redis не установлен, и `RedisStrategy` из `fastapi_users.authentication.strategy`
не появится.

Вывод для раздела 7: **вопрос «как отзывать токен» решается стратегией, а не транспортом.**

---

## 3. Вариант A. HttpOnly cookie (текущее состояние проекта)

### 3.1. Как это работает

1. Клиент шлёт форму на `/auth/jwt/login` (`application/x-www-form-urlencoded`, `username`/`password`).
2. Backend проверяет пароль, `JWTStrategy.write_token()` подписывает JWT, `CookieTransport`
   отвечает `204` и заголовком
   `Set-Cookie: auth=<JWT>; Max-Age=86400; HttpOnly; SameSite=Lax; Path=/`.
3. Браузер сам сохраняет cookie и сам прикладывает её к same-origin-запросам.

Frontend делает ровно одно (`frontend/src/api/client.ts`):
`fetch(path, { credentials: 'include', ...init })`. Кода «добавить токен к запросу» нет — cookie
недоступна JavaScript. В DevTools поток виден в Network → Response Headers (login),
Application → Cookies, Network → Request Headers; разбор — в `docs/04`, раздел 9.

### 3.2. Плюсы

- **XSS не читает токен**: `document.cookie` его не покажет, забрать и переиспользовать на
  другом устройстве нельзя.
- **Отправляется автоматически** — нельзя «забыть» обернуть вызов API; logout тривиален
  (`max_age=0`, браузер сразу теряет credential).
- **Нет вопроса «где хранить на клиенте»** и «что делать при перезагрузке страницы».

### 3.3. Минусы

- **CSRF.** Браузер прикладывает cookie сам. `SameSite=Lax` отсекает cross-site POST, но не
  заменяет CSRF-модель; в проекте CSRF-защиты нет (разделы 7.3, 7.7).
- **Привязка к origin.** Сценарий «SPA на `app.example.com`, API на `api.example.com`»
  требует решений по `cookie_domain`, `SameSite`, CORS.
- **CORS с credentials.** Нужны `Access-Control-Allow-Credentials: true` и точный
  `Access-Control-Allow-Origin`; `*` в этом режиме браузер отклоняет, а клиент обязан слать
  `credentials: 'include'`.
- **`Secure` обязателен в проде**: текущее `cookie_secure=False` — компромисс ради локального HTTP.
- **Неудобно для не-браузерных клиентов**: у CLI нет cookie-jar, у мобильного приложения
  cookie есть, но управлять ими вручную непривычно.
- **Прокси/CDN**: ответы с cookie требуют `Vary: Cookie`, иначе риск кэширования чужого ответа.

### 3.4. Что ломается, когда frontend на другом origin

1. `fetch` без `credentials: 'include'` → cookie не приложена → `401`.
2. Даже с credentials браузер отклонит ответ без точного
   `Access-Control-Allow-Origin: https://app.example.com` и `Allow-Credentials: true`
   (wildcard при credentials недопустим по Fetch-стандарту).
3. Cookie `SameSite=Lax`/`Strict` не прикладывается к cross-site запросу → нужно
   `SameSite=None` **и** `Secure` (браузеры игнорируют `None` без `Secure`). `Secure` здесь
   перестаёт быть опцией, а локальная разработка по http требует HTTPS или dev-прокси.
4. `SameSite=None` **возвращает CSRF целиком**: cookie снова ездит cross-site, и защиту надо
   строить заново (`X-CSRF-Token`, double-submit, проверка `Origin`).
5. В проекте dev-прокси покрывает только `/api` (`frontend/vite.config.ts`), поэтому при выносе
   `/auth/*` и `/users/*` на другой origin Vite их не найдёт.

---

## 4. Вариант B. Bearer-токен в заголовке `Authorization`

### 4.1. Обмен

```http
POST /auth/bearer/login
Content-Type: application/x-www-form-urlencoded

grant_type=password&username=user@example.com&password=password123
```

Ответ — буквально `BearerResponse` из `transport/bearer.py`:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"access_token": "<JWT>", "token_type": "bearer"}
```

Дальше каждый запрос идёт с `Authorization: Bearer <JWT>`. Токен читает `OAuth2PasswordBearer`,
созданный с `auto_error=False`; он ожидает именно этот заголовок со схемой `Bearer`.

Деталь: login-обработчик всегда ожидает `OAuth2PasswordRequestForm`, в котором `grant_type`
объявлен **необязательным**, поэтому и curl без него (`docs/05`), и стандартные OAuth2-клиенты
с ним работают; fastapi-users это поле не использует.

### 4.2. Как это выглядело бы

В проекте это **не включено**: к текущему `CookieTransport` добавляется второй транспорт и
второй backend с `name="bearer"` и той же `get_jwt_strategy` (полный код — раздел 8.1,
подключение и пути — раздел 7.2).

### 4.3. Где хранить токен на клиенте

| Место | Переживает перезагрузку | Читается любым скриптом | Комментарий |
|---|---:|---:|---|
| `localStorage` | да | **да** | самая популярная и самая опасная схема: одна XSS-инъекция отдаёт токен целиком |
| `sessionStorage` | в пределах вкладки | **да** | то же, но живёт до закрытия вкладки |
| Память (React state, модульная переменная) | нет | нет | скрипт не «прочитает хранилище», но сможет сделать запрос от имени пользователя, пока страница открыта |
| SecureStore / Keychain (натив) | да | нет | правильный вариант для мобильных |
| Файл с правами 600 (CLI) | да | n/a | обычная практика для dev-CLI |

Честная формулировка: **`localStorage` не защищает от XSS никак**. Компрометированная
зависимость, сторонняя аналитика или `innerHTML`-инъекция читают
`localStorage.getItem('access_token')` и уносят долгоживущий (24 часа в текущих настройках)
токен. Память снижает ущерб: перезагрузка страницы теряет токен, и вместо «тихого воскрешения»
нужен refresh-механизм или повторный вход.

### 4.4. Плюсы

- **CSRF фактически отсутствует**: заголовок не прикладывается браузером автоматически.
- **Работает с любым клиентом**: curl, мобильное приложение, стороннее SPA, Postman.
- **Работает на другом домене** без `SameSite=None` и, как правило, без CORS-credentials;
  `Allow-Credentials` не нужен, достаточно `Authorization` в `Allow-Headers`.

### 4.5. Минусы

- **XSS-кража при хранении в `localStorage`/`sessionStorage`** — цена, которую платит большинство.
- **Ручная подстановка заголовка** в каждый запрос (в проекте — правка центрального `request()`).
- **Logout/отзыв делает клиент.** Ни транспорт-logout, ни отзыв у `JWTStrategy` не работают;
  настоящий отзыв — только `DatabaseStrategy`/`RedisStrategy`, а refresh-токенов в
  fastapi-users нет вовсе (своя пара токенов, свой эндпоинт, своя ротация).
- **Токен «светится»** в логах middleware, APM, прокси и в DevTools.

---

## 5. Вариант C. Свой кастомный заголовок (например `X-Auth-Token`)

`HeaderTransport` в пакете нет, но расширение тривиально: `Transport` — `Protocol`.

```python
# ПРИМЕР ДЛЯ РАЗВИТИЯ — в проект не внесён.
from fastapi import Response, status
from fastapi.security import APIKeyHeader
from fastapi_users.authentication.transport import Transport
from fastapi_users.openapi import OpenAPIResponseType


class HeaderTransport(Transport):
    scheme: APIKeyHeader

    def __init__(self, header_name: str = "X-Auth-Token"):
        self.header_name = header_name
        self.scheme = APIKeyHeader(name=header_name, auto_error=False)

    async def get_login_response(self, token: str) -> Response:
        # Сигнатура именно (token): ни request, ни user, ни payload — сверено
        # с CookieTransport/BearerTransport 15.0.5. Старые примеры с
        # signature=(token, response, user, payload) здесь НЕ вызовутся.
        return Response(status_code=status.HTTP_204_NO_CONTENT,
                        headers={self.header_name: token})

    async def get_logout_response(self) -> Response:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def get_openapi_login_responses_success() -> OpenAPIResponseType:
        return {status.HTTP_204_NO_CONTENT: {"model": None}}

    @staticmethod
    def get_openapi_logout_responses_success() -> OpenAPIResponseType:
        return {status.HTTP_204_NO_CONTENT: {"model": None}}
```

Подводные камни: **CORS preflight** (кастомный заголовок выводит запрос из «simple request»:
нужен `Access-Control-Allow-Headers: X-Auth-Token`, иначе невнятная ошибка CORS); **Swagger UI**
штатной формы login не даёт (её даёт только `OAuth2PasswordBearer` в `BearerTransport`);
**чужие клиенты и шлюзы** (SDK, API-gateway, сервис-меш, WAF) знают `Authorization: Bearer`,
но не ваш заголовок; **токен в URL передавать нельзя** — попадёт в логи прокси, `Referer` и
историю браузера.

Это вариант «когда очень надо» — например, когда чужая инфраструктура фильтрует
`Authorization`. Как основной он проигрывает Bearer по совместимости, ничего не давая взамен.

---

## 6. Сравнительная таблица

| Критерий | Cookie `auth` (текущий) | `Authorization: Bearer` | Кастомный заголовок |
|---|---|---|---|
| Защита от кражи токена через XSS | высокая (HttpOnly недоступен JS) | зависит от хранения: `localStorage` — низкая, память — средняя | как у Bearer |
| Защита от CSRF | нужна отдельная (сейчас нет) | не нужна | не нужна |
| CORS-credentials | нужен `Allow-Credentials` + точный `Allow-Origin` | не нужен | не нужен |
| Другой origin | `SameSite=None; Secure` + CSRF-пересборка | работает | работает (+ preflight) |
| Не-браузерный клиент (мобильный, CLI, сервер-сервер) | неудобно (ручной cookie-jar) | родной сценарий | родной, но нужен свой SDK |
| Swagger UI | Authorize не нужен, cookie из браузера | штатная кнопка Authorize + форма login | частично (схема `apiKey`) |
| Logout | `Set-Cookie: max_age=0`, надёжно | «выбросить токен» (или серверная стратегия) | как у Bearer |
| Отзыв токена | невозможен при `JWTStrategy` | невозможен при `JWTStrategy` | невозможен при `JWTStrategy` |
| Refresh-токены | в fastapi-users нет | нет, но механика обычно на стороне такого клиента | нет |
| Кэширование прокси/CDN | риск, нужен `Vary: Cookie` | безопаснее: запросы с `Authorization` не кэшируются разделяемыми кэшами | зависит от заголовка |
| Размер credential | cookie ~4 KB — крупный JWT может не влезть | ограничения заголовка практически отсутствуют | как у Bearer |
| Влияние на SEO/статику | cookie летит и к статике того же домена: лишний трафик, `Vary` | статика не затрагивается | статика не затрагивается |
| Прозрачность в логах | значение cookie обычно не логируется | токен легко утекает в дампы middleware/APM | так же |
| Модель защиты одной фразой | «токена не видит JS, но запрос подделывается» | «подделать нельзя, но токен можно украсть» | то же, что Bearer |

Выбор идёт не между «безопасно» и «небезопасно», а между тем, от какой угрозы защищаемся и чем платим.

---

## 7. Несколько клиентов у одного API

### 7.1. Почему одна схема на всех — плохо

| Клиент | Главная угроза | Естественная схема |
|---|---|---|
| SPA на том же origin | CSRF (cookie едет сама) | cookie `Lax`/`Strict` (+ CSRF-токен при расхождении origin) |
| SPA на другом домене | CSRF + CORS + XSS | Bearer (память + refresh) либо cookie с CORS-credentials и CSRF |
| Мобильное приложение | кража токена с устройства | Bearer + SecureStore/Keychain |
| CLI / скрипт | утечка долгоживущего токена | Bearer с коротким TTL или API-ключ |
| Сервер → сервер | компрометация сервиса = доступ ко всему | client_credentials / API-ключ, не JWT пользователя |

Навязывать мобильному клиенту cookie-flow — заставлять его писать cookie-jar, разбираться с
`SameSite` и получать взамен угрозу CSRF, которой у него нет.

### 7.2. Несколько backend'ов одновременно (проверено по коду пакета)

`FastAPIUsers.__init__` принимает **последовательность** backend'ов:
`FastAPIUsers(get_user_manager, auth_backends: Sequence[AuthenticationBackend])`.
`Authenticator._authenticate` перебирает их по порядку и «побеждает первый, давший
пользователя» (`if user: break`), подставляя для каждого `Depends(backend.transport.scheme)` и
`Depends(backend.get_strategy)`. Имена должны различаться, иначе `DuplicateBackendNamesError`;
в OpenAPI попадают схемы всех backend'ов статически.

**Имя backend'а в путь не попадает** — это проверено по исходнику установленного пакета
(`fastapi_users/router/auth.py`):

```python
@router.post("/login", name=f"auth:{backend.name}.login", responses=login_responses)
async def login(...):
    ...

@router.post("/logout", name=f"auth:{backend.name}.logout", responses=logout_responses)
async def logout(...):
    ...
```

То есть пути в роутере — ровно `/login` и `/logout`; `backend.name` попадает только в имя
операции OpenAPI (`auth:jwt.login`). Путь задаёт вызывающий код через `prefix`:

```python
# ПРИМЕР ДЛЯ РАЗВИТИЯ — в проект не внесён.
router.include_router(auth_router,   prefix="/auth/jwt",    tags=["auth-jwt"])     # как сейчас
router.include_router(bearer_router, prefix="/auth/bearer", tags=["auth-bearer"])  # новый путь

# и второй backend в списке: /users/me начинает принимать оба credential'а
fastapi_users = FastAPIUsers[User, UUID](get_user_manager, [auth_backend, bearer_backend])
```

Итог: `/auth/jwt/login` (cookie, `204` + `Set-Cookie`) и `/auth/bearer/login` (JSON с
`access_token`) работают одновременно, а `current_user`, `active_user`, `optional_user`,
`superuser_user` из `auth_users/fastapi_users_obj.py` обслуживают любой из двух credential'ов.

### 7.3. CSRF при cookie-варианте

Как только cookie начинает ходить между сайтами (`SameSite=None`), нужна явная защита:
**synchronizer token** (сервер выдаёт токен, клиент шлёт его в `X-CSRF-Token`, сервер сравнивает),
**double-submit cookie** (тот же токен в cookie и в заголовке, сверка значений) и проверка
`Origin`/`Referer` как дополнительный, но не единственный слой. `SameSite=Lax` эту модель не
отменяет — он лишь сужает множество cross-site запросов.

### 7.4. CORS для браузерного клиента с другого origin

В проекте CORS-middleware **отсутствует**; пример для развития:

```python
# ПРИМЕР ДЛЯ РАЗВИТИЯ — в проект не внесён.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.example.com"],   # точный origin, НЕ "*"
    allow_credentials=True,                      # нужно только для cookie-варианта
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)
```

Почему `allow_origins=["*"]` + `allow_credentials=True` не работает: Fetch-стандарт запрещает
wildcard в `Access-Control-Allow-Origin` при credentials — браузер отклонит ответ. Starlette в
этом режиме также не отражает `*` как конкретный origin, а использует список как есть.
`allow_headers` обязан содержать `Authorization` (Bearer) и `X-CSRF-Token` (если выбран такой
механизм), иначе preflight отклонится.

### 7.5. API-ключи и client_credentials — отдельная история

JWT пользователя отвечает на вопрос «кто это» и сервису не выдаётся. Для сервер-сервер нужен
другой механизм: статический **API-ключ** (прост, но требует ротации и хранилища ключей) или
OAuth2 **`client_credentials`** (короткий TTL, права через scope). В fastapi-users этого нет —
там только аутентификация пользователей. Смешивать сервисный и пользовательский credential в
одном эндпоинте плохо: разбор прав придётся делать в каждом обработчике.

### 7.6. Рецепт выбора

- **SPA на том же origin, что API** (текущее состояние) → cookie `HttpOnly` + `SameSite=Lax/Strict`:
  максимальная защита от XSS, минимум клиентского кода.
- **SPA на своём домене, API на другом** → либо Bearer (токен в памяти + свой refresh: короткий
  access + долгий refresh в `HttpOnly`-cookie домена API), либо cookie с корректным CORS
  (`точный Allow-Origin` + `Allow-Credentials`), `SameSite=None; Secure` и обязательной CSRF-защитой.
- **Мобильное / нативное / CLI** → Bearer + SecureStore/Keychain/файл с правами 600.
- **Сервер → сервер** → `client_credentials` или API-ключ с отдельным слоем проверки прав.

### 7.7. Чего в текущем проекте нет

Пробелы для перехода на multi-client (см. [`docs/05_authorization_upgrade.md`](05_authorization_upgrade.md)):

- **Нет CORS-middleware** — ни `CORSMiddleware`, ни `allow_origins`; сейчас не мешает, потому что
  frontend и backend отдаются одним приложением (`core/setup_frontend.py`).
- **Нет CSRF-защиты** — при `SameSite=Lax` и same-origin достаточно, при `None` нужна модель.
- **Нет refresh-токенов** — единственный credential это 24-часовой JWT.
- **Нет отзыва токенов** — `JWTStrategy.destroy_token` не реализован, logout только удаляет cookie.
- **`cookie_secure=False`** — при HTTPS включить `True`.
- **Один backend** (`name="jwt"`, cookie) в `auth_users/fastapi_users_obj.py`.
- **Один секрет на всё**: `settings.web.secret_key` подписывает и JWT авторизации, и токены
  сброса пароля/verification (`auth_users/user_manager.py`).

Переход на «отдельное приложение-клиент» — это не «добавить Bearer», а пакет работ: второй
backend, CORS (или CSRF-модель), решение про refresh и отзыв, `Secure=true`, отдельный секрет.

---

## 8. Мини-примеры

Всё ниже — **иллюстрация вариантов**, в проект ничего из этого не внесено. Текущее состояние
остаётся: cookie `auth`, `CookieTransport` + `JWTStrategy`, `name="jwt"`.

### 8.1. Backend: cookie + Bearer рядом

Минимальная правка `auth_users/auth_backend.py` — второй транспорт и второй backend (контекст —
разделы 4.2 и 7.2):

```python
# ПРИМЕР ДЛЯ РАЗВИТИЯ — в проект не внесён.
from fastapi_users.authentication import BearerTransport

# tokenUrl — подсказка Swagger UI; путь определяется префиксом в router.py.
bearer_transport = BearerTransport(tokenUrl="auth/bearer/login")

bearer_backend = AuthenticationBackend(
    name="bearer",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,   # та же стратегия: содержимое токена одинаковое
)
```

Дальше — подключение (ориентиры `auth_users/router.py` и `auth_users/fastapi_users_obj.py`):
`get_auth_router(bearer_backend)` под `prefix="/auth/bearer"` и второй backend в списке
`FastAPIUsers[User, UUID](get_user_manager, [auth_backend, bearer_backend])`.

### 8.2. Frontend: Bearer-вариант в стиле `api/client.ts` / `api/auth.ts`

```ts
// ПРИМЕР ДЛЯ РАЗВИТИЯ — в проект не внесён.
// Токен намеренно в модульной переменной (память), а НЕ в localStorage:
// localStorage читается любой сторонней строкой JS, и одна XSS-инъекция
// уносит долгоживущий токен целиком.
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
    accessToken = token;
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
    // credentials: 'include' для Bearer не нужен — cookie не используется.
    return fetch(path, { ...init, headers });
}

export async function loginBearer(email: string, password: string): Promise<void> {
    const res = await fetch('/auth/bearer/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: email, password }).toString(),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as { access_token: string };
    setAccessToken(data.access_token);
}
```

При перезагрузке страницы токен из памяти не выживает — нужен повторный вход либо
refresh-механизм (короткий access в памяти + долгий refresh в `HttpOnly`-cookie домена API).
Refresh-токенов в fastapi-users нет: это отдельная разработка (эндпоинт, ротация, отзыв).

### 8.3. curl: оба варианта

Cookie — актуально сегодня:

```bash
# login: 204 + Set-Cookie: auth=<JWT>; cookie сохраняется в файл
curl -i -c /tmp/cookies.txt -X POST http://127.0.0.1:8000/auth/jwt/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data 'username=user@example.com&password=password123'

curl -s -b /tmp/cookies.txt http://127.0.0.1:8000/users/me
curl -s -b /tmp/cookies.txt http://127.0.0.1:8000/api/v1/auth/protected

# logout: 204 + Set-Cookie: auth=; Max-Age=0
curl -i -b /tmp/cookies.txt -X POST http://127.0.0.1:8000/auth/jwt/logout
```

Bearer — для развития (соответствует backend'у из 8.1). Токен вынимается из JSON без jq —
через `python` из `.venv` проекта:

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/bearer/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data 'username=user@example.com&password=password123' \
  | python -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')
# то же через jq: ... | jq -r .access_token

curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/users/me
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/v1/auth/protected

# logout у Bearer/stateless: пустой 204, токен остаётся валидным до истечения срока
curl -i -X POST -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/auth/bearer/logout
```

---

## 9. Источники и статус проверки

**Проверено чтением установленного `fastapi-users 15.0.5`** (`site-packages/fastapi_users/`):
состав `transport/` (есть только `Transport`-Protocol, `CookieTransport`, `BearerTransport` —
`HeaderTransport` нет); параметры и дефолты `CookieTransport`, включая `cookie_name="fastapiusersauth"`,
`cookie_max_age=None`, `cookie_secure=True`, `cookie_samesite="lax"`, `APIKeyCookie(auto_error=False)`,
`204` на login, `max_age=0` на logout; `BearerTransport(tokenUrl)` без дефолта,
`OAuth2PasswordBearer(auto_error=False)`, `BearerResponse`, `TransportLogoutNotSupportedError`;
сигнатуры `get_login_response(self, token)` / `get_logout_response(self)` без
`request`/`user`/`payload`; `AuthenticationBackend.login/logout` и проглатывание
`StrategyDestroyNotSupportedError` / `TransportLogoutNotSupportedError`; параметры и поведение
`JWTStrategy`, `DatabaseStrategy`, `RedisStrategy`; `FastAPIUsers.__init__` со списком backend'ов;
перебор backend'ов в `Authenticator._authenticate`; имена операций `auth:{backend.name}.login`;
`OAuth2PasswordRequestForm` в login-роутере.

**Взято из внешней документации и стандартов**: `SameSite=None; Secure` и wildcard в
`Allow-Origin` при credentials (Fetch-стандарт, MDN); семантика RFC 6750 и RFC 6749; практики
CSRF (double-submit, synchronizer token); хранение в SecureStore/Keychain.

**Проверено в проекте**: `AuthUsersConfig` и `CookieTransport` в `auth_users/auth_backend.py`;
`name="jwt"` и префикс `/auth/jwt` в `auth_users/router.py`;
`FastAPIUsers[User, UUID](get_user_manager, [auth_backend])` в `auth_users/fastapi_users_obj.py`;
`credentials: 'include'` в `frontend/src/api/client.ts`; отсутствие CORS-middleware в
`fastapi-application/`; dev-прокси только на `/api` в `frontend/vite.config.ts`.

Ссылки: [`docs/04_authorization.md`](04_authorization.md) — фактический cookie-flow;
[`docs/05_authorization_upgrade.md`](05_authorization_upgrade.md) — что не сделано;
[`docs/06_auth_visual.md`](06_auth_visual.md) — диаграммы и рантайм-граф.
Внешние: транспорты/стратегии/несколько backend'ов fastapi-users
(https://fastapi-users.github.io/fastapi-users/latest/configuration/authentication/transports/ ,
.../strategies/ , .../multiple-backends/), RFC 6750 (https://datatracker.ietf.org/doc/html/rfc6750),
RFC 6749 §4.3, MDN по `Set-Cookie`, `SameSite`, `HttpOnly`, CORS, `Authorization`.
