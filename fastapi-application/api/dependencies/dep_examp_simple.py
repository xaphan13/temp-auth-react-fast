from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
)

from .helper import get_header_dependency

router_dep_simple = APIRouter()


@router_dep_simple.get("/single-direct-dependency")
def single_direct_dependency(foobar: Annotated[str, Header()]):
    return {
        "foobar": foobar,
        "message": "single direct dependency foobar",
    }


def get_x_foo_bar(foobar: Annotated[str, Header(alias="x-foo-bar")] = "") -> str:
    return foobar


@router_dep_simple.get("/single-via-func")
def single_via_func(foobar: Annotated[str, Depends(get_x_foo_bar)]):
    return {
        "x-foo-bar": foobar,
        "message": "single via-func dependency foobar",
    }


@router_dep_simple.get("/multi-direct-and-via-func")
def multi_direct_and_via_func(
    foobar: Annotated[str, Depends(get_x_foo_bar)],
    fizzbuzz: Annotated[str, Header(alias="x-fizz-buzz")],
):
    return {
        "x-foo-bar": foobar,
        "x-fizz-buzz": fizzbuzz,
        "message": "multi-direct and-via-func dependency foobar",
    }


@router_dep_simple.get("/multi-indirect")
def multi_indirect_dependencies(
    foobar: Annotated[str, Depends(get_header_dependency("x-foo-bar"))],
    fizzbuzz: Annotated[
        str, Depends(get_header_dependency("x-fizz-buzz", default_value="FizzBuzz"))
    ],
):
    return {
        "x-foo-bar": foobar,
        "x-fizz-buzz": fizzbuzz,
        "message": "multi-indirect dependency",
    }
