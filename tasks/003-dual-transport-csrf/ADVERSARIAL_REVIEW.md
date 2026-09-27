# ADVERSARIAL_REVIEW — Dual-transport (Cookie + Bearer) с CSRF

Прогон: 2026-09-27, оркестратор (делегирование adversary дважды прервано сетевыми сбоями, прогон выполнен оркестратором по методологии adversary). Сервер: uvicorn 127.0.0.1:8051, cwd=fastapi-application/. Сырые выводы: /tmp/adv_body.txt (копия ниже).

## ADV-001: Method override заголовком не меняет HTTP-метод для CSRF-проверки

- Session: Dual-transport auth | final
- Suggested severity: LOW

What I did: Отправил GET /users/me с заголовком X-HTTP-Method-Override: PATCH и JSON-телом от авторизованного cookie-пользователя.
Expected: Если бы middleware доверял override-заголовку, PATCH-семантика прошла бы без CSRF-токена.
Actual: HTTP 200 — метод остался GET, CSRF-проверка корректно не применялась к фактическому GET; изменения не произошло (GET /users/me не мутирует). Middleware смотрит на request.method, а не на заголовки override — обхода нет.

Screenshot: —

Disposition: REJECTED - система корректно противостоит атаке; нарушение не найдено

## ADV-002: CSRF-токен не существует до cookie-login

- Session: Dual-transport auth | final
- Suggested severity: LOW

What I did: POST /auth/account без auth-cookie (без login) — попытка получить/использовать CSRF-механику неавторизованным.
Expected: Неавторизованный запрос не должен выдавать csrf_token или проходить дальше.
Actual: HTTP 401 Unauthorized — csrf_token выдаётся только в ответе успешного cookie-login; до login токена нет, состояние не меняется.

Screenshot: —

Disposition: REJECTED - система корректно противостоит атаке; нарушение не найдено

## ADV-003: Подделка подписи csrf_token

- Session: Dual-transport auth | final
- Suggested severity: HIGH (если бы прошла) — отклонена

What I did: PATCH /users/me с валидным nonce, но перебранной подписью (deadbeef...) и с полностью посторонним токеном aaa.bbb от авторизованного cookie-пользователя.
Expected: 403 при невалидной подписи.
Actual: Оба запроса → 403 CSRF validation failed. HMAC-SHA256-подпись с settings.web.secret_key не подделывается без секрета.

Screenshot: —

Disposition: REJECTED - система корректно противостоит атаке; нарушение не найдено

## ADV-004: Replay csrf_token после logout и после повторного login

- Session: Dual-transport auth | final
- Suggested severity: MEDIUM (если бы прошла) — отклонена

What I did: После cookie-logout попытался PATCH со старым csrf (auth-cookie уже удалён); после повторного login попытался PATCH со старым csrf-токеном (в cookie уже новый).
Expected: Оба replay должны быть отклонены.
Actual: replay после logout → 401 (auth удалён, до CSRF-проверки не дошло); старый csrf после re-login → 403 (cookie/header не совпадают); новый csrf → 200. Replay невозможен.

Screenshot: —

Disposition: REJECTED - система корректно противостоит атаке; нарушение не найдено

## ADV-005: Кросс-юзерный CSRF-токен

- Session: Dual-transport auth | final
- Suggested severity: MEDIUM (если бы прошла) — отклонена

What I did: PATCH /users/me от user2 (auth-cookie user2) с csrf-токеном user1.
Expected: 403.
Actual: 403 CSRF validation failed — csrf cookie и header должны совпадать в рамках одной сессии; чужой токен отклонён.

Screenshot: —

Disposition: REJECTED - система корректно противостоит атаке; нарушение не найдено

## ADV-006: Bearer login не должен ставить cookies

- Session: Dual-transport auth | final
- Suggested severity: LOW

What I did: POST /auth/bearer/login, проверил response headers.
Expected: Никаких Set-Cookie (чистый Bearer-контракт).
Actual: Set-Cookie отсутствует — BearerTransport отдаёт только JSON access_token.

Screenshot: —

Disposition: REJECTED - система корректно противостоит атаке; нарушение не найдено

---

## Сырые выводы прогона (дубль из /tmp/adv_body.txt)

```
=== A1 register+login user1 ===
reg1:201 login1:204
csrf1=FaLxOap1Z9REy66uy4_FstR3NJaUhNWIQGGbVxkRXOc.bdd95c4fc470b89eb42ade3409d3e39a93ae231b8ddb2516007eb23dee744f4e
=== A2 forgery ===
forged_sig:403
=== A3 swapped ===
swapped:403
=== A4 method override ===
method_override:200
=== A5 csrf до login ===
HTTP/1.1 401 Unauthorized
=== A6 logout + replay ===
logout:204 replay_after_logout:401
=== A7 re-login: старый csrf невалиден, новый валиден ===
relogin:204
old_csrf_after_relogin:403 new_csrf_after_relogin:200
=== A8 bearer login без cookies ===
no set-cookie: OK
=== A9 кросс-юзер csrf ===
reg2:201 login2:204 cross_user_csrf:403
```
