# 05. Авторизация: дальнейшее развитие

Этот документ описывает следующие шаги для auth-only шаблона. Фактическое состояние и контракты маршрутов находятся в [04_authorization.md](04_authorization.md).

## Что уже сделано

- auth-слой вынесен в `fastapi-application/auth_users/`;
- `User` использует UUID и стандартные поля fastapi-users;
- пароль проверяется через `UserManager`, минимум — 8 символов;
- вход/выход работают через JWT в HttpOnly cookie `auth`;
- `/auth/account` поддерживает username, email и optional avatar upload;
- avatar static сохраняется через `/static/profile_pics/`;
- users-router ограничен `/users/me` (GET/PATCH), без маршрутов `/users/{id}`;
- `GET /api/v1/auth/protected` проверяет backend boundary через `active_user` и возвращает JSON `401` для anonymous;
- фронтенд использует `/auth/*` и `/users/*`, cookie credentials и защищённые routes `/account` и `/protected`.

## Следующие варианты

### 1. Безопасность production

Перед публикацией приложения нужно:

- задавать уникальный `APP__WEB__SECRET_KEY` вне репозитория;
- включать `APP__AUTH_USERS__COOKIE_SECURE=true` только при HTTPS;
- проверить proxy headers и фактическую схему запроса;
- ограничить CORS, если API и фронтенд будут на разных origin;
- добавить rate limit на login и register;
- не использовать учебные пароли и dev-профиль PostgreSQL в production.

### 2. Email verification и reset password

`UserManager` уже содержит секреты `verification_token_secret` и `reset_password_token_secret`, но роутеры этих потоков не подключены. Для реализации нужны email-доставка, UI-состояния и явный контракт сроков жизни токенов. Это отдельная фича, а не продолжение миграции.

### 3. Управление пользователями и роли

В auth-only шаблоне стандартные маршруты управления пользователями `/users/{id}` не подключены. Если понадобится административное управление, следует отдельно зафиксировать API-контракт и использовать `superuser_user` либо permission-модель; не следует открывать эти маршруты для обычного `active_user`.

### 4. Сессии и отзыв токенов

JWT — stateless-токен: logout очищает cookie браузера, но уже скопированный токен остаётся действительным до истечения lifetime или смены секрета. Если нужен мгновенный отзыв на сервере, следует рассмотреть database/Redis strategy либо таблицу отозванных токенов.

### 5. Проверки

После изменений авторизации проверить anonymous boundary и cookie-flow:

```bash
cd fastapi-application
../.venv/bin/python -c "from main import main_app; paths=main_app.openapi()['paths']; print('/api/v1/auth/protected' in paths); print('/users/me' in paths); print('/users/{id}' in paths)"
curl -i http://127.0.0.1:8000/users/me
curl -i http://127.0.0.1:8000/api/v1/auth/protected
curl -i -c /tmp/auth.cookies -X POST http://127.0.0.1:8000/auth/register -H 'Content-Type: application/json' -d '{"email":"user@example.com","password":"password123"}'
curl -i -c /tmp/auth.cookies -b /tmp/auth.cookies -X POST http://127.0.0.1:8000/auth/jwt/login -H 'Content-Type: application/x-www-form-urlencoded' --data 'username=user@example.com&password=password123'
curl -i -b /tmp/auth.cookies http://127.0.0.1:8000/users/me
curl -i -b /tmp/auth.cookies http://127.0.0.1:8000/api/v1/auth/protected
curl -i -b /tmp/auth.cookies -X POST http://127.0.0.1:8000/auth/account -F 'username=authuser' -F 'email=user@example.com'
curl -i -b /tmp/auth.cookies -X POST http://127.0.0.1:8000/auth/jwt/logout
```

Ожидания: `/users/me` и `/api/v1/auth/protected` без cookie возвращают JSON `401`; register — `201`; login/logout — `204`; авторизованные me/protected — `200`; account — `200` с `{message, category, user}`. Поле `image_file` строит avatar URL только через `/static/profile_pics/{image_file}`.

Не фиксируйте в документации старые значения счётчика маршрутов: актуальный источник — `/openapi.json` и код `main.py`.
