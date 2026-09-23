# AGENTS.md — my-fastapi-one (агентный режим)

Контекст-инструкция для AI-агентов, работающих с кодом в этом репозитории, плюс правила
команды агентов (раздел «Агентный режим» в конце файла). Оркестратор — главная сессия
Qwen Code (инструкции — в `QWEN.md`). Подробная документация по проекту — в
[`docs/`](docs/). При сомнениях главенствует текущее задание, затем проектные
соглашения выше.

## Проект — выжимка

Учебно-демонстрационный FastAPI 0.111+ / Python 3.12. Три части: демонстрационная
(`api/` — 9 способов Depends, 4 стиля параметров), рабочая (`ex_user_post/`,
`ex_order_product/`, `db_core/` — SQLAlchemy 2.0 async + Alembic), блог
(`md_articles/` + `frontend/` — React SPA на JSON API `/api/blog`).

**Дублирование маршрутов и обработчиков в `api/` намеренное** — не рефакторить.

**Стек:** Python 3.12, uv, FastAPI 0.111+, Pydantic 2 + pydantic-settings,
SQLAlchemy 2.0 async (aiosqlite активен), Alembic, uvicorn/gunicorn, orjson,
React 18 + TypeScript + Vite + Tailwind v4, ruff + black.

**Маршруты:** 44 route-объекта. 37 `APIRoute` (21 демо + 7 блог + 9 auth_users)
+ 5 `Route` (4 служебных + SPA catch-all) + 2 `Mount` (/static, /assets).

Проверка: `cd fastapi-application && ../.venv/bin/python -c "from main import main_app; print(len(main_app.routes))"` → `44`.

**Тестов нет** — изменения проверяются запуском приложения и curl.

## Запуск и проверка

```bash
uv sync                      # создаёт .venv по uv.lock
cd fastapi-application
../.venv/bin/uvicorn main:main_app --host 0.0.0.0 --port 8000 --reload    # предпочтительно
# cwd имеет значение: SQLite резолвится от cwd — из корня база создастся не там. Запуск из fastapi-application/.
../.venv/bin/alembic upgrade heads          # alembic тоже требует cwd = fastapi-application/
```

Профиль БД — правка `env_file` в `fastapi-application/core/config.py` (активен
`db_sqlite_dev.env`), не переменная окружения.

**Линтеры:** `uv run ruff check .` / `uv run ruff format .` — ruff и black в
зависимостях проекта.

**Smoke-набор:** счётчик маршрутов (выше) + `/docs`, `/users/get_all_users`,
`/orders/get_all_orders`, один из `/api/v1/dep_examples/*`, `/api/blog/articles`.
Не утверждайте, что изменение проверено, без фактического запуска.

## Документация — маршрутизатор

Подробности по теме — не блуждайте по исходникам:

| Тема | Файл |
|---|---|
| Карта проекта, дерево, инварианты окружения | [`docs/01_project_structure.md`](docs/01_project_structure.md) |
| Архитектура, слои, потоки данных, развёртывание | [`docs/02_architecture.md`](docs/02_architecture.md) |
| Жизненный цикл, маршруты, процессы, логирование | [`docs/03_execution_flow.md`](docs/03_execution_flow.md) |
| Качество кодовой базы, дефекты по критичности | [`docs/04_code_quality.md`](docs/04_code_quality.md) |
| Паттерны DI / параметры / async-слой данных | `docs/05`–`07` |
| Идеи развития: DI+API / слой данных / тесты+инфра | `docs/08`–`10` |
| Блог: архитектура, JSON API, React-интеграция, SPA-модуль | `docs/11`–`13`, `15` |
| Фабрика `create_app()` и `lifespan` | [`docs/14_create_fastapi_factory.md`](docs/14_create_fastapi_factory.md) |

Авторизация (fastapi-users, пакет `auth_users/`): `docs/04_authorization.md` внутри
пакета — см. маршрутизатор в `docs/01`.

## Соглашения разработки

- Длина строки: **ruff 100**, black 120; отступ 4 пробела. Ruff намеренно игнорирует
  `F401`, `E402`, `F541` — не «исправляйте» их.
- Декоративные комментарии-разделители (`# ====`, `# ----`) — логические секции,
  соблюдайте локальный стиль файла, не удаляйте.
- Русский язык для комментариев, docstring'ов, документации.
- **Импорты плоские, не пакетные**: `from core.config import settings` — приложение
  не устанавливается как пакет, cwd/`--app-dir` = `fastapi-application/`.
- `APIRouter` — на уровне модуля с `prefix=settings.api...` и `tags=[...]`;
  включение вложенных — в `__init__.py` своей папки.
- Сессия БД — только через `CurrentSession` из `db_core/db_async.py`.
- Логирование — через `logF` из `config_log.py`.
- Конфиг — вложенные pydantic-модели в `core/config.py` (префикс `APP__`,
  разделитель `__`). Новые настройки — поля модели с дефолтом, не `os.environ`.
- SQLAlchemy 2.0: `Mapped[]` + `mapped_column`, Annotated-типы из
  `db_core/type_for_models.py`. Новые модели реэкспортируйте в `db_core/__init__.py`
  — иначе невидимы для Alembic.
- Pydantic-схемы — рядом с доменом (`schemas/` или `schema_*.py`), имена
  `XxxCreate`/`XxxResp`, сериализация через `response_model`.

## Грабли

- **cwd-зависимость SQLite:** `./one_simple.db` резолвится от cwd. Данные
  «пропали» после смены способа запуска — проверьте, где лежит `*.db`.
- **Побочные эффекты на импорте:** `config_log` создаёт `log/` и настраивает
  логгеры на импорте; engine создаётся на импорте `db_core/db_async.py`.
- **Alembic требует cwd = `fastapi-application/`** (плоские импорты в `env.py`).
- **Профиль БД переключается правкой кода** (`core/config.py`), не env-переменной.

### Известные дефекты — не «исправляйте» без отдельного задания

- `GET /api/v1/depends_function_annotated/my_items/{item_id}` без `param_id` → 500
  (`validate_query_safe` сравнивает `1 <= None`).
- Дублирующийся `nickname` в `POST /users/create_user` → 500 вместо 409.
- `UserResp` наследует поле `password` от `UserCreate` (утечка в ответе).
- `TestUser` не реэкспортирован в `db_core/__init__.py` — невидим для Alembic
  (намеренная демонстрация примеси).

## Git

Заголовки коммитов короткие, нижний регистр. `log/`, `*.db`, `*.log`, `pg_db/`,
серты nginx — в `.gitignore`, никогда не добавляйте. Индексируйте только файлы,
относящиеся к изменению.

---

## Агентный режим

Эти правила применяются к каждому агенту команды, работающему над заданием из
[tasks/current/REQUIREMENTS.md](tasks/current/REQUIREMENTS.md). Оркестратор — главная сессия Qwen Code. При сомнениях
главенствует текущее задание, затем проектные соглашения выше.

### Жизненный цикл заданий

- Текущее задание живёт в `tasks/current/REQUIREMENTS.md`. Все рабочие артефакты —
  в той же папке: `DEFECTS.md`, `ADVERSARIAL_REVIEW.md`, `e2e/`, `screenshots/`,
  `dev/` (прогресс-файлы).
- Две фазы: **создание** (оркестратор → скилл `task-spec` → spec-writer → спека с
  планом фаз → подтверждение пользователем → заморозка) и **исполнение** (строго
  по фазам: фаза = одно делегирование = 1–3 файла = ~10–15 ходов; следующая —
  только после зелёного checkpoint и ревью диффа оркестратором).
- Упавший прогон не возобновляют пересказом: проверить процессы (`pgrep -af
  "uvicorn.*main:main_app"`) и мусор, прочитать `tasks/current/dev/phaseNN_progress.md`
  и `git diff`, запустить свежий узкий прогон «фаза N: сделано X, доделай Y».
- Когда все критерии успеха подтверждены, оркестратор архивирует задание в
  `tasks/NNN-<slug>/` с отчётом (шаблон — в QWEN.md) и создаёт свежую заглушку
  `tasks/current/REQUIREMENTS.md` «Задания нет».
- Закрытые задания лежат в `tasks/NNN-<slug>/` — целиком, со всеми артефактами;
  пишет туда только оркестратор.
- Комплект агентного режима переносим между проектами: адаптируются `README.md`,
  `QWEN.md`, `AGENTS.md`, `.qwen/`.

### Команда

- **оркестратор** (главная сессия, `QWEN.md`) — планирует, делегирует, ревьюит,
  контролирует критерии успеха. Код не пишет.
- **spec-writer** — фаза создания: пишет `tasks/current/REQUIREMENTS.md` с планом
  фаз. Код не пишет.
- **frontend-dev** — UI-слой: `frontend/` (React SPA), `nginx/web/` (если появится).
- **backend-dev** — серверная часть: роуты, схемы, модели, CRUD, конфигурация,
  миграции.
- **qa** — проверки запуском и curl-сценариями, заметки e2e, реестр DEFECTS.md.
- **adversary** — враждебные прогоны, ADVERSARIAL_REVIEW.md.

### Зоны и проверки (привязка к этому проекту)

| Агент | Зона (можно редактировать) | Чем проверяет изменения | Особые запреты |
|---|---|---|---|
| frontend-dev | `frontend/` (React SPA: источники, Vite-конфиги, сборка), `nginx/web/` (если появится в задании) | `cd frontend && npm run build` без ошибок; просмотр страницы; скриншот в `tasks/current/screenshots/` | Python-модули `fastapi-application/` — зона backend-dev; `frontend/dist` не коммитится |
| backend-dev | Python-модули `fastapi-application/` (включая `alembic/`, env-профили, `md_articles/`, `auth_users/` — слой авторизации fastapi-users) | `uv run ruff check .`; счётчик маршрутов (44); curl изменённых эндпоинтов на запущенном приложении | `frontend/`, `nginx/web/`; известные дефекты — не чинить без задания; дублирование `api/my_routes_dep/` — намеренное |
| qa | `tasks/current/e2e/`, `tasks/current/DEFECTS.md`, `tasks/current/screenshots/` | curl-сценарии из критериев успеха; регресс: `/docs`, `/users/get_all_users`, `/orders/get_all_orders`, один из `/api/v1/dep_examples/*`, `/art_home` | любой код продукта |
| adversary | `tasks/current/ADVERSARIAL_REVIEW.md`, `tasks/current/screenshots/` | curl по запущенному приложению; логи `fastapi-application/log/` | всё, кроме своих файлов |
| spec-writer | `tasks/current/REQUIREMENTS.md` — только на фазе создания, одним `write_file` по шаблону `.qwen/skills/task-spec/TEMPLATE.md` | чек-лист скилла `task-spec` | код продукта; всё, кроме REQUIREMENTS.md на фазе создания |

Общее для всех: не редактировать `.qwen/`, `tasks/current/REQUIREMENTS.md`, папки
архивных заданий `tasks/NNN-*`, `AGENTS.md`, `QWEN.md`, `README.md`, `docs/`,
`templates_qwen_agents/`; не добавлять зависимости и тестовые фреймворки без решения
оркестратора. Единственное исключение: spec-writer на фазе создания. Границы ролей
обеспечиваются системным промптом каждого агента — не обходите их командами оболочки.

### Соглашения репозитория агентного режима

- Всё о задании живёт в его папке: текущее — `tasks/current/`, закрытое —
  `tasks/NNN-<slug>/` с отчётом. В корне проекта файлов заданий нет.
- `tasks/current/e2e/` пишет только qa; `tasks/current/dev/` — backend-dev и
  frontend-dev (прогресс-файлы — страховка восстановления).
- `tasks/current/DEFECTS.md` ведут qa и оркестратор;
  `tasks/current/ADVERSARIAL_REVIEW.md` — adversary и оркестратор.
- Никаких эмодзи в коде, комментариях и логах.
- Тестовые сервера живут только на время живого задания: субагент поднимает сервер
  по своей спецификации и не глушит поднятый другим, но все тестовые процессы гасит
  оркестратор при закрытии задания.
- Новых тяжёлых зависимостей не добавлять без решения оркестратора, согласованного
  с пользователем.

### Экономия токенов субагентов

Каждый ход субагента пересылает весь накопленный контекст, поэтому длинный прогон
дорожает с каждым ходом, а упавший на 50+ ходу — миллионы токенов впустую.

- AGENTS.md и `tasks/current/REQUIREMENTS.md` читать один раз в начале прогона.
- Не читать исходники продукта целиком: разработчик смотрит только свою зону правок,
  qa проверяет поведение, а не код.
- Объединять проверки в пачки (один shell-вызов — несколько curl), сырые выводы
  сразу писать в файл (`tasks/current/e2e/` у qa, `tasks/current/dev/` у
  разработчиков), в чат — только вердикты.
- Ошибку читать и исправлять, а не повторять вслепую. Две подряд неудачные попытки
  починить одно и то же — стоп и доклад оркестратору.
- Работать на минимум ходов.

Главный источник перерасхода — **backend-dev** (код-писатель тяжелеет быстрее всех).
Защита: спека с планом фаз заранее; короткие фазы; дисциплина внутри фазы. Формат
qa/adversary (пачки curl) дешёвый — не менять.

Урок 001-md-articles-blog: монолитный запуск backend-dev на весь бэкенд (~8 модулей
+ миграция) обошёлся в ~25 млн токенов; qa и adversary уложились дёшево.

Как запускать тестера — раздел «Экономия токенов» в `.qwen/agents/qa.md`.

### DEFECTS.md — реестр дефектов

Все дефекты живут в `tasks/current/DEFECTS.md` (создаётся при первом дефекте), одна
запись на дефект, новые сверху. Авторы: **qa** (создание, закрытие, переоткрытие) и
**оркестратор** (фиксация ответов разработчиков, отклонение). Больше никто.

Формат, точно:

    ## DEF-001: Краткий заголовок

    - Status: OPEN
    - Severity: HIGH | MEDIUM | LOW
    - Found by: qa | adversary (ADV-003)
    - Task: <название текущего задания>

    Steps to reproduce:
    1. Пронумерованные, конкретные, начиная с запуска приложения.

    Expected: Что должно произойти.
    Actual: Что происходит вместо этого.
    Screenshot: tasks/current/screenshots/def-001.png (опционально)

    History:
    - qa: opened

Статусы и кто их устанавливает:

| Статус | Значение | Кто устанавливает |
|---|---|---|
| OPEN | Заведён или переоткрыт после неудачного ретеста | qa |
| FIX-READY | Разработчик сообщил, что исправление внесено | оркестратор, передавая слова разработчика |
| DISPUTED | Разработчик сообщил НЕ ВОСПРОИЗВОДИТСЯ или РАБОТАЕТ КАК ЗАДУМАНО, с причиной | оркестратор, дословно |
| CLOSED | qa перетестировал и подтвердил исправление либо принял спор | только qa |
| REJECTED | Исправляться не будет, с письменной причиной | только оркестратор |

Каждая смена статуса добавляет строку в History. Дефект завершён, только когда qa
его закрывает.

### ADVERSARIAL_REVIEW.md — находки adversary

Все находки adversary живут в `tasks/current/ADVERSARIAL_REVIEW.md` (создаётся при
первом прогоне). Авторы: **adversary** (создание записей) и **оркестратор**
(заполнение Disposition). Больше никто.

Формат, точно:

    ## ADV-001: Краткий заголовок

    - Session: <задание> | final
    - Suggested severity: HIGH | MEDIUM | LOW

    What I did: ...
    Expected: ...
    Actual: ...
    Screenshot: tasks/current/screenshots/adv-001.png (опционально)

    Disposition: PENDING

Оркестратор заменяет PENDING на `ACCEPTED -> DEF-NNN` или `REJECTED - причина`.
Когда задание закрыто, ни одна запись не может оставаться PENDING.
