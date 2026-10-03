# QA retest-отчёт 2 (medium-depth), 2026-10-03

Прогон: qa на специализированной QA-модели, отдельный порт 8031 (чужой процесс на
8012 не затрагивался; одноразовый lifespan-перезапуск на 8032 погашен в том же шаге;
uvicorn 8031 PID 2268355 погашен в конце прогона). Продуктовый код и документация
qa не изменялись.

Скрипт: `run_qa_retest2.sh` (копия `run_qa_phase09.sh` с портом 8031).
Сырые выводы: `raw_retest2_static.txt`, `raw_retest2_run.txt`,
`raw_retest2_extra.txt`, `raw_retest2_csrf_bypass.txt`,
`raw_retest2_uvicorn_startup.log`, `raw_retest2_uvicorn_8032.log`.

## Минимальный обязательный ретест — результаты

| # | Проверка | Ожидание | Факт | Вердикт |
|---|---|---|---|---|
| 1 | `uv run ruff check auth_users/ main.py` | без ошибок | `All checks passed!` (RUFF_EXIT=0) | PASS |
| 2 | OpenAPI paths (python-счётчик и openapi.json на 8031) | 25 | 25 | PASS |
| 3 | Cookie-цикл: register 201 → cookie login 204 + `Set-Cookie: auth` + `Set-Cookie: csrf_token` → /users/me 200 → protected 200 `authenticated` → logout с X-CSRF-Token 204 (обе cookie удалены) → protected 401 | — | все коды совпали; Set-Cookie names при login: `['auth','csrf_token']`; при logout обе с expires=1970 | PASS |
| 4 | CSRF reject: state-changing logout без заголовка 403; mixed cookie+Bearer на /auth/account без заголовка 403; поддельный X-CSRF-Token на валидной сессии 403; auth-cookie без csrf-cookie (double-submit не пройден) 403 | 403 | 403 / 403 / 403 / 403 | PASS |
| 5 | Bearer-цикл: login 200 JSON `access_token`+`token_type: bearer` → /users/me 200 → protected 200 → logout 204; повторный cookie logout 401 | — | все совпали; bearer login без CSRF и без auth-cookie — не 403 (400 на невалидные креды) | PASS |
| 6 | Регресс: /docs 200; анонимный /users/me 401; /orders/get_all_orders?params=id 200; dep_examples/single-direct-dependency без foobar 422, с foobar 200 | — | все совпали | PASS |
| 7 | Логи: новые строки за прогон 97; маркеры: protected=7, csrf=48, get_user_manager=41; старт-строка `auth backends order: jwt-cookie -> jwt-bearer` присутствует | — | подтверждено | PASS |
| 8 | Секреты в логах: `eyJ...`, `password[:=]`, `csrf_token=<значение>`, полное значение auth-cookie — и в новых строках, и по всему temp_auth.log | 0 | 0 / 0 / 0 / 0 | PASS |
| 9 | README счётчик (`grep path-ключ README.md`) | 25 | `README.md:134 — # 25 path-ключей OpenAPI` | PASS |
| 10 | docs/12: URL fastapi-users | без 12.1 | единственная ссылка — `fastapi-users.github.io/fastapi-users/latest/configuration/authentication/` (строка 460); `12.1` не встречается | PASS |
| 11 | Целевой grep старых auth-фактов по docs (auth/jwt, «CSRF-защиты нет», «Один backend», «отдельного CSRF-токена сейчас нет», «второй backend не подключён») | нет как текущего состояния | «CSRF-защиты нет»/«Один backend»/«отдельного CSRF-токена сейчас нет»/«второй backend не подключён» — 0; `auth/jwt` — 5 совпадений, каждое явно помечено как устаревший прежний контракт (docs/02:55 «Прежний контракт … устарел», docs/05:22, docs/06:219 «устаревший контракт», docs/07:76 «прошлый», docs/08:353 «исторический контракт») — по формулировке чекпойнтов фаз 3–5 исторические явные пометки допустимы | PASS |
| 12 | docs/12 + навигация: ссылка в docs/00, пути login, ссылки, дата сверки | ≥6 ссылок, дата есть | docs/00: 1; `auth/bearer/login`: 4; `auth/cookie/login`: 5; `https?://`: 29; `2026-10-03`: 3 | PASS |

## Сознательно неприменённые проверки

- Нагрузочные/DoS, браузерные скриншоты (задание не трогает UI), полный adversary
  репертуар (фаза 10 — отдельный агент; здесь взято только CSRF-обходное покрытие
  из обязательного ретеста: подделка токена, отсутствие csrf-cookie, mixed-транспорт,
  повтор logout).
- Критерии 10–13 в полном объёме по всем девяти документам не пересказывались —
  применён целевой grep (строка 11 таблицы).

## Дефекты

- DEF-001 (ruff I001) — исправление подтверждено свежим прогоном ruff → CLOSED.
- DEF-002 (README «23 path-ключа») — исправление подтверждено: README:134 = 25 → CLOSED.
- DEF-003 (docs/12 ссылка на fastapi-users 12.1) — подтверждено: URL 12.1 отсутствует,
  актуальный `latest/` → CLOSED.
- Новых дефектов не заведено.

## Processes

- Поднимал: uvicorn 8031 (PID 2268355) — погашен; lifespan-проверка 8032 — погашен
  в рамках шага. Чужой 8012 (PID 2245960) не затрагивался.

ИТОГ: PASS по всем пунктам минимального обязательного ретеста.
