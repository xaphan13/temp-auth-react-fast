# 02. Архитектура

## Общая схема

Проект — auth-only модульный монолит: один FastAPI-процесс обслуживает JSON API, avatar static и собранный React-фронтенд.

```text
Браузер
  ├── React Router: /, /login, /register, /account, /protected
  ├── fetch /auth/* и /users/me
  └── fetch /api/v1/auth/protected
          │
          ▼
FastAPI main_app
  ├── demo API /api/v1/*
  ├── order API /orders/*
  ├── auth_users /auth/* и /users/me
  ├── protected API /api/v1/auth/protected
  ├── /static/profile_pics/*
  ├── /assets/*
  └── catch-all → frontend/dist/index.html
          │
          ├── SQLite/PostgreSQL через db_core
          ├── User через auth_users
          └── orders/products через ex_order_product
```

## Границы пакетов

| Слой | Ответственность |
|---|---|
| `core`, `base_dir_path`, `config_log` | настройки, пути, логирование |
| `db_core` | engine, async-сессии, `Base`, типы SQLAlchemy |
| `api` | учебные примеры FastAPI |
| `ex_order_product` | учебный SQLAlchemy-домен заказов |
| `auth_users` | User, пароль, два транспорта JWT (cookie + bearer), CSRF-защита, зависимости доступа, аккаунт и avatar flow |
| `setup_frontend.py` | mounts для avatar static, frontend assets и generic SPA fallback |
| `frontend` | auth UI, React Router, fetch-клиенты и локальное состояние |
| `main.py` | единственная точка композиции приложения |

Домены подключаются через `main.py`: он включает demo, order и auth routers, а затем передаёт приложение в `mount_frontend()`. Root-level frontend setup не содержит auth- или order-логики.

## Авторизация и защищённый endpoint

Пакет `auth_users` поддерживает два транспорта авторизации на общей `JWTStrategy`: `CookieTransport` для браузерного потока (HttpOnly-cookie `auth` + Signed Double Submit Cookie CSRF через `CSRFMiddleware` в `auth_users/csrf.py`) и `BearerTransport` для не-браузерных клиентов (JSON `access_token`). Dependency `active_user` перебирает backend'ы в порядке cookie → bearer и используется auth router и endpoint `GET /api/v1/auth/protected`; этот endpoint является независимой backend-границей и не полагается на client-side guard. Anonymous получает JSON 401, авторизованный пользователь — JSON с подтверждением доступа и данными пользователя.

Auth router сохраняет следующие операции:

- `/auth/cookie/login` и `/auth/cookie/logout` (CookieTransport; state-changing запросы с auth-cookie требуют заголовок `X-CSRF-Token`);
- `/auth/bearer/login` и `/auth/bearer/logout` (BearerTransport);
- `/auth/register`;
- `/auth/account`;
- `GET/PATCH /users/me`.

Стандартные маршруты управления пользователями по идентификатору не подключаются. Прежний контракт `/auth/jwt/*` устарел и заменён разделёнными префиксами `/auth/cookie/*` и `/auth/bearer/*`.

## Хранилища данных

- **SQLAlchemy/БД:** пользователь `user`, демо-таблицы заказов и товаров.
- **Файлы:** `static/profile_pics/` — аватары пользователей.
- **Браузер:** HttpOnly cookie `auth` для JWT (CookieTransport) и cookie `csrf_token` для Signed Double Submit CSRF; BearerTransport хранит токен только на клиенте.

Путь аватара в БД хранится как имя файла; URL `/static/profile_pics/<имя>` формируется клиентом.

## Поток запроса

1. Uvicorn передаёт запрос FastAPI.
2. `CSRFMiddleware` проверяет state-changing cookie-запросы: при наличии auth-cookie требуется заголовок `X-CSRF-Token`, совпадающий с подписью cookie `csrf_token`.
3. Роутинг выбирает вложенный API-роутер; catch-all находится последним.
4. FastAPI разрешает dependency и открывает `CurrentSession`, если она нужна.
5. Для защищённого маршрута `active_user` перебирает backend'ы (cookie → bearer), читает JWT и загружает `User` через `SQLAlchemyUserDatabase`.
6. Обработчик читает или изменяет БД.
7. Ответ сериализуется FastAPI; JSON API возвращает данные для auth-клиента.

JWT самодостаточен для аутентификации, но dependency обращается к БД за актуальным пользователем и проверяет `is_active`.

## Frontend dev и production

В dev Vite работает на `:5173` и проксирует API-запросы на FastAPI. В production `mount_frontend()` раздаёт `frontend/dist/assets` и возвращает `index.html` для history-mode маршрутов React. Для неизвестных `/api/*` catch-all отдаёт JSON 404, а не HTML.

## Архитектурные инварианты

1. `mount_frontend(main_app)` вызывается после всех `include_router`.
2. `frontend/dist` не коммитится.
3. Путь аватара в БД хранится как имя файла; URL `/static/profile_pics/<имя>` собирает фронтенд.
4. Секрет `settings.web.secret_key` используется JWT-стратегией и токенами fastapi-users.
5. `/api/v1/auth/protected` остаётся защищённым `active_user` независимо от состояния UI.
6. OpenAPI содержит 25 path-ключей (считайте через `main_app.openapi()['paths']`, а не через `len(main_app.routes)`).

</content>