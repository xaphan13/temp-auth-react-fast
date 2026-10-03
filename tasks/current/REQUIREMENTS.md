# Актуализация документации auth под два транспорта, учебный разбор потоков и логирование цепочки вызовов

В проекте уже реализованы два транспорта авторизации (`CookieTransport` для браузера и
`BearerTransport` для не-браузерных клиентов) на общей `JWTStrategy` и Signed Double Submit
Cookie CSRF — но часть `docs/` осталась от прежнего контракта `/auth/jwt/*` и утверждает,
что CSRF-защиты нет. Задание: привести существующую документацию авторизации в соответствие
фактическому коду, написать подробный живой учебный разбор обоих потоков с фрагментами кода
и схемами, добавить в бэкенд целевое логирование цепочки вызовов авторизации и сверять
внешние утверждения через Tavily по первичным источникам (RFC, OWASP, MDN, FastAPI,
fastapi-users), включая ссылки в документы.

## Архитектурный разбор

- **Bounded context:** документация auth (`docs/02`, `docs/03`, `docs/04`, `docs/05`,
  `docs/06`, `docs/07`, `docs/08`, `docs/10`, `docs/11`), плюс целевое логирование в
  `fastapi-application/auth_users/*` и `fastapi-application/main.py`. Вне зоны: домен заказов,
  демо-API, фронтенд-логика (меняется только в объёме, нужном для точности документации),
  миграции и модели.
- **Интеграционные границы:** `auth_users/auth_backend.py` (`cookie_backend`,
  `bearer_backend`, `get_jwt_strategy`), `auth_users/fastapi_users_obj.py` (порядок
  backend'ов cookie → bearer), `auth_users/router.py` (префиксы `/auth/cookie`,
  `/auth/bearer`, `/auth/register`, `/users/me`, `/api/v1/auth/protected`),
  `auth_users/csrf.py` (`CSRFMiddleware`, cookie `csrf_token`, заголовок `X-CSRF-Token`),
  `config_log.py` (`logF`, `logFC`, logger `OnlyFile` уровня DEBUG).
- **Порядок работ:** сначала логирование в бэкенде (фазы 1–2), затем документация по
  фактическому коду (фазы 3–5), затем проверки qa/adversary. Документация не может быть
  достоверной до появления логов.
- **Зависимости:** новых тяжёлых зависимостей не добавляем. Логирование — стандартный
  `logging` через существующий `logF`. Tavily — внешний инструмент поиска, вызывается в фазе
  docs-writer; в кодовой базе изменений не требует.
- **Безопасность:** логи не должны содержать пароли, значения JWT/токенов, полные значения
  cookie и CSRF-токена — только факты (префиксы путей, имена транспортов, результат проверки,
  идентификатор пользователя, статус). Это отдельный критерий успеха.
- **Производительность:** логирование в auth-path обязано быть дешёвым (одна строка на
  запрос уровня DEBUG/INFO), без сериализации объектов запроса и без раскрытия секретов.

## Подтверждённые решения

- Задание только про документацию и логирование; продуктовый код меняется исключительно в
  части логирования и не меняет поведение API (маршруты, коды ответов, cookie, CSRF).
- Целевая документация — существующие файлы `docs/`; новые документы не создаём, кроме
  случаев, когда содержимое не помещается в существующий файл (границы ниже).
- Логирование — через существующий `logF`/`logFC` из `config_log.py`; новые библиотеки и
  настройки логирования (formatters/handlers) не добавляем.
- Логировать: вход в `protected` (identify факта и пользователя), результат CSRF-проверки,
  выбор транспорта в `Depends(active_user)`-цепочке, lifecycle CSRF-cookie (выдача/удаление)
  и вход/выход `get_user_manager`. Не логировать секреты и PII сверх `email`/`user.id`.
- Tavily обязателен для внешних утверждений (RFC/OWASP/MDN/FastAPI/fastapi-users) в
  учебных разборах; ссылки и дата сверки указываются в документе.
- Adversary в план не включён по умолчанию, но пользователь просил его участие — поэтому
  фаза adversary присутствует и обязательна.
- Файл `docs/13_frontend_spa_module.md` упомянут в `main.py`, но отсутствует; создавать его
  вне рамок задания.
- Дубликат нумерации `docs/09_*` (`09_auth_transport_and_api_keys.md` и
  `09_auth_tutorial.md`) не переименовываем — вне рамок.

## Результат

После задания в репозитории:

- `docs/02_architecture.md`, `docs/03_execution_flow.md` — без устаревшего `/auth/jwt/*`;
  актуальные `/auth/cookie/*` и `/auth/bearer/*`, счётчик OpenAPI 25.
- `docs/04_authorization.md` — актуальный контракт двух транспортов, CSRF-поток с
  `X-CSRF-Token`, ссылки на код; без утверждения «CSRF-защиты нет».
- `docs/05_authorization_upgrade.md` — ручные curl-рецепты на `/auth/cookie/*` и
  `/auth/bearer/*`; раздел «что уже работает» согласован с CSRF-middleware.
- `docs/06_auth_visual.md`, `docs/07_auth_token_flow_code.md` — маршруты и примеры кода на
  актуальных путях; `docs/07` разбирает оба потока (cookie и Bearer).
- `docs/08_jwt_transport_options.md`, `docs/10_auth_transport_strategy_tutorial.md`,
  `docs/11_frontend_browser_api_csrf.md` — снято утверждение об отсутствии CSRF, добавлен
  разбор реализованной Signed Double Submit Cookie и обоих транспортов.
- Новый учебный документ `docs/12_auth_dual_transport_walkthrough.md` — подробный живой
  разбор обоих потоков: cookie (React → fastapi-users → Set-Cookie → CSRF → protected) и
  bearer (`/auth/bearer/login` → JSON access_token → `Authorization: Bearer` → protected),
  фрагменты реального кода backend и frontend, mermaid-схемы, curl-рецепты, ссылки Tavily.
- `fastapi-application/auth_users/*` и `main.py` — целевое логирование цепочки авторизации
  (DEBUG/INFO, без секретов), `ruff check` чист, OpenAPI paths = 25, поведение API неизменно.
- `tasks/current/e2e/` — сырые доказательства qa; `tasks/current/ADVERSARIAL_REVIEW.md` —
  находки adversary.

## Вне рамок

- Любые изменения поведения API: маршруты, коды ответов, cookie-атрибуты, CSRF-логика,
  модели, схемы, миграции, зависимости.
- Фронтенд-код `frontend/` (кроме чтения для точности документации; правок не требуется).
- Правки `AGENTS.md`, `QWEN.md`, `README.md`, `.qwen/`, `tasks/NNN-*`.
- Создание `docs/13_frontend_spa_module.md`, переименование дубликатов `docs/09_*`.
- Добавление тестов/pytest и новых зависимостей.
- Утверждения о финальном выпуске в production (это учебный шаблон); roadmap-разделы
  `docs/05` сохраняют статус «не реализовано», кроме уже сделанного dual-transport + CSRF.

## План фаз

Единица исполнения — фаза: одно делегирование, 1–3 файла, бюджет ~10–15 ходов.
Следующая фаза стартует только после зелёного checkpoint и ревью диффа оркестратором.
Прогресс фазы разработчик фиксирует в `tasks/current/dev/phaseNN_progress.md`.

| # | Фаза | Исполнитель | Файлы | Контракт | Checkpoint | Бюджет ходов |
|---|---|---|---|---|---|---|
| 1 | Логирование auth-цепочки (backend) | backend-dev | `auth_users/router.py`, `auth_users/csrf.py`, `auth_users/user_manager.py` | logger `logF`, без секретов | `ruff check` чист; OpenAPI paths = 25; `/protected` пишет строку в `log/temp_auth.log` | ~12 |
| 2 | Логирование lifecycle и старта (backend) | backend-dev | `main.py` | одна строка логирования порядка backend'ов при старте | import `main` без ошибок; `ruff check` чист; строка в логе | ~8 |
| 3 | Актуализация `docs/02`, `docs/03`, `docs/05` | docs-writer | `docs/02_architecture.md`, `docs/03_execution_flow.md`, `docs/05_authorization_upgrade.md` | пути `/auth/cookie/*`, `/auth/bearer/*`, 25 paths | grep не находит устаревших утверждений о текущем `/auth/jwt/*` | ~12 |
| 4 | Актуализация `docs/04` (контракт двух транспортов + CSRF) | docs-writer | `docs/04_authorization.md` | актуальные пути, CSRF-поток, ссылки на код | grep не находит «CSRF-защиты нет»; есть оба транспорта | ~12 |
| 5 | Актуализация `docs/06`, `docs/07`, `docs/08` | docs-writer | `docs/06_auth_visual.md`, `docs/07_auth_token_flow_code.md`, `docs/08_jwt_transport_options.md` | актуальные маршруты и код; оба транспорта | grep не находит «Один backend», «CSRF-защиты нет», текущих `/auth/jwt/*` | ~15 |
| 6 | Актуализация `docs/10`, `docs/11` (снятие устаревших тезисов о CSRF) | docs-writer | `docs/10_auth_transport_strategy_tutorial.md`, `docs/11_frontend_browser_api_csrf.md` | реализованная Signed Double Submit Cookie; cookie + bearer | grep не находит «отдельного CSRF-токена сейчас нет» | ~12 |
| 7 | Учебный разбор обоих потоков с Tavily | docs-writer | новый `docs/12_auth_dual_transport_walkthrough.md` | фрагменты реального кода, mermaid, Tavily-ссылки, curl | файл существует; содержит оба потока, ≥6 Tavily-ссылок, `auth/bearer/login` и `/auth/cookie/login` | ~15 |
| 8 | Синхронизация навигации и README-таблицы | docs-writer (запрет на README.md → правит оркестратор) / оркестратор | `docs/00_agent_navigation.md`, `docs/01_project_structure.md`; README — оркестратор | ссылка на новый `docs/12`; актуальные пути | grep находит `docs/12` в навигаторе; нет устаревших путей | ~10 |
| 9 | E2E-проверка: логи, curl-потоки, регресс | qa | `tasks/current/e2e/*.md` | сырые выводы и вердикты | cookie-цикл, bearer-цикл и регресс пройдены; логи содержат строки auth | ~12 |
| 10 | Враждебный прогон CSRF/транспортов и логирования | adversary | `tasks/current/ADVERSARIAL_REVIEW.md` | находки по формату ADV | записи созданы, без PENDING после триажа | ~10 |

### Фаза 1: Логирование auth-цепочки (backend)

- Файлы: `fastapi-application/auth_users/router.py`, `fastapi-application/auth_users/csrf.py`,
  `fastapi-application/auth_users/user_manager.py`.
- Контракт: используем `logF` из `config_log.py`; уровень DEBUG/INFO; сообщения — только
  факты без секретов. Строки должны позволять проследить цепочку: вход в `protected`
  (путь, факт успешной/неуспешной аутентификации, `user.id` при успехе); результат CSRF-проверки
  (`method`, `path`, `required=True/False`, `valid=True/False`); lifecycle CSRF-cookie
  (выдача/удаление); вход/выход `get_user_manager`.
- Шаги:
  1. В `router.py::protected` добавить `logF.info` при входе (идёт до `Depends`, поэтому
     логирование факта аутентификации — в самом обработчике с `user.id`).
  2. В `csrf.py::dispatch` — `logF.debug` о результате `_requires_check`/`_check_request`
     и о выдаче/удалении `csrf_token`; при 403 — `logF.warning` с method/path.
  3. В `user_manager.py::get_user_manager` — заменить текущий `logF.debug(user_db)` на
     безопасную строку (без repr объекта с данными БД) и добавить лог входа/выхода.
  4. Не логировать значения `csrf_token`, cookie `auth`, JWT, пароли.
- Checkpoint:
  ```bash
  cd fastapi-application && uv run ruff check auth_users/ && \
  ../.venv/bin/python -c "from main import main_app; print(len(main_app.openapi()['paths']))"
  ```
  Ожидание: ruff чист, вывод `25`. Плюс: после прогона `protected` в `log/temp_auth.log`
  появляется строка с маркером auth-цепочки.
- Готовность фазы: логирование добавлено, лишнего кода нет, поведение API неизменно
  (проверяется на фазе 9).

### Фаза 2: Логирование lifecycle и старта (backend)

- Файлы: `fastapi-application/main.py`.
- Контракт: при старте приложения логируется порядок зарегистрированных backend'ов
  (`jwt-cookie`, `jwt-bearer`) — факт, подтверждающий контракт «cookie → bearer» из
  `fastapi_users_obj.py`. Формат строки фиксируется в спеке: содержит имена обоих backend'ов.
- Шаги:
  1. Добавить одну строку `logF.info` с именами backend'ов, полученных из
     `fastapi_users.authenticator.backends` (или из явного списка), без раскрытия секретов.
  2. Не менять порядок `add_middleware`/`include_router`/`mount_frontend`.
- Checkpoint:
  ```bash
  cd fastapi-application && uv run ruff check main.py && \
  ../.venv/bin/python -c "from main import main_app; print('ok')"
  ```
  Ожидание: ruff чист, `ok`. Плюс: строка с `jwt-cookie` и `jwt-bearer` в `log/temp_auth.log`.
- Готовность фазы: логируется порядок и состав backend'ов; маршрутизация не затронута.

### Фаза 3: Актуализация `docs/02`, `docs/03`, `docs/05`

- Файлы: `docs/02_architecture.md`, `docs/03_execution_flow.md`, `docs/05_authorization_upgrade.md`.
- Контракт: единственный актуальный контракт — `/auth/cookie/login|logout`,
  `/auth/bearer/login|logout`, `/auth/register`, `/users/me` (GET/PATCH), `/auth/account`,
  `/api/v1/auth/protected`; OpenAPI paths = 25; CSRF-защита реализована в
  `auth_users/csrf.py`.
- Шаги:
  1. Заменить упоминания `/auth/jwt/*` как текущих путей на `/auth/cookie/*` и
     `/auth/bearer/*` (docs/02, docs/03).
  2. В docs/03 описать поток login/logout на актуальных путях.
  3. В docs/05 обновить раздел «что уже работает» (два транспорта + CSRF) и curl-рецепты
     ручной проверки на актуальные пути и обязательный `X-CSRF-Token`.
- Checkpoint:
  ```bash
  rg -n "auth/jwt" docs/02_architecture.md docs/03_execution_flow.md docs/05_authorization_upgrade.md
  ```
  Ожидание: совпадений нет (кроме явных исторических примечаний, если сохранены — тогда
  каждое помечено как «устаревший прежний контракт»).
- Готовность фазы: документы описывают только актуальный контракт.

### Фаза 4: Актуализация `docs/04` (контракт двух транспортов + CSRF)

- Файлы: `docs/04_authorization.md`.
- Контракт: два транспорта на общей `JWTStrategy`; cookie-поток с `csrf_token` и
  `X-CSRF-Token`; bearer-поток с JSON `access_token`; `active_user` перебирает backend'ы
  cookie → bearer; ссылки на фактические файлы кода.
- Шаги:
  1. Сверить с кодом таблицу маршрутов и шаги cookie-login (включая `Set-Cookie: csrf_token`).
  2. Добавить раздел bearer-потока: `/auth/bearer/login` → JSON → `Authorization: Bearer`.
  3. Устранить любое утверждение, что CSRF-защиты нет; описать `CSRFMiddleware` и
     файл `auth_users/csrf.py`.
  4. Проверить раздел «Файлы реализации» — добавить `auth_users/csrf.py` в backend-список.
- Checkpoint:
  ```bash
  rg -n "CSRF-защиты нет|отдельного CSRF" docs/04_authorization.md
  ```
  Ожидание: совпадений нет; в документе присутствуют `/auth/cookie/login`, `/auth/bearer/login`,
  `X-CSRF-Token`, `csrf.py`.
- Готовность фазы: docs/04 — единый актуальный разбор обоих транспортов.

### Фаза 5: Актуализация `docs/06`, `docs/07`, `docs/08`

- Файлы: `docs/06_auth_visual.md`, `docs/07_auth_token_flow_code.md`,
  `docs/08_jwt_transport_options.md`.
- Контракт: маршруты и примеры кода — на актуальных путях; backend'ов два; CSRF реализована.
- Шаги:
  1. docs/06: заменить `/auth/jwt/login|logout` в диаграммах и инвентаре на `/auth/cookie/*`
     и `/auth/bearer/*`; обновить инвентарь маршрутов (учесть bearer-пути).
  2. docs/07: примеры `api/auth.ts` и curl — на `/auth/cookie/*`; добавить разбор bearer-потока
     по коду.
  3. docs/08: убрать утверждения «CSRF-защиты нет», «Один backend», обновить пример
     «cookie + bearer рядом» как реализованный, а не «вариант для развития».
- Checkpoint:
  ```bash
  rg -n "auth/jwt|CSRF-защиты нет|Один backend" docs/06_auth_visual.md docs/07_auth_token_flow_code.md docs/08_jwt_transport_options.md
  ```
  Ожидание: нет совпадений как текущего состояния (исторические пометки допустимы и явно
  помечены).
- Готовность фазы: три документа согласованы с кодом и друг с другом.

### Фаза 6: Актуализация `docs/10`, `docs/11` (снятие устаревших тезисов о CSRF)

- Файлы: `docs/10_auth_transport_strategy_tutorial.md`, `docs/11_frontend_browser_api_csrf.md`.
- Контракт: CSRF реализована (Signed Double Submit Cookie); пути — `/auth/cookie/*`,
  `/auth/bearer/*`; обоих транспортов два.
- Шаги:
  1. docs/11: заменить «отдельного CSRF-токена сейчас нет» на описание реализованной
     защиты (`csrf_token` cookie + `X-CSRF-Token` header, `CSRFMiddleware`); обновить
     примеры путей и `api/auth.ts`.
  2. docs/10: обновить разделы 3.x и примеры на `/auth/cookie/*` и `/auth/bearer/*`;
     сверить утверждение «в проекте второй backend не подключён».
- Checkpoint:
  ```bash
  rg -n "auth/jwt|отдельного CSRF-токена сейчас нет|второй backend не подключён" docs/10_auth_transport_strategy_tutorial.md docs/11_frontend_browser_api_csrf.md
  ```
  Ожидание: нет совпадений.
- Готовность фазы: оба документа отражают фактическое состояние.

### Фаза 7: Учебный разбор обоих потоков с Tavily

- Файлы: новый `docs/12_auth_dual_transport_walkthrough.md`.
- Контракт: документ самодостаточный; фрагменты реального кода backend (`auth_backend.py`,
  `router.py`, `csrf.py`, `fastapi_users_obj.py`) и frontend (`client.ts`, `auth.ts`,
  `AuthContext.tsx`, `ProtectedPage.tsx`); mermaid-схемы для обоих потоков; curl-рецепты;
  ссылки с датой сверки, полученные через Tavily. Обязательные внешние темы: OWASP CSRF
  Cheat Sheet (double-submit), RFC 6750 (Bearer), RFC 6265 (Cookie), RFC 7519 (JWT),
  MDN fetch/credentials/Set-Cookie, документация fastapi-users (несколько backend'ов),
  FastAPI Security. Минимум 6 ссылок с датой сверки «2026-10-03».
- Шаги:
  1. Собрать внешние источники через Tavily (первичные: RFC, OWASP, MDN, официальные доки).
  2. Написать разбор cookie-потока: LoginPage → `/auth/cookie/login` → `Set-Cookie auth +
     csrf_token` → `/users/me` → `/api/v1/auth/protected` c `X-CSRF-Token` → logout.
  3. Написать разбор bearer-потока: `/auth/bearer/login` → JSON `access_token` →
     `Authorization: Bearer` → `/users/me`, `/api/v1/auth/protected`; отсутствие CSRF при
     отсутствии auth-cookie; смешанный запрос не обходит CSRF.
  4. Добавить mermaid (sequence + graph) и curl-рецепты для обоих потоков.
  5. Добавить раздел источников с ссылками Tavily и датой сверки.
- Checkpoint:
  ```bash
  test -f docs/12_auth_dual_transport_walkthrough.md && \
  rg -c "auth/bearer/login" docs/12_auth_dual_transport_walkthrough.md && \
  rg -c "auth/cookie/login" docs/12_auth_dual_transport_walkthrough.md && \
  rg -c "https?://" docs/12_auth_dual_transport_walkthrough.md
  ```
  Ожидание: файл есть; оба пути встречаются; ссылок ≥ 6.
- Готовность фазы: документ читается самостоятельно, согласован с кодом, имеет внешние
  источники.

### Фаза 8: Синхронизация навигации и структуры

- Файлы: `docs/00_agent_navigation.md`, `docs/01_project_structure.md`. README.md правит
  оркестратор (docs-writer его не трогает).
- Контракт: навигатор ссылается на `docs/12`; инвентарь маршрутов и счётчик 25 актуальны;
  разделы про CSRF не содержат устаревшего «нет защиты».
- Шаги:
  1. docs/00: добавить строку про `docs/12` в таблицу вопрос → документ; проверить, что
     инвентарь auth-маршрутов актуален.
  2. docs/01: сверить API-инвентарь и любой счётчик маршрутов.
  3. Сообщить оркестратору точную строку для README-таблицы (сам README не править).
- Checkpoint:
  ```bash
  rg -n "12_auth_dual_transport_walkthrough" docs/00_agent_navigation.md && \
  rg -n "auth/jwt" docs/00_agent_navigation.md docs/01_project_structure.md
  ```
  Ожидание: ссылка на docs/12 найдена; `auth/jwt` как текущий путь не встречается.
- Готовность фазы: навигация полная, структура согласована.

### Фаза 9: E2E-проверка

- Файлы: `tasks/current/e2e/*.md` (сырые выводы), `tasks/current/DEFECTS.md` при находках.
- Контракт: проверяем поведение, а не код; сырые выводы — в файлы, в чат — вердикты.
- Шаги:
  1. Запустить приложение из `fastapi-application/` (uvicorn, порт 8000).
  2. Прогнать cookie-цикл: register → `/auth/cookie/login` → `/users/me` →
     `/api/v1/auth/protected` → `/auth/cookie/logout` с `X-CSRF-Token` (взять из
     `csrf_token` cookie) → повторный `protected` = 401.
  3. Прогнать bearer-цикл: `/auth/bearer/login` → `Authorization: Bearer` на `/users/me` и
     `/api/v1/auth/protected` → `/auth/bearer/logout` = 204.
  4. Прогнать регресс: `/docs`, анонимный `/users/me` = 401,
     `/orders/get_all_orders?params=id`, `/api/v1/dep_examples/single-direct-dependency`,
     CSRF-проверки (state-changing без заголовка = 403, смешанный cookie+Bearer без
     заголовка = 403).
  5. Проверить логи: `log/temp_auth.log` содержит строки auth-цепочки; в логах нет значений
     JWT/паролей/полных cookie.
  6. Сохранить сырые выводы в `tasks/current/e2e/`.
- Checkpoint: все сценарии возвращают ожидаемые коды; лог-файл содержит маркеры фаз 1–2;
  секреты в логе отсутствуют.
- Готовность фазы: критерии успеха подтверждены доказательствами.

### Фаза 10: Враждебный прогон

- Файлы: `tasks/current/ADVERSARIAL_REVIEW.md`.
- Контракт: найти обходы CSRF и утечки через логи; формат записей — ADV.
- Шаги:
  1. Попытки обойти CSRF: mixed cookie+Bearer без заголовка, повторный logout, подделка
     `X-CSRF-Token`, запрос без auth-cookie.
  2. Проверка, что bearer-login/logout не требуют CSRF и не создают cookie.
  3. Проверка утечек: поиск JWT/паролей/полных cookie в `log/`.
  4. Записать находки в `tasks/current/ADVERSARIAL_REVIEW.md`.
- Checkpoint: файл создан, каждая запись имеет Disposition (после триажа оркестратором —
  не PENDING).
- Готовность фазы: ни одна запись не остаётся PENDING при закрытии.

## Критерии успеха

Проверяются qa по завершении всех фаз; сырые выводы — в `tasks/current/e2e/`.

| # | Критерий | Проверка | Ожидание |
|---|---|---|---|
| 1 | Поведение API не изменено | `cd fastapi-application && ../.venv/bin/python -c "from main import main_app; print(len(main_app.openapi()['paths']))"` | `25` |
| 2 | Cookie-login выдаёт обе cookie | `curl -i -c /tmp/a.cookies -X POST http://127.0.0.1:8000/auth/cookie/login -H 'Content-Type: application/x-www-form-urlencoded' --data 'username=<email>&password=<pass>'` | `204` + `Set-Cookie: auth=...` + `Set-Cookie: csrf_token=...` |
| 3 | Bearer-login выдаёт JWT в JSON | `curl -i -X POST http://127.0.0.1:8000/auth/bearer/login -H 'Content-Type: application/x-www-form-urlencoded' --data 'username=<email>&password=<pass>'` | `200` + `{"access_token":"...","token_type":"bearer"}` |
| 4 | Bearer-запрос к protected работает | `curl -i -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/v1/auth/protected` | `200` + `authenticated: true` |
| 5 | CSRF обязателен для cookie state-changing | `curl -i -b /tmp/a.cookies -X POST http://127.0.0.1:8000/auth/cookie/logout` без `X-CSRF-Token` | `403` |
| 6 | Cookie+Bearer не обходит CSRF | `curl -i -b /tmp/a.cookies -H "Authorization: Bearer $TOKEN" -X POST .../auth/account` без `X-CSRF-Token` | `403` |
| 7 | Cookie-logout с CSRF успешен, затем 401 | logout с `X-CSRF-Token` → `204`; повторный `protected` | `401` |
| 8 | Логирование цепочки auth присутствует | `rg -n "auth" fastapi-application/log/temp_auth.log` после прогонов | строки про protected/CSRF/lifecycle найдены |
| 9 | Секреты не попадают в логи | `rg -n "eyJ|password|csrf_token=.*\." fastapi-application/log/temp_auth.log` | совпадений значений JWT/пароля/cookie нет |
| 10 | Устаревшие утверждения удалены | `rg -n "auth/jwt|CSRF-защиты нет|Один backend" docs/02_architecture.md docs/03_execution_flow.md docs/04_authorization.md docs/05_authorization_upgrade.md docs/06_auth_visual.md docs/07_auth_token_flow_code.md docs/08_jwt_transport_options.md docs/10_auth_transport_strategy_tutorial.md docs/11_frontend_browser_api_csrf.md` | нет совпадений как текущего состояния |
| 11 | Новый учебный разбор существует | `test -f docs/12_auth_dual_transport_walkthrough.md && rg -c "auth/bearer/login" docs/12_auth_dual_transport_walkthrough.md` | файл есть; оба пути встречаются |
| 12 | Внешние источники через Tavily | `rg -c "https?://" docs/12_auth_dual_transport_walkthrough.md` | ≥ 6 ссылок, есть дата сверки `2026-10-03` |
| 13 | Навигатор ссылается на новый документ | `rg -n "12_auth_dual_transport_walkthrough" docs/00_agent_navigation.md` | найдено |
| 14 | Ruff чист по изменённым модулям | `cd fastapi-application && uv run ruff check auth_users/ main.py` | без ошибок |

## Финальные критерии

1. Каждый критерий успеха подтверждён доказательством (e2e/, DEFECTS.md,
   ADVERSARIAL_REVIEW.md).
2. `tasks/current/DEFECTS.md` существует только если найдены дефекты; все записи
   не OPEN.
3. Adversarial-прогон выполнен, ни одна запись ADVERSARIAL_REVIEW.md не PENDING.

## Открытые вопросы

Закрываются с пользователем ДО старта исполнения; ответы переезжают
в «Подтверждённые решения».

- Нет открытых вопросов: все развилки закрыты разумными решениями выше (объём
  документации — существующие файлы + один новый разбор; логирование — через `logF` без
  новых зависимостей; пути и счётчик маршрутов сверены с кодом; Tavily-ссылки обязательны в
  учебном разборе).