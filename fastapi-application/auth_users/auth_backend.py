"""
Бэкенды аутентификации fastapi-users: CookieTransport и BearerTransport + JWTStrategy.

Два backend'а для двух типов клиентов:
- `cookie_backend` (jwt-cookie) — для браузера: JWT в cookie, автоматическая
  передача React SPA;
- `bearer_backend` (jwt-bearer) — для не-браузерных клиентов (CLI, мобильные,
  server-to-server): JSON {"access_token": ..., "token_type": "bearer"} на
  /auth/bearer/login, далее заголовок Authorization: Bearer <token>.

Оба используют единый `get_jwt_strategy` — JWT payload идентичен (sub, exp).
Все параметры читаются из settings.auth_users (см. core/config.py::AuthUsersConfig).
Секрет JWT — settings.web.secret_key (общий секретный ключ проекта).
"""

from core.config import settings
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
)
from fastapi_users.authentication.strategy import JWTStrategy

cookie_transport = CookieTransport(
    cookie_name=settings.auth_users.cookie_name,
    cookie_max_age=settings.auth_users.cookie_max_age,
    cookie_secure=settings.auth_users.cookie_secure,
    cookie_httponly=settings.auth_users.cookie_httponly,
    cookie_samesite=settings.auth_users.cookie_samesite,
)

bearer_transport = BearerTransport(tokenUrl="/auth/bearer/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.web.secret_key,
        lifetime_seconds=settings.auth_users.jwt_lifetime_seconds,
        algorithm=settings.auth_users.jwt_algorithm,
    )


cookie_backend = AuthenticationBackend(
    name="jwt-cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

bearer_backend = AuthenticationBackend(
    name="jwt-bearer",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# Alias для обратной совместимости: auth_users/__init__.py реэкспортирует auth_backend.
auth_backend = cookie_backend
