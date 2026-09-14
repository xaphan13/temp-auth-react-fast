"""
Pydantic-схемы fastapi-users для User.

UserRead — то, что вернёт /api/v1/users/me и остальные роуты fastapi-users.
Наследует id/email/is_active/is_verified от schemas.BaseUser[UUID] и добавляет
наше поле username.

UserCreate / UserUpdate — без полей: fastapi-users сам проверит email/password.
Валидация username — на уровне UserManager.on_after_register и
helpers (см. user_manager.py / helpers.py).
"""

from uuid import UUID

from fastapi_users import schemas


class UserRead(schemas.BaseUser[UUID]):
    username: str


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass
