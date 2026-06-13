"""Handler registry: each module exports `schema` (dict) and `handle(client, arguments) -> dict`."""

from . import (
    customers,
    opportunities,
    production_orders,
    products,
    purchase_orders,
    sale_orders,
    stock,
    user_todos,
    vendors,
    vouchers,
    ys_api,
)

ALL_HANDLERS = [
    ys_api,
    sale_orders,
    purchase_orders,
    production_orders,
    stock,
    user_todos,
    opportunities,
    products,
    customers,
    vendors,
    vouchers,
]
