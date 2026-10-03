# 11. Как браузер обращается к backend: React, HTTP, fetch, cookies и CSRF

Это учебное пособие отвечает на четыре связанных вопроса:

1. когда React обращается к API и что именно делает `fetch`;
2. какие ещё механизмы браузер использует для сетевого доступа;
3. где должна находиться настоящая защита доступа;
4. что такое CSRF, почему он связан с cookie и как выбирать защиту.

Документ одновременно объясняет общую веб-модель и показывает фактическую реализацию
этого проекта. Если нужно быстро найти конкретный код, сначала прочитайте раздел 8.
Если нужно подготовиться к собеседованию, переходите к разделам 4, 9 и 13.

> Рекомендации и ссылки в этом документе сверены с MDN, OWASP, FastAPI и
> fastapi-users через Tavily 26 сентября 2026 года. Документ не заменяет security
> review production-приложения: конкретная защита зависит от доменов, прокси,
> threat model и типа клиента.

---

## 1. Сначала разделим четыре слоя

В разговорах о «фронтенде и API» часто смешивают разные вещи. Удобно разложить их
по слоям:

```text
React-компонент
    ↓ решает, когда нужно получить или отправить данные
API-клиент
    ↓ формирует HTTP-запрос
браузер
    ↓ применяет правила cookies, Same-Origin Policy, CORS и отправляет запрос
HTTP
    ↓ метод, URL, headers, body, cookies
backend
    ↓ аутентифицирует запрос и проверяет права
база данных / бизнес-логика
```

### 1.1. React не является сетью

React отвечает за состояние и отображение интерфейса. Он не «ходит в API» сам по себе.
Сетевой запрос появится только потому, что код приложения вызвал браузерный API:

```ts
const response = await fetch('/users/me');
```

или, например, создал `WebSocket`, `EventSource`, отправил форму либо изменил `src`
у ресурса.

Переход по адресу `/account` внутри `BrowserRouter` обычно только меняет компонент,
который отображается. Но этот компонент может выполнить `useEffect()` и уже из него
вызвать API:

```text
клик по ссылке /account
    → React Router меняет маршрут без полной загрузки HTML
    → AccountPage монтируется
    → useEffect() вызывает GET /users/me
    → React получает JSON и строит интерфейс
```

Поэтому нужно различать:

- **навигацию внутри SPA** — изменение состояния маршрутизатора;
- **запрос за данными** — отдельный HTTP-запрос к backend;
- **загрузку документа** — запрос браузера за `index.html` при холодном заходе;
- **загрузку ресурсов** — запросы за JS, CSS, изображениями и шрифтами.

### 1.2. HTML и JSON — разные ответы

При холодном заходе браузер может получить:

```http
GET /account HTTP/1.1
Accept: text/html
```

В этом проекте SPA catch-all возвращает `frontend/dist/index.html`, если путь не является
API-путём. React загружается, а затем сам решает, какую страницу показать.

Данные аккаунта приходят другим ответом:

```http
GET /users/me HTTP/1.1
Accept: application/json

HTTP/1.1 200 OK
Content-Type: application/json

{"id":"...","email":"student@example.com","username":"student"}
```

`index.html` не является ответом на `GET /users/me`, а JSON аккаунта не является
HTML-страницей. Для понимания SPA это принципиальное разделение.

---

## 2. Из чего состоит HTTP-запрос

Любой вызов API в конечном счёте превращается в HTTP-запрос. У него есть:

```text
метод       GET / POST / PATCH / PUT / DELETE
URL         /users/me
заголовки   Content-Type, Accept, Authorization, Origin ...
credentials Cookie или другие данные аутентификации
body        JSON, form-urlencoded, multipart или пустое тело
```

Пример регистрации из текущего проекта:

```http
POST /auth/register HTTP/1.1
Content-Type: application/json
Accept: */*

{"email":"student@example.com","password":"password123"}
```

Пример login:

```http
POST /auth/cookie/login HTTP/1.1
Content-Type: application/x-www-form-urlencoded

username=student%40example.com&password=password123
```

После успешного login backend возвращает не JSON с JWT, а примерно такой ответ:

```http
HTTP/1.1 204 No Content
Set-Cookie: auth=<JWT>; Max-Age=86400; HttpOnly; SameSite=Lax; Path=/
Set-Cookie: csrf_token=<nonce>.<signature>; Max-Age=86400; SameSite=Lax; Path=/
```

Вместе с `auth` сервер устанавливает cookie `csrf_token` (без `HttpOnly`, чтобы SPA
мог прочитать её через `document.cookie`). Значение подписано HMAC-SHA256 — это Signed
Double Submit Cookie (см. `auth_users/csrf.py`).

Затем браузер самостоятельно отправляет cookie:

```http
GET /users/me HTTP/1.1
Cookie: auth=<JWT>
```

JavaScript не обязан и не должен извлекать JWT из этой cookie.

---

## 3. `fetch`: что это и чего он не делает

`fetch()` — браузерный JavaScript API для выполнения HTTP-запросов. Он возвращает
Promise с объектом `Response`:

```ts
const response = await fetch('/users/me');

if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
}

const user = await response.json();
```

`fetch` умеет:

- выбрать HTTP-метод;
- указать заголовки;
- передать тело запроса;
- указать режим credentials;
- получить статус, заголовки и тело ответа;
- отменить запрос через `AbortController`;
- работать с потоками и бинарными данными.

`fetch` **не является авторизацией**. Он не решает:

- имеет ли пользователь право читать данные;
- можно ли ему менять конкретный заказ;
- является ли cookie действительной;
- нужно ли требовать CSRF-токен;
- можно ли доверять входным данным.

Это только способ попросить браузер отправить HTTP-запрос.

### 3.1. Что делает `credentials: 'include'`

В текущем API-клиенте есть центральная строка:

```ts
async function request(path: string, init: RequestInit = {}): Promise<Response> {
    return fetch(path, { credentials: 'include', ...init });
}
```

`credentials` относится к credentials браузера: прежде всего cookies, а также к
некоторым другим данным аутентификации.

Значения:

| Значение | Смысл |
|---|---|
| `omit` | не отправлять credentials и не учитывать `Set-Cookie` в ответе |
| `same-origin` | отправлять credentials только для same-origin; значение по умолчанию |
| `include` | разрешить credentials и для cross-origin-запросов, если остальные правила браузера это допускают |

Для текущего same-origin production-сценария `include` явно подчёркивает, что login
может установить cookie, а следующие запросы могут её отправить.

Важно: `credentials: 'include'` не отменяет `SameSite`. Если cookie имеет `SameSite=Lax`
или `SameSite=Strict`, браузер всё равно не отправит её в запрещённом cross-site
сценарии.

Важно и другое: JavaScript не может прочитать заголовок `Set-Cookie` через
`response.headers.get('set-cookie')`. Это запрещённый для frontend кодов response
header. Браузер обрабатывает `Set-Cookie` сам.

### 3.2. Обёртки текущего проекта

`frontend/src/api/client.ts` предоставляет несколько функций:

```text
getJson()        → GET, ожидается JSON
postJson()       → POST + application/json
postForm()       → POST + application/x-www-form-urlencoded
postMultipart()  → POST + FormData
```

Это не четыре разных сетевых протокола. Все они используют один внутренний `fetch`.
Различается способ формирования тела и `Content-Type`.

Пример регистрации:

```ts
export function register(body: { email: string; password: string }): Promise<User> {
    return postJson<User>('/auth/register', body);
}
```

Пример login:

```ts
export function login(body: { email: string; password: string }): Promise<User> {
    const form = new URLSearchParams({
        username: body.email,
        password: body.password,
    });

    return postForm<unknown>('/auth/cookie/login', form)
        .then(() => getJson<User>('/users/me'));
}
```

Login здесь состоит из двух запросов:

```text
POST /auth/cookie/login
    ← 204 + Set-Cookie: auth=...

GET /users/me
    → браузер приложил auth автоматически
    ← 200 + UserRead
```

---

## 4. Когда именно текущий frontend вызывает API

### 4.1. Проверка при старте приложения

`AuthProvider` в `frontend/src/context/AuthContext.tsx` при монтировании вызывает
`refresh()`, а тот вызывает `getCurrentUser()`:

```text
main.tsx
  → AuthProvider
      → useEffect()
          → refresh()
              → getCurrentUser()
                  → GET /users/me
```

Результаты:

- `200` — cookie распознана, объект пользователя помещается в `AuthContext.user`;
- `401` — пользователь считается анонимным;
- ошибка сети — текущий код также сбрасывает состояние в `null`.

В `AuthContext.user` хранится объект пользователя для интерфейса. JWT там не хранится.

### 4.2. Регистрация

Страница `RegisterPage` делает только один прикладной запрос:

```text
POST /auth/register
Content-Type: application/json

{"email":"...","password":"..."}
```

Регистрация не выдаёт cookie. После успешного ответа frontend отправляет пользователя
на `/login`.

### 4.3. Вход

`LoginPage` вызывает `login()`:

```text
1. POST /auth/cookie/login
2. получить 204 и сохранить cookie силами браузера
3. GET /users/me
4. setUser(user) в React Context
5. перейти на /
```

`setUser(user)` меняет только UI-состояние. Доступ к backend всё равно определяется
cookie и серверной проверкой.

### 4.4. Страница `/protected`

`ProtectedPage` при монтировании вызывает:

```http
GET /api/v1/auth/protected
```

Backend endpoint имеет зависимость:

```python
async def protected(user: Annotated[User, Depends(active_user)]):
```

Если cookie отсутствует или JWT недействителен, `active_user` не передаст управление
обработчику и backend вернёт `401`.

### 4.5. Аккаунт

`AccountPage` сначала делает:

```http
GET /users/me
```

При сохранении формы:

```http
POST /auth/account
Content-Type: application/x-www-form-urlencoded

username=newname&email=new@example.com
```

Это изменяющая состояние операция. Она должна быть защищена не только UI-guard, но и
backend-проверками аутентификации, авторизации и CSRF-механизмом, если выбранная
cookie-модель этого требует.

### 4.6. Выход

Кнопка выхода вызывает:

```http
POST /auth/cookie/logout
```

Backend возвращает инструкцию удалить cookie. Затем React делает `setUser(null)`.
При JWT-стратегии это удаляет cookie браузера, но само по себе не отзывает копию уже
выданного JWT на сервере.

---

## 5. Какие ещё механизмы браузера обращаются к backend

`fetch` — не единственный механизм. Важно знать не только названия, но и сценарии,
для которых они предназначены.

### 5.1. Обычная навигация и ссылки

```html
<a href="/account">Аккаунт</a>
```

Браузер отправляет запрос за документом. Обычно это полноценная навигация и загрузка
новой страницы. В SPA React Router перехватывает ссылку и меняет маршрут без полной
перезагрузки, если ссылка оформлена через `Link`.

### 5.2. HTML-форма

```html
<form method="post" action="/profile">
    <input name="username">
    <button type="submit">Сохранить</button>
</form>
```

Браузер сам создаёт `POST`, без JavaScript `fetch`. Это важная деталь для CSRF: чужая
страница тоже может попытаться отправить HTML-форму на ваш сайт.

### 5.3. `XMLHttpRequest`

`XMLHttpRequest` — более старый API для асинхронных HTTP-запросов. Он всё ещё
поддерживается, но современный прикладной код обычно выбирает `fetch`.

```js
const xhr = new XMLHttpRequest();
xhr.open('GET', '/users/me');
xhr.onload = () => console.log(xhr.responseText);
xhr.send();
```

Для cookies у XHR используется `withCredentials = true`, а не
`credentials: 'include'`:

```js
const xhr = new XMLHttpRequest();
xhr.open('GET', 'https://api.example.test/users/me');
xhr.withCredentials = true;
xhr.send();
```

`fetch` и XHR подчиняются политике same-origin и CORS.

### 5.4. `EventSource` и Server-Sent Events

SSE — длительное HTTP-соединение, по которому сервер отправляет события браузеру.
Это удобно для уведомлений, ленты событий или статуса фоновой задачи.

```js
const source = new EventSource('/events');
source.onmessage = (event) => {
    console.log(event.data);
};
```

SSE в основном однонаправленный: сервер отправляет данные, а клиент не посылает
сообщения через тот же поток. Для credentials есть режим `withCredentials` в
конструкторе, если это требуется для cross-origin-сценария.

### 5.5. `WebSocket`

WebSocket создаёт двустороннее соединение. После handshake клиент и сервер могут
обмениваться сообщениями без отдельного HTTP-запроса на каждое сообщение.

```js
const socket = new WebSocket('wss://example.test/live');
socket.onmessage = (event) => console.log(event.data);
socket.send(JSON.stringify({ type: 'ping' }));
```

WebSocket не используется в текущем frontend-проекте. Для его защиты нужно отдельно
проверять `Origin`, аутентификацию на handshake и права на каждое сообщение. Нельзя
считать WebSocket защищённым только потому, что соединение однажды прошло login.

### 5.6. Автоматические запросы за ресурсами

Браузер делает запросы, когда встречает:

```html
<script src="/assets/index.js"></script>
<link rel="stylesheet" href="/assets/index.css">
<img src="/assets/logo.png">
```

Также запросы могут появляться из CSS, `<video>`, `<iframe>`, service worker и других
механизмов. Это сетевой доступ, но не обязательно «вызов API из React».

### 5.7. `sendBeacon`

`navigator.sendBeacon()` предназначен для небольшой фоновой отправки данных, например
статистики при уходе со страницы. Он не является заменой обычному API-клиенту и не
подходит для операций, где нужно обработать подробный ответ сервера.

### 5.8. Что используется в этом проекте

В прикладном коде `frontend/src/` используется:

- `fetch` для API-запросов;
- обычные browser-запросы за SPA и static assets;
- React Router для SPA-навигации.

В проверенных файлах текущего frontend не используются `XMLHttpRequest`, `WebSocket`
или `EventSource`.

---

## 6. Аутентификация, авторизация и UI-guard — три разные вещи

### 6.1. Аутентификация

Аутентификация отвечает на вопрос:

> Кто отправил запрос?

В текущем проекте backend:

1. получает cookie `auth`;
2. извлекает JWT;
3. проверяет подпись и срок действия;
4. получает идентификатор пользователя;
5. загружает пользователя из базы;
6. проверяет `active_user`.

### 6.2. Авторизация

Авторизация отвечает на вопрос:

> Имеет ли этот пользователь право выполнить именно эту операцию с именно этим ресурсом?

Пример:

```text
Alice authenticated → да
Alice может читать заказ 42 → нужно проверить отдельно
Alice может удалить заказ 42 → нужно проверить ещё одно правило
```

Проверка «пользователь вошёл» не равна проверке ownership, роли, tenant или scope.

### 6.3. UI-guard

`RequireAuth` в `frontend/src/App.tsx` смотрит на `AuthContext.user` и решает,
показывать ли защищённую страницу или перенаправить на `/login`.

Это полезно для UX, но не является security boundary:

- пользователь может вызвать API через DevTools;
- запрос можно отправить через curl или Postman;
- frontend-код можно изменить;
- скрытая кнопка не скрывает HTTP endpoint.

Настоящая граница находится в backend endpoint и его dependencies.

### 6.4. Правило backend

Каждый endpoint должен явно попасть в одну из категорий:

```text
public:
  login, register, health check, публичный каталог

authenticated:
  данные текущего пользователя, личный кабинет

authorized:
  операция разрешена только роли/владельцу/tenant
```

Решение должно приниматься на сервере. OWASP рекомендует deny-by-default и проверку
прав на каждом запросе.

### 6.5. Что видно в текущем проекте

`GET /api/v1/auth/protected` защищён через `Depends(active_user)`. Но демонстрационные
маршруты в `fastapi-application/ex_order_product/router_order_one.py` в текущем коде
не имеют такой зависимости. Поэтому нельзя говорить «всё API авторизовано» только
потому, что в React есть защищённая страница.

Это учебный пример открытых маршрутов заказов, но в production для каждого маршрута
нужно отдельно принять решение о публичности и правах.

---

## 7. Cookie-аутентификация текущего проекта

### 7.1. Где собирается схема

`fastapi-application/auth_users/auth_backend.py` соединяет:

```text
CookieTransport + JWTStrategy
```

`CookieTransport` отвечает за конверт передачи токена:

```text
Set-Cookie при login
Cookie при следующих запросах
удаление cookie при logout
```

`JWTStrategy` отвечает за создание и проверку содержимого JWT.

### 7.2. Полный поток

```text
[1] LoginPage
      │
      ▼
[2] fetch POST /auth/cookie/login
      │ username=email, password=...
      ▼
[3] FastAPI Users проверяет пароль
      │
      ▼
[4] JWTStrategy создаёт подписанный JWT
      │
      ▼
[5] CookieTransport возвращает Set-Cookie: auth=...
      │
      ▼
[6] Браузер сохраняет HttpOnly-cookie
      │
      ▼
[7] fetch GET /users/me
      │ браузер сам добавляет Cookie: auth=...
      ▼
[8] backend проверяет JWT и загружает User
      │
      ▼
[9] React сохраняет объект User в AuthContext
```

### 7.3. Почему JWT не лежит в `localStorage`

В текущем варианте JavaScript не получает строку JWT и не сохраняет её в
`localStorage`/`sessionStorage`. Это уменьшает риск простой кражи токена через
JavaScript при XSS.

Но `HttpOnly` не означает «XSS не опасен». Если вредоносный скрипт уже выполняется в
origin приложения, он может вызвать `fetch('/auth/account', { method: 'POST', ... })`,
а браузер может приложить cookie. Поэтому нужны и защита от XSS, и CSRF-модель.

### 7.4. Ключевые cookie-флаги

| Флаг | Зачем |
|---|---|
| `HttpOnly` | не давать JavaScript прочитать значение cookie |
| `Secure` | отправлять только по HTTPS |
| `SameSite=Lax` | ограничить отправку cookie в cross-site сценариях |
| `Path=/` | указать область URL, к которой относится cookie |
| `Max-Age` | срок хранения cookie браузером |

Текущий `cookie_secure=False` нужен для локального HTTP. В production с HTTPS его
нужно включать. Dev-секрет `dev-insecure-secret-key-change-me` также нельзя оставлять
в production.

---

## 8. Same-origin, origin, site и CORS

### 8.1. Что такое origin

Origin состоит из трёх частей:

```text
scheme + host + port
```

Например:

```text
http://localhost:5173
http://localhost:8000
```

Это разные origin, потому что отличаются порты.

```text
https://app.example.com
https://api.example.com
```

Это тоже разные origin, потому что отличаются host.

### 8.2. Same-origin Policy

Браузер не даёт JavaScript произвольно читать ответы чужого origin. Это ограничение
браузера, а не firewall и не backend authorization.

Серверный `curl` или Python-клиент обычно не соблюдают CORS: они могут отправить
запрос независимо от того, есть ли `Access-Control-Allow-Origin`.

### 8.3. CORS

CORS — механизм, которым сервер сообщает браузеру:

> этому frontend origin разрешено читать мои ответы.

Пример для cookie cross-origin:

```http
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Credentials: true
```

Нельзя использовать:

```http
Access-Control-Allow-Origin: *
Access-Control-Allow-Credentials: true
```

для credentialed-запросов. Браузеру нужен конкретный разрешённый origin.

Если запрос нестандартный, браузер может сначала отправить preflight:

```http
OPTIONS /auth/account
Origin: https://app.example.com
Access-Control-Request-Method: POST
Access-Control-Request-Headers: content-type, x-csrf-token
```

Сервер должен разрешить именно нужные origin, методы и заголовки.

### 8.4. CORS не равен CSRF

| Вопрос | CORS | CSRF |
|---|---|---|
| Главная задача | можно ли frontend прочитать cross-origin-ответ | можно ли заставить браузер выполнить нежелательное действие |
| Где действует | главным образом в браузере | на серверной модели state-changing запросов |
| Защищает от curl | нет смысла: curl не обязан соблюдать CORS | серверная проверка должна отказать и curl без нужного токена |
| Заменяет authorization | нет | нет |
| Связан с cookie | влияет на cross-origin credentials | автоматическая cookie — причина риска |

Можно иметь корректный CORS и всё ещё ошибиться в CSRF. Можно закрыть CSRF-токеном
изменяющие операции и всё ещё неправильно реализовать authorization.

### 8.5. Текущая архитектура

В production собранный frontend и API раздаются одним ASGI-приложением. Это удобная
same-origin схема.

В `frontend/vite.config.ts` dev proxy сейчас описан для `/api`. Auth-вызовы используют
`/auth/...` и `/users/me`, поэтому при запуске frontend только на `localhost:5173`
нужно отдельно проверить dev-маршрутизацию этих путей. Наличие proxy для `/api` не
означает автоматический proxy для `/auth` и `/users`.

---

## 9. CSRF: понятное объяснение

### 9.1. Определение

CSRF — это атака, при которой злоумышленник заставляет браузер уже вошедшего
пользователя отправить запрос на ваш сайт. Браузер может автоматически приложить
cookie, поэтому backend увидит запрос как авторизованный.

Атакующему не обязательно читать ответ. Для CSRF достаточно, чтобы запрос изменил
состояние: создал заказ, изменил email, удалил объект или сменил настройки.

Уязвимость особенно вероятна, если одновременно выполняются условия:

1. запрос изменяет состояние;
2. authentication основана на автоматически отправляемой cookie;
3. запрос можно предсказать или сформировать без дополнительного доказательства намерения пользователя.

### 9.2. Пример атаки формой

На вредоносном сайте может оказаться форма:

```html
<form action="https://shop.example.test/auth/account" method="post">
    <input type="hidden" name="username" value="attacker-controlled">
    <input type="hidden" name="email" value="attacker@example.test">
</form>
<script>
    document.forms[0].submit();
</script>
```

Если браузер отправит cookie `auth`, backend может увидеть запрос от авторизованного
пользователя. Вредоносный сайт не обязан иметь доступ к JSON-ответу, чтобы изменение
состояния уже произошло.

### 9.3. Что CSRF не означает

CSRF — это не:

- кража пароля;
- чтение cookie `HttpOnly`;
- SQL injection;
- CORS error;
- XSS.

Но угрозы могут усиливать друг друга. XSS обычно позволяет выполнить действия от имени
пользователя и может обойти многие CSRF-механизмы, поэтому нельзя «лечить XSS только
CSRF-токеном».

---

## 10. Нужен ли CSRF в текущем проекте

**Текущий код проекта**: CSRF-защита реализована через Signed Double Submit Cookie
в `fastapi-application/auth_users/csrf.py` (`CSRFMiddleware`).

Как это работает:

- после успешного `POST /auth/cookie/login` (204) middleware устанавливает cookie
  `csrf_token` со значением формата `<nonce>.<HMAC-SHA256-signature>`;
- cookie `csrf_token` не имеет флага `HttpOnly` — SPA читает её через
  `document.cookie`;
- для state-changing запросов (POST/PUT/PATCH/DELETE), если присутствует auth-cookie,
  middleware требует заголовок `X-CSRF-Token`, значение которого точно совпадает
  с cookie `csrf_token`, а подпись валидна;
- наличие заголовка `Authorization: Bearer` не освобождает от CSRF-проверки, если
  auth-cookie тоже присутствует (защита от смешанного обхода);
- после успешного `POST /auth/cookie/logout` cookie `csrf_token` удаляется.

Правильная формулировка для документации и собеседования:

> Текущая same-origin-схема с `SameSite=Lax` снижает CSRF-риск, а явная защита
> реализована через Signed Double Submit Cookie (`CSRFMiddleware` в
> `auth_users/csrf.py`). State-changing cookie-запросы требуют `X-CSRF-Token`.
> Bearer-запросы без auth-cookie CSRF-проверку не проходят.

<!-- Историческая пометка: до реализации CSRFMiddleware документация утверждала,
что отдельного CSRF-токена нет. Это устаревший прежний контракт. -->

### 10.1. Когда риск ниже

Риск ниже, если:

- frontend и backend работают через один origin;
- cookie имеет `SameSite=Lax` или `Strict`;
- state-changing операции используют `POST`/`PATCH`/`DELETE`, а не `GET`;
- backend проверяет `Origin` и права пользователя;
- нет cross-site embedding/legacy-сценариев;
- отсутствует XSS.

«Риск ниже» не означает «доказано, что уязвимости нет».

### 10.2. Когда CSRF-защита особенно нужна

Явная защита особенно важна, если:

- frontend и API находятся на разных sites или должны поддерживать cross-site cookie;
- используется `SameSite=None; Secure`;
- приложение меняет email, пароль, платёжные данные или права;
- сервер принимает form-urlencoded или multipart-запросы;
- есть legacy-браузеры или сложная интеграция с iframe;
- требования безопасности требуют defense in depth.

---

## 11. Как реализуют CSRF-защиту

Нет единственного универсального варианта. Для API на JavaScript обычно выбирают
явный токен в custom header и проверяют его на backend.

### 11.1. Вариант A: synchronizer token

Сервер хранит CSRF-токен вместе с сессией и отдаёт frontend непредсказуемое значение:

```text
GET /auth/csrf
    ← {"csrf_token":"random-value"}
```

Frontend отправляет его в изменяющем запросе:

```http
POST /auth/account
Cookie: auth=<HttpOnly JWT>
X-CSRF-Token: random-value
Content-Type: application/x-www-form-urlencoded
```

Backend проверяет токен до выполнения операции.

Для stateless JWT-cookie этот вариант требует дополнительного серверного состояния:
связать CSRF-токен с сессией пользователя, JWT `jti` или другим идентификатором.

### 11.2. Вариант B: double-submit cookie

Сервер выдаёт отдельную CSRF-cookie, а frontend читает её и повторяет значение в
заголовке:

```text
Set-Cookie: csrf_token=random-value; Secure; SameSite=Lax
```

```http
X-CSRF-Token: random-value
```

Backend сравнивает cookie и header. Для серьёзного приложения токен должен быть
непредсказуемым и криптографически связанным с сессией, а не просто копироваться без
проверки. Наивный double-submit вариант слабее подписанного варианта.

Плюс: cookie `csrf_token` не должна быть `HttpOnly`, иначе JavaScript не сможет её
прочитать. Это нормально: CSRF-токен не является authentication credential. JWT `auth`
при этом остаётся `HttpOnly`.

### 11.3. Вариант C: custom header с токеном из HTML/bootstrap

Backend может встроить CSRF-токен в HTML или initial JSON state. React читает его и
добавляет заголовок:

```ts
const csrfToken = document
    .querySelector('meta[name="csrf-token"]')
    ?.getAttribute('content');

const headers = new Headers(init.headers);
if (csrfToken && methodChangesState(init.method)) {
    headers.set('X-CSRF-Token', csrfToken);
}
```

Backend проверяет header на всех state-changing endpoints.

### 11.4. Origin и Fetch Metadata как дополнительный слой

Backend может проверять:

```text
Origin: https://app.example.com
Sec-Fetch-Site: same-origin | same-site | cross-site
```

Для чувствительных операций можно отвергать неожиданные `Origin` и `Sec-Fetch-Site`.

Но это лучше использовать как defense in depth, а не как единственную защиту:

- не все клиенты и старые браузеры ведут себя одинаково;
- некоторые запросы могут не иметь нужного заголовка;
- allowlist origins нужно поддерживать аккуратно;
- CSRF-токен лучше выражает намерение приложения.

### 11.5. Как frontend-клиент передаёт CSRF-токен

**Текущий код проекта**: frontend читает cookie `csrf_token` через `document.cookie`
и добавляет заголовок `X-CSRF-Token` к state-changing запросам. Общий клиент
(`frontend/src/api/client.ts`) использует `credentials: 'include'`, поэтому
браузер автоматически прикладывает auth-cookie и csrf_token-cookie.

Концептуальный паттерн (уже реализованный в проекте):

```ts
function readCsrfToken(): string | null {
    const match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : null;
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    const method = (init.method ?? 'GET').toUpperCase();

    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
        const csrfToken = readCsrfToken();
        if (csrfToken) {
            headers.set('X-CSRF-Token', csrfToken);
        }
    }

    return fetch(path, {
        ...init,
        headers,
        credentials: 'include',
    });
}
```

Backend (`CSRFMiddleware` в `auth_users/csrf.py`) выполняет серверную часть:

1. выдаёт подписанный `csrf_token` при cookie-login;
2. проверяет совпадение cookie и заголовка `X-CSRF-Token` + валидность HMAC-подписи;
3. отклоняет запрос (403) при отсутствии или несовпадении токена;
4. удаляет `csrf_token` при cookie-logout;
5. выполняет authentication и authorization только после CSRF-проверки.

Frontend-изменение без серверной проверки не защищает приложение — оба слоя обязательны.

### 11.6. Какие операции защищать

Обычно CSRF-проверку применяют к операциям, изменяющим состояние:

```text
POST
PUT
PATCH
DELETE
```

`GET`, `HEAD` и `OPTIONS` должны быть безопасными и не менять состояние. Если endpoint
меняет базу через `GET`, сначала исправляют HTTP-дизайн endpoint, а не пытаются
замаскировать проблему CSRF-токеном.

Login и logout тоже следует включить в анализ: они меняют состояние authentication
cookie. Для чувствительных действий аккаунта полезно дополнительно требовать повторный
пароль или MFA.

---

## 12. Почему `Content-Type` тоже имеет значение

Браузеры выделяют так называемые simple requests. Исторически cross-site HTML-форма
может отправить:

- `application/x-www-form-urlencoded`;
- `multipart/form-data`;
- `text/plain`.

Она не может произвольно добавить ваш custom header вроде `X-CSRF-Token` без механизма
CORS/preflight. Поэтому обязательный нестандартный заголовок помогает сделать запрос
труднее для простой cross-site формы.

Но это не абсолютная защита:

- CORS можно настроить слишком широко;
- custom header нужно проверять на сервере;
- `application/x-www-form-urlencoded` всё ещё используется текущим login и account;
- XSS действует внутри доверенного origin.

JSON `Content-Type` может вызвать preflight в cross-origin-сценарии, но не следует
объявлять «JSON сам по себе — CSRF-токен». Это лишь один слой браузерного поведения.

---

## 13. Готовые ответы для собеседования

### «Как React обращается к API?»

React сам не является сетевым клиентом. Обработчик события или `useEffect` вызывает
браузерный API, чаще всего `fetch`. Вызов формирует HTTP-запрос, браузер применяет
same-origin/CORS/cookie-правила, backend возвращает HTTP-ответ, а React обновляет
состояние и UI.

### «В этом проекте используется только `fetch`?»

Для прикладных API-вызовов — да, общий клиент в `frontend/src/api/client.ts` построен
на `fetch`. Но браузер обращается к backend и другими способами: обычная навигация,
HTML-формы, загрузка script/style/image, `XMLHttpRequest`, SSE через `EventSource`,
WebSocket и `sendBeacon`. В текущем frontend `XMLHttpRequest`, `EventSource` и
`WebSocket` не используются.

### «Что делает `credentials: 'include'`?»

Он говорит Fetch API учитывать credentials, в частности cookies, включая cross-origin
сценарии, если cookie, CORS и остальные браузерные правила это разрешают. В текущем
проекте это позволяет принять `Set-Cookie` после login и отправить cookie `auth` в
последующих запросах. Он не означает «всегда отправить cookie»: `SameSite` может
запретить cross-site отправку.

### «Где хранится JWT?»

В текущем проекте JWT находится в cookie `auth`, установленной backend через
`Set-Cookie`. Cookie имеет `HttpOnly`, поэтому React не читает JWT и не хранит его в
`localStorage`. Объект `user` в `AuthContext` — это данные для UI, а не токен.

### «Почему нельзя защищать API через React?»

React можно изменить или обойти. Пользователь может вызвать endpoint через curl,
DevTools или другой клиент. React guard улучшает UX, но окончательная authentication и
authorization должны проверяться на backend для каждого защищённого запроса.

### «Чем authentication отличается от authorization?»

Authentication отвечает «кто ты?». Authorization отвечает «что тебе можно?». Валидная
cookie доказывает, что запрос связан с пользователем, но не доказывает право изменить
любой объект. Для объекта нужно отдельно проверить роль, ownership, tenant, scope или
relationship.

### «Что такое CSRF?»

Это атака, при которой чужой сайт заставляет браузер вошедшего пользователя отправить
запрос на ваш сайт. Cookie прикладывается автоматически, поэтому backend может принять
подделанный запрос как авторизованный. Цель CSRF — выполнить действие; читать ответ
атакующему необязательно.

### «Защищает ли `HttpOnly` от CSRF?»

Нет. `HttpOnly` запрещает JavaScript прочитать cookie, но браузер всё ещё может
приложить её к запросу. `HttpOnly` снижает риск кражи значения cookie, а CSRF требует
отдельных мер: SameSite, CSRF-токен, Origin/Fetch Metadata и безопасный дизайн
state-changing методов.

### «`SameSite=Lax` — это полная CSRF-защита?»

Нет. Это важный слой снижения риска, но не универсальная замена CSRF-токену. Нужная
модель зависит от same-site/cross-site архитектуры, чувствительности операций и
поддерживаемых сценариев. Для `SameSite=None` явная CSRF-защита особенно важна.

### «CORS защищает от CSRF?»

Нет. CORS в основном регулирует, может ли JavaScript одного origin прочитать ответ
другого origin. Он не является общей authorization-проверкой и не гарантирует, что
cross-site state-changing запрос не будет отправлен. CSRF защищают на серверной границе
отдельной проверкой.

### «Почему Bearer часто не требует CSRF?»

Потому что браузер не прикладывает произвольный `Authorization: Bearer ...`
автоматически к запросу с чужого сайта. Клиент должен сам знать token и добавить header.
Но это переносит другую ответственность: bearer token нужно безопасно хранить, не
класть в URL, не логировать и защищать от XSS/утечек.

### «Почему logout с JWT не всегда отзывает токен?»

JWT может быть stateless: backend проверяет подпись и `exp`, не храня список выданных
токенов. Logout удаляет cookie в браузере, но ранее скопированный JWT остаётся
действительным до истечения срока. Для мгновенного revoke нужны stateful-сессии,
Database/Redis strategy, introspection или другой server-side механизм.

### «Что проверить перед production?»

Нужно проверить:

- HTTPS и `Secure` для auth-cookie;
- production secret вне репозитория;
- `HttpOnly`, `SameSite`, `Path` и область домена;
- backend authentication на каждом защищённом endpoint;
- object-level authorization и deny-by-default;
- CSRF для изменяющих cookie-запросов;
- CORS allowlist без wildcard при credentials;
- отсутствие state-changing `GET`;
- XSS-защиту, CSP и безопасную работу с DOM;
- rate limit login/register;
- TTL и revoke/refresh policy;
- отсутствие token/password/cookie в логах.

---

## 14. Сводная схема текущего проекта

```text
Холодный заход:
  browser → GET /account
            ← index.html
  browser → GET /assets/index-<hash>.js
            ← JavaScript bundle
  React   → GET /users/me через fetch
            ← 401 или текущий User

Login:
  React   → fetch POST /auth/cookie/login
            ← 204 + Set-Cookie: auth=<JWT>; HttpOnly; SameSite=Lax
  browser сохраняет cookie
  React   → fetch GET /users/me
  browser → добавляет Cookie: auth=<JWT>
            ← UserRead
  React   → setUser(user)

Protected API:
  React   → fetch GET /api/v1/auth/protected
  browser → добавляет Cookie: auth=<JWT>
  backend → active_user → JWT verification → user lookup → authorization
            ← 200 или 401

Account update:
  React   → fetch POST /auth/account
  browser → автоматически добавляет auth-cookie
  backend → auth + authorization + CSRF policy + validation
            ← 200 или отказ
```

Главная мысль:

```text
React инициирует действие.
fetch формирует запрос.
Браузер добавляет свои правила и cookies.
HTTP переносит данные.
Backend принимает окончательное security-решение.
```

---

## 15. Источники

### MDN

- [Using the Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch)
- [Request: credentials property](https://developer.mozilla.org/en-US/docs/Web/API/Request/credentials)
- [CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS)
- [Access-Control-Allow-Credentials](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Access-Control-Allow-Credentials)
- [Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie)
- [Cross-site request forgery](https://developer.mozilla.org/en-US/docs/Web/Security/Attacks/CSRF)
- [XMLHttpRequest](https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest)
- [Server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)

### OWASP

- [Cross-Site Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
- [Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [Cross Site Scripting Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [WebSocket Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html)

### Документация используемого стека

- [FastAPI: CORS](https://fastapi.tiangolo.com/tutorial/cors)
- [FastAPI Users: Authentication](https://fastapi-users.github.io/fastapi-users/latest/configuration/authentication)
- [FastAPI Users: Cookie transport](https://fastapi-users.github.io/fastapi-users/latest/configuration/authentication/transports/cookie)

### Связанные документы проекта

- [04_authorization.md](04_authorization.md) — полный auth-flow React → FastAPI → JWT-cookie;
- [07_auth_token_flow_code.md](07_auth_token_flow_code.md) — где выдаётся JWT и кто отправляет cookie;
- [08_jwt_transport_options.md](08_jwt_transport_options.md) — cookie/Bearer/custom header;
- [09_auth_tutorial.md](09_auth_tutorial.md) — общая теория authentication и authorization;
- [10_auth_transport_strategy_tutorial.md](10_auth_transport_strategy_tutorial.md) — транспорт и стратегия в `fastapi-users`.
