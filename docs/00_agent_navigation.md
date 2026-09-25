# 00. Навигатор для AI-агентов

Документ для моделей AI в агентном режиме программирования. Это карта-оглавление:
«по какому вопросу куда идти». Прочитайте его до первого захода в код — ответы
уже сняты в `docs/`, блуждать по исходникам не нужно.

Порядок первого захода:

1. `QWEN.md` — правила главной сессии (оркестратор).
2. `AGENTS.md` — правила команды агентов, зоны ответственности.
3. Этот документ — карта проекта и документации.
4. Дальше — точечно по ссылкам ниже.

Факты сверены 2026-09-23 запуском приложения (команды — в конце документа).
Первоисточник маршрутов — живое приложение (`/openapi.json`), не документы.

## Проект — выжимка для модели

| Аспект | Суть |
|---|---|
| Назначение | Учебный auth-only шаблон: авторизация fastapi-users поверх демо-API |
| Бэкенд | FastAPI 0.111+ / Python 3.12, одно ASGI-приложение `main:main_app` в `fastapi-application/` |
| Фронтенд | React 18 + TypeScript + Vite + Tailwind v4 (`frontend/`); сборка `frontend/dist` обслуживается тем же приложением и не коммитится |
| БД | SQLAlchemy 2.0 async; активен SQLite (`db_sqlite_dev.env`), PostgreSQL-профиль — `db_post_prod.env` |
| Миграции | Alembic async; cwd = `fastapi-application/` обязателен |
| Конфиг | pydantic-settings в `core/config.py`, env-префикс `APP__`, разделитель `__`; настройка — код + env-файлы, не `os.environ` |
| Логи | `logF` из `config_log.py`; папка `log/` создаётся на импорте |
| Пакеты | uv (`uv.lock` — источник истины); линтеры ruff + black |
| Тестов нет | Проверка — запуск приложения и curl (smoke-набор внизу документа) |

## Композиция приложения

Сборка в `fastapi-application/main.py`:

1. `create_app(custom_docs_url=False)` — каркас FastAPI (`core/create_fastapi.py`):
   ORJSONResponse, `lifespan` с закрытием пула engine, штатные `/docs` и `/redoc`.
2. `include_router` × 3: `router_api` (демо `api/`), `r_order_one` (заказы
   `ex_order_product/`), auth-router (`auth_users/router.py`).
3. `mount_frontend(main_app)` (`core/setup_frontend.py`) — строго последним:
   `Mount /assets` и SPA catch-all `/{full_path:path}` добавляются после API-маршрутов.

Побочные эффекты на импорте: `config_log` создаёт `log/` и настраивает логгеры;
`db_core/db_async.py` создаёт engine. SQLite-файл `./one_simple.db` резолвится
от cwd — приложение и alembic запускать из `fastapi-application/`.

## Инвентарь маршрутов (факт, 2026-09-23)

| Группа | Пути | Источник |
|---|---|---|
| Демо DI | `/api/v1/dep_examples/*` (7 GET) | `api/dependencies/` |
| Демо 4 стилей параметров | `/api/v1/fastapi_class_old`, `fastapi_class_annotated`, `depends_class_annotated`, `depends_function_annotated` — каждая `my_items/{item_id}` | `api/my_routes_dep/` |
| Заказы | `/orders/*` — get_all_orders, get_all_join, get_order_where, get_order_filter_by, insert_order, add_order | `ex_order_product/router_order_one.py` |
| Авторизация | `/auth/jwt/login`, `/auth/jwt/logout`, `/auth/register`, `/auth/account`, `/users/me` (GET+PATCH) | `auth_users/router.py` |
| Защищённая граница | `GET /api/v1/auth/protected` — требует `active_user` | `auth_users/router.py` |
| Swagger/OpenAPI | `/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect` | FastAPI |
| Фронтенд и статика | `/assets/*`, `/{full_path:path}` (SPA catch-all) | `core/setup_frontend.py` |

Счётчики и подводный камень:

- OpenAPI path-ключей — **23**; команда проверки внизу документа.
- Наивный `len(main_app.routes)` даёт **9** и вводит в заблуждение: starlette 1.6
  оборачивает каждый `include_router` в непрозрачный `_IncludedRouter`, внутри —
  вложенные обёртки. Не считайте это багом и не «чините».
- Канонический список путей — `main_app.openapi()['paths']`.

## Вопрос → где ответ (документация)

| Вопрос | Документ |
|---|---|
| Карта файлов, дерево, API-инвентарь, конфиг и база | `docs/01_project_structure.md` |
| Слои, границы пакетов, инварианты | `docs/02_architecture.md` |
| Жизненный цикл: импорт, lifespan, порядок маршрутов, ошибки | `docs/03_execution_flow.md` |
| Как работает авторизация: полный цикл React → FastAPI → JWT-cookie | `docs/04_authorization.md` |
| Что развивать дальше в auth (production, verification, роли) | `docs/05_authorization_upgrade.md` |
| Диаграммы связей и рантайм-граф вызовов (cProfile, py-spy) | `docs/06_auth_visual.md` |
| Где выдаётся JWT, где живёт cookie, кто шлёт — построчно по файлам | `docs/07_auth_token_flow_code.md` |
| Транспорты/стратегии JWT: cookie vs Bearer vs свой заголовок | `docs/08_jwt_transport_options.md` |
| Общее пособие по аутентификации и авторизации: методы, протоколы, угрозы и выбор | `docs/09_auth_tutorial.md` |
| Пособие: Cookie/Bearer и JWT/Database/Redis стратегии с кодом | `docs/10_auth_transport_strategy_tutorial.md` |

## Задача → точка входа в коде

| Задача | Точка входа | Рядом |
|---|---|---|
| Поменять конфиг | `core/config.py` — вложенные модели с дефолтами | env-профили `db_sqlite_dev.env`, `db_post_prod.env` в `fastapi-application/` |
| Новый маршрут | `main.py` — добавить include_router | префиксы из `settings.api.v1.*`; APIRouter уровня модуля с prefix и tags |
| Маршрут-пример DI | `api/dependencies/` | `dep_examp_simple.py`, `dep_examp_cls.py`, `cls_deps.py`, `helper.py` |
| Маршрут-пример параметров | `api/my_routes_dep/` | `my_param_fast_cls.py`, `my_param_fast_ann.py`, `my_param_dep_cls.py`, `my_param_dep_func.py` |
| Домен заказов | `ex_order_product/` | `router_order_one.py`, `model_order_product.py`, `schema_order_product.py` |
| Сессия БД | `db_core/db_async.py` — `CurrentSession` | engine создаётся на импорте модуля |
| Новая модель в БД | `db_core/model_base.py` (`Base`), типы колонок — `type_for_models.py` | `__tablename__` автогенерится (`case_converter.py`); модель должна быть импортирована до Alembic |
| Миграции | `alembic/` | `../.venv/bin/alembic upgrade heads` из `fastapi-application/` |
| Раздача фронтенда | `core/setup_frontend.py` — `/assets` + SPA catch-all | вызов `mount_frontend()` — последним в `main.py` |
| Кастомные Swagger/ReDoc | `core/docs.py` | сейчас выключены: `custom_docs_url=False` |
| Логирование | `config_log.py` — `logF` | `log/` создаётся на импорте |
| Фронтенд: HTTP-клиент | `frontend/src/api/client.ts` — единственное место с `credentials` | обёртки getJson/postJson/postForm/postMultipart |
| Фронтенд: auth-вызовы | `frontend/src/api/auth.ts` — login это ДВА запроса | register/logout/getAccount/updateAccount |
| Фронтенд: состояние пользователя | `frontend/src/context/AuthContext.tsx` | в памяти лежит ПОЛЬЗОВАТЕЛЬ, не токен |
| Фронтенд: страницы и guard | `frontend/src/App.tsx`, `frontend/src/pages/` | HomePage, LoginPage, RegisterPage, ProtectedPage, AccountPage |
| Фронтенд: layout, выход, тосты | `frontend/src/components/` | `Layout.tsx`, `Header.tsx`, `Toast.tsx` |

### auth_users/ — карта пакета

| Файл | Содержимое |
|---|---|
| `models.py` | SQLAlchemy-модель пользователя |
| `schemas.py` | Pydantic-схемы register/update/read |
| `user_manager.py` | UserManager: валидация пароля (мин. длина из config), жизненный цикл пользователя |
| `auth_backend.py` | CookieTransport + JWTStrategy, сборка backend |
| `fastapi_users_obj.py` | экземпляр FastAPIUsers и зависимости текущего пользователя (`active_user`) |
| `router.py` | auth/register-роутеры от fastapi-users + собственный `GET /api/v1/auth/protected` |
| `account.py` | `POST /auth/account` — аккаунт и профиль |
| `helpers.py` | вспомогательные функции |

Детали реализации и ограничения схемы — `docs/04_authorization.md` (разделы
«Файлы реализации» и «Ограничения текущей реализации»).

## Чего в проекте НЕТ — не ищите

- Тестов и pytest — проверка только запуском и curl.
- Блога, статей, `md_articles/` — нет этого контента в репозитории.
- Refresh-токенов, email verification, CSRF/CORS-конфигурации — это roadmap
  (`docs/07` §11, `docs/08` §7, `docs/05`).
- Отдельного фронтенд-хоста: фронт и API — одно приложение (в dev — Vite-прокси на `:8000`).

## Графовый индекс (codebase-memory) — статус и границы

Проверено 2026-09-23: проект в индексе, статус `ready`, 998 узлов / 2265 связей;
skipped — нет; единственный parse_partial — `nginx/nginx.conf` (строки 1–58, конфиг,
не код). Перед доверяемыми структурными утверждениями — `index_status` или
`check_index_coverage` по затронутым файлам.

Приоритет инструментов: `search_graph` → `trace_path` → `get_code_snippet` →
`check_index_coverage` → `query_graph` → `get_architecture`.

Ограничения, экономящие ходы:

- Связи авторизации через `Depends(...)` статическому графу НЕ видны —
  `trace_path` по `active_user`/`protected` пуст в обе стороны. Фактическая
  цепочка снята в рантайме и оформлена в `docs/06_auth_visual.md` (§5.3, §5.4).
- Маршруты `fastapi_users.get_auth_router()/get_register_router()` не имеют
  обработчиков в репозитории — их создаёт библиотека на импорте. Поведение
  этих эндпоинтов ищите в `docs/04`, `docs/07`, `docs/08`.
- `TestClient` (starlette 1.6) требует пакет `httpx2`, установленный в `.venv`
  вручную и отсутствующий в `uv.lock` — RuntimeError без него ожидаем.
- Не индексируется by-design: `node_modules`, `frontend/dist`, `.venv`, `log/`,
  `uv.lock` — для них не стройте выводов по графу.

## Smoke-проверка изменения

```bash
cd fastapi-application
../.venv/bin/python -c "from main import main_app; print(len(main_app.openapi()['paths']))"   # 23
../.venv/bin/uvicorn main:main_app --host 0.0.0.0 --port 8000                                  # cwd = fastapi-application/
# затем curl: /docs, /orders/get_all_orders, /api/v1/dep_examples/single-direct-dependency,
# анонимный /users/me -> 401 (ожидаемо); cookie-flow целиком — рецепт в docs/05
uv run ruff check .
```

Фронтенд: `cd frontend && npm run build` — сборка без ошибок; без `dist` API работают,
SPA catch-all отвечает JSON 404 с подсказкой собрать фронт.

## Поддержание карты

- Счётчики и инвентарь здесь — факт на дату сверки в шапке. Изменили состав
  маршрутов или пакетов — обновите синхронно этот файл, `docs/01_project_structure.md`
  и раздел «Документация» в `README.md`.
- Расхождение документа с живым приложением — всегда неправ документ; первенство
  у `/openapi.json` и команды проверки.
