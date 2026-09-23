# 07. Авторизация по коду: где выдаётся JWT, где живёт в браузере, кто шлёт cookie

Документ самодостаточный: все места, где участвует токен, показаны **кодом**, а не ссылками
на код. Читать исходники после него не нужно.

Опирается на [`docs/04_authorization.md`](04_authorization.md) (полный цикл по шагам),
[`docs/06_auth_visual.md`](06_auth_visual.md) (диаграммы и рантайм-граф).
Способы передачи токена (cookie / Bearer / кастомный заголовок), сравнение и выбор под
несколько клиентов — [`docs/08_jwt_transport_options.md`](08_jwt_transport_options.md).

Стек на момент написания: `fastapi 0.141.1`, `fastapi-users 15.0.5`,
`fastapi-users-db-sqlalchemy 7.0.0`, `starlette 1.6.0`, `pydantic 2.13.5`,
`sqlalchemy 2.0.52`, `pyjwt 2.14.0`, `pwdlib 0.3.0` (Argon2).

---

## 0. Ответы на четыре вопроса коротко

| Вопрос | Ответ | Где в коде |
|---|---|---|
| Где выдаётся токен? | Внутри библиотеки `fastapi-users`, на `POST /auth/jwt/login`. Своего обработчика в проекте нет — маршрут порождается `get_auth_router(auth_backend)` | `auth_users/router.py` + `auth_users/auth_backend.py` |
| Где он хранится в браузере? | В cookie `auth`, `HttpOnly`. Браузер сохраняет её сам по `Set-Cookie`. JavaScript токен прочитать не может | ставит `CookieTransport`, JS не участвует |
| Кто посылает cookie? | Браузер, автоматически. JS лишь помечает запрос `credentials: 'include'` | `frontend/src/api/client.ts` |
| Кто инициирует передачу токена на защищённый ресурс? | Браузер — по факту наличия cookie. Проверяет токен бэкенд через `Depends(active_user)`; фронтовый `RequireAuth` API не защищает | `auth_users/router.py`, `frontend/src/App.tsx` |

---

## 1. Точка сборки: транспорт + стратегия

`fastapi-application/auth_users/auth_backend.py` — **единственное место**, где выбирается
«чем токен едет» (транспорт) и «как токен устроен» (стратегия):

```python
from core.config import settings
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
)
from fastapi_users.authentication.strategy import JWTStrategy

cookie_transport = CookieTransport(
    cookie_name=settings.auth_users.cookie_name,        # "auth"
    cookie_max_age=settings.auth_users.cookie_max_age,  # 86400 секунд
    cookie_secure=settings.auth_users.cookie_secure,    # False — локальный HTTP
    cookie_httponly=settings.auth_users.cookie_httponly,# True — JS не прочитает
    cookie_samesite=settings.auth_users.cookie_samesite,# "lax"
)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.web.secret_key,
        lifetime_seconds=settings.auth_users.jwt_lifetime_seconds,
        algorithm=settings.auth_users.jwt_algorithm,
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)
```

`name="jwt"` — это то, что даёт префикс пути `/auth/jwt/...`. Замена транспорта на
`BearerTransport` здесь же, одной строкой, даёт другую схему передачи токена, ничего больше
в проекте не меняя (см. отдельный документ про способы передачи).

---

## 2. Параметры токена и cookie — `core/config.py`

```python
class WebConfig(BaseModel):
    secret_key: str = "dev-insecure-secret-key-change-me"


class AuthUsersConfig(BaseModel):
    cookie_name: str = "auth"
    cookie_max_age: int = 86400
    cookie_secure: bool = False
    cookie_httponly: bool = True
    cookie_samesite: str = "lax"
    jwt_lifetime_seconds: int = 86400
    jwt_algorithm: str = "HS256"
    password_min_length: int = 8
```

| Параметр | Значение | Что делает |
|---|---|---|
| `secret_key` | dev-значение | секрет подписи HS256; в проде задавать `APP__WEB__SECRET_KEY` вне репозитория |
| `cookie_name` | `auth` | имя cookie, в которой едет JWT |
| `cookie_max_age` | `86400` | сколько секунд браузер хранит cookie |
| `cookie_httponly` | `true` | запрещает `document.cookie` читать cookie |
| `cookie_samesite` | `lax` | когда браузер прикладывает cookie к запросам |
| `cookie_secure` | `false` | для HTTPS включать `true` |
| `jwt_lifetime_seconds` | `86400` | срок действия самого JWT (внутри токена, поле `exp`) |
| `jwt_algorithm` | `HS256` | алгоритм подписи |

Важно: **`cookie_max_age` и `jwt_lifetime_seconds` — разные вещи**. Cookie может быть
удалена браузером раньше, а JWT с истёкшим `exp` не пройдёт проверку, даже если cookie
ещё лежит в браузере. Совпадающие значения здесь — совпадение по смыслу, а не одно поле.

---

## 3. Где выдается токен: маршруты

`fastapi-application/auth_users/router.py` — обработчиков login/logout в проекте **нет**,
их создаёт библиотека:

```python
auth_router = fastapi_users.get_auth_router(auth_backend)                   # login + logout
register_router = fastapi_users.get_register_router(UserRead, UserCreate)   # register
users_router = fastapi_users.get_users_router(UserRead, UserUpdate)
users_router.routes = [route for route in users_router.routes if route.path == "/me"]

protected_router = APIRouter(
    prefix=f"{settings.api.prefix}{settings.api.v1.prefix}/auth"            # /api/v1/auth
)


@protected_router.get("/protected", tags=["auth"])
async def protected(user: Annotated[User, Depends(active_user)]):
    return {
        "authenticated": True,
        "user": UserRead.model_validate(user),
    }


router = APIRouter()
router.include_router(auth_router, prefix="/auth/jwt", tags=["auth-jwt"])
router.include_router(register_router, prefix="/auth", tags=["auth-register"])
router.include_router(users_router, prefix="/users", tags=["users"])
router.include_router(account_router)
router.include_router(protected_router)
```

Что получается на выходе (префикс `/auth/jwt` даёт `name` транспортного backend'а):

| Метод | Путь | Кто создал | Что делает |
|---|---|---|---|
| `POST` | `/auth/jwt/login` | `get_auth_router` | проверяет пароль, **создаёт JWT**, ставит cookie |
| `POST` | `/auth/jwt/logout` | `get_auth_router` | удаляет cookie |
| `POST` | `/auth/register` | `get_register_router` | создаёт пользователя, токен **не выдаёт** |
| `GET`/`PATCH` | `/users/me` | `get_users_router` (обрезан до `/me`) | текущий пользователь |
| `POST` | `/auth/account` | `auth_users/account.py` | меняет `username`/`email` |
| `GET` | `/api/v1/auth/protected` | `router.py` | демонстрация backend-защиты |

Экземпляр, от которого берутся зависимости, — `auth_users/fastapi_users_obj.py`:

```python
fastapi_users = FastAPIUsers[User, UUID](get_user_manager, [auth_backend])

current_user = fastapi_users.current_user
active_user = fastapi_users.current_user(active=True)
optional_user = fastapi_users.current_user(optional=True)
superuser_user = fastapi_users.current_user(active=True, superuser=True)
```

---

## 4. Что библиотека делает на `POST /auth/jwt/login`

Схема (реальные вызовы библиотеки, снятые профайлером в `docs/06_auth_visual.md`):

```text
POST /auth/jwt/login  (application/x-www-form-urlencoded: username=<email>&password=<...>)
  │
  ├── authenticate()
  │     └── verify_and_update(password, hashed_password)
  │           └── pwdlib … argon2.verify_secret          # 98% времени логина — Argon2
  │
  ├── JWTStrategy.write_token(user)
  │     └── pyjwt.encode(payload, secret, algorithm="HS256")
  │           payload: { "sub": "<user.id>", "aud": "fastapi-users:auth", "exp": <now+lifetime> }
  │
  └── CookieTransport.get_login_response(token)
        └── Set-Cookie: auth=<JWT>; Max-Age=86400; HttpOnly; SameSite=Lax; Path=/
```

Тело ответа пустое: успех — `204 No Content`. **JWT в JSON не приходит ни в каком виде.**

Как этот же ответ выглядит в терминале:

```http
HTTP/1.1 204 No Content
set-cookie: auth=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.<payload>.<signature>; HttpOnly; Max-Age=86400; Path=/; SameSite=lax
```

Содержимое JWT (декодированное, подпись не проверяется — читаем для наглядности):

```json
{
  "sub": "3f1c9a44-...-b7d2",
  "aud": "fastapi-users:auth",
  "exp": 1789999999
}
```

То есть **в токене нет ни email, ни ролей** — только идентификатор пользователя, аудитория и
срок. Все остальные данные бэкенд достаёт из БД по `sub`. Это важно при проектировании:
смена роли/блокировка пользователя действует сразу, потому что данные берутся из БД, а не из
токена.

---

## 5. Что происходит на фронте: файлы целиком по смыслу

### 5.1. `frontend/src/api/client.ts` — единственное место с `credentials`

```ts
export class ApiError extends Error {
    status: number;
    data: unknown;
    constructor(status: number, message: string, data: unknown = null) {
        super(message);
        this.status = status;
        this.data = data;
        this.name = 'ApiError';
    }
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
    const res = await fetch(path, { credentials: 'include', ...init });
    return res;
}

async function ensureOk(res: Response): Promise<unknown> {
    if (res.ok) {
        if (res.status === 204) return null;
        const ct = res.headers.get('content-type') || '';
        if (ct.includes('application/json')) return res.json();
        return res.text();
    }
    let data: unknown = null;
    try {
        data = await res.json();
    } catch {
        data = await res.text().catch(() => null);
    }
    throw new ApiError(res.status, `HTTP ${res.status}`, data);
}

export async function getJson<T = unknown>(path: string): Promise<T> {
    const res = await request(path, { method: 'GET' });
    return (await ensureOk(res)) as T;
}

export async function postJson<T = unknown>(path: string, body: unknown): Promise<T> {
    const res = await request(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    return (await ensureOk(res)) as T;
}

export async function postForm<T = unknown>(path: string, form: URLSearchParams): Promise<T> {
    const res = await request(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: form.toString(),
    });
    return (await ensureOk(res)) as T;
}
```

Ключевая строка одна:

```ts
fetch(path, { credentials: 'include', ...init })
```

`credentials: 'include'` означает для браузера две вещи: **(а)** принять `Set-Cookie` из
ответа и сохранить cookie; **(б)** прикладывать подходящие cookie к последующим запросам.
Никакого кода, который «достаёт токен и подставляет его», в проекте нет и не должно быть.

### 5.2. `frontend/src/api/auth.ts` — login это ДВА запроса

```ts
// /auth/jwt/login отвечает 204 — фронт после успешного логина делает
// refresh через /users/me (возвращает UserRead).
export function login(body: { email: string; password: string }): Promise<User> {
    const form = new URLSearchParams({
        username: body.email,      // fastapi-users ждёт OAuth2-поле "username"
        password: body.password,
    });
    return postForm<unknown>('/auth/jwt/login', form).then(() => getJson<User>('/users/me'));
}

// /auth/jwt/logout отвечает 204 — фронт НЕ падает, если logout вернул ошибку.
export function logout(): Promise<MessageResp> {
    return postForm<MessageResp>('/auth/jwt/logout', new URLSearchParams())
        .catch(() => ({ message: 'Logged out', category: 'info' }));
}

export function register(body: { email: string; password: string }): Promise<User> {
    return postJson<User>('/auth/register', body);
}

export function updateAccount(body: {
    username: string;
    email: string;
}): Promise<MessageResp & { user: User }> {
    const form = new URLSearchParams({
        username: body.username,
        email: body.email,
    });
    return postForm<MessageResp & { user: User }>('/auth/account', form);
}

// getCurrentUser: для AuthContext.refresh() — возвращает User или null
// (если 401 — пользователь не залогинен).
export function getCurrentUser(): Promise<User | null> {
    return getJson<User>('/users/me').catch((err) => {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
    });
}
```

Разбор `login()` по шагам:

| Шаг | HTTP | Что важно |
|---|---|---|
| 1 | `POST /auth/jwt/login` с телом `username=user@example.com&password=...` | `Content-Type: application/x-www-form-urlencoded`, ответ `204` — **тела нет** |
| 2 | `GET /users/me` | браузер уже приложил cookie `auth` автоматически; ответ `200` + `UserRead` |

Почему нельзя обойтись одним запросом: `204` не несёт данных, поэтому объект пользователя
берётся отдельным `GET /users/me`. Заодно это проверка, что cookie реально принялась.

Почему поле называется `username`, хотя в форме email: стандартный login-router
`fastapi-users` реализует OAuth2 password flow и читает поля `username`/`password` из
форм-тела, а не JSON `email`/`password`.

### 5.3. `frontend/src/context/AuthContext.tsx` — в памяти лежит ПОЛЬЗОВАТЕЛЬ, не токен

```tsx
export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);

    const refresh = useCallback(async () => {
        try {
            // fastapi-users /users/me возвращает User (или null при 401).
            const currentUser = await getCurrentUser();
            setUser(currentUser);
        } catch {
            // Неавторизованный или сбой сети — считаем анонимом.
            setUser(null);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    return (
        <AuthContext.Provider value={{ user, loading, setUser, refresh }}>
            {children}
        </AuthContext.Provider>
    );
}
```

Смысл: при монтировании приложения один раз идёт `GET /users/me`. Если cookie валидна —
в `user` записывается объект пользователя, если нет — `null`. Это **единственный** источник
ответа на вопрос «залогинен ли пользователь» на фронте. Токен в этом состоянии не хранится.

### 5.4. `frontend/src/pages/LoginPage.tsx` — обработчик кнопки

```tsx
const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) {
        showToast('Заполните email и пароль', 'warning');
        return;
    }
    setSubmitting(true);
    try {
        // fastapi-users /auth/jwt/login -> 204, затем /users/me.
        const user: User = await login({ email, password });
        setUser(user);
        showToast('Вход выполнен', 'success');
        navigate('/');
    } catch (err) {
        // fastapi-users /auth/jwt/login: 400 при неверных email/пароле.
        let message = 'Не удалось войти';
        let category: ToastCategory = 'danger';
        if (err instanceof ApiError) {
            if (err.status === 400) {
                message = 'Неверный email или пароль';
            } else {
                const data = err.data as
                    | { message?: string; category?: string; detail?: string }
                    | null;
                if (data?.message) message = data.message;
                else if (data?.detail) message = data.detail;
                if (data?.category) category = data.category as ToastCategory;
            }
        }
        showToast(message, category);
    } finally {
        setSubmitting(false);
    }
};
```

Здесь видно, что фронт **не видит и не трогает токен**: он получает готовый объект `User`
и кладёт его в контекст. Установка cookie произошла «где-то в ответе» — и это ровно то,
что делает `credentials: 'include'` вместе с `Set-Cookie` от бэкенда.

### 5.5. `frontend/src/components/Layout.tsx` и `Header.tsx` — выход

```tsx
const handleLogout = async () => {
    try {
        const resp = await apiLogout();
        setUser(null);
        showToast(resp.message, resp.category as ToastCategory);
    } catch {
        // Даже если запрос не прошёл — локально пользователя сбрасываем.
        setUser(null);
        showToast('Вы вышли из аккаунта', 'message');
    }
};
```

Кнопка в `Header.tsx` просто вызывает `onLogout`:

```tsx
<button type="button" className="nav-link as-button" onClick={onLogout}>
    Выход
</button>
```

На бэке `POST /auth/jwt/logout` отвечает `Set-Cookie: auth=; Max-Age=0; ...` — браузер
удаляет cookie. Локальный `setUser(null)` нужен, чтобы UI не ждал следующего запроса.

---

## 6. Защищённый ресурс: кто инициирует передачу токена

### 6.1. Бэкенд — настоящая защита

`auth_users/router.py` (показан выше) + `Depends(active_user)`: `active_user` — это
`fastapi_users.current_user(active=True)` из `fastapi_users_obj.py`.

Что реально происходит внутри `Depends(active_user)` (цепочка снята профайлером,
`docs/06_auth_visual.md` §5.3):

```text
GET /api/v1/auth/protected
  │
  ├── current_user_dependency            (fastapi_users/authenticator.py)
  │     └── current_user_token_dependency
  │           └── _authenticate
  │                 ├── CookieTransport.get_token(request)
  │                 │     └── читает cookie "auth" из заголовка Cookie
  │                 ├── JWTStrategy.read_token(...)
  │                 │     └── pyjwt.decode → проверка подписи HS256 и поля exp
  │                 └── get_user_manager → get_user_db → get_async_session
  │                       └── SQLAlchemyUserDatabase._get_user
  │                             └── SELECT user.* FROM user WHERE user.id = ?
  │
  └── проверка is_active → в обработчик приходит объект User
```

Если cookie нет, она просрочена, подпись не сходится или `exp` истёк — ответ `401`,
обработчик даже не вызывается:

```json
{"detail": "Unauthorized"}
```

Успешный ответ `200`:

```json
{
  "authenticated": true,
  "user": {
    "id": "3f1c9a44-...-b7d2",
    "email": "user@example.com",
    "username": "user"
  }
}
```

### 6.2. Фронтенд — только запрос, никакой подстановки токена

`frontend/src/pages/ProtectedPage.tsx`:

```tsx
useEffect(() => {
    let cancelled = false;

    getJson<ProtectedResponse>('/api/v1/auth/protected')
        .then((data) => {
            if (!cancelled) setResponse(data);
        })
        .catch((err: unknown) => {
            if (cancelled) return;
            if (err instanceof ApiError && err.status === 401) {
                setError('Backend отклонил запрос: требуется авторизация.');
            } else {
                setError('Не удалось проверить доступ к защищённому backend API.');
            }
        })
        .finally(() => {
            if (!cancelled) setLoading(false);
        });

    return () => {
        cancelled = true;
    };
}, []);
```

Запрос — одна строка. Токен прикладывает браузер: для него `/api/v1/auth/protected` и
`/users/me` одинаковы — оба same-origin, оба требуют cookie `auth`.

### 6.3. UI guard ≠ защита API

`frontend/src/App.tsx`:

```tsx
function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="page-stub text-muted">Проверка доступа...</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}
```

Этот компонент **смотрит только на `AuthContext.user`** и управляет навигацией. Проверка
API от него не зависит: `curl` без всякого UI получит ровно тот же ответ, что и браузер.
Окончательный контроль — `Depends(active_user)` на бэкенде.

---

## 7. Полный поток одной картинкой (HTTP-уровень)

```text
1) POST /auth/jwt/login                 (форма username=<email>&password=<...>)
   ← 204  Set-Cookie: auth=<JWT>; HttpOnly; Max-Age=86400; SameSite=Lax
   ↑ браузер сам сохранил cookie, JS токена не видел

2) GET /users/me                        Cookie: auth=<JWT>   ← приложил браузер
   ← 200  {"id": "...", "email": "...", "username": "..."}
   ↑ фронт записал объект в AuthContext.user

3) GET /api/v1/auth/protected           Cookie: auth=<JWT>   ← приложил браузер
   ← 200  {"authenticated": true, "user": {...}}

4) POST /auth/jwt/logout                Cookie: auth=<JWT>
   ← 204  Set-Cookie: auth=; Max-Age=0
   ↑ cookie удалена; JWT при этом остаётся валидным до exp, если его кто-то скопировал
```

Проверка руками (сервер поднят из `fastapi-application/`, файл cookie — `/tmp/auth.cookies`):

```bash
# 1. анонимный доступ
curl -i http://127.0.0.1:8000/users/me                     # 401
curl -i http://127.0.0.1:8000/api/v1/auth/protected        # 401

# 2. регистрация (токен НЕ выдаёт)
curl -i -X POST http://127.0.0.1:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"password123"}'   # 201

# 3. логин — вот здесь и выдаётся JWT
curl -i -c /tmp/auth.cookies \
  -X POST http://127.0.0.1:8000/auth/jwt/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data 'username=user@example.com&password=password123'      # 204 + Set-Cookie: auth=...

# 4. защищённые запросы с cookie
curl -i -b /tmp/auth.cookies http://127.0.0.1:8000/users/me              # 200
curl -i -b /tmp/auth.cookies http://127.0.0.1:8000/api/v1/auth/protected # 200

# 5. выход
curl -i -b /tmp/auth.cookies -X POST http://127.0.0.1:8000/auth/jwt/logout   # 204, cookie удаляется

# 6. после выхода
curl -i -b /tmp/auth.cookies http://127.0.0.1:8000/api/v1/auth/protected    # 401
```

Полезно посмотреть глазами, что именно лежит в cookie (только для отладки; в браузере
значение HttpOnly-cookie из JS недоступно):

```bash
cat /tmp/auth.cookies          # там строка с auth=eyJhbGciOiJIUzI1NiIs...
```

---

## 8. Как это выглядит в браузере (DevTools)

| Что проверяем | Куда смотреть |
|---|---|
| токен пришёл | Network → `POST /auth/jwt/login` → **Response Headers** → `set-cookie: auth=...` |
| токен сохранён | Application (Storage) → Cookies → домен приложения → `auth`, атрибуты `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age` |
| токен отправлен | Network → `GET /users/me` или `/api/v1/auth/protected` → **Request Headers** → `Cookie: auth=...` |
| токена нет в JS | Console → `document.cookie` → значение `auth` **не появится** (это правильно, это `HttpOnly`) |

---

## 9. Где что хранится (сводно)

| Что | Где | Доступно из JavaScript | Назначение |
|---|---|---:|---|
| JWT | cookie браузера `auth` | нет (`HttpOnly`) | credential для бэкенда |
| атрибуты cookie | браузер | частично (DevTools) | domain/path/max-age/samesite |
| текущий `User` | память React, `AuthContext.user` | да | отображение UI, UI guard |
| JWT в `localStorage` / `sessionStorage` | нигде | — | проект так не делает |
| JWT в БД | нигде | — | в таблице `user` лежит `hashed_password`, не токен |
| секрет подписи | `settings.web.secret_key` | нет | подпись и проверка JWT |
| пароль | БД, хеш Argon2 | нет | вход |

---

## 10. Регистрация: почему после неё не залогинен

`POST /auth/register` (`get_register_router`) создаёт пользователя и возвращает `201` с
`UserRead` — **cookie не ставится**. Токен выдаёт только login-маршрут. Поэтому фронт после
успешной регистрации отправляет пользователя на `/login`:

```text
RegisterPage ──POST /auth/register──▶ 201 {id, email, username}
                                        │
                                        └─ токена нет → navigate('/login')
```

Пароль при регистрации хешируется (`UserManager` → `pwdlib`/Argon2), в БД попадает только
хеш. `username` выводится из email автоматически в `UserManager.on_after_register()`.

---

## 11. Чего в этой схеме нет (и что из этого следует)

| Чего нет | Следствие | Где описано |
|---|---|---|
| отзыва JWT | logout удаляет cookie, но скопированный токен валлиден до `exp` или смены `secret_key` | `docs/05_authorization_upgrade.md` §4 |
| `CORS` | годится для same-origin; другому origin не отдаст ни ответ, ни cookie | §1, §2 того же документа |
| CSRF-защиты | `SameSite=Lax` закрывает часть сценариев, но не все | §1 |
| `Secure` cookie | `cookie_secure=false` — только для локального HTTP; в проде обязательно `true` | §1 |
| refresh-токена | при истечении `86400` с пользователь просто становится анонимом (`/users/me` → 401) | — |
| email verification / reset password | маршруты не подключены | §2 |

Главный практический вывод под будущее отдельное приложение: cookie-схема хороша ровно
для same-origin браузерного клиента. Для клиента на другом домене или не-браузерного
(мобильное, CLI, сервер-сервер) нужен другой транспорт — `Authorization: Bearer <JWT>`,
и `fastapi-users` умеет держать оба одновременно. Разбор вариантов, сравнительная таблица
и рецепт выбора — [`docs/08_jwt_transport_options.md`](08_jwt_transport_options.md).
