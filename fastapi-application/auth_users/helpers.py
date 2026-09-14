"""
Вспомогательные функции для слоя авторизации fastapi-users.

Содержит проверки email, уникальности username/email и стандартный
422-ответ с ошибками для форм авторизации.
"""

from db_core.db_async import CurrentSession
from fastapi.responses import JSONResponse
from pydantic import EmailStr
from sqlalchemy import select

from auth_users.models import User


# ==============================================================================
# +++++++++++++++++++++++++++++ auth helpers +++++++++++++++++++++++++++++++++++
# ------------------------------------------------------------------------------
def is_valid_email(email: str) -> bool:
    try:
        EmailStr._validate(email)  # type: ignore[attr-defined]
        return True
    except (TypeError, ValueError):
        return False


async def username_exists(session: CurrentSession, username: str) -> bool:
    """SELECT 1 FROM user WHERE username = ?."""
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none() is not None


async def email_exists(session: CurrentSession, email: str) -> bool:
    """SELECT 1 FROM user WHERE email = ?."""
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none() is not None


# ==============================================================================
# ++++++++++++++++++++++++++++++ validation handler ++++++++++++++++++++++++++++
# ------------------------------------------------------------------------------
ERROR_EMAIL_TAKEN = "That email is taken. Please choose a different one."
ERROR_USERNAME_TAKEN = "That username is taken. Please choose a different one."


def validation_response(errors: dict[str, list[str]]) -> JSONResponse:
    """Стандартный ответ 422 с errors для форм фронтенда."""
    return JSONResponse(status_code=422, content={"errors": errors})
