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
| `auth_users` | User, пароль, cookie-JWT, зависимости доступа, аккаунт и avatar flow |
| `setup_frontend.py` | mounts для avatar static, frontend assets и generic SPA fallback |
| `frontend` | auth UI, React Router, fetch-клиенты и локальное состояние |
| `main.py` | единственная точка композиции приложения |

Домены подключаются через `main.py`: он включает demo, order и auth routers, а затем передаёт приложение в `mount_frontend()`. Root-level frontend setup не содержит auth- или order-логики.

## Авторизация и защищённый endpoint

Пакет `auth_users` выдаёт JWT в HttpOnly-cookie. Dependency `active_user` используется auth router и endpoint `GET /api/v1/auth/protected`; этот endpoint является независимой backend-границей и не полагается на client-side guard. Anonymous получает JSON 401, авторизованный пользователь — JSON с подтверждением доступа и данными пользователя.

Auth router сохраняет следующие операции:

- `/auth/jwt/login` и `/auth/jwt/logout`;
- `/auth/register`;
- `/auth/account`;
- `GET/PATCH /users/me`.

Стандартные маршруты управления пользователями по идентификатору не подключаются.

## Хранилища данных

- **SQLAlchemy/БД:** пользователь `user`, демо-таблицы заказов и товаров.
- **Файлы:** `static/profile_pics/` — аватары пользователей.
- **Браузер:** HttpOnly cookie `auth` для JWT и состояние auth-контекста.

Путь аватара в БД хранится как имя файла; URL `/static/profile_pics/<имя>` формируется клиентом.

## Поток запроса

1. Uvicorn передаёт запрос FastAPI.
2. Роутинг выбирает вложенный API-роутер; catch-all находится последним.
3. FastAPI разрешает dependency и открывает `CurrentSession`, если она нужна.
4. Для защищённого маршрута `active_user` читает JWT из cookie и загружает `User` через `SQLAlchemyUserDatabase`.
5. Обработчик читает или изменяет БД.
6. Ответ сериализуется FastAPI; JSON API возвращает данные для auth-клиента.

JWT самодостаточен для аутентификации, но dependency обращается к БД за актуальным пользователем и проверяет `is_active`.

## Frontend dev и production

В dev Vite работает на `:5173` и проксирует API-запросы на FastAPI. В production `mount_frontend()` раздаёт `frontend/dist/assets` и возвращает `index.html` для history-mode маршрутов React. Для неизвестных `/api/*` catch-all отдаёт JSON 404, а не HTML.

## Архитектурные инварианты

1. `mount_frontend(main_app)` вызывается после всех `include_router`.
2. `frontend/dist` не коммитится.
3. Путь аватара в БД хранится как имя файла; URL `/static/profile_pics/<имя>` собирает фронтенд.
4. Секрет `settings.web.secret_key` используется JWT-стратегией и токенами fastapi-users.
5. `/api/v1/auth/protected` остаётся защищённым `active_user` независимо от состояния UI.
