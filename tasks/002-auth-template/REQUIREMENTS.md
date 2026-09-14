# FastAPI-шаблон для изучения авторизации без блогового слоя

Удалить из проекта блог со статьями и весь связанный с ним не-auth backend/frontend-код, сохранив рабочий слой `fastapi-users`, демонстрационные API и `ex_order_product`. Домен `ex_user_post` также удалить как не относящийся к целям шаблона. На его месте оставить минимальный React SPA для изучения auth-flow: home, login, registration, account и защищённая страница.

Архитектурная граница задания: bounded context — учебный auth-шаблон поверх существующего FastAPI-приложения. Внутри границы находятся `auth_users`, пользовательская модель и avatar static, auth-интеграция приложения, минимальный SPA и его API-клиент. Вне границы остаются `api/`, `ex_order_product/`, общая инфраструктура БД/FastAPI/Alembic и их существующие демонстрационные маршруты. `ex_user_post/` удаляется вместе с blog-кодом как лишний домен.

Существующая blog-связка объединяет auth и blog через `md_articles/setup_frontend.py`; после удаления блога generic-раздача SPA переносится в новый `fastapi-application/setup_frontend.py`. Это минимальная необходимая абстракция: без неё `main.py` либо сохранит ложную зависимость от `md_articles`, либо будет одновременно отвечать за auth-router, static mounts и SPA fallback.

## Подтверждённые решения

- «удалить блог со статьями и все не-auth frontend/backend части блогового слоя».
- «сохранить fastapi-users auth».
- «сохранить демонстрационные api и ex_order_product».
- «оставить минимальный frontend login/registration/account/home/protected page».
- Удалить `ex_user_post/`, потому что пользователь подтвердил, что этот не-auth домен в шаблоне не нужен.
- Auth-маршруты сохраняются только для auth-flow: `/auth/jwt/login`, `/auth/jwt/logout`, `/auth/register`, `/auth/account`, `/users/me` (GET/PATCH). Стандартные маршруты управления пользователями `/users/{id}` (GET/PATCH/DELETE) удаляются.
- Auth-пользователь остаётся SQLAlchemy-моделью `auth_users.models.User` с UUID, `email`, `username`, `image_file` и стандартными полями fastapi-users.
- Avatar storage `/static/profile_pics/` сохраняется: он используется account-flow и не относится к статьям.
- Для проверки backend-защиты добавляется `GET /api/v1/auth/protected`, защищённый `active_user`. Anonymous получает JSON `401`, авторизованный пользователь — JSON с подтверждением доступа и данными пользователя.
- Frontend `/protected` использует `RequireAuth` и вызывает `GET /api/v1/auth/protected`; backend endpoint остаётся обязательной независимой границей безопасности.
- Регистрация соответствует фактическому fastapi-users API и отправляет только `email` и `password`; поле `username` не является отдельным обязательным полем регистрации и вычисляется auth manager после создания пользователя.
- Blog routes, registry, Markdown-rendering, article management, themes/highlight.js и blog navigation удаляются, а не заменяются совместимыми заглушками.
- В репозитории нет `*.db`; задание не создаёт миграций очистки и не работает с runtime-базой.

## Результат

После выполнения в репозитории должны существовать:

### Backend

- `fastapi-application/auth_users/` со всеми текущими auth-модулями, включая `User`, `UserRead`, `UserCreate`, `UserUpdate`, `auth_backend`, `fastapi_users`, `active_user`, account endpoint и сборный `router`; users-router ограничен `/users/me` (GET/PATCH), без `/users/{id}`.
- `fastapi-application/api/` без изменений поведения.
- `fastapi-application/ex_order_product/` без изменений поведения.
- Общие `db_core/`, `core/`, `create_fastapi.py`, `utils/docs.py`, Alembic и текущая SQLite/PostgreSQL конфигурация.
- Новый `fastapi-application/setup_frontend.py` с публичной функцией `mount_frontend(app: FastAPI) -> None`. Функция монтирует `/static` из `BASE_DIR / "static"`, `/assets` из `frontend/dist/assets` и последним добавляет `/{full_path:path}`; для `/api` и `/api/*` fallback возвращает JSON 404, для остальных путей — `frontend/dist/index.html`, если сборка существует.
- `fastapi-application/main.py`, который подключает `router_api`, `r_order_one`, `auth_users.router` и `mount_frontend`, не импортируя `md_articles` или `ex_user_post`.
- Защищённый `GET /api/v1/auth/protected`, использующий `active_user` и возвращающий JSON с подтверждением доступа и auth-данными пользователя; anonymous получает JSON `401`.
- `db_core/model_registry.py` без `BlogUser`/`BlogPost`, но с auth `User` и сохранёнными order/product-моделями, чтобы metadata для auth и order domain оставалась доступной.

### Frontend

- React routes: `/`, `/login`, `/register`, `/account`, `/protected`; `/account` и `/protected` проходят через `RequireAuth`, неизвестные пути перенаправляются на `/`.
- `AuthContext` и `api/auth.ts` используют cookie credentials и следующие контракты:
  - `POST /auth/jwt/login`, form fields `username=<email>`, `password=<password>`, успешный ответ 204, затем `GET /users/me`;
  - `POST /auth/jwt/logout`, успешный ответ 204;
  - `POST /auth/register`, JSON `{email, password}`, успешный ответ 201 с `UserRead`;
  - `GET /users/me`, 200 с `UserRead` для auth и 401 для anonymous;
  - `PATCH /users/me`, если используется стандартное обновление полей без управления чужими пользователями;
  - `POST /auth/account`, multipart fields `username`, `email`, optional `picture`, успешный JSON `{message, category, user}`;
  - `GET /api/v1/auth/protected`, 200 с auth JSON для authorized и 401 для anonymous;
  - avatar URL строится как `/static/profile_pics/{image_file}`.
- Home показывает назначение auth-шаблона и ссылки на login/register либо account/protected в зависимости от состояния пользователя.
- Protected page вызывает `/api/v1/auth/protected`, показывает подтверждение backend-доступа и недоступна anonymous в UI; прямой backend access без cookie отвечает 401.
- Blog pages, blog API clients, article-management components, Markdown/highlight.js components, section/theme controls и blog-only типы отсутствуют.
- `frontend/package.json` и lock-файл остаются согласованными; frontend собирается командой `npm run build`, `frontend/dist` не коммитится.

### Точные зоны удаления

- Полностью удалить backend package `fastapi-application/md_articles/`: `__init__.py`, `api_blog.py`, `models.py`, `schema_art.py`, `schema_blog.py`, `setup_frontend.py` и registry/data files внутри package.
- Полностью удалить `fastapi-application/content_art/` со всеми Markdown-статьями и registry/data files.
- Полностью удалить `fastapi-application/ex_user_post/` со всеми User/Post CRUD-модулями и моделями.
- Удалить blog-only dependency `markdown` и, если после удаления blog/session code больше не используется, `pyyaml` и `itsdangerous`; `Pillow` и `python-multipart` сохранить: они нужны account/avatar flow. Lock-файл обновить штатным способом.
- Из frontend удалить:
  - `frontend/src/api/blog.ts`, `frontend/src/api/artManage.ts`;
  - `frontend/src/pages/ArticlePage.tsx`, `frontend/src/pages/ArtManagePage.tsx`, `frontend/src/pages/AboutPage.tsx`;
  - `frontend/src/components/ArticleCard.tsx`, `ArtManageForms.tsx`, `MarkdownContent.tsx`, `Pagination.tsx`, `SectionMenu.tsx`, `SidePanel.tsx`, `ThemeSelect.tsx`, `HljsThemeSelect.tsx`;
  - `frontend/src/hooks/useTheme.ts`, `frontend/src/hooks/useHljsTheme.ts`;
  - orphaned `frontend/components/Toast.tsx`, если он не используется сборкой.
- Из `frontend/index.html` удалить blog/highlight.js CDN assets и связанные ссылки. `frontend/src/index.css` оставить только с минимальными auth/layout styles.
- Удалить или актуализировать product-документацию, которая описывает удаляемый blog: реально существующие `docs/06_blog.md` удалить; ссылки на blog в реально существующих `docs/01_project_structure.md`, `docs/02_architecture.md`, `docs/03_execution_flow.md`, `docs/04_authorization.md`, `docs/05_authorization_upgrade.md` привести к auth-only шаблону. Операционные `QWEN.md` и `AGENTS.md` не входят в product cleanup и сохраняются как инструкции агентного режима.

## Вне рамок

- Изменение или переосмысление реализации `fastapi-users`, JWT/cookie backend, password policy, avatar validation и account semantics, кроме удаления blog coupling.
- Добавление OAuth, refresh-token rotation, password reset, email verification, RBAC, CSRF redesign, rate limiting, production secret management или нового auth provider.
- Изменение `api/` и `ex_order_product/` ради рефакторинга или исправления известных дефектов.
- Удаление `ex_user_post/` как не-auth домена — входит в это задание и не требует отдельного решения.
- Удаление `static/profile_pics/` или отказ от multipart account update.
- Перенос SPA на другой сервер, SSR, новый UI-фреймворк, новый test framework или новую runtime dependency.
- Удаление/переписывание пользовательской SQLite-файловой базы: в репозитории нет `*.db`, поэтому runtime-база не является частью задания.
- Ручное исправление известных дефектов из `AGENTS.md`.
- Adversarial-прогон: явно не включён в это задание.

## План фаз

Единица исполнения — фаза: одно делегирование, 1–3 файла или явно обозначенная одна файловая зона удаления, бюджет ~10–15 ходов. Следующая фаза стартует только после зелёного checkpoint и ревью диффа оркестратором. Прогресс фазы разработчик фиксирует в `tasks/current/dev/phaseNN_progress.md`.

| # | Фаза | Исполнитель | Файлы | Контракт | Checkpoint | Бюджет ходов |
|---|---|---|---|---|---|---|
| 1 | Развязать приложение от блога и добавить protected API | backend-dev | `fastapi-application/main.py`, новый `fastapi-application/setup_frontend.py`, `fastapi-application/auth_users/router.py` | Auth/router wiring без `md_articles`/`ex_user_post`; users-router только `/users/me`; `GET /api/v1/auth/protected` защищён `active_user` | import app, OpenAPI содержит protected и не содержит blog или `/users/{id}` | ~14 |
| 2 | Очистить registry моделей | backend-dev | `fastapi-application/db_core/model_registry.py`, `fastapi-application/md_articles/models.py` | Metadata содержит auth/order модели, не blog models | импорт registry и auth `User` проходит | ~10 |
| 3 | Удалить blog API и схемы | backend-dev | `md_articles/api_blog.py`, `md_articles/schema_art.py`, `md_articles/schema_blog.py` | Ни одного `/api/blog/*` и blog data import | файлы отсутствуют, импорт `main` проходит | ~9 |
| 4 | Удалить остаток package | backend-dev | `md_articles/__init__.py`, `md_articles/setup_frontend.py` | `md_articles` больше не является backend package | `test ! -e md_articles` и import app | ~8 |
| 5 | Удалить article data и User/Post domain | backend-dev | `fastapi-application/content_art/`, `fastapi-application/ex_user_post/` | В репозитории нет article corpus, User/Post CRUD и моделей | `test ! -e` для обеих зон | ~10 |
| 6 | Удалить blog dependency | backend-dev | `pyproject.toml`, `uv.lock` | `markdown`/неиспользуемые blog-only deps отсутствуют, auth/avatar deps сохранены | `uv lock --check` и dependency grep | ~10 |
| 7 | Зафиксировать frontend routes | frontend-dev | `frontend/src/App.tsx`, `frontend/src/pages/HomePage.tsx`, новый `frontend/src/pages/ProtectedPage.tsx` | Ровно home/login/register/account/protected; auth guard на двух routes; Protected вызывает backend JSON API | `cd frontend && npm run build` | ~13 |
| 8 | Упростить auth layout | frontend-dev | `frontend/src/components/Layout.tsx`, `frontend/src/components/Header.tsx`, `frontend/src/types.ts` | Header содержит только auth/home navigation; `User` type не содержит article fields | `npm run build` и grep старых blog imports в этих файлах | ~12 |
| 9 | Привести auth forms к контракту | frontend-dev | `frontend/src/pages/RegisterPage.tsx`, `frontend/src/pages/AccountPage.tsx`, `frontend/src/context/AuthContext.tsx` | Registration JSON только email/password; account multipart и `/users/me` сохранены | `npm run build`; точечный grep endpoint paths | ~13 |
| 10 | Удалить blog API clients/pages | frontend-dev | `frontend/src/api/blog.ts`, `frontend/src/api/artManage.ts`, `frontend/src/pages/ArticlePage.tsx` | Blog client/article detail code отсутствует | `test ! -e` для трёх файлов и `npm run build` | ~9 |
| 11 | Удалить management/about UI | frontend-dev | `frontend/src/pages/ArtManagePage.tsx`, `frontend/src/pages/AboutPage.tsx`, `frontend/src/components/ArticleCard.tsx` | Нет article management/about/article-card UI | отсутствие файлов и `npm run build` | ~9 |
| 12 | Удалить article components | frontend-dev | `frontend/src/components/ArtManageForms.tsx`, `frontend/src/components/MarkdownContent.tsx`, `frontend/src/components/Pagination.tsx` | Нет registry forms, Markdown renderer или article pagination | отсутствие файлов и `npm run build` | ~9 |
| 13 | Удалить blog navigation/themes | frontend-dev | `frontend/src/components/SectionMenu.tsx`, `frontend/src/components/SidePanel.tsx`, `frontend/src/components/ThemeSelect.tsx` | Нет section/theme management controls | отсутствие файлов и `npm run build` | ~9 |
| 14 | Удалить highlight/theme остаток | frontend-dev | `frontend/src/components/HljsThemeSelect.tsx`, `frontend/src/hooks/useTheme.ts`, `frontend/src/hooks/useHljsTheme.ts` | Нет highlight.js/theme hooks | отсутствие файлов и `npm run build` | ~9 |
| 15 | Очистить SPA shell и assets | frontend-dev | `frontend/index.html`, `frontend/src/index.css`, `frontend/components/Toast.tsx` | Только auth-template markup/styles; auth Toast из `src` сохранён | `npm run build`; в bundle нет blog/highlight.js markers | ~11 |
| 16 | Обновить документацию структуры и архитектуры | backend-dev | `docs/01_project_structure.md`, `docs/02_architecture.md`, `docs/03_execution_flow.md` | Документы описывают auth-template без blog/ex_user_post | точечный grep blog/ex_user_post и просмотр auth routes | ~12 |
| 17 | Обновить документацию авторизации и удалить blog guide | backend-dev | `docs/04_authorization.md`, `docs/05_authorization_upgrade.md`, удалить `docs/06_blog.md` | Authorization docs описывают protected API; blog guide отсутствует | `test ! -e docs/06_blog.md`, grep protected route | ~10 |
| 18 | Финальная интеграционная проверка | qa | `tasks/current/e2e/` | Evidence по auth, protected behavior, retained APIs и отсутствию blog | один запуск сервера, пакет curl, build/import evidence | ~10 |

### Фаза 1: Развязать приложение от блога и добавить protected API

- Файлы: `fastapi-application/main.py`, новый `fastapi-application/setup_frontend.py`, `fastapi-application/auth_users/router.py`.
- Контракт: `mount_frontend(app: FastAPI) -> None` отвечает только за auth static и generic React SPA. В `main.py` остаются `router_api`, `r_order_one`, `auth_users.router`; импортов `md_articles` и `ex_user_post` нет. Auth router публикует `/auth/jwt/login`, `/auth/jwt/logout`, `/auth/register`, `/auth/account`, `/users/me` (GET/PATCH), но не `/users/{id}`. В том же auth router добавляется `GET /api/v1/auth/protected`, защищённый `active_user`, с JSON-ответом authorized user.
- Шаги: перенести generic SPA fallback из старого setup-модуля без blog imports; сохранить `/static` для avatar; подключить auth router напрямую; сохранить semantics `/users/me`; удалить generated user-by-id routes; добавить protected API без изменения auth backend.
- Checkpoint: из `fastapi-application/` выполнить `../.venv/bin/python -c "from main import main_app; paths=main_app.openapi()['paths']; print(len(paths)); print('/api/v1/auth/protected' in paths); print(any(p.startswith('/api/blog') for p in paths)); print('/users/{id}' in paths); print('/users/me' in paths)"`. Ожидание: `23`, `True`, `False`, `False`, `True`.
- Готовность фазы: приложение импортируется, auth/demo/order routes зарегистрированы, protected API зарегистрирован, blog и user-by-id routes отсутствуют, `/assets`/catch-all находятся после API.

### Фаза 2: Очистить registry моделей

- Файлы: `fastapi-application/db_core/model_registry.py`, `fastapi-application/md_articles/models.py`.
- Контракт: registry больше не импортирует `BlogUser`/`BlogPost`; auth `User` и order/product модели остаются видимыми для `Base.metadata`. `md_articles/models.py` удаляется.
- Шаги: сначала убрать blog imports и tuple entries из registry, затем удалить старые blog ORM models; auth model не дублировать и не переименовывать.
- Checkpoint: `cd fastapi-application && ../.venv/bin/python -c "import db_core.model_registry; from auth_users.models import User; print(User.__tablename__); print('ok')"`. Ожидание: вывод `user` и `ok`, без импорта `md_articles`.
- Готовность фазы: registry import зелёный и новая/чистая БД не требует blog models для metadata.

### Фаза 3: Удалить blog API и схемы

- Файлы: `fastapi-application/md_articles/api_blog.py`, `schema_art.py`, `schema_blog.py`.
- Контракт: удаляются `/api/blog/articles`, `/api/blog/sections`, `/api/blog/art_manage*`, Markdown/render/registry schemas; auth dependencies не переносятся в blog compatibility layer.
- Шаги: удалить три файла после того, как `main.py` и registry перестали их импортировать; убедиться, что auth helpers используются только `auth_users`.
- Checkpoint: `test ! -e fastapi-application/md_articles/api_blog.py && test ! -e fastapi-application/md_articles/schema_art.py && test ! -e fastapi-application/md_articles/schema_blog.py` и импорт `main` из фазы 1.
- Готовность фазы: три blog API/data files отсутствуют, auth router продолжает импортироваться независимо.

### Фаза 4: Удалить остаток package

- Файлы: `fastapi-application/md_articles/__init__.py`, `setup_frontend.py`.
- Контракт: весь `md_articles` package удалён; его generic frontend responsibilities уже находятся в новом module root-level.
- Шаги: удалить оставшиеся два файла; не оставлять compatibility re-export.
- Checkpoint: `test ! -e fastapi-application/md_articles` и `cd fastapi-application && ../.venv/bin/python -c "from main import main_app; paths=main_app.openapi()['paths']; print(len(paths)); print('/api/v1/auth/protected' in paths); print(any(p.startswith('/api/blog') for p in paths)); print('/users/{id}' in paths)"`. Ожидание: `23`, `True`, `False`, `False`.
- Готовность фазы: ни один Python import не требует `md_articles`.

### Фаза 5: Удалить article data

- Файлы: файловая зона `fastapi-application/content_art/` целиком.
- Контракт: статьи, YAML registry и article-only content удалены; `static/profile_pics/` не затрагивается.
- Шаги: удалить всю content-art directory, включая вложенные каталоги и служебные файлы.
- Checkpoint: `test ! -e fastapi-application/content_art` и точечный поиск `md_articles|content_art|router_blog_api` в `fastapi-application/*.py fastapi-application/*/*.py` не должен вернуть runtime references.
- Готовность фазы: в backend workspace нет article corpus и его кода.

### Фаза 6: Удалить blog dependency

- Файлы: `pyproject.toml`, `uv.lock`.
- Контракт: `markdown` удалён как blog-only dependency; `fastapi-users[sqlalchemy]`, `python-multipart`, `pillow`, FastAPI и существующие DB dependencies сохранены.
- Шаги: изменить declaration и обновить lock штатным `uv` способом; не добавлять новые зависимости.
- Checkpoint: `uv lock --check` и `grep -n 'markdown' pyproject.toml` с ожидаемым отсутствием строки; `grep -n 'fastapi-users\|python-multipart\|pillow' pyproject.toml` должен показать сохранённые зависимости.
- Готовность фазы: lock согласован с manifest и auth account flow сохраняет свои runtime packages.

### Фаза 7: Зафиксировать frontend routes

- Файлы: `frontend/src/App.tsx`, `frontend/src/pages/HomePage.tsx`, новый `frontend/src/pages/ProtectedPage.tsx`.
- Контракт: `RequireAuth` остаётся единственным UI guard; `/account` и `/protected` redirect anonymous на `/login`; Home не вызывает blog API; Protected показывает backend response из `/api/v1/auth/protected` и не считается безопасной только из-за client guard.
- Шаги: удалить Article/About/section/art_manage routes; сделать минимальный Home dashboard; добавить Protected page с fetch к защищённому JSON endpoint и обработкой unauthorized.
- Checkpoint: `cd frontend && npm run build`. Ожидание: exit code 0, `dist/index.html` создан локально.
- Готовность фазы: route graph frontend не содержит blog URLs и компилируется.

### Фаза 8: Упростить auth layout

- Файлы: `frontend/src/components/Layout.tsx`, `Header.tsx`, `types.ts`.
- Контракт: Layout/Header знают только auth state, home/login/register/account/protected и logout; `types.ts` содержит `User` и только поля, необходимые auth UI (`id`, `email`, `username`, `image_file`, flags). Theme/section/article props исчезают.
- Шаги: убрать side menu, theme selectors и article navigation; сохранить `Toast`, `Outlet`, logout и avatar URL contract.
- Checkpoint: `cd frontend && npm run build` и `grep -R "Article\|Section\|Theme\|Hljs\|art_manage\|/api/blog" src/components/Layout.tsx src/components/Header.tsx src/types.ts` с ожидаемым отсутствием совпадений.
- Готовность фазы: общий shell собирается и не содержит blog coupling.

### Фаза 9: Привести auth forms к контракту

- Файлы: `frontend/src/pages/RegisterPage.tsx`, `AccountPage.tsx`, `context/AuthContext.tsx`.
- Контракт: Register отправляет `{email, password}` и отображает server validation; Account читает `/users/me`, отправляет multipart `username/email/picture` на `/auth/account`; AuthContext initial refresh использует `/users/me`, 401 трактует как anonymous.
- Шаги: убрать неиспользуемое registration username из payload/UI либо явно оставить его только как локальное поле без отправки; предпочтительно минимизировать форму до email/password; сохранить shared `FormField` и error mapping.
- Checkpoint: `cd frontend && npm run build`; `grep -R "api/blog\|/auth/account\|/users/me\|/auth/register" src/pages/RegisterPage.tsx src/pages/AccountPage.tsx src/context/AuthContext.tsx src/api/auth.ts`. Ожидание: только разрешённые auth paths, blog path отсутствует.
- Готовность фазы: формы соответствуют backend contract и не зависят от удаляемых компонентов.

### Фаза 10: Удалить blog API clients/pages

- Файлы: `frontend/src/api/blog.ts`, `frontend/src/api/artManage.ts`, `frontend/src/pages/ArticlePage.tsx`.
- Контракт: article list/detail/management clients и page удалены; auth API client остаётся.
- Шаги: удалить файлы и не добавлять заглушки с теми же URLs.
- Checkpoint: `test ! -e` для трёх путей и `cd frontend && npm run build`.
- Готовность фазы: сборка не импортирует blog clients.

### Фаза 11: Удалить management/about UI

- Файлы: `frontend/src/pages/ArtManagePage.tsx`, `AboutPage.tsx`, `ArticleCard.tsx`.
- Контракт: management, old about и article-card UI отсутствуют.
- Checkpoint: три файла отсутствуют, `npm run build` зелёный.
- Готовность фазы: App не может направить пользователя в удалённые blog pages.

### Фаза 12: Удалить article components

- Файлы: `frontend/src/components/ArtManageForms.tsx`, `MarkdownContent.tsx`, `Pagination.tsx`.
- Контракт: нет registry form, Markdown HTML renderer или article pagination.
- Checkpoint: файлы отсутствуют, `npm run build` зелёный.
- Готовность фазы: удалены UI-компоненты, требующие article data shape.

### Фаза 13: Удалить blog navigation/themes

- Файлы: `frontend/src/components/SectionMenu.tsx`, `SidePanel.tsx`, `ThemeSelect.tsx`.
- Контракт: shell не содержит section menu, side panel или blog theme selector.
- Checkpoint: файлы отсутствуют, `npm run build` зелёный.
- Готовность фазы: Layout/Header не имеют orphaned imports.

### Фаза 14: Удалить highlight/theme остаток

- Файлы: `frontend/src/components/HljsThemeSelect.tsx`, `frontend/src/hooks/useTheme.ts`, `frontend/src/hooks/useHljsTheme.ts`.
- Контракт: highlight.js/theme hooks и selectors отсутствуют; обычная auth CSS не зависит от них.
- Checkpoint: файлы отсутствуют, `npm run build` зелёный.
- Готовность фазы: blog presentation state полностью удалён.

### Фаза 15: Очистить SPA shell и assets

- Файлы: `frontend/index.html`, `frontend/src/index.css`, `frontend/components/Toast.tsx`.
- Контракт: index HTML не подключает article/highlight.js assets; `src/components/Toast.tsx` сохраняется как auth feedback component; orphaned duplicate вне `src` удаляется только если не используется.
- Шаги: оставить React root и обычные auth styles; не удалять `src/components/Toast.tsx`.
- Checkpoint: `cd frontend && npm run build`; `grep -R "highlight.js\|cdnjs\|article\|art_manage\|md_articles" index.html src` не должен находить runtime/blog references, кроме допустимых исторических слов в комментариях, которые следует убрать из затронутых файлов.
- Готовность фазы: production SPA build существует и не тянет blog CDN/assets.

### Фаза 16: Финальная интеграционная проверка

- Файлы: `tasks/current/e2e/`.
- Контракт: qa не меняет product code, поднимает один сервер из `fastapi-application/`, сохраняет сырые выводы в e2e и выключает свой процесс по правилам задания.
- Шаги: проверить route count/import, собрать frontend, проверить auth anonymous/register/login/logout/account flow cookie-сессией, protected API 401 до login, retained demo/order routes, `/api/blog/*` JSON 404 и SPA `/protected`.
- Checkpoint: один пакет команд с точными HTTP status/body assertions; все результаты записаны в `tasks/current/e2e/`.
- Готовность фазы: каждый критерий успеха имеет машинное evidence; найденные дефекты заведены qa в `DEFECTS.md`.

### Разрешение blocker миграций (решение оркестратора, 2026-09-14)

Финальный QA выявил, что `fastapi-application/alembic/versions/` содержит только `.keep`: `alembic upgrade heads` завершается успешно, но не создаёт таблицы `user` и `orders`, поэтому обязательные auth/order flow дают `500`. Git-диагностика показала, что пустой каталог унаследован до текущего задания; текущая metadata содержит только auth User и order/product-модели. Для восстановления заявленного рабочего контракта добавляется одна новая initial migration по текущей metadata (`user`, `orders`, `products`, `order_product_association`). Старые blog/ex_user_post revisions и migration cleanup не восстанавливаются, runtime SQLite не изменяется вручную.

### Фаза 19: Восстановить initial migration auth/order

- Файлы: новая ревизия в `fastapi-application/alembic/versions/`, `tasks/current/dev/phase19_progress.md` и raw logs.
- Контракт: `alembic upgrade heads` на чистой временной SQLite создаёт только `user`, `orders`, `products`, `order_product_association` и `alembic_version`; blog/user-post таблиц в новой схеме нет. Existing `auth_users` и `ex_order_product` semantics не меняются.
- Ограничения: не изменять runtime `fastapi-application/one_simple.db`, не восстанавливать старые revision chains, не добавлять blog cleanup operations, не менять product code вне migration.
- Checkpoint: на временной SQLite через штатный Alembic `upgrade heads`, затем SQL-инспекция таблиц; импорт приложения и `uv lock --check` остаются зелёными.
- Готовность фазы: новая миграция проверена на чистой временной SQLite, а DEF-001/DEF-002 готовы к повторному QA-прогону.

## Критерии успеха

Проверяются qa по завершении всех фаз; сырые выводы — в `tasks/current/e2e/`.

| # | Критерий | Проверка | Ожидание |
|---|---|---|---|
| 1 | Backend импортируется без blog package | `cd fastapi-application && ../.venv/bin/python -c "from main import main_app; paths=main_app.openapi()['paths']; print(len(paths)); print('/api/v1/auth/protected' in paths); print(any(p.startswith('/api/blog') for p in paths)); print('/users/{id}' in paths)"` | Exit code 0; ожидаются `23`, `True`, `False`, `False` |
| 2 | Blog routes удалены, auth routes сохранены | Parse `main_app.openapi()['paths']` или `/openapi.json`; curl `/api/blog/articles` и `/auth/register` | `/api/blog/articles` — JSON 404; `/auth/register` существует и на невалидном payload даёт 422; login/logout/register/account/me/protected присутствуют |
| 3 | Auth anonymous boundary работает | `curl -i http://127.0.0.1:8000/users/me` без cookie и `curl -i http://127.0.0.1:8000/api/v1/auth/protected` без cookie | Оба ответа HTTP 401, JSON, не HTML и не 500 |
| 4 | Registration/login/logout flow работает по зафиксированному контракту | curl с cookie jar: POST `/auth/register` JSON email/password, POST `/auth/jwt/login` form username/password, GET `/users/me`, GET `/api/v1/auth/protected`, POST `/auth/jwt/logout` | Register — 201; login/logout — 204; authenticated me/protected — 200; protected содержит auth confirmation и user data без password |
| 5 | Account contract сохранён | Авторизованный multipart POST `/auth/account` с `username`, `email` и без/с `picture`; GET avatar URL | 200 с `{message, category, user}`; поля пользователя обновляются; `/static/profile_pics/...` отвечает не blog HTML |
| 6 | Сохранены demo API и order domain | curl `/docs`, `/api/v1/dep_examples/single-direct-dependency`, `/orders/get_all_orders` | `/docs` — 200; demo endpoint не 404/500; order endpoint зарегистрирован и отвечает ожидаемым приложением статусом |
| 7 | Backend article/UserPost code/data действительно удалены | `test ! -e fastapi-application/md_articles`; `test ! -e fastapi-application/content_art`; `test ! -e fastapi-application/ex_user_post`; точечный grep runtime imports; dependency grep | Три зоны отсутствуют; нет runtime references к `md_articles`, `router_blog_api`, `content_art`, `ex_user_post`; blog-only deps отсутствуют, auth dependencies присутствуют |
| 8 | Frontend собирается без blog code | `cd frontend && npm run build`; поиск по `src` и `index.html` | Exit code 0; отсутствуют imports/URLs `api/blog`, `art_manage`, article pages, highlight.js CDN; `dist/index.html` создан |
| 9 | Frontend route/auth guard соответствует минимальному шаблону | Проверка исходников `App.tsx`/`ProtectedPage.tsx` плюс curl GET `/`, `/login`, `/register`, `/account`, `/protected` после сборки | Ровно требуемые routes; `/account` и `/protected` используют `RequireAuth`; SPA fallback отдаёт index для UI routes; `/api/*` отдаёт JSON 404 |
| 10 | Retained auth API и SPA используют один source of truth для avatar URL | grep `api/auth.ts`, `AccountPage.tsx`, backend `/static` mount | Multipart field называется `picture`, backend response field `image_file`, URL только `/static/profile_pics/{image_file}` |

## Риски и грабли

- `main_app.routes` зависит от порядка подключения: generic catch-all должен добавляться после auth/demo/order routers, иначе он перехватит API. `/api*` fallback обязан возвращать JSON 404, а не `index.html`.
- Старый `md_articles/setup_frontend.py` одновременно содержал frontend infrastructure и blog imports. Нельзя просто удалить его без нового generic setup module: сломается раздача SPA и avatar static.
- `db_core/model_registry.py` — скрытая граница Alembic metadata. Если удалить blog imports механически и не сохранить auth `User`/order models, чистая схема перестанет видеть таблицы auth или order.
- Регистрация fastapi-users фактически принимает только email/password, тогда как старый frontend показывал username. Это надо исправить в UI, иначе пользователь будет думать, что имя сохранено, хотя backend его вычисляет.
- `auth_users.helpers.save_picture` требует `Pillow`, а account upload требует `python-multipart`; их нельзя считать blog dependencies и удалять вместе с `markdown`.
- SQLite URL относителен cwd. Все будущие import/server/curl checkpoints должны запускаться из `fastapi-application/`; в репозитории нет `*.db`, поэтому задание не удаляет и не мигрирует runtime-базу.
- В проекте нет тестового фреймворка. Доказательством поведения служат import, `npm run build`, один запущенный сервер и curl assertions; в фазе создания сервер не запускается.

## Финальные критерии

1. Каждый критерий успеха подтверждён машинным доказательством в `tasks/current/e2e/`.
2. `tasks/current/DEFECTS.md` существует только если найдены дефекты; перед закрытием задания все записи имеют статус не `OPEN`.
3. Спека не требует adversarial-прогона, так как он не был явно заказан пользователем.

---

# Отчёт о выполнении

Дата закрытия: 2026-09-14.

Блог, `content_art` и `ex_user_post` удалены; приложение отвязано от blog-layer, сохранены auth/demo/order domains, добавлены protected API и generic SPA setup. Frontend оставлен auth-only, добавлена initial migration для `user` и order/product tables. Полный runtime evidence: [e2e/phase20_final.md](e2e/phase20_final.md), сырые проверки: [e2e/phase20_raw.txt](e2e/phase20_raw.txt). DEF-001 и DEF-002 закрыты после повторного прогона.

