# DEFECTS.md — реестр дефектов текущего задания

Задание: Актуализация документации auth под два транспорта, учебный разбор потоков и
логирование цепочки вызовов.

## DEF-001: ruff не проходит по изменённым модулям (критерий успеха 14)

- Status: CLOSED
- Severity: MEDIUM
- Found by: qa
- Task: Актуализация документации auth под два транспорта + логирование цепочки

Steps to reproduce:
1. Из корня репозитория: `cd fastapi-application`.
2. Выполнить команду checkpoint'а критерия успеха 14:
   `../.venv/bin/ruff check auth_users/ main.py`
   (эквивалент `uv run ruff check auth_users/ main.py`).

Expected: ruff без ошибок (спека: «`ruff check` чист», критерий 14 «без ошибок»).
Actual: `Found 1 error.` — `I001 [*] Import block is un-sorted or un-formatted` в
`auth_users/user_manager.py:12` (импорт добавленного `from config_log import logF`
сломал сортировку блока импортов; исправляется `ruff check --fix`, одно из двух:
перестановка `fastapi_users.models`). Сырой вывод: `e2e/raw_ruff_auth_users.txt`.
Фаза 1 checkpoint («ruff check чист») формально не зелёный; функционально поведение API
не затронуто (все curl-прогоны зелёные).
Screenshot: (не требуется — текстовый вывод)

History:
- qa: opened (2026-10-03, прогон фазы 9)
- qa: closed (2026-10-03, retest2 на специализированной QA-модели, порт 8031): свежий
  `uv run ruff check auth_users/ main.py` → `All checks passed!` (raw_retest2_static.txt).
  Регресс вокруг исправления: OpenAPI paths=25; полный cookie-цикл (login 204 + обе cookie,
  /users/me 200, protected 200, CSRF-reject 403, logout с X-CSRF-Token 204, protected 401);
  bearer-цикл (login 200 JSON, protected 200, logout 204); логи с маркерами auth-цепочки
  без секретов. Доказательства: e2e/raw_retest2_static.txt, e2e/raw_retest2_run.txt,
  e2e/2026-10-03_qa_retest2_report.md.

## DEF-002: README содержит устаревший счётчик маршрутов «23 path-ключа»

- Status: CLOSED
- Severity: LOW
- Found by: qa
- Task: Актуализация документации auth под два транспорта + логирование цепочки

Steps to reproduce:
1. Из корня репозитория: `sed -n '125,140p' README.md` (или grep `path-ключа` README.md).
2. Сравнить с фактом: `cd fastapi-application && ../.venv/bin/python -c "from main import main_app; print(len(main_app.openapi()['paths']))"` → `25`.

Expected: внешняя проверка в README («Линтеры и проверка изменений») даёт актуальный
счётчик 25 path-ключей OpenAPI, согласованный с docs/00 («25»), docs/01 («25») и AGENTS.md.
Actual: `README.md:134` — комментарий команды `# 23 path-ключа OpenAPI`. Расхождение с
фактическими 25. Примечание: строка была устаревшей и до этого задания (`git diff README.md`
показывает, что задание добавило в README только ссылку на docs/12, строку 134 не трогало);
README в этом задании правит оркестратор, для qa файл — вне зоны записи, поэтому дефект
регистрационный, правка — за оркестратором.
Screenshot: (не требуется)

History:
- qa: opened (2026-10-03, прогон фазы 9)
- qa: closed (2026-10-03, retest2): `grep -n "path-ключ" README.md` → `README.md:134`
  содержит `# 25 path-ключей OpenAPI`; факт подтверждён двумя независимыми измерениями:
  python-счётчик `main_app.openapi()['paths']` = 25 и `openapi.json` на живом приложении
  (порт 8031) = 25. Регресс: целиковой curl-прогон (cookie/bearer/CSRF/регресс) зелёный —
  правка README не затронула поведение. Доказательства: e2e/raw_retest2_static.txt,
  e2e/raw_retest2_run.txt, e2e/2026-10-03_qa_retest2_report.md.

## DEF-003: docs/12 ссылается на документацию fastapi-users 12.1 при установленной 15.0.5

- Status: CLOSED
- Severity: LOW
- Found by: qa
- Task: Актуализация документации auth под два транспорта + логирование цепочки

Steps to reproduce:
1. `rg -n "fastapi-users.github.io" docs/12_auth_dual_transport_walkthrough.md` — строка 460:
   ссылка `https://fastapi-users.github.io/fastapi-users/12.1/configuration/oauth`.
2. Проверить установленную версию: `.venv/bin/python -c "import importlib.metadata as m; print(m.version('fastapi-users'))"` → `15.0.5`.

Expected: внешние ссылки учебных разборов ведут на документацию версии, соответствующей
используемой (для fastapi-users 15.x актуальные доки
`https://fastapi-users.github.io/fastapi-users/15.0/...`, либо версия `latest`), либо явная
оговорка о расхождении версий.
Actual: ссылка на раздел OAuth доков 12.1; оговорка в тексте есть («general library
context; this project uses custom dual-backend setup»), но версия документации расходится
с установленной на два минорных релиза. Контракт критериев 11–12 при этом выполнен
(ссылок ≥6, оба login-пути присутствуют, дата сверки 2026-10-03) — дефект косметический,
косвенно касается требования «сверять внешние утверждения по первичным источникам».
Screenshot: (не требуется)

History:
- qa: opened (2026-10-03, прогон фазы 9)
- qa: closed (2026-10-03, retest2): `grep -n "fastapi-users.github.io"
  docs/12_auth_dual_transport_walkthrough.md` — единственная ссылка на доки библиотеки
  (строка 460) ведёт на `https://fastapi-users.github.io/fastapi-users/latest/configuration/authentication/`;
  URL с версией `12.1` в файле не встречается (заменён на `latest`, версия больше не
  расходится явным образом). Регресс по контракту критериев 11–12: файл существует,
  `auth/bearer/login` — 4 вхождения, `auth/cookie/login` — 5, `https?://` — 29 ссылок (≥6),
  дата сверки `2026-10-03` — 3 вхождения; ссылка на docs/12 в docs/00 присутствует.
  Доказательства: e2e/raw_retest2_static.txt, e2e/2026-10-03_qa_retest2_report.md.
