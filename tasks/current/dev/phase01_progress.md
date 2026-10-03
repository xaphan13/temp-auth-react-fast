# Фаза 1: логирование auth-цепочки (backend)

Задание: `tasks/current/REQUIREMENTS.md`, фаза 1.
Зона: `fastapi-application/auth_users/router.py`, `auth_users/csrf.py`, `auth_users/user_manager.py`.

## План

1. `router.py::protected` — `logF.info` при входе (факт authenticated=True, `user.id`).
2. `csrf.py::dispatch` — `logF.debug` о результате `_requires_check`/`_check_request`
   (method, path, required, valid), `logF.warning` при 403, `logF.info` о выдаче/удалении
   `csrf_token`. Без значений cookie/токена.
3. `user_manager.py::get_user_manager` — убрать `logF.debug("get_user_manager %s", user_db)`
   (repr объекта с данными БД), заменить на безопасные строки входа/выхода.

Контракт: только `logF` из `config_log.py`; секреты (JWT, пароли, значения cookie/CSRF)
не логировать; поведение API не менять.

## Чекпоинт фазы

```bash
cd fastapi-application && uv run ruff check auth_users/ && \
../.venv/bin/python -c "from main import main_app; print(len(main_app.openapi()['paths']))"
```
Ожидание: ruff чист, `25`; после прогона `/protected` — строка в `log/temp_auth.log`.

## Прогресс

- 2026-10-03, `auth_users/router.py`: добавлен `logF.info` в `protected` —
  факт аутентификации + `user.id` (email не логируем, id достаточно).
  Статус: выполнено.
- 2026-10-03, `auth_users/csrf.py`: в `dispatch` добавлены `logF.debug` о решении
  `_requires_check`/`_check_request` (method, path, required, valid), `logF.warning`
  при отказе 403, `logF.info` о lifecycle csrf-cookie (выдача/удаление). Полные
  значения cookie/token не логируются. Статус: выполнено.
- 2026-10-03, `auth_users/user_manager.py`: `logF.debug("get_user_manager %s", user_db)`
  заменён на безопасные строки входа/выхода (без repr объекта и данных БД).
  Статус: выполнено.

## Проверки

- `uv run ruff check auth_users/` — 1 предсуществующая `I001` в `user_manager.py`
  (есть и на чистом дереве); изменения фазы 1 ошибок не добавляют.
- `python -c "from main import main_app; print(len(main_app.openapi()['paths']))"` — 25.
- Smoke (uvicorn 127.0.0.1:8011, гашён):
  - `openapi=200`, `protected=401` (аноним), `cookie/login` с неверным паролем = 400.
  - В `log/temp_auth.log` появились строки новых маркеров (снимок):
    ```
    DEBUG: auth csrf: method=GET path=/api/v1/auth/protected required=False valid=None
    DEBUG: auth_users: get_user_manager enter
    DEBUG: auth csrf: method=POST path=/auth/cookie/login required=False valid=None
    ```
  - Значения JWT/паролей/полных cookie/csrf-токена в лог не пишутся.

Замечание: `uv run ruff check auth_users/` даёт 1 ошибку `I001` (import block unsorted) в
`user_manager.py` — она присутствует и на чистом дереве (`git stash` → та же ошибка), т.е.
предсуществующая, не внесена фазой 1. Правки фазы 1 ruff-чистые (изменённые строки).