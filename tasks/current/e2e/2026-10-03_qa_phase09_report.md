# QA-прогон фазы 9 — 2026-10-03

Задание: «Актуализация документации auth под два транспорта, учебный разбор потоков и
логирование цепочки вызовов». Проверка поведения запущенным приложением + grep по docs.

## Как воспроизвести

```bash
# сервер (cwd обязателен — SQLite резолвится от cwd)
cd fastapi-application
../.venv/bin/uvicorn main:main_app --host 127.0.0.1 --port 8021   # PID прогона 2260461
# чужой процесс на 8012 (PID 2245960) не затрагивался

bash tasks/current/e2e/run_qa_phase09.sh > tasks/current/e2e/2026-10-03_phase09_raw_run.txt
```

Сырые выводы: `2026-10-03_phase09_raw_run.txt` (этот каталог), `raw_batch1_static.txt`,
`raw_batch_docs.txt`, `raw_batch_logs.txt`, `raw_batch_readme.txt`.

## Результаты по пунктам задания

### 1. Запуск + OpenAPI paths — PASS

- Сервер поднялся на 127.0.0.1:8021 за 1s; `openapi.json` → `paths: 25`.
- Импорт-проверка: `python -c "from main import main_app; print(len(main_app.openapi()['paths']))"` → `25`.

### 2. Cookie flow — PASS

| Шаг | Ожидалось | Факт |
|---|---|---|
| register нового пользователя | 201 | `HTTP/1.1 201 Created` |
| POST /auth/cookie/login | 204 + Set-Cookie auth + Set-Cookie csrf_token | `204 No Content`, обе `set-cookie:` в ответе (`auth=eyJ...; HttpOnly; SameSite=lax`, `csrf_token=<sig>.<hex>; SameSite=lax`) |
| GET /users/me с cookie | 200 | `200 OK`, email test-пользователя |
| GET /api/v1/auth/protected с cookie | 200 | `200 OK` authenticated |
| POST /auth/cookie/logout без X-CSRF-Token | 403 | `403 Forbidden` `{"detail":"CSRF validation failed"}` |
| PATCH /auth/account без X-CSRF-Token | 403 | `403 Forbidden` |
| mixed cookie+Bearer на /auth/account без X-CSRF-Token | 403 | `403 Forbidden` — Bearer не обходит CSRF |
| POST /auth/cookie/logout с X-CSRF-Token | 204 | `204 No Content` + `set-cookie: auth=""; Max-Age=0` + `csrf_token=""; Max-Age=0` |
| protected после logout | 401 | `401 Unauthorized` `{"detail":"Unauthorized"}` |

### 3. Bearer flow — PASS

- `/auth/bearer/login` → `200` + `{"access_token":"eyJ...","token_type":"bearer"}`;
  cookie-jar пустой (auth-cookie не выдаётся).
- `/users/me` и `/api/v1/auth/protected` с `Authorization: Bearer` → `200`.
- `/auth/bearer/logout` с Bearer → `204` (без CSRF-заголовка, не требует).

### 4. Регресс — PASS

- `/docs` → 200.
- анонимный `/users/me` → 401.
- `/orders/get_all_orders?params=id` → 200, JSON-массив заказов.
- `/api/v1/dep_examples/single-direct-dependency`: без заголовка `foobar` → 422,
  с `foobar: qa-check` → 200 (контракт сохранён).

### 5. Логи `fastapi-application/log/temp_auth.log` — PASS

Новые строки прогона (LOG_START_LINE=2800, всего 48 записей):

- Маркеры: `auth csrf:` ×21 (DEBUG required/valid + 2 INFO issued/deleted + 3 WARNING
  `rejected method=... path=...`), `auth protected: authenticated user_id=<uuid>` ×2,
  `auth_users: get_user_manager enter/exit` + `registered <email>`,
  `auth backends order: jwt-cookie -> jwt-bearer` (строки 2758/2776/2786 — старт/ллайфспан).
- lifecycle CSRF-cookie: `INFO: auth csrf: issued csrf_token cookie path=/auth/cookie/login`,
  `INFO: auth csrf: deleted csrf_token cookie path=/auth/cookie/logout`.
- Скан секретов: `eyJ` (JWT) — 0 совпадений в новых строках и во всём `log/`;
  `password` (значение) — 0; `csrf_token=<значение>` — 0; `auth=eyJ` — 0;
  значенia паролей прогона (`Qa-Pass`, `Qa-Other`) — 0. В логе только факты: method, path,
  required/valid, user_id, email.

### 6. Документация

- Критерий 10 (`auth/jwt|CSRF-защиты нет|Один backend` по docs 02,03,04,05,06,07,08,10,11):
  5 совпадений, все — явные исторические примечания («прежний контракт устарел и заменён»,
  docs/02:55, docs/05:22, docs/06:219, docs/07:76, docs/08:353). Как текущее состояние —
  нет. PASS (спека прямо допускает помеченные исторические примечания).
- docs/10, docs/11 checkpoint-паттернов (`отдельного CSRF-токена сейчас нет`,
  `второй backend не подключён`, `auth/jwt`) — 0 совпадений. PASS.
- docs/04: `/auth/cookie/login` ×8, `/auth/bearer/login` ×3, `X-CSRF-Token` ×8, `csrf.py` ×1. PASS.
- docs/05: оба login-пути ×4, `X-CSRF-Token` ×7 (curl-рецепты). PASS.
- docs/12: существует; `auth/bearer/login` ×4, `auth/cookie/login` ×5,
  уникальных URL — 17 (из них внешних 10: OWASP CSRF, RFC 6750/6265/7519, MDN ×3,
  FastAPI ×2, fastapi-users ×1), дата сверки `2026-10-03` ×2. Критерии 11, 12 — PASS.
- docs/00: ссылка на `docs/12_auth_dual_transport_walkthrough` (строка 80); счётчик
  «OpenAPI path-ключей — 25»; `auth/jwt` нет. docs/01: «Ожидается 25 path-ключей»,
  `auth/jwt` нет. Критерий 13 — PASS.
- README: строка 120 содержит docs/12 (добавлена этим заданием — git diff показывает один
  added-hunk); НЕ содержит счётчика маршрутов.

## Находки (см. DEFECTS.md)

1. DEF-001 (MEDIUM): `ruff check auth_users/ main.py` — 1 ошибка I001 в
   `auth_users/user_manager.py:12` → критерий успеха 14 FAIL. Сырой вывод в
   `raw_batch1_static.txt`.
2. DEF-002 (LOW): `README.md:134` — «23 path-ключа OpenAPI» при фактических 25
   (строка была устаревшей и до задания — git diff её не трогал; README в этой фазе правит
   оркестратор).
3. DEF-003 (LOW): docs/12:460 — ссылка на документацию fastapi-users версии 12.1 при
   установленной 15.0.5 (контекстная ссылка, оговорка в тексте есть).

## Сознательно НЕ применявшиеся проверки

- Разрушительная нагрузка/DoS, массовый брутфорс register — вне рамок smoke и задания.
- Проверки `frontend/` SPA и скриншоты — задание не трогает UI; `/docs` проверен кодом 200
  (контракт Swagger не менялся).
- known-defect `GET /api/v1/depends_function_annotated/my_items/{item_id}` без `query` → 500
  — известный дефект по AGENTS.md, не часть этого задания, не перепроверялся.
- Полный аудит Tavily-ссылок на доступность из сети — проверялось только наличие/форма
  ссылок и дата сверки (qa без сетевого прогона внешних источников).

## Итог

13 из 14 критериев успеха подтверждены. Критерий 14 (ruff) — FAIL (DEF-001).
Поведение API не изменилось: все коды ответов cookie/bearer/CSRF/регресса совпали.
