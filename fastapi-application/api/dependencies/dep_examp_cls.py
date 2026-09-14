from typing import Annotated

from fastapi import APIRouter, Depends

from .cls_deps import (
    TokenIntrospectResult,
    access_required,
)

from .helper import GreatHelper, GreatService, get_great_helper

router_dep_cls = APIRouter()


@router_dep_cls.get("/helper-as-dependency")
def helper_as_dependency(
    helper: Annotated[
        GreatHelper,
        Depends(get_great_helper),
    ],
):
    return {
        "helper": helper.as_dict(),
        "message": "helper-as-dependency",
    }


@router_dep_cls.get("/great-service-as-dependency")
def get_great_service_dependency(
    service: Annotated[
        GreatService,
        Depends(GreatService),
    ],
):
    return {
        "service": service.as_dict(),
        "message": "great-service-as-dependency",
    }


@router_dep_cls.get("/direct-cls-dependency")
def direct_cls_dependency(
    token_data: Annotated[
        TokenIntrospectResult,
        # Depends(HeaderAccessDependency(secret_token="qwerty-abc")),
        Depends(access_required),
    ],
):
    return {
        "token_data": token_data.model_dump(),
        "message": "direct-cls-dependency",
    }
