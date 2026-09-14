# 03. Жизненный цикл и выполнение запросов

## Импорт и запуск

Команда запускается из `fastapi-application/`:

```bash
../.venv/bin/uvicorn main:main_app --host 0.0.0.0 --port 8000 --reload
```

При импорте `main` происходят следующие действия:

1. Загружаются `BASE_DIR`, логирование и `Settings`.
2. Создаётся `AsyncEngine` и менеджер async-сессий.
3. Импортируются роутеры демонстраций, заказов и `auth_users`.
4. `create_app()` создаёт FastAPI с lifespan.
5. `main.py` подключает demo, order и auth routers.
6. `mount_frontend()` добавляет `/static`, `/assets` и последний catch-all.

## Lifespan

В startup приложение логирует конфигурацию. Таблицы не создаются автоматически: схема должна быть подготовлена Alembic. Engine лениво открывает соединения при первом SQL-запросе. На shutdown lifespan закрывает engine через `engine_dispose()`.

## Порядок маршрутов

В `main.py` порядок такой:

```text
router_api
r_order_one
auth_users.router
/static + /assets + /{full_path:path} через setup_frontend.py
```

Catch-all добавляется последним. Для путей `/api` и `/api/*` он возвращает JSON 404, а для обычных browser-путей — `frontend/dist/index.html`, если сборка существует.

## Авторизованный запрос

Для `GET /users/me`, `POST /auth/account` или `GET /api/v1/auth/protected`:

1. Клиент отправляет cookie `auth` с JWT (`credentials: 'include'`).
2. Dependency `active_user` извлекает и проверяет JWT.
3. `get_user_manager()` получает `SQLAlchemyUserDatabase` поверх `CurrentSession`.
4. Пользователь загружается из таблицы `user`; невалидный/просроченный токен даёт 401.
5. Обработчик выполняет чтение или изменение.

`GET /api/v1/auth/protected` возвращает JSON с подтверждением доступа и auth-данными пользователя. Отсутствие cookie даёт JSON 401 независимо от client-side `RequireAuth`.

## Вход и регистрация

### Регистрация

`POST /auth/register` принимает JSON `{email, password}`. `fastapi-users` проверяет email и уникальность, `UserManager.validate_password()` требует минимум 8 символов, пароль хешируется библиотекой. После создания `on_after_register()` заполняет `username` из части email до `@` и задаёт `default.jpg`.

Успех — 201 с `UserRead`; пользователь автоматически не входит.

### Вход

`POST /auth/jwt/login` принимает `application/x-www-form-urlencoded`:

```text
username=<email>&password=<пароль>
```

Успех — 204 и `Set-Cookie: auth=...`. React после 204 вызывает `GET /users/me`, чтобы получить профиль.

### Выход

`POST /auth/jwt/logout` очищает cookie. Клиент не зависит от тела ответа и сбрасывает пользователя в `AuthContext`.

## Account и аватар

`POST /auth/account` принимает multipart-поля `username`, `email`, необязательный `picture`.

1. `active_user` проверяет доступ.
2. Проверяются длина username, email и уникальность изменённых значений.
3. `save_picture()` принимает jpg/jpeg/png, уменьшает изображение до 125×125 и сохраняет случайное имя в `static/profile_pics/`.
4. Поля пользователя обновляются через текущую SQLAlchemy-сессию.
5. Ответ содержит `{message, category, user}`.

Пароль не возвращается. В БД хранится только имя файла, не полный URL.

## Ошибки

| Ситуация | Ответ |
|---|---|
| Нет/невалиден JWT на защищённом маршруте | 401 fastapi-users |
| Неверные данные входа | 400 `LOGIN_BAD_CREDENTIALS` |
| Дубликат email при регистрации | 400 `REGISTER_USER_ALREADY_EXISTS` |
| Пароль короче 8 символов | 400 `REGISTER_INVALID_PASSWORD` |
| Невалидный JSON/form | 422 FastAPI/fastapi-users |
| Неизвестный `/api/*` путь | JSON 404 от catch-all |
| Нет frontend/dist для обычного browser-пути | JSON 404 с подсказкой `npm run build` |

## Проверка запуска

```bash
cd fastapi-application
../.venv/bin/python -c "from main import main_app; print(len(main_app.openapi()['paths']))"
# 23
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/docs
curl -s http://127.0.0.1:8000/users/me
curl -s http://127.0.0.1:8000/api/v1/auth/protected
```
