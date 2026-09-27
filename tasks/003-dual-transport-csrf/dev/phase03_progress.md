# Фаза 3: Frontend CSRF integration

- Исполнитель: frontend-dev
- Дата: 2026-09-27
- Файлы фазы: `frontend/src/api/client.ts`, `frontend/src/api/auth.ts`

## Исходное состояние

- `client.ts`: `request()` с `credentials: 'include'`, `getJson`/`postJson`/`postForm`/`postMultipart`.
  Шапка-комментарий утверждает «CSRF больше нет» — устарело после фазы 2.
- `auth.ts`: `login` → `postForm('/auth/jwt/login', ...)` + `getJson('/users/me')`;
  `logout` → `postForm('/auth/jwt/logout', ...)` с fallback-catch.
- `postMultipart` не выставляет Content-Type (браузер ставит boundary сам).

## План правок

1. `client.ts`:
   - Экспортировать `getCsrfToken(): string | null` — regex по `document.cookie`
     (`(?:^|;\s*)csrf_token=([^;]*)`) + `decodeURIComponent`.
   - Приватный хелпер `withCsrfHeader(headers)` — добавляет `X-CSRF-Token` только
     если cookie существует; иначе возвращает headers без изменений.
   - `postJson` / `postForm`: обернуть существующий Content-Type через
     `withCsrfHeader({...})`.
   - `postMultipart`: `headers: withCsrfHeader({})` — Content-Type не выставляем,
     FormData boundary не трогаем.
   - Актуализировать шапку-комментарий (CSRF через Signed Double Submit Cookie).
2. `auth.ts`:
   - `'/auth/jwt/login'` → `'/auth/cookie/login'`, `'/auth/jwt/logout'` → `'/auth/cookie/logout'`.
   - Обновить комментарии к login/logout; поведение (fallback logout, refresh через
     `/users/me`) не меняется.
3. Checkpoint: `cd frontend && npm run build` без ошибок, `dist/index.html` существует.
   Сервер не нужен (спека, шаг 7).

## Прогресс

- [x] Прочитаны client.ts, auth.ts, REQUIREMENTS.md (фаза 3)
- [x] План зафиксирован (этот файл)
- [x] client.ts правки
- [x] auth.ts правки
- [x] npm run build + dist/index.html
- [x] Финальная сводка

## Чекпоинты

- `npm run build`: зелёный (tsc + vite, 42 modules, exit 0); артефакты
  `dist/index.html` (0.64 kB), `dist/assets/index-Di_rNHxW.js` (179.75 kB),
  `dist/assets/index-C2uD5gh2.css` — существуют.
- Контроль бандла: `grep -c "X-CSRF-Token" dist/assets/index-Di_rNHxW.js` → 1;
  `grep -c "/auth/cookie/login" ...` → 1.
- `grep -rn "/auth/jwt/" frontend/src/` → только 2 комментария в
  `src/pages/LoginPage.tsx` (строки 31, 37) — вне зоны фазы (менять только
  client.ts и auth.ts), на runtime не влияют.
- `git diff --stat -- frontend/`: только `frontend/src/api/auth.ts` (+13/-6)
  и `frontend/src/api/client.ts` (+30/-5); dist не индексируется.
- Сервер не поднимался — по спеке фазы 3 runtime-сценарии выполняет qa.

## Финальная сводка

- `client.ts`: экспорт `getCsrfToken(): string | null` (regex
  `(?:^|;\s*)csrf_token=([^;]*)` + `decodeURIComponent`); приватный хелпер
  `withCsrfHeader(headers)` добавляет `X-CSRF-Token` только при наличии cookie;
  `postJson`/`postForm` сохраняют Content-Type, `postMultipart` передаёт
  `withCsrfHeader({})` — FormData boundary не тронут; `credentials: 'include'`
  в `request()` не менялся; шапка-комментарий актуализирована.
- `auth.ts`: `login` → `/auth/cookie/login`, `logout` → `/auth/cookie/logout`;
  поведение (refresh через `/users/me`, logout fallback-catch) сохранено;
  комментарии обновлены.
- Checkpoint фазы зелёный: `npm run build` без ошибок, `dist/index.html` создан.
- Блокеров нет. Примечание для оркестратора: 2 комментария `/auth/jwt/` в
  `src/pages/LoginPage.tsx` (31, 37) вне зоны фазы — runtime не затрагивают;
  обновить при случае (например, фаза 4 docs).

