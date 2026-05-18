"""Generic YonSuite API tool.

Loads the YonSuiteClient from agent/yonsuite_client/, providing a single
generic interface for direct YonSuite API calls.
"""

import json
import logging

from agent.tools.registry import registry, tool_result, tool_error

logger = logging.getLogger(__name__)

_ys_client = None


def _get_client():
    global _ys_client
    if _ys_client is not None:
        return _ys_client
    try:
        from agent.yonsuite_client.config import config as ys_config
        if not ys_config.is_configured():
            return None
        from agent.yonsuite_client.ys_client import YonSuiteClient
        _ys_client = YonSuiteClient()
        return _ys_client
    except Exception as e:
        logger.warning("YonSuite client init failed: %s", e)
        return None


# Methods exposed via the generic tool — same names as YonSuiteClient methods.
_ALLOWED_METHODS = frozenset({
    "query_sale_orders",
    "get_order_detail",
    "query_purchase_orders",
    "get_purchase_order_detail",
    "query_current_stock",
    "query_products",
    "query_customers",
    "query_vendors",
    "get_vendor_detail",
    "query_production_orders",
    "get_production_order_detail",
    "query_accbooks",
    "query_vouchers",
    "query_user_todos",
    "query_opportunities",
    "get_org_detail",
    "query_org_units",
    "format_order_info",
    "format_stock_info",
    "format_todo_info",
    "format_production_order_info",
    "format_org_unit_info",
})


def _format_response(result) -> str:
    """Safely format API response to JSON string."""
    if isinstance(result, str):
        if result.startswith("{"):
            return result
        return json.dumps({"data": result}, ensure_ascii=False)
    try:
        return json.dumps(result, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(result)


def _handle_connection_check() -> str:
    """Test YonSuite API connection."""
    client = _get_client()
    if client is None:
        return tool_result(
            data="YonSuite 连接测试",
            connected=False,
            message="配置不完整，请在设置中配置 App Key、App Secret、Tenant ID",
        )

    try:
        token = client.get_access_token()
        return tool_result(
            data="YonSuite 连接成功",
            connected=True,
            message="Token 获取成功",
        )
    except Exception as e:
        return tool_result(
            data="YonSuite 连接失败",
            connected=False,
            message=str(e),
        )


def _handle_ys_api(args: dict) -> str:
    """Execute a YonSuite API call."""
    method = args.get("method", "")
    params = args.get("params", {}) or {}

    if not method:
        return tool_error("method (API 方法名) 是必需的")

    if method == "connection_check":
        return _handle_connection_check()

    if method not in _ALLOWED_METHODS:
        supported = ", ".join(sorted(_ALLOWED_METHODS))
        return tool_error(f"未知方法: {method}，支持的方法: {supported}")

    client = _get_client()
    if client is None:
        return tool_error(
            "YonSuite 未配置，请在设置中配置 App Key、App Secret 和 Tenant ID"
        )

    try:
        func = getattr(client, method)
        result = func(**params)
        return _format_response(result)
    except Exception as e:
        logger.exception("YonSuite API 调用失败: %s", method)
        return tool_error(f"API 调用失败: {e}")


# ── Schema ─────────────────────────────────────────────────────────────────


YS_API_SCHEMA = {
    "name": "ys_api",
    "description": (
        "执行 YonSuite API 调用。支持查询销售订单、采购订单、客户、供应商、"
        "库存、生产订单、物料、凭证、待办、商机、组织等业务数据。"
        "使用方式: ys_api(method='query_sale_orders', params={'page_index': 1, 'page_size': 20})。"
        "详细的方法名和参数说明请参考 YonSuite 技能的完整指令。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "description": (
                    "API 方法名。常用方法: query_sale_orders (销售订单列表), "
                    "get_order_detail (销售订单详情, 需传 order_id), "
                    "query_purchase_orders (采购订单), "
                    "get_purchase_order_detail (采购订单详情), "
                    "query_current_stock (库存现存量), "
                    "query_products (物料档案, 支持 product_code/product_name 过滤), "
                    "query_customers (客户), query_vendors (供应商), "
                    "get_vendor_detail (供应商详情), "
                    "query_production_orders (生产订单), "
                    "get_production_order_detail (生产订单详情), "
                    "query_vouchers (凭证), query_user_todos (待办), "
                    "query_opportunities (商机), query_accbooks (账簿), "
                    "get_org_detail (组织详情), "
                    "connection_check (连接测试)"
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "方法参数（键值对）。通用参数: page_index (页码, 默认1), "
                    "page_size (每页条数, 默认20-500)。部分方法特有参数: "
                    "order_id (单据ID, 详情查询), "
                    "product_code/product_name (物料查询过滤), "
                    "date_from/date_to (日期过滤, 格式 YYYY-MM-DD)。"
                    "具体参数说明见 YonSuite 技能文档。"
                ),
            },
        },
        "required": ["method"],
    },
}

registry.register(
    name="ys_api",
    toolset="yonsuite",
    schema=YS_API_SCHEMA,
    handler=_handle_ys_api,
    emoji="📊",
)
