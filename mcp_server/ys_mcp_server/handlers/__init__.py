"""Handler registry: each module exports `schema` (dict) and `handle(client, arguments) -> dict`."""

from . import ys_api
from . import sale_orders
from . import purchase_orders
from . import production_orders
from . import stock
from . import user_todos
from . import opportunities
from . import products
from . import customers
from . import vendors
from . import vouchers

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
