from typing import Annotated

from fastapi import (
    Header,
    HTTPException,
    status,
)
from pydantic import BaseModel


class TokenData(BaseModel):
    id: int
    username: str


class TokenIntrospectResult(BaseModel):
    result: TokenData


class HeaderAccessDependency:
    def __init__(self, secret_token: str) -> None:
        self.secret_token = secret_token

    def validate(self, token: str) -> TokenIntrospectResult:
        if token != self.secret_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is invalid",
            )

        return TokenIntrospectResult(result=TokenData(id=42, username="john_smith"))

    def __call__(
        self,
        token: Annotated[str, Header(alias="x-access-token")],
    ) -> TokenIntrospectResult:
        token_data = self.validate(token=token)
        return token_data


access_required = HeaderAccessDependency(secret_token="foo-bar-fizz-buzz")
