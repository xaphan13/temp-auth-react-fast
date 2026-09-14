from typing import Annotated

from fastapi import Header, Depends


def get_header_dependency(header_name: str, default_value: str = ""):
    def dependency(header: Annotated[str, Header(alias=header_name)] = default_value) -> str:
        return header

    return dependency


class BaseGreat:
    name: str
    default: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "default": self.default}


class GreatHelper(BaseGreat):
    def __init__(self, name: str, default: str) -> None:
        self.name = name
        self.default = default


def get_great_helper(
    helper_name: Annotated[
        str,
        Depends(get_header_dependency("x-helper-name")),
    ],
    helper_default: Annotated[
        str,
        Depends(get_header_dependency("x-helper-default-value")),
    ],
) -> GreatHelper:
    helper = GreatHelper(name=helper_name, default=helper_default)
    return helper


class GreatService(BaseGreat):
    def __init__(
        self,
        name: Annotated[str, Header(alias="x-great-service-name")],
        default: Annotated[str, Header(alias="x-great-service-default-value")],
    ) -> None:
        self.name = name
        self.default = default
