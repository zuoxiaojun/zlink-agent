from .customer import QUERIES as CUST_QUERIES
from .material import QUERIES as MAT_QUERIES
from .organization import QUERIES as ORG_QUERIES
from .purchase_order import QUERIES as PO_QUERIES
from .sales_order import QUERIES as SO_QUERIES
from .supplier import QUERIES as SUPP_QUERIES

QUERIES = {**SO_QUERIES, **PO_QUERIES, **CUST_QUERIES, **SUPP_QUERIES, **MAT_QUERIES, **ORG_QUERIES}

__all__ = ["QUERIES"]
