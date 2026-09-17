from collections.abc import Sequence
from typing import Annotated

from config_log import logF
from core.config import settings
from db_core.db_async import CurrentSession
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Row
from sqlalchemy.engine import Result
from sqlalchemy.orm import InstrumentedAttribute, joinedload
from sqlalchemy.sql import Insert, Select, insert, select
from starlette import status

from .model_order_product import (
    Order,
    Product,
)
from .schema_order_product import (
    OrderCreateBody,
    OrderGetAllOrderbyQuery,
    OrderGetQuery,
    OrderResp,
    OrderRespWithProducts,
)

r_order_one = APIRouter(
    prefix=settings.api.order_product_prefix,
    tags=["Examples - Order - add get joinedload"],
)


# =============================================================== #
#                           added Order                           #
# =============================================================== #
@r_order_one.post("/add_order", response_model=OrderResp)
async def add_order(body: OrderCreateBody, db: CurrentSession):
    new_order: Order = Order(**body.model_dump())
    db.add(new_order)

    await db.commit()
    await db.refresh(new_order)

    return new_order


@r_order_one.post("/insert_order", response_model=OrderCreateBody)
async def insert_order(db: CurrentSession, body: OrderCreateBody):
    stmt: Insert[Order] = insert(Order).values(**body.model_dump())

    await db.execute(stmt)
    await db.commit()

    return body


# ==================================================================== #
#                    get Orders - with condition                       #
# ==================================================================== #
@r_order_one.get("/get_order_filter_by", response_model=OrderResp)
async def get_order_filter_by(db: CurrentSession, params: Annotated[OrderGetQuery, Depends()]):
    # stmt: Select[tuple[Order]] = select(Order).filter_by(id=22)
    filter_where = {key: value for key, value in params.model_dump().items() if value is not None}

    stmt: Select[tuple[Order]] = select(Order).filter_by(**filter_where)

    result: Result[tuple[Order]] = await db.execute(stmt)

    order: Order = result.scalar()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Order with {filter_where} not found",
        )
    return order


@r_order_one.get("/get_order_where", response_model=OrderResp | list[OrderResp])
async def get_order_where(db: CurrentSession, params: Annotated[OrderGetQuery, Depends()]):
    # stmt = select(Order).where(Order.id == 22)
    filter_where = [
        getattr(Order, key) == value for key, value in params.model_dump(exclude_none=True).items()
    ]

    stmt: Select[tuple[Order]] = select(Order).where(*filter_where)

    result: Result[tuple[Order]] = await db.execute(stmt)

    # orders: Order = result.scalar()
    # orders: Order = result.scalars().first()
    orders: Sequence[Order] = result.scalars().all()

    if not orders:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Orders with {filter_where} not found",
        )
    return orders


# ======================================================================= #
#                      get all Orders - order_by                          #
# ======================================================================= #
@r_order_one.get("/get_all_orders", response_model=list[OrderResp])
async def get_all_orders(db: CurrentSession, params: OrderGetAllOrderbyQuery):
    if params == "time":
        order_by_list_o: list[InstrumentedAttribute] = [Order.created_at, Order.id]
    elif params == "promocode":
        order_by_list_o: list[InstrumentedAttribute] = [Order.promocode, Order.created_at]
    else:
        order_by_list_o: list[InstrumentedAttribute] = [Order.id, Order.created_at]

    logF.info(f"get_all_orders : {type(order_by_list_o)=}\n{order_by_list_o=}")

    stmt: Select[tuple[Order]] = select(Order).order_by(*order_by_list_o)

    await_result_execute: Result[tuple[Order]] = await db.execute(stmt)
    result_scalars_all: Sequence[Order] = await_result_execute.scalars().all()

    return result_scalars_all


# ===================================================================== #
#                get all Orders with join Order.products                #
# ===================================================================== #
@r_order_one.get("/get_all_join", response_model=list[OrderRespWithProducts])
async def get_all_join(db: CurrentSession, variant: int = 1):
    stmt: Select[tuple[Order]] = (
        select(Order)
        .order_by(Order.id)
        # .options(selectinload(Order.products))
        .options(joinedload(Order.products))
    )
    await_result_execute: Result[tuple[Order]] = await db.execute(stmt)

    result_scalars_all: Sequence[Order] = []
    if variant == 1:
        result_scalars_all: Sequence[Order] = await_result_execute.unique().scalars().all()
        order0: Order = result_scalars_all[0]
        order1: Order = result_scalars_all[1]
    else:
        result_all: Sequence[Row[tuple[Order]]] = await_result_execute.unique().all()
        row0: Row[tuple[Order]] = result_all[0]
        order0: Order = row0[0]
        row1: Row[tuple[Order]] = result_all[1]
        order1: Order = row1[0]

    prods0: list[Product] = order0.products
    prods1: list[Product] = order1.products

    logF.info(f"get_all_join : \n{order0=}\n{prods0=}")
    logF.info(f"get_all_join : \n{order1=}\n{prods1=}")

    return result_scalars_all
