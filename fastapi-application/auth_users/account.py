"""
POST /auth/account — обновление username/email авторизованным пользователем.

Использует те же helpers, что и register-flow (валидация email, уникальность
username/email, единый 422-формат ошибок). Отличие от md_articles
— опирается на active_user из fastapi_users_obj и обновляет уже существующего
current_user (без создания нового).

Возвращает {message, category, user} в формате, привычном фронтенду блога.
"""

from db_core.db_async import CurrentSession
from fastapi import APIRouter, Depends, Form

from auth_users.fastapi_users_obj import active_user
from auth_users.helpers import (
    ERROR_EMAIL_TAKEN,
    ERROR_USERNAME_TAKEN,
    email_exists,
    is_valid_email,
    username_exists,
    validation_response,
)
from auth_users.models import User

router = APIRouter(tags=["auth-account"], prefix="/auth")


@router.post("/account", name="auth.account_post")
async def account_post(
    session: CurrentSession,
    current_user: User = Depends(active_user),  # noqa: B008
    username: str = Form(""),
    email: str = Form(""),
):
    errors: dict[str, list[str]] = {}
    username = username.strip()
    email = email.strip()
    if not username:
        errors.setdefault("username", []).append("This field is required.")
    elif len(username) < 2 or len(username) > 20:
        errors.setdefault("username", []).append("Field must be between 2 and 20 characters long.")
    if not email:
        errors.setdefault("email", []).append("This field is required.")
    elif not is_valid_email(email):
        errors.setdefault("email", []).append("Invalid email address.")
    if username and username != current_user.username and await username_exists(session, username):
        errors.setdefault("username", []).append(ERROR_USERNAME_TAKEN)
    if email and email != current_user.email and await email_exists(session, email):
        errors.setdefault("email", []).append(ERROR_EMAIL_TAKEN)
    if errors:
        return validation_response(errors)
    current_user.username = username
    current_user.email = email
    await session.commit()
    return {
        "message": "Your account has been updated!",
        "category": "success",
        "user": {
            "id": str(current_user.id),
            "username": current_user.username,
            "email": current_user.email,
            "is_active": current_user.is_active,
            "is_superuser": current_user.is_superuser,
            "is_verified": current_user.is_verified,
        },
    }
