# 04. Авторизация: полный цикл React → FastAPI → JWT-cookie

Этот документ описывает фактическую реализацию авторизации в проекте. Авторизация построена на `fastapi-users`, SQLAlchemy и связке `CookieTransport + JWTStrategy`.

Главная идея: JWT не передаётся в JSON-ответе и не сохраняется в `localStorage`. После успешного входа backend отправляет браузеру cookie `auth`. Браузер сам прикладывает эту cookie к последующим same-origin-запросам, а backend проверяет подпись JWT и по идентификатору пользователя загружает пользователя из базы.

## 1. Общая схема

```text
Пользователь нажал «Войти»
        │
        ▼
React LoginPage.handleSubmit()
        │
        ▼
api/auth.ts::login()
        │  POST /auth/jwt/login
        │  Content-Type: application/x-www-form-urlencoded
        │  credentials: include
        ▼
FastAPI / fastapi-users
        │  проверка email и пароля
        │  создание и подпись JWT
        │  Set-Cookie: auth=<JWT>; HttpOnly; ...
        ▼
Браузер сохраняет cookie auth
        │
        ├── GET /users/me
        │      Cookie: auth=<JWT>
        │      → UserRead → AuthContext.user
        │
        └── GET /api/v1/auth/protected
               Cookie: auth=<JWT>
               → active_user → защищённый ответ
```

В этом потоке есть два разных объекта:

- **JWT** — credential для backend. Он находится в cookie браузера и недоступен JavaScript.
- **`user` в `AuthContext`** — обычный объект с данными текущего пользователя для отображения UI. Это не токен и не источник безопасности.

## 2. Какие маршруты участвуют

| Метод | Путь | Доступ | Результат |
|---|---|---|---|
| `POST` | `/auth/register` | публичный | создаёт пользователя, обычно `201` |
| `POST` | `/auth/jwt/login` | публичный | проверяет пароль, ставит cookie `auth`, `204` |
| `POST` | `/auth/jwt/logout` | публичный | удаляет cookie `auth`, `204` |
| `GET` | `/users/me` | авторизованный | возвращает текущего `UserRead`, `401` без валидной cookie |
| `PATCH` | `/users/me` | авторизованный | стандартное обновление пользователя fastapi-users |
| `POST` | `/auth/account` | авторизованный | обновляет `username` и `email`, возвращает `{message, category, user}` |
| `GET` | `/api/v1/auth/protected` | авторизованный | демонстрирует backend-защиту через `active_user` |

Users-router намеренно оставлен только с `/users/me` (GET/PATCH). Маршруты управления пользователями по ID не подключены.

## 3. Базовый frontend API-клиент

Файл `frontend/src/api/client.ts` содержит общий `request()`:

```ts
fetch(path, { credentials: 'include', ...init })
```

`credentials: 'include'` означает, что браузер:

1. принимает `Set-Cookie` от backend;
2. отправляет подходящие cookies в следующих запросах.

Для текущего frontend и backend это same-origin-сценарий, поэтому запросы используют относительные пути: `/auth/jwt/login`, `/users/me` и т. д.

Клиент предоставляет три варианта запроса:

- `postJson()` — JSON, используется регистрацией;
- `postForm()` — `application/x-www-form-urlencoded`, используется login/logout;
- `postMultipart()` — для multipart-сценариев, если они появятся.

`ensureOk()` преобразует неуспешный ответ в `ApiError`, сохраняя HTTP-статус и тело ошибки для UI.

## 4. Запуск приложения и первичная проверка сессии

Корневой компонент подключён так:

```text
main.tsx
  └── BrowserRouter
      └── ToastProvider
          └── AuthProvider
              └── App
```

При монтировании `AuthProvider` в `frontend/src/context/AuthContext.tsx` вызывается `refresh()`:

```text
AuthProvider.useEffect()
    → getCurrentUser()
    → GET /users/me
    → credentials: include
```

Варианты результата:

- `200` — backend распознал cookie, `UserRead` записывается в `AuthContext.user`;
- `401` — cookie отсутствует, просрочена или невалидна, `user` становится `null`;
- ошибка сети — текущая реализация также сбрасывает `user` в `null`, чтобы UI не оставался в бесконечном состоянии загрузки.

Пока запрос выполняется, `loading = true`. Поэтому `RequireAuth` сначала показывает `Проверка доступа...`, а не делает преждевременный редирект на `/login`.

## 5. Регистрация: от кнопки до записи в базе

### 5.1. Действие пользователя

Пользователь открывает `/register`, вводит email, пароль и подтверждение пароля и нажимает кнопку `Зарегистрироваться`.

Обработчик находится в `frontend/src/pages/RegisterPage.tsx`:

```text
<form onSubmit={handleSubmit}>
    → validate(form)
    → register({ email, password })
```

Клиентская проверка останавливает запрос, если email пустой/некорректный, пароль короче 8 символов или подтверждение не совпадает.

### 5.2. HTTP-запрос frontend

`frontend/src/api/auth.ts::register()` вызывает:

```http
POST /auth/register
Content-Type: application/json

{"email":"user@example.com","password":"password123"}
```

В запросе нет `username`: backend после создания пользователя выводит его из части email до `@` в `UserManager.on_after_register()`.

### 5.3. Обработка backend

Маршрут подключён в `fastapi-application/auth_users/router.py` через:

```python
fastapi_users.get_register_router(UserRead, UserCreate)
```

Далее `fastapi-users` и `UserManager`:

1. валидируют входную схему;
2. проверяют минимальную длину пароля (`8`);
3. хешируют пароль — исходный пароль в базу не записывается;
4. создают строку в таблице `user`;
5. выполняют `on_after_register()` и заполняют `username`;
6. возвращают `UserRead`.

Регистрация **не выдаёт JWT-cookie**. Это отдельный маршрут от login. После `201` React показывает уведомление и делает `navigate('/login')`.

### 5.4. Ошибки регистрации

Backend может вернуть:

- `422` — ошибки схемы или формата данных;
- `400` с `REGISTER_USER_ALREADY_EXISTS` — email уже занят;
- `400` с `REGISTER_INVALID_PASSWORD` — пароль не прошёл проверку.

`extractErrors()` и `getServerValidationErrors()` превращают эти ответы в ошибки под конкретными полями формы.

## 6. Вход: полный пошаговый цикл

### 6.1. Нажатие кнопки

На `/login` пользователь заполняет email и пароль и нажимает `Войти`.

`frontend/src/pages/LoginPage.tsx` запускает:

```text
handleSubmit()
    → login({ email, password })
    → setUser(user)
    → navigate('/')
```

### 6.2. Формирование запроса

`frontend/src/api/auth.ts::login()` преобразует поле `email` в поле `username`, потому что именно такое имя ожидает стандартный login-router `fastapi-users`:

```http
POST /auth/jwt/login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=password123
```

Запрос отправляется через `postForm()`, а общий клиент добавляет `credentials: 'include'`.

### 6.3. Проверка credentials на backend

`fastapi-application/auth_users/router.py` подключает auth-router:

```python
fastapi_users.get_auth_router(auth_backend)
```

`auth_backend` из `fastapi-application/auth_users/auth_backend.py` состоит из двух частей:

- `CookieTransport` — место передачи токена, cookie `auth`;
- `JWTStrategy` — создание и проверка JWT.

Backend получает `username` и `password`, находит пользователя по email и сравнивает переданный пароль с `hashed_password` из таблицы `user`.

### 6.4. Создание и отправка JWT

Если пароль верный, `JWTStrategy` создаёт подписанный JWT. Для подписи используются:

- секрет `settings.web.secret_key`;
- алгоритм `HS256`;
- срок жизни `86400` секунд в текущей конфигурации.

`CookieTransport` добавляет JWT в HTTP-заголовок ответа:

```http
HTTP/1.1 204 No Content
Set-Cookie: auth=<JWT>; Max-Age=86400; HttpOnly; SameSite=Lax; Path=/
```

В зависимости от версии библиотеки дополнительные атрибуты cookie могут быть представлены в другом порядке, но смысл тот же.

Тело ответа на login пустое: успешный ответ — `204`. JWT не приходит в JSON.

### 6.5. Что делает браузер

Браузер принимает `Set-Cookie` и сохраняет cookie `auth` для домена приложения. React не вызывает `document.cookie` и не записывает токен вручную.

Сразу после успешного `204` функция `login()` делает второй запрос:

```text
POST /auth/jwt/login  → 204 + Set-Cookie
GET  /users/me        → UserRead
```

Второй запрос также получает `credentials: 'include'`, поэтому браузер автоматически добавляет:

```http
Cookie: auth=<JWT>
```

`getCurrentUser()` возвращает `User`, после чего `LoginPage` вызывает `setUser(user)`. В результате шапка показывает аккаунт и кнопку выхода.

### 6.6. Что происходит при неверном входе

Если email или пароль неверны, login-router возвращает ошибку, cookie не устанавливается, а `LoginPage` показывает `Неверный email или пароль`. В текущем frontend для такого случая ожидается HTTP `400`.

## 7. Защищённый запрос после входа

UI-защита и backend-защита — разные уровни.

### 7.1. UI guard

В `frontend/src/App.tsx` компонент `RequireAuth` смотрит только на `AuthContext.user`:

```text
user есть       → отрендерить защищённую страницу
user отсутствует → Navigate('/login')
```

Это улучшает навигацию, но не защищает API. Пользователь может вручную отправить запрос без UI.

### 7.2. Backend boundary

`frontend/src/pages/ProtectedPage.tsx` при открытии `/protected` делает:

```http
GET /api/v1/auth/protected
Cookie: auth=<JWT>
```

Обработчик backend в `auth_users/router.py` получает:

```python
user: Annotated[User, Depends(active_user)]
```

`active_user` выполняет цепочку:

1. `CookieTransport` читает cookie `auth` из входящего запроса;
2. `JWTStrategy` проверяет подпись, срок действия и данные токена;
3. по идентификатору пользователя из JWT загружается `User` из базы;
4. проверяется, что пользователь активен;
5. dependency передаёт объект `User` в обработчик.

При успехе backend возвращает `200`:

```json
{
  "authenticated": true,
  "user": {
    "id": "...",
    "email": "user@example.com",
    "username": "user"
  }
}
```

При отсутствии, просрочке или повреждении cookie backend возвращает `401`. Именно backend, а не React, является окончательным контролем доступа.

## 8. Выход из аккаунта

Кнопка `Выход` находится в `frontend/src/components/Header.tsx` и вызывает `Layout.handleLogout()`.

Полный поток:

```text
Header button
    → Layout.handleLogout()
    → api/auth.ts::logout()
    → POST /auth/jwt/logout
    → CookieTransport удаляет auth
    → 204
    → setUser(null)
```

Запрос:

```http
POST /auth/jwt/logout
Content-Type: application/x-www-form-urlencoded
Cookie: auth=<JWT>
```

Ответ содержит инструкцию удаления cookie, обычно через `Set-Cookie` с истёкшим сроком:

```http
HTTP/1.1 204 No Content
Set-Cookie: auth=; Max-Age=0; ...
```

После этого `Layout` сбрасывает объект `user` в React-памяти. При следующем запросе `/users/me` браузер уже не отправляет `auth`, поэтому backend возвращает `401`.

Важно: JWT stateless. Logout удаляет cookie из браузера, но backend не ведёт отдельный список активных JWT и не добавляет токен в blacklist. Если кто-то заранее скопировал JWT, он теоретически останется действительным до истечения срока жизни или смены `secret_key`.

## 9. Где именно хранится авторизация

| Что | Где находится | Можно ли прочитать из JavaScript | Назначение |
|---|---|---:|---|
| JWT | Cookie браузера `auth` | Нет, `HttpOnly` | подтверждает авторизацию для backend |
| cookie-настройки | браузер, атрибуты cookie | частично через DevTools | domain/path/max-age/samesite и т. д. |
| текущий `User` | память React, `AuthContext.user` | Да | отображение UI и UI guard |
| JWT в `localStorage` | нигде | — | проект его не использует |
| JWT в `sessionStorage` | нигде | — | проект его не использует |
| JWT в таблице `user` | нигде | — | база хранит не JWT, а `hashed_password` |
| секрет подписи JWT | backend `settings.web.secret_key` | Нет | проверка подписи и создание новых JWT |
| пользователь | backend БД, таблица `user` | через разрешённые API-поля | загрузка `User` после проверки JWT |

### Что видно в DevTools

В браузере можно проверить поток в двух местах:

1. **Network → `POST /auth/jwt/login` → Response Headers** — увидеть `Set-Cookie`.
2. **Application/Storage → Cookies → домен приложения** — увидеть cookie `auth` и её атрибуты.
3. **Network → `GET /users/me` или `/api/v1/auth/protected` → Request Headers** — увидеть, что браузер отправил `Cookie`.

Значение HttpOnly-cookie не должно читаться приложением через `document.cookie`. Это ожидаемое поведение, а не ошибка frontend.

## 10. Конфигурация auth

Настройки находятся в `fastapi-application/core/config.py`, модель `AuthUsersConfig`:

| Параметр | Текущее значение | Смысл |
|---|---:|---|
| `cookie_name` | `auth` | имя cookie с JWT |
| `cookie_max_age` | `86400` | срок cookie в секундах |
| `cookie_secure` | `false` | разрешает работу по локальному HTTP; для HTTPS включить `true` |
| `cookie_httponly` | `true` | запрещает чтение cookie JavaScript-кодом |
| `cookie_samesite` | `lax` | политика отправки cookie между сайтами |
| `jwt_lifetime_seconds` | `86400` | срок действия JWT |
| `jwt_algorithm` | `HS256` | алгоритм подписи |
| `password_min_length` | `8` | минимальная длина пароля |

В production `APP__WEB__SECRET_KEY` должен задаваться вне репозитория и быть уникальным. Значение `dev-insecure-secret-key-change-me` предназначено только для разработки.

## 11. Account и изменение профиля

`frontend/src/pages/AccountPage.tsx` отправляет данные через `api/auth.ts::updateAccount()`, а backend-маршрут находится в `auth_users/account.py`:

```http
POST /auth/account
Content-Type: application/x-www-form-urlencoded
Cookie: auth=<JWT>

username=newname&email=new@example.com
```

`Depends(active_user)` сначала проверяет cookie. Затем endpoint проверяет формат и уникальность username/email, обновляет текущего пользователя и возвращает:

```json
{
  "message": "Your account has been updated!",
  "category": "success",
  "user": { "id": "...", "username": "...", "email": "..." }
}
```

Текущий endpoint `/auth/account` принимает только `username` и `email`. Загрузка аватара в этом маршруте сейчас не реализована.

## 12. Файлы реализации

### Backend

- `fastapi-application/auth_users/router.py` — сборка auth-, register-, users- и protected-роутеров;
- `fastapi-application/auth_users/auth_backend.py` — `CookieTransport` и `JWTStrategy`;
- `fastapi-application/auth_users/fastapi_users_obj.py` — `fastapi_users`, `active_user`, `optional_user`;
- `fastapi-application/auth_users/user_manager.py` — проверка пароля, регистрация, работа с user database;
- `fastapi-application/auth_users/models.py` — SQLAlchemy-модель `User`;
- `fastapi-application/auth_users/schemas.py` — `UserRead`, `UserCreate`, `UserUpdate`;
- `fastapi-application/auth_users/account.py` — изменение username/email;
- `fastapi-application/core/config.py` — параметры cookie и JWT.

### Frontend

- `frontend/src/pages/LoginPage.tsx` — форма входа и обработчик кнопки;
- `frontend/src/pages/RegisterPage.tsx` — форма регистрации;
- `frontend/src/api/client.ts` — `fetch`, `credentials: 'include'`, обработка ошибок;
- `frontend/src/api/auth.ts` — функции register/login/logout/account/me;
- `frontend/src/context/AuthContext.tsx` — текущий пользователь в памяти React;
- `frontend/src/App.tsx` — `RequireAuth` для UI-маршрутов;
- `frontend/src/components/Header.tsx` — кнопка выхода;
- `frontend/src/components/Layout.tsx` — обработка logout;
- `frontend/src/pages/ProtectedPage.tsx` — запрос к защищённому backend API.

## 13. Ограничения текущей реализации

- Email verification и reset password не подключены.
- OAuth не подключён.
- Отдельная серверная сессия и Redis не используются.
- Logout не отзывает уже скопированный JWT до его истечения.
- Rate limit для login/register не реализован.
- `SameSite=Lax` и текущая cookie-модель рассчитаны на текущую same-origin-схему. При разнесении frontend и API по разным origin нужно отдельно настроить CORS, cookie `Secure`/`SameSite` и CSRF-защиту.
- UI guard не заменяет backend dependency `active_user`.
