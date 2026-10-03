"""
Сборный роутер auth_users: login/logout + register + /users/me + /auth/account.

Покрывает:
- /auth/cookie/login, /auth/cookie/logout      (cookie_backend, браузер)
- /auth/bearer/login, /auth/bearer/logout      (bearer_backend, не-браузерные клиенты)
- /auth/register                               (FastAPIUsers.get_register_router)
- /users/me (GET/PATCH)                        (FastAPIUsers.get_users_router)
- POST /auth/account                           (account.py)
- /api/v1/auth/protected                       (проверка active_user)

Сигнатура fastapi-users 15.x: методы FastAPIUsers сами подставляют
self.get_user_manager и self.authenticator — явно передавать не нужно.
"""

from typing import Annotated

from config_log import logF
from core.config import settings
from fastapi import APIRouter, Depends

from auth_users.account import router as account_router
from auth_users.auth_backend import bearer_backend, cookie_backend
from auth_users.fastapi_users_obj import active_user, fastapi_users
from auth_users.models import User
from auth_users.schemas import UserCreate, UserRead, UserUpdate

cookie_auth_router = fastapi_users.get_auth_router(cookie_backend)
bearer_auth_router = fastapi_users.get_auth_router(bearer_backend)
register_router = fastapi_users.get_register_router(UserRead, UserCreate)
users_router = fastapi_users.get_users_router(UserRead, UserUpdate)
users_router.routes = [route for route in users_router.routes if route.path == "/me"]

protected_router = APIRouter(prefix=f"{settings.api.prefix}{settings.api.v1.prefix}/auth")


@protected_router.get("/protected", tags=["auth"])
async def protected(user: Annotated[User, Depends(active_user)]):
    # Факт входа в protected логируется в самом обработчике: dependency уже
    # прошла аутентификацию, при успехе известен user.id. Секретов не пишем.
    logF.info("auth protected: authenticated user_id=%s", user.id)
    return {
        "authenticated": True,
        "user": UserRead.model_validate(user),
    }


router = APIRouter()
router.include_router(cookie_auth_router, prefix="/auth/cookie", tags=["auth-cookie"])
router.include_router(bearer_auth_router, prefix="/auth/bearer", tags=["auth-bearer"])
router.include_router(register_router, prefix="/auth", tags=["auth-register"])
router.include_router(users_router, prefix="/users", tags=["users"])
router.include_router(account_router)
router.include_router(protected_router)
