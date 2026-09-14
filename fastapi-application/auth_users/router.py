"""
Сборный роутер auth_users: login/logout + register + /users/me + /auth/account.

Покрывает:
- /auth/jwt/login, /auth/jwt/logout        (FastAPIUsers.get_auth_router)
- /auth/register                           (FastAPIUsers.get_register_router)
- /users/me (GET/PATCH)                    (FastAPIUsers.get_users_router)
- POST /auth/account                       (account.py)
- /api/v1/auth/protected                   (проверка active_user)

Сигнатура fastapi-users 15.x: методы FastAPIUsers сами подставляют
self.get_user_manager и self.authenticator — явно передавать не нужно.
"""

from typing import Annotated

from core.config import settings
from fastapi import APIRouter, Depends

from auth_users.account import router as account_router
from auth_users.auth_backend import auth_backend
from auth_users.fastapi_users_obj import active_user, fastapi_users
from auth_users.models import User
from auth_users.schemas import UserCreate, UserRead, UserUpdate

auth_router = fastapi_users.get_auth_router(auth_backend)
register_router = fastapi_users.get_register_router(UserRead, UserCreate)
users_router = fastapi_users.get_users_router(UserRead, UserUpdate)
users_router.routes = [route for route in users_router.routes if route.path == "/me"]

protected_router = APIRouter(prefix=f"{settings.api.prefix}{settings.api.v1.prefix}/auth")


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
