# Фаза 2: логирование lifecycle и старта (backend)

Задание: `tasks/current/REQUIREMENTS.md`, фаза 2.
Зона: `fastapi-application/main.py` (+ этот прогресс-файл). Больше ничего не трогалось.

## План

1. `main.py`: добавить одну строку `logF.info` после `main_app = create_app(...)`,
   выводящую имена и порядок auth backend'ов из `fastapi_users.authenticator.backends`.
2. Источник данных — `fastapi_users` из `auth_users/fastapi_users_obj.py` (порядок
   `cookie -> bearer` задаётся там же). Логируются только имена транспортов.
3. Порядок `add_middleware` / `include_router` / `mount_frontend` не менять.

Контракт: только существующий `logF`; уровень INFO; без секретов (JWT, пароли,
значения cookie/CSRF не логируются).

## Прогресс

- 2026-10-03, `main.py`: добавлен импорт `from auth_users.fastapi_users_obj import fastapi_users`.
- 2026-10-03, `main.py`: после `create_app(...)` добавлен вызов
  `logF.info("auth backends order: %s", " -> ".join(backend.name for backend in fastapi_users.authenticator.backends))`.
  Порядок middleware/router/frontend не изменён. Статус: выполнено.

## Проверки

Checkpoint из спецификации фазы 2:

```bash
cd fastapi-application && uv run ruff check main.py && \
../.venv/bin/python -c "from main import main_app; print('ok')"
```

Результат:

- `uv run ruff check main.py` — `All checks passed!` (чисто).
- импорт `main_app` — без ошибок, `paths= 25` (поведение API неизменно).
- фактическая строка в `fastapi-application/log/temp_auth.log`:
  `INFO: auth backends order: jwt-cookie -> jwt-bearer`
  (источник `main.<module>(21)`); содержит оба имени backend'ов в порядке
  cookie -> bearer.

Готовность фазы: порядок и состав backend'ов логируются, маршрутизация не затронута.