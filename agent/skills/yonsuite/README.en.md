# yonsuite-skill

A Python skill library for querying business data from Yonyou YonSuite system.

## Overview

yonsuite-skill is a Python library designed to connect to and query data from the Yonyou YonSuite system, supporting queries and analysis of business data including sales orders, purchase orders, production orders, inventory, customers, vendors, products, organizational structure, accounting vouchers, pending tasks, and CRM opportunities.

## Features

- **Sales Management**: Query sales order lists, order details, and batch queries
- **Procurement Management**: Query purchase order lists and order details
- **Production Management**: Query production order lists, order details, and batch queries (including processes, materials, and by-products)
- **Inventory Management**: Real-time inventory query
- **Customer Management**: Query customer profiles and batch query customer details
- **Vendor Management**: Query vendor lists, vendor details, and batch queries
- **Product Management**: Query product profiles
- **Organizational Structure**: Query organizational details and organizational units
- **Financial Management**: Query accounting ledgers and accounting vouchers
- **Pending Tasks Center**: Query user pending tasks
- **CRM Opportunities**: Query opportunity lists and filter by opportunity status

## Environment Requirements

- Python 3.8+
- Dependencies listed in `requirements.txt`

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root directory and configure the following parameters:

```env
YONSUITE_APP_KEY=your_app_key
YONSUITE_APP_SECRET=your_app_secret
YONSUITE_TENANT_ID=your_tenant_id
YONSUITE_GATEWAY_URL=https://gateway.yonyou.com
```

Or configure via environment variables:

```bash
export YONSUITE_APP_KEY=your_app_key
export YONSUITE_APP_SECRET=your_app_secret
export YONSUITE_TENANT_ID=your_tenant_id
export YONSUITE_GATEWAY_URL=https://gateway.yonyou.com
```

## Quick Start

### Basic Usage

```python
from ys_client import YonSuiteClient

# Initialize client (automatically reads configuration)
client = YonSuiteClient()

# Query sales orders
orders = client.query_sale_orders(page_index=1, page_size=500)
print(orders)

# Query purchase orders
purchase_orders = client.query_purchase_orders(page_index=1, page_size=500)

# Query inventory
stock = client.query_current_stock(page_index=1, page_size=500)

# Query customers
customers = client.query_customers(page_index=1, page_size=500)

# Query vendors
vendors = client.query_vendors(page_index=1, page_size=500)

# Query production orders
production_orders = client.query_production_orders(page_index=1, page_size=500)
```

### Query Order Details

```python
# Sales order detail
order_detail = client.get_order_detail(order_id="order_id")

# Purchase order detail
purchase_detail = client.get_purchase_order_detail(order_id="order_id")

# Production order detail
production_detail = client.get_production_order_detail(order_id="order_id")
```

### Batch Queries

```python
# Batch query customer details
customer_list = [{"id": "customer_id1"}, {"id": "customer_id2"}]
customer_details = client.query_customer_details_batch(customer_list)

# Batch query vendors
vendor_ids = ["vendor_id1", "vendor_id2"]
vendors = client.query_vendors_batch(client.cache.get("access_token"), vendor_ids)

# Batch query production orders (supports processes, materials, and by-products)
order_ids = ["order_id1", "order_id2"]
production_orders = client.query_production_orders_batch(
    order_ids,
    show_process=True,    # Include processes
    show_material=True,   # Include materials
    show_by_product=True  # Include by-products
)
```

### Query Pending Tasks

```python
# Query user pending tasks
todos = client.query_user_todos(page_no=1, page_size=10)
todos_parsed = client.query_user_todos_parsed(page_no=1, page_size=10)

# Format output
todo_info = client.format_todo_info(todos_parsed)
print(todo_info)
```

### Query CRM Opportunities

```python
# Query opportunity list
opportunities = client.query_opportunities(
    page_index=1,
    page_size=500,
    is_sum=True  # Aggregate data
)

# Query ongoing opportunities
opportunities = client.query_opportunities(
    oppt_state="0",  # Ongoing
    is_sum=True
)

# Query won opportunities
opportunities = client.query_opportunities(
    win_lose_state="0",  # Won
    is_sum=True
)
```

### Query Accounting Vouchers

```python
# Query accounting ledgers
accbooks = client.query_accbooks()

# Query vouchers
vouchers = client.query_vouchers(
    page_index=1,
    page_size=20,
    voucher_date_start="2024-01-01",
    voucher_date_end="2024-12-31"
)
```

## Data Models

The project includes comprehensive data model classes:

- `SaleOrder` - Sales Order
- `SaleOrderDetail` - Sales Order Detail
- `PurchaseOrder` - Purchase Order
- `ProductionOrder` - Production Order
- `ProductionOrderDetail` - Production Order Detail (includes processes and materials)
- `Customer` - Customer
- `Vendor` / `VendorDetail` - Vendor
- `StockItem` - Inventory Item
- `ProductItem` - Product
- `TodoItem` - Pending Task
- `Opportunity` - Opportunity

## Query Scripts

The project provides ready-to-run query scripts:

```bash
# Query sales orders and export
python query_sale_orders_to_sheet.py

# Query purchase orders and export
python query_purchase_orders_to_sheet.py

# Query production orders and export
python query_production_orders_to_sheet.py

# Query production order details and export
python query_production_orders_detail_to_sheet.py

# Query inventory and export
python query_stock_to_sheet.py
```

## Error Handling

The project defines comprehensive exception classes:

```python
from exceptions import (
    YonSuiteError,
    YonSuiteConfigError,
    YonSuiteAuthError,
    YonSuiteAPIError,
    YonSuiteNotFoundError,
    YonSuitePermissionError,
    YonSuiteRateLimitError,
    YonSuiteDataError,
    YonSuiteNetworkError,
    YonSuiteCacheError
)

try:
    orders = client.query_sale_orders()
except YonSuiteAuthError as e:
    print(f"Authentication failed: {e}")
except YonSuiteAPIError as e:
    print(f"API error: {e}, Error code: {e.error_code}")
except YonSuiteRateLimitError as e:
    print(f"Rate limit exceeded, retry after: {e.retry_after} seconds")
```

## Field Documentation

Detailed field descriptions are available in:

- `docs/sale_order_list_fields.md` - Sales Order Fields
- `docs/purchase_order_list_fields.md` - Purchase Order Fields
- `docs/production_order_detail_fields.md` - Production Order Detail Fields

## Example Code

For more usage examples, see the `examples/` directory:

- `basic_usage.py` - Basic usage example
- `advanced_usage.py` - Advanced usage example
- `new_features_demo.py` - New features demonstration

## Notes

1. **Token Caching**: Token caching is enabled by default; cache expiration is determined by the server's `expire_in` response.
2. **Date Format**: When filtering by date, use the format `YYYY-MM-DD`.
3. **Master-Child Structure**: Order data uses a master-child structure; detail queries retrieve child table information (e.g., material lines).
4. **Batch Queries**: Batch queries significantly improve efficiency; recommended for large datasets.

## License

MIT License

## Changelog

See `CHANGELOG.md`