# 01. Карта проекта

Проект — учебный auth-only шаблон на FastAPI 0.111+ / Python 3.12 с React 18 + TypeScript + Vite + Tailwind CSS v4. Бэкенд и собранный фронтенд обслуживаются одним ASGI-приложением; в dev фронтенд запускается отдельным Vite-сервером.

## Основные части

- `fastapi-application/api/` — демонстрации `Depends` и извлечения параметров.
- `fastapi-application/ex_order_product/` — демонстрационный домен заказов и товаров.
- `fastapi-application/db_core/` — SQLAlchemy 2.0 async, общая `Base`, сессии и типы колонок.
- `fastapi-application/auth_users/` — текущая авторизация на `fastapi-users`, аккаунт и avatar flow.
- `fastapi-application/static/profile_pics/` — аватары пользователей.
- `../fastapi-application/core/setup_frontend.py` — mounts для avatar static, frontend assets и SPA fallback.
- `frontend/` — минимальное React-приложение auth-шаблона и клиентские API-обёртки.
- `fastapi-application/alembic/` — асинхронные миграции.
- `docs/` — актуальная техническая документация.

## Точки сборки приложения

`fastapi-application/main.py` создаёт приложение через `create_app()`, подключает демонстрационный роутер, роутер заказов и auth router, затем вызывает `mount_frontend()`. Этот вызов должен оставаться последним: он добавляет `/static`, `/assets` и catch-all `/{full_path:path}` после API-маршрутов.

`create_fastapi.py` отвечает только за каркас FastAPI и lifespan. Доменная композиция находится в `main.py`, а generic frontend-раздача — в корневом `setup_frontend.py`.

## Дерево важных файлов

```text
fastapi-application/
├── main.py
├── create_fastapi.py
├── setup_frontend.py
├── core/config.py
├── db_core/
│   ├── db_async.py
│   ├── model_base.py
│   └── type_for_models.py
├── api/
├── ex_order_product/
├── auth_users/
│   ├── models.py
│   ├── schemas.py
│   ├── user_manager.py
│   ├── auth_backend.py
│   ├── fastapi_users_obj.py
│   ├── router.py
│   ├── account.py
│   └── helpers.py
├── static/profile_pics/
└── alembic/versions/

frontend/
├── src/api/
├── src/context/AuthContext.tsx
├── src/pages/
├── src/components/
├── src/App.tsx
├── src/main.tsx
└── vite.config.ts
```

## API-инвентарь

Проверка OpenAPI на текущем коде:

```bash
cd fastapi-application
../.venv/bin/python -c "from main import main_app; print(len(main_app.openapi()['paths']))"
```

Ожидается **23 path-ключа OpenAPI**. Полный контракт удобнее всего смотреть в `/openapi.json`.

Группы маршрутов:

| Группа | Пути | Источник |
|---|---|---|
| Depends и параметры | `/api/v1/...` | `api/` |
| Заказы | `/orders/...` | `ex_order_product/router_order_one.py` |
| Авторизация | `/auth/...`, `/users/me` | `auth_users/router.py` |
| Защищённая проверка доступа | `/api/v1/auth/protected` | `auth_users/router.py` |
| Swagger/OpenAPI | `/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect` | FastAPI |
| React и статика | `/assets/*`, `/static/*`, `/{full_path:path}` | `setup_frontend.py` |

Auth router публикует login/logout, registration, account update и операции текущего пользователя: `/auth/jwt/login`, `/auth/jwt/logout`, `/auth/register`, `/auth/account`, `GET/PATCH /users/me`. Маршрут `/api/v1/auth/protected` требует `active_user` и является независимой backend-границей доступа.

## Конфигурация и база

Конфигурация описана вложенными моделями в `core/config.py`. Переменные используют `APP__` и разделитель `__`; обязательное поле — `APP__DB__URL`. По умолчанию активен SQLite из `db_sqlite_dev.env`, PostgreSQL описан в `db_post_prod.env`.

SQLite-файл `./one_simple.db` разрешается относительно cwd процесса. Поэтому приложение предпочтительно запускать из `fastapi-application/`. Логи привязаны к `BASE_DIR` и не зависят от cwd.

Модели авторизации и домена заказов должны быть импортированы до запуска Alembic, чтобы попасть в `Base.metadata`. Реестр моделей сохраняет auth User и order/product-модели.

## Проверка фронтенда

```bash
cd frontend
npm run build
```

Сборка создаёт `frontend/dist`, который не коммитится. Без `dist` API и Swagger работают, а catch-all возвращает JSON 404 с подсказкой собрать фронтенд.
