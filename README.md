
## Стек

| Область | Выбор |
|---|---|
| Язык | Python 3.12 (`.python-version`) |
| Менеджер пакетов | `uv` (`uv.lock` — источник истины) |
| Веб-фреймворк | FastAPI 0.111+ (ORJSONResponse по умолчанию) |
| Валидация / конфигурация | Pydantic 2 + pydantic-settings (префикс `APP__`) |
| ORM | SQLAlchemy 2.0 async (`asyncpg` / `aiosqlite`) |
| Миграции | Alembic (асинхронный env.py) |
| ASGI-сервер | uvicorn (dev), gunicorn + UvicornWorker (multi-worker) |
| Сериализация | orjson |
| Линтеры | ruff + black (объявлены в зависимостях) |

## Быстрый старт (локально)

```bash
uv sync                      # создаёт .venv по uv.lock
```

Профиль БД выбирается в `fastapi-application/core/config.py` (поле `env_file` класса
`Settings`): по умолчанию активен `db_sqlite_dev.env` — SQLite (`sqlite+aiosqlite:///./one_simple.db`),
никакой внешней БД не нужно. Профиль PostgreSQL (`db_post_prod.env`,
`postgresql+asyncpg://user:password@localhost:5432/shop`) включается раскомментированием
строки в `env_file`; файл `.env`, если существует, перекрывает оба.

Запуск приложения (из каталога `fastapi-application/`):

```bash
cd fastapi-application
../.venv/bin/uvicorn main:main_app --host 0.0.0.0 --port 8000 --reload    # предпочтительно
../.venv/bin/python main.py                                               # то же + баннер в лог
# из корня проекта: make run_app11_lin  (uvicorn --app-dir fastapi-application)
```

> ⚠️ **cwd имеет значение.** Файл SQLite `./one_simple.db` и относительные пути
> резолвятся от рабочего каталога: запуск из корня через `--app-dir` создаст базу в корне
> проекта, а не в `fastapi-application/`. Логи при этом всегда пишутся в
> `fastapi-application/log/` (путь привязан к `BASE_DIR`). Предпочтителен запуск из
> `fastapi-application/`. Swagger: <http://127.0.0.1:8000/docs>.

Фронтенд блога собирается отдельно — сборка `frontend/dist` **не коммитится**:

```bash
cd frontend && npm install && npm run build   # → frontend/dist
```

Без сборки JSON API (`/api/blog/*`) и Swagger работают, а SPA-страницы (`/`,
`/art/...`) отвечают 404 JSON с подсказкой выполнить `npm run build`. Dev-режим
фронтенда — два процесса: `cd frontend && npm run dev` (порт 5173, Vite проксирует
`/api` и `/static` на `:8000`), бэкенд — как выше.

Для PostgreSQL поднимите dev-стек из `docker-compose.yml` (pg на `5432`, adminer на
`8080`, pgadmin на `5050`; креды `user/password`, база `shop`) и переключите профиль на
`db_post_prod.env`.

## Запуск агентного режима

1. Убедитесь, что модели, указанные в frontmatter `model:` файлов `.qwen/agents/`,
   объявлены в `~/.qwen/settings.json` (authType `openai`); оркестратор — модель,
   с которой запущена главная сессия.
2. Поднимите приложение (см. «Быстрый старт» — для SQLite внешний сервис не нужен) —
   агентам нужен работающий URL для проверок.
3. Запустите `qwen-code` в корне проекта. `QWEN.md` превратит главную сессию в
   оркестратора; субагенты подхватятся из `.qwen/agents/`.
4. Дайте команду:

   > Выполни текущее задание из tasks/current/REQUIREMENTS.md и не останавливайся,
   > пока все критерии успеха не будут подтверждены доказательствами.

Пока команда работает: дефекты появляются в `tasks/current/DEFECTS.md`, находки
adversary — в `tasks/current/ADVERSARIAL_REVIEW.md`, сценарии и сырые выводы проверок —
в `tasks/current/e2e/`. Закрытые задания лежат в `tasks/NNN-<slug>/` — целиком, с
отчётом о выполнении.

## Конфигурация

Вся конфигурация — вложенные pydantic-модели в `fastapi-application/core/config.py`,
читаются из env-файлов с префиксом `APP__` и разделителем `__` (например,
`APP__DB__URL`, `APP__RUN__PORT`, `APP__GUNICORN__WORKERS`). Единственное обязательное
поле — `db.url`.

| Переменная | Обязательна | По умолчанию / профиль |
|---|---|---|
| `APP__DB__URL` | да | `db_sqlite_dev.env`: sqlite, `db_post_prod.env`: postgres |
| `APP__DB__ECHO` | нет | `0` |
| `APP__RUN__HOST` / `APP__RUN__PORT` | нет | `0.0.0.0` / `8000` |
| `APP__GUNICORN__WORKERS` | нет | `1` |
| `APP__WEB__SECRET_KEY` | нет | dev-значение (подпись JWT и auth-токенов) |

Env-файлы лежат в `fastapi-application/` и **закоммичены** (`db_post_prod.env`, `db_sqlite_dev.env`) — это
учебный проект без секретов; `.env` (если создаёте) тоже в каталоге приложения и имеет
высший приоритет.


## Модель данных

`__tablename__` генерируется автоматически из имени класса (`CamelCase` → `snake_case`);
`OrderProductAssociation` переопределяет его вручную. Миграции: 3 ревизии Alembic в
`fastapi-application/alembic/versions/`. Реестр статей блога — `md_articles/articles.yaml`
(контент-статьи `.md` пользователь кладёт в `fastapi-application/content_art/`).


## Документация

В папке [`docs/`](docs/) лежит актуальная техническая документация по проекту:

- [01_project_structure.md](docs/01_project_structure.md) — карта файлов и API-инвентарь;
- [02_architecture.md](docs/02_architecture.md) — слои и границы приложения;
- [03_execution_flow.md](docs/03_execution_flow.md) — запуск и прохождение запросов;
- [04_authorization.md](docs/04_authorization.md) — текущая авторизация `fastapi-users`;
- [05_authorization_upgrade.md](docs/05_authorization_upgrade.md) — варианты дальнейшего развития auth;
- [06_blog.md](docs/06_blog.md) — отдельное устройство блога и реестра статей.

## Индекс кодовой базы

Для структурных запросов по коду (кто вызывает функцию, что она вызывает, мёртвый код,
анализ влияния изменений) используйте графовый индекс через **codebase-memory-mcp** —
это быстрее и точнее, чем обход исходников вручную. Скилл `codebase-memory` описывает
доступные MCP-инструменты (`search_graph`, `trace_path`, `detect_changes` и др.).
Перед структурным исследованием проверяйте наличие/свежесть индекса через `index_status`.

## Линтеры и проверка изменений

```bash
uv run ruff check .                                                        # линтер (ruff в зависимостях)
cd fastapi-application && ../.venv/bin/python -c "from main import main_app; print(len(main_app.openapi()['paths']))"   # 32 path-ключа OpenAPI
cd fastapi-application && ../.venv/bin/uvicorn main:main_app --port 8000    # затем curl /docs, /users/me, /api/blog/articles, /
```

Тестов нет — изменения проверяются запуском приложения и curl-запросами. Подробные
соглашения, грабли и правила для агентов см. в [AGENTS.md](AGENTS.md).
