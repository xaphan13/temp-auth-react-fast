# 04. Авторизация

Текущая авторизация находится в `fastapi-application/auth_users/` и построена на `fastapi-users` с SQLAlchemy-адаптером, `CookieTransport` и `JWTStrategy`. Это самостоятельный auth-only слой приложения: он обслуживает регистрацию, вход, cookie-сессию, профиль пользователя и защищённую проверочную точку API.

## Контракт маршрутов

| Метод | Путь | Доступ | Назначение |
|---|---|---|---|
| POST | `/auth/jwt/login` | публичный | form-urlencoded `username=<email>&password=...`; 204 + cookie |
| POST | `/auth/jwt/logout` | публичный | очистить cookie; 204 |
| POST | `/auth/register` | публичный | JSON `{email,password}`; 201 |
| GET | `/users/me` | `active_user` | текущий пользователь; 401 для анонима |
| PATCH | `/users/me` | `active_user` | стандартное обновление собственного профиля fastapi-users |
| POST | `/auth/account` | `active_user` | username/email/аватар, multipart |
| GET | `/api/v1/auth/protected` | `active_user` | проверка независимой backend-защиты; 401 для анонима |

Users-router ограничен маршрутами `/users/me` (GET/PATCH). Стандартные маршруты управления другими пользователями (`/users/{id}`) в auth-only шаблон не подключены.

## Модель User

`auth_users/models.py` содержит:

- UUID `id` из `SQLAlchemyBaseUserTableUUID`;
- уникальный `email`;
- `hashed_password`;
- `is_active`, `is_superuser`, `is_verified`;
- `username` длиной до 20 символов;
- `image_file` с default `default.jpg`;
- `created_at`.

`username` nullable на уровне SQLAlchemy, потому что стандартная регистрация сначала создаёт пользователя только с email и password. `UserManager.on_after_register()` затем записывает username из email и default-аватар.

`UserRead` отдаёт `id`, `email`, флаги пользователя, `username` и `image_file`; пароль и `hashed_password` в ответ не попадают.

## Сборка fastapi-users

```text
auth_users/router.py
  ├── get_auth_router(auth_backend)      → /auth/jwt/login, /auth/jwt/logout
  ├── get_register_router(...)           → /auth/register
  ├── get_users_router(...)              → только /users/me (GET/PATCH)
  ├── account.router                     → /auth/account
  └── protected_router                   → /api/v1/auth/protected
```

`fastapi_users_obj.py` создаёт:

- `fastapi_users = FastAPIUsers[User, UUID](...)`;
- `active_user = fastapi_users.current_user(active=True)`;
- `optional_user`;
- `superuser_user`.

`user_manager.py` связывает `CurrentSession` с `SQLAlchemyUserDatabase`, проверяет минимальную длину пароля 8 и переводит `IntegrityError` дубликата в штатный `UserAlreadyExists`.

## Cookie и JWT

Настройки находятся в `core/config.py` в `AuthUsersConfig`:

| Параметр | Текущее значение |
|---|---|
| cookie name | `auth` |
| max age | `86400` секунд |
| HttpOnly | `true` |
| SameSite | `lax` |
| Secure | `false` для dev HTTP |
| JWT lifetime | `86400` секунд |
| algorithm | `HS256` |
| minimum password length | `8` |

JWT подписывается `settings.web.secret_key`. Тот же секрет передан менеджеру для токенов verification/reset, хотя соответствующие маршруты сейчас не подключены.

`POST /auth/jwt/login` выдаёт JWT в cookie `auth`; тело успешного ответа не используется, поскольку статус — `204`. Браузер автоматически отправляет cookie на последующие same-origin запросы, поэтому `GET /users/me` и `GET /api/v1/auth/protected` получают текущего пользователя через `active_user`. `POST /auth/jwt/logout` возвращает `204` и очищает cookie в браузере.

`frontend/src/api/client.ts` всегда использует `credentials: 'include'`. JWT не сохраняется в `localStorage`, а cookie имеет `HttpOnly`, поэтому JavaScript не читает её напрямую. Отдельного CSRF-токена нет: текущий контракт рассчитан на same-origin cookie с `SameSite=Lax`. При выносе API на другой origin нужно отдельно пересмотреть CORS, cookie-политику и CSRF-модель.

## Account и аватар

`POST /auth/account` — проектный multipart-маршрут поверх `active_user`.

```text
username: str
email: str
picture: UploadFile | отсутствует
```

`auth_users/helpers.py` проверяет email и уникальность, а `save_picture()` сохраняет изображение после resize 125×125. Имя файла генерируется случайно и сохраняется в `User.image_file`. React строит URL как `/static/profile_pics/${image_file}`; backend раздаёт этот каталог через mount `/static`, поэтому avatar URL не попадает в SPA fallback.

Успешный ответ account endpoint имеет форму `{message, category, user}`. Для обычного изменения email/password можно использовать стандартный `PATCH /users/me`; multipart account endpoint предназначен для username, email и optional `picture`.

## Protected API

`GET /api/v1/auth/protected` — независимая backend-проверка auth boundary. Маршрут использует dependency `active_user`: запрос без cookie получает JSON `401`, а авторизованный запрос получает `200` и JSON с `authenticated: true` и данными `UserRead`. Ответ не содержит пароль или `hashed_password`. UI guard защищает страницу `/protected`, но безопасность обеспечивается именно backend dependency.

## React-контракт

- `api/auth.ts`: login → form-urlencoded и последующий `/users/me`; logout → `/auth/jwt/logout`; register → `/auth/register`; account → `/auth/account`.
- `AuthContext.tsx`: при старте вызывает `/users/me`; 401 означает `user = null`.
- `App.tsx`: `RequireAuth` защищает `/account` и `/protected` на уровне UI; страница `/protected` вызывает `GET /api/v1/auth/protected`.
- Регистрация отправляет только `{email, password}`. `username` вычисляется auth manager после создания пользователя.
- API всё равно проверяет dependency `active_user`; UI-защита не является механизмом безопасности.

## Схема базы и миграции

Таблица текущей авторизации — `user`, с UUID и полями fastapi-users. Alembic берёт `Base.metadata` из приложения; перед генерацией миграции должны импортироваться модели `auth_users`.

## Важные ограничения

- Email verification, reset password, OAuth и rate limit не подключены.
- Авторизация не даёт отдельной роли редактора: управление реестром доступно любому `active_user`.
- Смена `secret_key` инвалидирует ранее выданные JWT и токены.
- `cookie_secure` нужно включать за HTTPS; текущий `false` предназначен для локального HTTP.
