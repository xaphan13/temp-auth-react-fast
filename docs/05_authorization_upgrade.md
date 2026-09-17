# 05. Авторизация: дальнейшее развитие

Фактическая реализация и полный пошаговый цикл описаны в [04_authorization.md](04_authorization.md). Этот документ фиксирует только возможные следующие шаги.

## Что уже работает

- auth-слой находится в `fastapi-application/auth_users/`;
- пользователь хранится в таблице `user`, идентификатор — UUID;
- пароль хешируется перед записью в базу, исходный пароль не сохраняется;
- вход и выход работают через JWT в HttpOnly-cookie `auth`;
- frontend использует `credentials: 'include'` и не хранит JWT в `localStorage`;
- после login frontend отдельно вызывает `GET /users/me` и кладёт только объект пользователя в `AuthContext`;
- `GET /api/v1/auth/protected` демонстрирует независимую backend-проверку через `active_user`;
- users-router ограничен `/users/me` (GET/PATCH), без `/users/{id}`;
- `/auth/account` изменяет `username` и `email` авторизованного пользователя;
- logout удаляет cookie в браузере, но не отзывает ранее скопированный stateless JWT.

## Приоритетные следующие шаги

### 1. Безопасность production

Перед публикацией приложения нужно:

- задавать уникальный `APP__WEB__SECRET_KEY` вне репозитория;
- включать `APP__AUTH_USERS__COOKIE_SECURE=true` при работе по HTTPS;
- проверить proxy headers и фактическую схему запроса;
- ограничить CORS при разделении frontend и API по разным origin;
- определить CSRF-модель для cookie-аутентификации, особенно если изменятся `SameSite` и схема размещения;
- добавить rate limit на login и register;
- не использовать dev-секрет и учебные credentials в production.

### 2. Email verification и reset password

`UserManager` уже содержит секреты `verification_token_secret` и `reset_password_token_secret`, но маршруты этих потоков не подключены. Для реализации потребуются:

- подключение соответствующих fastapi-users routers;
- почтовая доставка;
- страницы frontend для подтверждения и смены пароля;
- явный контракт сроков жизни токенов и обработки ошибок.

Это отдельная функциональность, а не часть текущего login-flow.

### 3. Управление пользователями и роли

Обычный `active_user` сейчас достаточен для текущих защищённых endpoint-ов. Если понадобится административное управление, нужно отдельно определить:

- какие маршруты доступны администратору;
- какие операции разрешены обычному пользователю;
- используется ли `superuser_user` или отдельная permission-модель;
- какие данные можно возвращать в `UserRead`.

Нельзя просто открыть `/users/{id}` для любого `active_user`.

### 4. Мгновенный отзыв токенов

Сейчас JWT stateless: backend проверяет подпись и срок действия, но не хранит список активных токенов. Logout очищает cookie браузера.

Если нужен мгновенный отзыв уже выданного JWT, возможные варианты:

- database/Redis strategy с серверным состоянием;
- таблица или Redis-набор отозванных идентификаторов токенов;
- ротация секретов как аварийный отзыв всех JWT, если допустима такая операция.

У каждого варианта есть цена по задержке, хранению состояния и поведению при нескольких worker-процессах.

### 5. Аватар и расширение account-flow

Текущий `POST /auth/account` принимает только `username` и `email`. Если нужен upload аватара, его следует оформить отдельным согласованным контрактом:

- `multipart/form-data`;
- проверка MIME-типа, размера и содержимого файла;
- безопасное имя и место хранения;
- URL выдачи изображения;
- обновление `UserRead` и frontend account page.

Не следует описывать avatar upload как уже работающий сценарий, пока backend endpoint его не принимает.

## Минимальная ручная проверка cookie-flow

Команды выполняются из `fastapi-application/` при запущенном приложении. Cookie сохраняется в `/tmp/auth.cookies` только для проверки командой `curl`.

```bash
curl -i http://127.0.0.1:8000/users/me
curl -i http://127.0.0.1:8000/api/v1/auth/protected

curl -i -c /tmp/auth.cookies \
  -X POST http://127.0.0.1:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"password123"}'

curl -i -c /tmp/auth.cookies -b /tmp/auth.cookies \
  -X POST http://127.0.0.1:8000/auth/jwt/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data 'username=user@example.com&password=password123'

curl -i -b /tmp/auth.cookies http://127.0.0.1:8000/users/me
curl -i -b /tmp/auth.cookies http://127.0.0.1:8000/api/v1/auth/protected

curl -i -b /tmp/auth.cookies \
  -X POST http://127.0.0.1:8000/auth/account \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data 'username=authuser&email=user@example.com'

curl -i -b /tmp/auth.cookies \
  -X POST http://127.0.0.1:8000/auth/jwt/logout
```

Ожидаемый порядок:

- анонимные `/users/me` и `/api/v1/auth/protected` возвращают `401`;
- register возвращает `201` и не логинит автоматически;
- login возвращает `204` и `Set-Cookie: auth=...`;
- `/users/me` и protected с cookie возвращают `200`;
- logout возвращает `204` и очищает cookie;
- повторный защищённый запрос после logout снова возвращает `401`.

Проверка должна подтверждать именно HTTP-заголовки и cookie-flow, а не только наличие объекта `user` в React.
