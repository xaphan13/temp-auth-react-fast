# Авторизация и аутентификация: полное учебное пособие

Пособие не привязано к FastAPI, React, `fastapi-users` или конкретному провайдеру.
Примеры используют обычный HTTP, Python-подобный псевдокод и JavaScript, чтобы
объяснить **принципы**, а не API одной библиотеки.

Актуальность рекомендаций и ссылок: **24 сентября 2026 года**.
Нормативные требования и рекомендации сверены через Tavily по RFC/IETF, OWASP,
OpenID Foundation и W3C. Источники собраны в конце документа.

---

## 1. Как отвечать на собеседовании: короткая версия

> Аутентификация отвечает на вопрос «кто ты?», а авторизация — «что тебе можно?». После
> успешной аутентификации система выдаёт или устанавливает credential: серверную сессию,
> cookie, access token, JWT, API key или другой механизм. Дальше каждый запрос должен
> пройти две независимые проверки: credential действителен и субъект имеет право на
> конкретную операцию над конкретным ресурсом.
>
> Для браузерного приложения обычно выбирают серверную сессию в `HttpOnly; Secure`
> cookie либо BFF-паттерн. Для мобильного приложения и API-клиента — OAuth 2.0
> Authorization Code + PKCE и короткоживущий access token в защищённом хранилище.
> Для server-to-server — Client Credentials, mTLS или private_key_jwt. OAuth отвечает
> за делегирование доступа к API, а для входа пользователя нужен OpenID Connect.
> JWT — не протокол входа, а формат токена. Cookie и Bearer — способы доставки
> credential, а JWT, opaque token и серверная сессия — разные способы его представить
> и проверять.

Эта формулировка уже исправляет распространённую ошибку: **не существует «четырёх
стратегий транспортов»**. Есть несколько независимых осей, которые можно комбинировать.

---

## 2. Четыре понятия, которые нельзя смешивать

### 2.1. Идентификация — «какой субъект заявлен?»

Пользователь сообщает идентификатор: email, username, номер сотрудника, client ID.
Идентификатор сам по себе ничего не доказывает.

### 2.2. Аутентификация — «субъект действительно владеет credential?»

Система проверяет доказательство:

- пароль;
- одноразовый код;
- push-подтверждение;
- passkey/WebAuthn;
- сертификат клиента;
- внешний провайдер через OIDC или SAML.

Результат: система установила, **кто** действует, с некоторой степенью уверенности.

### 2.3. Авторизация — «что этому субъекту разрешено?»

Проверяется не только пользователь, но и действие, ресурс и контекст:

```text
can(subject=alice, action="update", resource=invoice/42, context=request)
```

Важно: скрыть кнопку во frontend — не авторизация. Проверка обязана выполняться
на сервере на каждом защищённом запросе. OWASP рекомендует deny-by-default,
наименьшие привилегии и проверку прав на каждый запрос.

### 2.4. Аудит — «что произошло и можно ли это расследовать?»

Логируются входы, отказы, изменения прав, отзыв сессий и чувствительные операции.
В лог нельзя писать пароли, access/refresh tokens, API keys и полные cookie.
Аудит не заменяет авторизацию, но помогает обнаружить злоупотребление и восстановить
хронологию инцидента.

---

## 3. Базовая схема любого защищённого запроса

```text
1. Клиент получает credential после аутентификации.
2. Клиент передаёт credential серверу.
3. Сервер извлекает credential и проверяет его подлинность, срок и назначение.
4. Сервер определяет subject: user, service или client.
5. Сервер проверяет authorization policy для method + resource + context.
6. Сервер выполняет операцию или возвращает отказ.
7. Событие попадает в безопасный audit log.
```

Отличайте HTTP-ошибки:

- **401 Unauthorized** — на практике означает «нет действительного credential».
- **403 Forbidden** — credential распознан, но права на действие нет.

---

## 4. Пароли: старый, но всё ещё распространённый способ

Пароль нельзя хранить как plaintext и нельзя шифровать обратимым шифрованием.
Сервер хранит результат медленного password hashing с солью:

```python
# Псевдокод: конкретную библиотеку выбирает проект.
password_hash = argon2id.hash(password)

# При login сравнение выполняется специальным constant-time методом.
if not argon2id.verify(password_hash, submitted_password):
    reject_login()
```

Практические правила:

- предпочтительно использовать **Argon2id**; scrypt — подходящая альтернатива;
- bcrypt оставляют в основном для legacy-систем, если Argon2id/scrypt недоступны;
- соль должна быть уникальной и генерироваться библиотекой;
- стоимость хеширования настраивают по реальному времени ответа и периодически
  повышают;
- поддерживают автоматический rehash при успешном входе пользователя;
- не обрезают пароль молча и не вводят бессмысленные правила вроде обязательного
  набора спецсимволов вместо проверки скомпрометированных паролей;
- защищают login от brute force, credential stuffing и password spraying: rate limit,
  обнаружение аномалий, MFA, блок-листы скомпрометированных паролей;
- password reset-ссылки — одноразовые, случайные и короткоживущие.

**Чего не делать:** `MD5(password)`, `SHA256(password)`, самодельная соль,
`encrypt(password)` и сравнение строк, полученных обычным быстрым хешем.

---

## 5. Сессия: сервер хранит состояние, клиент носит идентификатор

Классическая веб-сессия выглядит так:

```text
POST /login
  username + password

HTTP/1.1 303 See Other
Set-Cookie: __Host-session=RANDOM_OPAQUE_ID;
            Path=/; Secure; HttpOnly; SameSite=Lax

GET /account
Cookie: __Host-session=RANDOM_OPAQUE_ID
```

На сервере:

```python
session_id = secrets.token_urlsafe(32)
sessions.store(
    session_id=session_id,
    user_id=user.id,
    expires_at=now() + timedelta(hours=8),
)
```

Cookie содержит не user ID и не пароль, а непредсказуемый идентификатор.
Сервер по нему находит состояние сессии в Redis или БД.

### Флаги cookie

- `Secure` — отправлять только через HTTPS;
- `HttpOnly` — не отдавать cookie JavaScript через `document.cookie`;
- `SameSite=Lax` или `Strict` — ограничить автоматическую отправку в cross-site
  сценариях;
- `Path=/` — ограничить область пути;
- префикс `__Host-` — полезный безопасный вариант для host-only cookie: нужен
  `Secure`, `Path=/`, и нельзя задавать `Domain`.

`HttpOnly` не делает приложение неуязвимым к XSS: вредоносный скрипт может отправить
запрос от имени пользователя, даже если не может прочитать cookie. Но он затрудняет
кражу и повторное использование session ID.

### Logout и отзыв

Для серверной сессии logout естественен: удалить запись на сервере и истечь cookie.
Можно отозвать одну сессию, все сессии пользователя или сессии после смены пароля.
Это преимущество stateful-сессии над полностью самодостаточным JWT.

### Когда выбирать

Сессия в HttpOnly cookie — хороший default для обычного web-приложения, особенно
если frontend и backend работают через один origin или используется BFF. Минус —
нужно хранить состояние и защищать state-changing запросы от CSRF.

---

## 6. Cookie и Bearer — это транспорт, а не стратегия

### 6.1. Cookie transport

Браузер сам прикладывает cookie. Это удобно, но именно автоматическая отправка
создаёт CSRF-риск:

```http
POST /transfer
Cookie: session=...
```

Чужой сайт может попытаться заставить браузер отправить такой запрос. Защита:
SameSite как дополнительный слой, CSRF token/double-submit token и проверка Origin.
OWASP подчёркивает: XSS может обойти CSRF-защиту, поэтому XSS нужно устранять отдельно.

### 6.2. Bearer transport

Клиент явно добавляет credential:

```http
GET /api/orders
Authorization: Bearer eyJ...
```

Любой, кто владеет bearer token, обычно может им пользоваться. RFC 6750 поэтому
требует TLS и осторожного обращения с токеном.

```javascript
const response = await fetch('/api/orders', {
  headers: { Authorization: `Bearer ${accessToken}` },
});
```

Плюсы: работает с CLI, mobile и server-to-server; CSRF от автоматической cookie
отсутствует. Минусы: необходимо безопасно хранить токен и не допускать утечки в
логи, URL, browser history, `localStorage` и `sessionStorage`.

OWASP рекомендует не хранить authentication tokens, session IDs, JWT и refresh
токены в `localStorage`/`sessionStorage`: любой JavaScript в origin может их прочитать.
Для браузера предпочтительны HttpOnly cookie или BFF; access token в памяти —
компромисс, но XSS всё равно может выполнять действия от имени страницы.

### 6.3. Нельзя передавать credential в URL

Плохо:

```http
GET /api/orders?access_token=secret
```

Токен окажется в истории браузера, access logs, proxy logs и иногда в `Referer`.
Используйте cookie или `Authorization` header.

---

## 7. Opaque token и JWT: две модели access token

### 7.1. Opaque/reference token

```text
access_token = "random-long-string"
```

Resource Server спрашивает Authorization Server или общий store:

```text
GET /introspection
  token=random-long-string

→ active=true, sub=42, scope="orders:read"
```

Плюсы: отзыв и изменение прав действуют сразу; payload не виден клиенту.
Минусы: дополнительный сетевой запрос или кэш, зависимость от хранилища.

### 7.2. JWT

JWT — компактный подписанный формат claims, например:

```json
{
  "iss": "https://id.example.com",
  "sub": "user-42",
  "aud": "orders-api",
  "scope": "orders:read",
  "iat": 1780000000,
  "exp": 1780000900,
  "jti": "unique-token-id"
}
```

JWT состоит из `header.payload.signature`. Base64url — это кодирование, не шифрование:
payload можно прочитать. Подпись защищает целостность, но не конфиденциальность.

Проверка должна включать allow-list алгоритмов и как минимум:

```python
claims = verify_signature(
    token,
    key=trusted_key,
    algorithms=["RS256"],       # алгоритм не берём из непроверенного token header
)
assert claims["iss"] == "https://id.example.com"
assert claims["aud"] == "orders-api"
assert claims["exp"] > now_timestamp()
assert required_scope in claims.get("scope", "").split()
```

JWT не обязательно лучше сессии. Его плюсы — локальная проверка, горизонтальное
масштабирование, удобная передача claims. Минусы — отзыв сложнее, украденный токен
живёт до `exp`, размер больше, ошибки проверки `iss`/`aud`/`alg` опасны.

JWT не даёт магического logout. Если сервер не проверяет blacklist/introspection,
удаление JWT у клиента не делает уже выданный токен недействительным. Практические
варианты: короткий TTL, refresh-token rotation, revocation store, key rotation,
introspection или stateful session.

### 7.3. Подпись и шифрование — разные вещи

- JWS/JWT signature: «токен не изменили»;
- JWE/encryption: «содержимое нельзя прочитать».

Не кладите в обычный JWT пароль, секрет, персональные данные, которые нельзя раскрывать,
или единственный источник критичных прав без серверной проверки.

---

## 8. OAuth 2.0: делегирование доступа к API

OAuth — не протокол «проверить пароль приложения». Он описывает, как Resource Owner
разрешает Client получить access token для Resource Server через Authorization Server.

Роли:

```text
Resource Owner  — пользователь или владелец ресурса
Client          — приложение, действующее от имени owner
Authorization Server — выдаёт tokens и управляет consent
Resource Server — API, проверяющее access token
```

OAuth отвечает на вопрос: **«может ли это приложение вызвать данный API с такими scope?»**

### 8.1. Authorization Code + PKCE — основной flow для пользователя

Используется для SPA, desktop и mobile public clients; также полезен для web apps.
Упрощённая последовательность:

```text
1. Client создаёт случайные code_verifier и state.
2. code_challenge = BASE64URL(SHA256(code_verifier)).
3. Client отправляет browser на Authorization Endpoint.
4. Authorization Server аутентифицирует пользователя и получает consent.
5. AS возвращает короткоживущий code на заранее зарегистрированный redirect_uri.
6. Client меняет code + code_verifier на access token.
7. Resource Server принимает access token.
```

Запрос авторизации:

```http
GET https://id.example/authorize?
    response_type=code&
    client_id=spa-client&
    redirect_uri=https%3A%2F%2Fapp.example%2Fcallback&
    scope=openid%20orders:read&
    state=RANDOM_STATE&
    code_challenge=BASE64URL_SHA256(verifier)&
    code_challenge_method=S256
```

Обмен:

```http
POST https://id.example/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&
client_id=spa-client&
code=ONE_TIME_CODE&
redirect_uri=https%3A%2F%2Fapp.example%2Fcallback&
code_verifier=ORIGINAL_RANDOM_VERIFIER
```

RFC 9700 требует для Authorization Server поддержки PKCE; `S256` — предпочтительный
метод. Redirect URI сопоставляется точно, а не «по началу строки». `state` защищает
от CSRF, если PKCE не обеспечивает нужную защиту; в OIDC дополнительно используется
`nonce`.

### 8.2. Что больше не следует применять

**Implicit Grant** (`response_type=token`) не рекомендуется: access token попадает
в redirect response/URL и повышается риск утечки через history, referer и неправильные
redirects. Используйте code flow.

**Resource Owner Password Credentials Grant** (password grant) запрещён актуальной
best practice RFC 9700: приложение получает пароль пользователя напрямую, расширяет
места утечки, плохо сочетается с MFA и WebAuthn. Наличие поля `username/password`
в форме login — не причина строить новый OAuth password flow.

### 8.3. Client Credentials — server-to-server

Когда нет пользователя и один сервис вызывает другой:

```bash
curl -u orders-worker:CLIENT_SECRET \
  -d 'grant_type=client_credentials&scope=orders:write' \
  https://id.example/token
```

Ответ содержит access token для identity сервиса, а не человека. Для confidential
clients лучше применять асимметричную аутентификацию: mTLS или `private_key_jwt`,
если инфраструктура это поддерживает. Секрет клиента не должен попадать в frontend,
мобильное приложение или публичный репозиторий.

---

## 9. OpenID Connect: когда OAuth нужен для входа пользователя

OAuth сам по себе говорит о доступе к ресурсу, а не о том, как приложение надёжно
узнало личность пользователя. **OpenID Connect (OIDC)** — identity layer поверх OAuth.

Клиент запрашивает scope `openid` и получает:

- **ID Token** — JWT с утверждениями о результате аутентификации;
- **Access Token** — credential для API/UserInfo, его нельзя путать с ID Token;
- иногда Refresh Token.

```text
OAuth:  «этому client разрешён доступ к orders API»
OIDC:   «этот пользователь аутентифицирован у этого OpenID Provider»
```

ID Token валидируют по `iss`, `aud`, `exp`, `nonce`, подписи и требованиям конкретного
OIDC flow. Нельзя отправлять ID Token в API вместо access token только потому, что оба
выглядят как JWT.

Типичный «Войти через Google/Microsoft/корпоративный IdP» — это OIDC, если используется
OIDC. Enterprise SSO также может использовать SAML 2.0.

---

## 10. SAML 2.0: корпоративный федеративный SSO

SAML передаёт XML assertions между Identity Provider (IdP) и Service Provider (SP),
обычно через браузерные redirects и POST. Он широко используется в enterprise,
intranet, AD/LDAP-интеграциях и старых корпоративных продуктах.

```text
Пользователь → SP → IdP
IdP аутентифицирует пользователя
IdP подписывает SAML Response
SP проверяет подпись, issuer, audience, recipient, InResponseTo и expiry
SP создаёт локальную сессию
```

SAML и OIDC решают похожую задачу федерации, но технологически различаются:

| | OIDC | SAML 2.0 |
|---|---|---|
| Формат | JSON/JWT | XML/signature |
| Типичная среда | web, mobile, современные API | enterprise SSO, legacy, intranet |
| Что получает приложение | ID Token + claims | SAML Assertion |
| Риски реализации | token validation, redirect, PKCE | XML Signature Wrapping, неверная проверка audience/issuer |

Не пишите SAML parser самостоятельно. Проверяйте XML signature и все ограничения
assertion библиотекой, следуя профилю провайдера. Приватные signing keys IdP —
критический актив; OWASP рекомендует защищать их, в том числе HSM в серьёзных средах.

---

## 11. MFA, 2FA и passkeys/WebAuthn

MFA требует минимум два разных фактора:

1. knowledge — пароль/PIN;
2. possession — телефон, security key, passkey;
3. inherence — биометрический признак.

Два пароля — не MFA: это один тип фактора.

MFA нужно требовать не только при входе, но и при смене пароля/email, отключении MFA,
административном повышении привилегий и рискованных транзакциях. Возможен step-up:
обычный session для чтения и повторная MFA-проверка перед переводом денег.

### WebAuthn/passkeys

WebAuthn использует challenge-response с публичным ключом:

```text
Registration:
  сервер → random challenge
  authenticator создаёт key pair, private key остаётся у authenticator
  сервер сохраняет public key + credential ID

Authentication:
  сервер → новый challenge
  authenticator подписывает challenge private key
  сервер проверяет подпись public key и origin/RP ID
```

Passkeys дают phishing-resistant authentication: credential связан с origin/Relying
Party и не требует передачи общего пароля серверу. Но сервер должен строго выполнять
WebAuthn ceremony и проверять challenge, origin, RP ID, type, sign counter и user
verification согласно спецификации.

Нельзя автоматически утверждать, что любой passkey hardware-backed или никогда не
экспортируется: synced passkeys могут иметь другую модель резервного копирования.

---

## 12. API keys, mTLS и DPoP

### API key

API key — длинный секрет, идентифицирующий приложение или интеграцию:

```http
GET /v1/data
X-API-Key: key-value
```

Подходит для простых server-to-server интеграций, quota и идентификации клиента.
Нужно обеспечить scope, rate limit, ротацию, отзыв, last-used metadata и безопасное
хранение. API key легко скопировать, поэтому OWASP не рекомендует полагаться только
на него для критичных ресурсов. Не класть ключ в URL и не коммитить в Git.

API key обычно не заменяет user authentication и не выражает интерактивный consent.

### mTLS

При mutual TLS и клиент, и сервер предъявляют сертификаты. Сервер удостоверяет
клиентский сертификат и может связать access token с ключом клиента. Это сильный
вариант для сервисов, банковских интеграций и контролируемой инфраструктуры, но
сложен для обычного browser SPA и управления сертификатами.

### DPoP

Обычный bearer token можно использовать, просто обладая строкой. DPoP добавляет
доказательство владения private key для конкретного HTTP-запроса:

```text
Client создаёт key pair
AS связывает token с public key (cnf/jkt)
Client подписывает DPoP proof: method + URL + timestamp + unique jti + token hash
Resource Server проверяет token и proof
```

DPoP уменьшает риск replay украденного токена, но не заменяет HTTPS и не спасает,
если атакующий полностью контролирует клиента.

---

## 13. Refresh tokens, expiry и отзыв

Рекомендуемый жизненный цикл для access token:

```text
короткий access token (минуты)
        ↓ истёк
refresh token → новый access token
```

Refresh token опаснее access token: он живёт дольше и позволяет получать новые
access tokens. Для public clients RFC 9700 рекомендует sender-constraining или
rotation:

```text
refresh_1 → access_2 + refresh_2
refresh_1 сразу инвалидирован
повторное использование refresh_1 → обнаружение replay и отзыв цепочки
```

Отдельно проектируют:

- TTL access и refresh token;
- отзыв одной сессии и всех сессий;
- смену пароля и отзыв старых tokens;
- key rotation и `kid`/JWKS;
- аудит refresh replay;
- idle timeout и absolute timeout;
- logout на одном устройстве и global logout.

**Logout не всегда означает revoke:**

- серверная сессия: удалить state — настоящий отзыв;
- opaque token: удалить/деактивировать в store или introspection;
- JWT без server-side проверки: клиент перестал его хранить, но уже выданный JWT
  живёт до `exp`;
- refresh rotation: можно обнаружить повторное использование и закрыть цепочку.

---

## 14. Модели авторизации: RBAC, ABAC, ReBAC и scopes

### RBAC — Role-Based Access Control

```python
if user.role == "admin":
    allow()
```

Плюсы: просто объяснить и внедрить. Минусы: роли разрастаются, когда правила зависят
от организации, объекта, времени или отношений.

### ABAC — Attribute-Based Access Control

Решение зависит от атрибутов субъекта, ресурса, действия и окружения:

```python
allow = (
    user.department == document.department
    and document.classification <= user.clearance
    and request.mfa_recent
    and request.method in user.allowed_methods
)
```

ABAC лучше подходит для динамических политик и least privilege, но требует дисциплины
в модели атрибутов и тестах.

### ReBAC — Relationship-Based Access Control

```text
allow(alice, "edit", document_42)
если alice является owner document_42
или member team document_42
```

Подходит для SaaS, совместных документов, folders, multi-tenant систем.

### OAuth scopes

Scope — грубое делегированное разрешение клиента:

```text
orders:read orders:write profile
```

Scope не заменяет object-level authorization. Наличие `orders:read` ещё не означает,
что Alice может читать **любой** заказ. Сначала проверяют scope, затем tenant,
отношение к объекту и политику доступа.

### Всегда проверяйте объект

Плохой endpoint:

```http
GET /users/42/private-data
```

Если проверяется только login, пользователь 41 может подменить `42` и получить чужие
данные — IDOR/BOLA. Сервер обязан проверять ownership/relationship именно объекта 42.

---

## 15. CSRF, XSS и CORS: не взаимозаменяемые понятия

### CSRF

Атакующий заставляет браузер отправить запрос, а браузер автоматически прикладывает
cookie. Защита: SameSite, CSRF token, Origin/Referer validation и отсутствие опасных
state-changing GET.

### XSS

Атакующий выполняет JavaScript в origin приложения. XSS может читать доступные
токены и отправлять авторизованные действия. HttpOnly cookie ограничивает чтение
cookie, но не отменяет необходимость исправить XSS.

### CORS

CORS — политика браузера, разрешающая frontend одного origin читать ответы другого.
Это не механизм authentication и не замена authorization.

Для cookie cross-origin обычно нужны:

```text
Access-Control-Allow-Origin: https://app.example
Access-Control-Allow-Credentials: true
```

Нельзя сочетать credentialed requests с бездумным `Access-Control-Allow-Origin: *`.
Для `Authorization` и custom headers браузер может выполнять preflight; сервер должен
разрешить нужные methods и headers.

---

## 16. Практический выбор по типу клиента

| Клиент | Практичный default | Главные меры |
|---|---|---|
| Web SSR / same-origin | серверная сессия + HttpOnly cookie | HTTPS, Secure, SameSite, CSRF, session rotation |
| SPA | BFF + HttpOnly cookie; либо Authorization Code + PKCE | не localStorage; exact redirect; CSP/XSS defense |
| Mobile/native | Authorization Code + PKCE | OS secure storage, короткий access, refresh rotation |
| Desktop | Authorization Code + PKCE | system browser, loopback/app redirect, не embedded login form |
| CLI | device authorization или Authorization Code + PKCE | keychain/secure file, scopes, short TTL |
| Server-to-server | Client Credentials | mTLS/private_key_jwt, scopes, audience, rotation |
| Enterprise SSO | OIDC или SAML 2.0 | доверенный IdP, строгая проверка claims/assertions |
| High-value API | opaque/JWT access + sender-constraining | mTLS или DPoP, audience restriction, audit |
| Простая интеграция | API key с ограниченными scope | vault, rotation, revocation, rate limit |

Это не догма. Выбор зависит от threat model, требований к logout/revocation,
наличия IdP, типа клиента, multi-tenancy и того, кто контролирует устройство.

---

## 17. Типичные ошибки на собеседовании и в коде

1. «JWT — это способ авторизации». Нет: JWT — формат claims; OAuth — протокол
   делегирования; cookie/Bearer — транспорт.
2. «OAuth аутентифицирует пользователя». OAuth выдаёт доступ к ресурсу; для identity
   используйте OIDC.
3. «CORS защищает API». CORS ограничивает браузерное чтение, но curl и серверный
   клиент его не обязаны соблюдать.
4. «HttpOnly полностью защищает от XSS». Он мешает украсть cookie, но XSS может
   совершать действия от имени текущей страницы.
5. «JWT logout отозвал токен». Без server-side revocation это обычно неправда.
6. «Спрячем кнопку — значит запретили действие». Authorization проверяет сервер.
7. «User ID в URL уже гарантирует безопасность». Нужна проверка прав на объект.
8. «Положим access token в localStorage». OWASP прямо предупреждает о чтении его
   любым JavaScript в origin.
9. «Сделаем свой OAuth login с password grant». RFC 9700 запрещает этот подход;
   используйте Authorization Code + PKCE.
10. «Зашифруем пароль». Пароли хешируют медленным password hashing, а не шифруют.
11. «Разрешим redirect_uri по префиксу». Нужна точная регистрация и проверка.
12. «Проверим только подпись JWT». Нужны алгоритм, `iss`, `aud`, `exp`, scopes,
   token type и назначение токена.

---

## 18. Универсальный checklist перед выпуском

### Authentication

- [ ] Пароли хешируются Argon2id/scrypt, plaintext не хранится.
- [ ] Есть rate limit, защита от credential stuffing и безопасный reset password.
- [ ] Для чувствительных действий есть MFA/step-up.
- [ ] Сессия ротируется после login и смены привилегий.
- [ ] Есть idle/absolute timeout и отзыв сессий.

### Tokens

- [ ] Access tokens короткоживущие, refresh tokens защищены rotation или sender constraint.
- [ ] JWT валидируется с фиксированным allow-list алгоритмов, `iss`, `aud`, `exp`.
- [ ] Credential не попадает в URL, логи, analytics и ошибки.
- [ ] Есть key rotation, `kid`/JWKS или понятная процедура смены ключей.
- [ ] Принято осознанное решение: JWT или opaque token.

### Authorization

- [ ] Default deny и least privilege.
- [ ] Проверка выполняется на сервере и на каждом запросе.
- [ ] Проверяются tenant, объект и relationship, а не только роль.
- [ ] Scope не принимается за object-level permission.
- [ ] Отказы и чувствительные действия попадают в audit log.

### Browser/API

- [ ] HTTPS везде, cookie имеют Secure/HttpOnly/SameSite.
- [ ] Cookie-auth защищена от CSRF.
- [ ] XSS mitigations: output encoding, CSP, безопасная работа с DOM.
- [ ] CORS ограничен точными origins и не используется как access control.
- [ ] Mobile/SPA используют Authorization Code + PKCE, не Implicit/password grant.

---

## 19. Источники

Источники ниже — нормативные документы и материалы организаций, а не пересказы блогов.
Доступ и проверка ссылок: **24 сентября 2026 года**, поиск выполнен через Tavily.

### IETF / RFC

- [RFC 9700 — Best Current Practice for OAuth 2.0 Security](https://www.rfc-editor.org/rfc/rfc9700.html) — PKCE, exact redirect URI, запрет Implicit и Password grant, refresh rotation, sender-constrained tokens, scopes и client authentication.
- [RFC 7636 — Proof Key for Code Exchange by OAuth Public Clients](https://www.rfc-editor.org/rfc/rfc7636.html) — `code_verifier`, `code_challenge`, метод `S256`.
- [RFC 6749 — The OAuth 2.0 Authorization Framework](https://www.rfc-editor.org/rfc/rfc6749.html) — роли, endpoints и authorization flows.
- [RFC 6750 — OAuth 2.0 Bearer Token Usage](https://www.rfc-editor.org/rfc/rfc6750.html) — Bearer в HTTP и требования к защите токенов.
- [RFC 8705 — OAuth 2.0 Mutual-TLS Client Authentication and Certificate-Bound Access Tokens](https://www.rfc-editor.org/rfc/rfc8705.html) — mTLS и привязка токена к сертификату.
- [RFC 9449 — OAuth 2.0 Demonstrating Proof of Possession](https://www.rfc-editor.org/rfc/rfc9449.html) — DPoP и proof-of-possession.
- [RFC 7519 — JSON Web Token](https://www.rfc-editor.org/rfc/rfc7519.html) — формат JWT.

### OAuth / OpenID

- [OpenID Connect Core 1.0](https://openid.net/specs/openid-connect-core-1_0.html) — identity layer поверх OAuth, ID Token, UserInfo и claims.
- [OpenID Foundation: How OpenID Connect Works](https://openid.net/developers/how-connect-works) — объяснение ролей и потока входа.

### OWASP

- [Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) — пароли, MFA, SAML, authentication controls.
- [Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) — Argon2id, scrypt, bcrypt и параметры hashing.
- [Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) — session IDs, cookie flags, browser storage и timeout.
- [Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html) — deny-by-default, least privilege, ABAC/RBAC/ReBAC, object-level checks.
- [OAuth 2.0 Protocol Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html) — OAuth threats, DPoP, refresh rotation и scopes.
- [CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) — CSRF tokens, SameSite и ограничения защиты.
- [REST Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html) — HTTPS, API keys, JWT, rate limit и API security.
- [SAML Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SAML_Security_Cheat_Sheet.html) — signature validation и защита SAML keys.

### W3C

- [Web Authentication: WebAuthn Level 3](https://www.w3.org/TR/webauthn-3/) — public-key credentials, registration/authentication ceremonies и passkeys.
