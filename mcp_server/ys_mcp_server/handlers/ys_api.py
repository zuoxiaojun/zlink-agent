"""YonSuite generic API gateway."""

from ..utils import get_client, tool_result, tool_error

ALLOWED_METHODS = frozenset({
    "query_sale_orders", "get_order_detail", "query_purchase_orders",
    "get_purchase_order_detail", "query_current_stock", "query_products",
    "query_customers", "query_vendors", "get_vendor_detail",
    "query_production_orders", "get_production_order_detail",
    "query_accbooks", "query_vouchers", "query_user_todos",
    "query_opportunities", "get_org_detail", "query_org_units",
    "format_order_info", "format_stock_info", "format_todo_info",
    "format_production_order_info", "format_org_unit_info",
})

schema = {
    "name": "ys_api",
    "description": "执行 YonSuite API 调用。支持查询销售订单、采购订单、客户、供应商、库存、生产订单、物料、凭证、待办、商机、组织等业务数据。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "description": "API 方法名。常用: query_sale_orders, get_order_detail, query_purchase_orders, get_purchase_order_detail, query_current_stock, query_products, query_customers, query_vendors, get_vendor_detail, query_production_orders, get_production_order_detail, query_vouchers, query_user_todos, query_opportunities, query_accbooks, get_org_detail, connection_check",
            },
            "params": {
                "type": "object",
                "description": "方法参数。通用参数: page_index(页码,默认1), page_size(每页条数,默认20-500)。部分方法特有: order_id, product_code, product_name, date_from, date_to(格式YYYY-MM-DD)等。",
            },
        },
        "required": ["method"],
    },
}


def handle(client, arguments: dict) -> dict:
    method = arguments.get("method", "")
    params = arguments.get("params", {}) or {}

    if method == "connection_check":
        if client is None:
            return tool_error("YonSuite 未配置，请在设置中配置 App Key、App Secret、Tenant ID")
        try:
            client.get_access_token()
            return tool_result(data="YonSuite 连接成功", connected=True)
        except Exception as e:
            return tool_result(data="YonSuite 连接失败", connected=False, message=str(e))

    if method not in ALLOWED_METHODS:
        return tool_error(f"未知方法: {method}")

    if client is None:
        return tool_error("YonSuite 未配置")

    try:
        func = getattr(client, method)
        result = func(**params)
        if isinstance(result, str):
            if result.startswith("{"):
                return tool_result(data=json.loads(result))
            return tool_result(data=result)
        return tool_result(data=result)
    except Exception as e:
        return tool_error(f"API 调用失败: {e}")


import json
