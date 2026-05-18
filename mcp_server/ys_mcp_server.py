#!/usr/bin/env python3
"""YonSuite MCP server — JSON-RPC 2.0 over stdio.

Exposes 12 YonSuite tools (11 query tools + 1 generic API gateway).
Reads YonSuite credentials from data/config.json at startup.
"""

import json
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path for agent/ imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── Config loading ──────────────────────────────────────────────────────────

def _load_ys_config() -> dict:
    config_path = _PROJECT_ROOT / "data" / "config.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            cfg = {}
    else:
        cfg = {}

    # Inject into os.environ so yonsuite_client.Config picks them up
    for key, env_key in [
        ("ys_app_key", "YONSUITE_APP_KEY"),
        ("ys_app_secret", "YONSUITE_APP_SECRET"),
        ("ys_tenant_id", "YONSUITE_TENANT_ID"),
        ("ys_gateway_url", "YONSUITE_GATEWAY_URL"),
    ]:
        val = cfg.get(key, "")
        if val and not os.environ.get(env_key):
            os.environ[env_key] = val

    return cfg


_load_ys_config()


_ys_client = None


def _get_client():
    global _ys_client
    if _ys_client is not None:
        return _ys_client
    from agent.yonsuite_client.config import config as ys_config
    if not ys_config.is_configured():
        return None
    from agent.yonsuite_client.ys_client import YonSuiteClient
    _ys_client = YonSuiteClient()
    return _ys_client


# ── JSON-RPC ────────────────────────────────────────────────────────────────

def _rpc_result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _rpc_error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _send(msg: dict):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


# ── initialize ──────────────────────────────────────────────────────────────

def handle_initialize(req_id: int, params: dict):
    return _rpc_result(req_id, {
        "protocolVersion": "2024-11-05",
        "serverInfo": {"name": "ys-mcp-server", "version": "1.0.0"},
        "capabilities": {"tools": {}},
    })


# ── tools/list ──────────────────────────────────────────────────────────────

def _make_tool(name: str, description: str, properties: dict, required: list[str] | None = None):
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required or [],
        },
    }


def handle_tools_list(req_id: int):
    tools = [
        _make_tool(
            "ys_api",
            "执行 YonSuite API 调用。支持查询销售订单、采购订单、客户、供应商、库存、生产订单、物料、凭证、待办、商机、组织等业务数据。使用方式: method 参数指定方法名，params 传入具体参数。",
            {
                "method": {
                    "type": "string",
                    "description": "API 方法名。常用: query_sale_orders, get_order_detail, query_purchase_orders, get_purchase_order_detail, query_current_stock, query_products, query_customers, query_vendors, get_vendor_detail, query_production_orders, get_production_order_detail, query_vouchers, query_user_todos, query_opportunities, query_accbooks, get_org_detail, connection_check",
                },
                "params": {
                    "type": "object",
                    "description": "方法参数。通用参数: page_index(页码,默认1), page_size(每页条数,默认20-500)。部分方法特有: order_id, product_code, product_name, date_from, date_to(格式YYYY-MM-DD)等。",
                },
            },
            ["method"],
        ),
        _make_tool(
            "query_sale_orders",
            "查询 YonSuite 销售订单。返回已解析的 29 字段记录，含税额自动计算、状态中文映射、币种嵌套解析。is_sum=False 返回逐行明细（含物料详情），is_sum=True 返回按订单汇总。",
            {
                "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD（可选）"},
                "date_to": {"type": "string", "description": "截止日期 YYYY-MM-DD（可选）"},
                "is_sum": {"type": "boolean", "description": "是否汇总模式，默认 false"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        ),
        _make_tool(
            "query_purchase_orders",
            "查询 YonSuite 采购订单。返回已解析的 32 字段记录，含状态中文映射（到货/入库/发票状态）。支持日期过滤。",
            {
                "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "截止日期 YYYY-MM-DD"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        ),
        _make_tool(
            "query_production_orders",
            "查询 YonSuite 生产订单。返回已解析的 24 字段记录，含状态中文映射。date_from/date_to 在客户端侧过滤。",
            {
                "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD，客户端侧过滤"},
                "date_to": {"type": "string", "description": "截止日期 YYYY-MM-DD，客户端侧过滤"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        ),
        _make_tool(
            "query_stock",
            "查询 YonSuite 库存现存量。按仓库+SKU 聚合同物料不同批次的数据。支持按物料ID精确查询。",
            {
                "warehouse": {"type": "string", "description": "仓库名称模糊匹配（可选）"},
                "sku": {"type": "string", "description": "SKU 编码或物料编码模糊匹配（可选）"},
                "product_id": {"type": "string", "description": "物料ID精确查询（推荐！从 query_products 结果中获取 id 字段），支持逗号分隔多个ID"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        ),
        _make_tool(
            "query_user_todos",
            "查询 YonSuite 用户待办事项。返回已解析的待办列表，含 richText 清洗、单据类型自动映射。",
            {
                "page_no": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
                "page_size": {"type": "integer", "description": "每页条数，默认 50"},
            },
        ),
        _make_tool(
            "query_opportunities",
            "查询 YonSuite CRM 商机列表。返回已解析的商机记录，自动处理金额字段选择。",
            {
                "oppt_state": {"type": "string", "description": "商机状态：0-进行中, 1-暂停, 2-作废, 3-关闭"},
                "win_lose_state": {"type": "string", "description": "赢丢单状态：0-赢单, 1-丢单, 2-未定, 3-部分赢单"},
                "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "截止日期 YYYY-MM-DD"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        ),
        _make_tool(
            "query_products",
            "查询 YonSuite 物料档案。支持按物料编码（精确）或物料名称（模糊）搜索。",
            {
                "product_code": {"type": "string", "description": "物料编码（精确匹配）"},
                "product_name": {"type": "string", "description": "物料名称（模糊匹配）"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        ),
        _make_tool(
            "query_customers",
            "查询 YonSuite 客户档案。支持按客户名称模糊搜索。",
            {
                "customer_name": {"type": "string", "description": "客户名称（模糊匹配）"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        ),
        _make_tool(
            "query_vendors",
            "查询 YonSuite 供应商档案。支持按供应商名称模糊搜索。",
            {
                "vendor_name": {"type": "string", "description": "供应商名称（模糊匹配）"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        ),
        _make_tool(
            "query_vouchers",
            "查询 YonSuite 财务凭证。支持按日期、会计期间、账簿过滤。",
            {
                "date_from": {"type": "string", "description": "凭证起始日期 YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "凭证截止日期 YYYY-MM-DD"},
                "accbook_code": {"type": "string", "description": "账簿编码"},
                "period_start": {"type": "string", "description": "会计期间起始 YYYY-MM"},
                "period_end": {"type": "string", "description": "会计期间截止 YYYY-MM"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        ),
    ]
    return _rpc_result(req_id, {"tools": tools})


# ── tools/call ──────────────────────────────────────────────────────────────

def _r2(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return 0.0


def _tool_result(**kwargs):
    return {"content": [{"type": "text", "text": json.dumps(kwargs, ensure_ascii=False, default=str)}]}


def _tool_error(msg: str):
    return {"content": [{"type": "text", "text": json.dumps({"error": msg}, ensure_ascii=False)}]}


def _paginate(arguments: dict, default_page_size: int, fetch):
    """Auto-paginate: if page_index absent, loop all pages; else single page.

    fetch(page_index, page_size) -> list[dict]
    """
    page_index = arguments.get("page_index")
    page_size = arguments.get("page_size", default_page_size)

    if page_index is not None:
        return fetch(page_index, page_size)

    all_records = []
    pi = 1
    while True:
        batch = fetch(pi, page_size)
        all_records.extend(batch)
        if len(batch) < page_size:
            break
        pi += 1
    return all_records


def _parse_name(raw) -> str:
    """Customer/vendor name field is a nested dict, not a string."""
    if isinstance(raw, dict):
        return raw.get("simplifiedName") or raw.get("name") or ""
    return str(raw) if raw else ""


# ── Status maps (shared across handlers) ────────────────────────────────────

SALE_STATUS_MAP = {"CONFIRMORDER": "开立", "DELIVERY_PART": "部分发货", "DELIVERY_TAKE_PART": "部分发货待收货", "DELIVERGOODS": "待发货", "TAKEDELIVERY": "待收货", "ENDORDER": "已完成", "OPPOSE": "已取消", "APPROVING": "审批中"}
PURCHASE_STATUS_MAP = {0: "开立", 1: "已审核", 2: "已关闭", 3: "审核中"}
PURCHASE_ARRIVED_MAP = {1: "到货完成", 2: "未到货", 3: "部分到货", 4: "到货完成"}
PURCHASE_INWH_MAP = {1: "入库完成", 2: "未入库", 3: "部分入库", 4: "入库结束"}
PURCHASE_INVOICE_MAP = {1: "开票完成", 2: "未开票", 3: "部分开票", 4: "开票结束"}
PROD_STATUS_MAP = {0: "开立", 1: "已审核", 2: "已关闭", 3: "审核中", 4: "已锁定", 5: "已开工", 6: "生产完工"}
PROD_STOCK_MAP = {0: "未入库", 1: "部分入库", 2: "全部入库"}
OPPT_STATE_MAP = {0: "进行中", 1: "暂停", 2: "作废", 3: "关闭"}
OPPT_WIN_LOSE_MAP = {0: "赢单", 1: "丢单", 2: "未定", 3: "部分赢单"}
TODO_TYPE_MAP_LOCAL = {"SCMSA": "销售订单", "SACT": "销售合同", "RBSM": "报销单", "PGRM": "项目管理"}


def _ys_api_handler(method: str, params: dict) -> dict:
    if method == "connection_check":
        client = _get_client()
        if client is None:
            return _tool_error("YonSuite 未配置，请在设置中配置 App Key、App Secret、Tenant ID")
        try:
            client.get_access_token()
            return _tool_result(data="YonSuite 连接成功", connected=True)
        except Exception as e:
            return _tool_result(data="YonSuite 连接失败", connected=False, message=str(e))

    ALLOWED = frozenset({
        "query_sale_orders", "get_order_detail", "query_purchase_orders",
        "get_purchase_order_detail", "query_current_stock", "query_products",
        "query_customers", "query_vendors", "get_vendor_detail",
        "query_production_orders", "get_production_order_detail",
        "query_accbooks", "query_vouchers", "query_user_todos",
        "query_opportunities", "get_org_detail", "query_org_units",
        "format_order_info", "format_stock_info", "format_todo_info",
        "format_production_order_info", "format_org_unit_info",
    })

    if method not in ALLOWED:
        return _tool_error(f"未知方法: {method}")

    client = _get_client()
    if client is None:
        return _tool_error("YonSuite 未配置")

    try:
        func = getattr(client, method)
        result = func(**params)
        if isinstance(result, str):
            if result.startswith("{"):
                return _tool_result(data=json.loads(result))
            return _tool_result(data=result)
        return _tool_result(data=result)
    except Exception as e:
        return _tool_error(f"API 调用失败: {e}")


def handle_tools_call(req_id: int, params: dict):
    name = params.get("name", "")
    arguments = params.get("arguments", {})

    # ys_api is handled separately (delegates to YonSuiteClient methods directly)
    if name == "ys_api":
        method = arguments.get("method", "")
        if not method:
            return _rpc_result(req_id, _tool_error("method 是必需的"))
        result = _ys_api_handler(method, arguments.get("params", {}) or {})
        return _rpc_result(req_id, result)

    client = _get_client()
    if client is None:
        return _rpc_result(req_id, _tool_error("YonSuite 未配置"))

    try:
        if name == "query_sale_orders":
            is_sum = arguments.get("is_sum", False)
            date_from = arguments.get("date_from") or None
            date_to = arguments.get("date_to") or None

            def fetch(pi, ps):
                result = client.query_sale_orders(page_index=pi, page_size=ps, isSum=is_sum, date_from=date_from, date_to=date_to)
                return result.get("data", {}).get("recordList", [])

            records = _paginate(arguments, 500, fetch)
            parsed = []
            grand_total = 0.0
            grand_tax = 0.0
            for r in records:
                if r.get("code") == "合计":
                    continue
                ori_sum = float(r.get("oriSum", 0) or 0)
                tax_rate = float(r.get("taxRate", 0) or 0)
                calc_tax = ori_sum / (1 + tax_rate / 100) * (tax_rate / 100) if tax_rate > 0 else 0.0
                grand_total += ori_sum
                grand_tax += calc_tax
                status_raw = r.get("nextStatus", "") or ""
                parsed.append({
                    "code": r.get("code", ""), "vouchdate": str(r.get("vouchdate", ""))[:10],
                    "customer": r.get("agentId_name", ""),
                    "status": SALE_STATUS_MAP.get(status_raw, status_raw),
                    "skuCode": r.get("skuCode", ""), "skuName": r.get("skuName", ""),
                    "qty": _r2(r.get("qty", 0)), "unitPrice": _r2(r.get("oriTaxUnitPrice", 0)),
                    "oriSum": _r2(ori_sum), "tax": _r2(calc_tax),
                    "department": r.get("saleDepartmentId_name", ""),
                    "salesman": r.get("corpContactUserName", ""),
                    "warehouse": r.get("stockName", "") or None,
                })
            return _rpc_result(req_id, _tool_result(
                data=f"销售订单查询结果（{len(parsed)} 条）", records=parsed,
                summary={"recordCount": len(parsed), "grandTotal": _r2(grand_total), "grandTax": _r2(grand_tax)},
            ))

        elif name == "query_purchase_orders":
            date_from = arguments.get("date_from") or None
            date_to = arguments.get("date_to") or None

            if date_from and date_to:
                import urllib.parse

                def fetch(pi, ps):
                    token = client.get_access_token()
                    url = f"{client.purchase.gateway_url}{client.purchase.base_path}/list?access_token={urllib.parse.quote(token)}"
                    body = {"pageIndex": pi, "pageSize": ps, "isSum": True,
                            "simpleVOs": [{"field": "vouchdate", "op": "between", "value1": date_from, "value2": date_to}],
                            "queryOrders": [{"field": "vouchdate", "order": "desc"}]}
                    return client.purchase._http_post_raw(url, body).get("data", {}).get("recordList", [])
            else:
                def fetch(pi, ps):
                    return client.query_purchase_orders(page_index=pi, page_size=ps).get("data", {}).get("recordList", [])

            records = _paginate(arguments, 500, fetch)
            parsed = []
            grand_total = 0.0
            for r in records:
                if r.get("code") == "合计":
                    continue
                list_ori_sum = float(r.get("listOriSum", 0) or 0)
                grand_total += list_ori_sum
                status_raw = r.get("status", 0)
                parsed.append({
                    "code": r.get("code", ""), "vouchdate": str(r.get("vouchdate", ""))[:10],
                    "vendor": r.get("vendor_name", ""),
                    "materialCode": r.get("product_cCode", ""), "materialName": r.get("product_cName", ""),
                    "qty": _r2(r.get("subQty", 0)), "unitPrice": _r2(r.get("oriTaxUnitPrice", 0)),
                    "listOriSum": _r2(list_ori_sum), "tax": _r2(r.get("listOriTax", 0)),
                    "status": PURCHASE_STATUS_MAP.get(status_raw, str(status_raw)),
                    "arrivedStatus": PURCHASE_ARRIVED_MAP.get(r.get("purchaseOrders_arrivedStatus", 0), ""),
                    "inWhStatus": PURCHASE_INWH_MAP.get(r.get("purchaseOrders_inWHStatus", 0), ""),
                    "invoiceStatus": PURCHASE_INVOICE_MAP.get(r.get("purchaseOrders_invoiceStatus", 0), ""),
                })
            return _rpc_result(req_id, _tool_result(
                data=f"采购订单查询结果（{len(parsed)} 条）", records=parsed,
                summary={"recordCount": len(parsed), "grandTotal": _r2(grand_total)},
            ))

        elif name == "query_production_orders":
            date_from = arguments.get("date_from") or None
            date_to = arguments.get("date_to") or None

            def fetch(pi, ps):
                return client.query_production_orders(page_index=pi, page_size=ps).get("data", {}).get("recordList", [])

            records = _paginate(arguments, 500, fetch)
            if date_from or date_to:
                records = [r for r in records if (
                    (not date_from or str(r.get("vouchdate", ""))[:10] >= date_from) and
                    (not date_to or str(r.get("vouchdate", ""))[:10] <= date_to)
                )]
            parsed = []
            for r in records:
                if r.get("code") in ("合计", "物料SKU编码", "物料SKU名称", "自由项特征组"):
                    continue
                parsed.append({
                    "code": r.get("code", ""), "factory": r.get("orgName", ""),
                    "vouchdate": str(r.get("vouchdate", ""))[:10],
                    "status": PROD_STATUS_MAP.get(r.get("status", 0), ""),
                    "materialCode": r.get("OrderProduct_productCode", ""),
                    "materialName": r.get("OrderProduct_productName", ""),
                    "qty": _r2(r.get("OrderProduct_quantity", 0)),
                    "completedQty": _r2(r.get("OrderProduct_completedQuantity", 0)),
                    "incomingQty": _r2(r.get("OrderProduct_incomingQuantity", 0) or r.get("cfmIncomingQty", 0)),
                    "stockStatus": PROD_STOCK_MAP.get(r.get("OrderProduct_stockStatus", 0), ""),
                })
            return _rpc_result(req_id, _tool_result(
                data=f"生产订单查询结果（{len(parsed)} 条）", records=parsed,
                summary={"recordCount": len(parsed)},
            ))

        elif name == "query_stock":
            # Stock API doesn't support page_index pagination; uses page_size only
            product_id_raw = (arguments.get("product_id") or "").strip() or None
            warehouse = (arguments.get("warehouse") or "").strip() or None
            sku = (arguments.get("sku") or "").strip() or None
            page_size = arguments.get("page_size", 500)

            product_param = None
            if product_id_raw:
                ids = [pid.strip() for pid in product_id_raw.split(",") if pid.strip()]
                product_param = ids if len(ids) > 1 else ids[0]

            result = client.query_current_stock(page_size=page_size, product=product_param)
            raw_data = result.get("data", [])
            records = raw_data if isinstance(raw_data, list) else []

            if warehouse:
                records = [r for r in records if warehouse in str(r.get("warehouse_name", ""))]
            if sku and not product_param:
                records = [r for r in records if sku in str(r.get("productsku_code", "")) or sku in str(r.get("product_code", ""))]

            from collections import defaultdict
            aggregated = defaultdict(lambda: {"currentQty": 0.0, "availableQty": 0.0})
            for r in records:
                sku_code = str(r.get("productsku_code", "") or "").strip()
                mat_code = str(r.get("product_code", "") or "").strip()
                wh_name = str(r.get("warehouse_name", "") or "").strip()
                agg_key = (wh_name, sku_code) if sku_code else (wh_name, mat_code)
                entry = aggregated[agg_key]
                if "productCode" not in entry:
                    entry["productCode"] = mat_code
                    entry["productName"] = r.get("product_name", "")
                    entry["skuCode"] = sku_code if sku_code else "(无SKU)"
                    entry["warehouseName"] = wh_name
                    entry["orgName"] = r.get("org_name", "")
                    entry["unitName"] = r.get("product_unitName", "")
                entry["currentQty"] += float(r.get("currentqty", 0) or 0)
                entry["availableQty"] += float(r.get("availableqty", 0) or 0)

            parsed = []
            grand_current = 0.0
            grand_available = 0.0
            for entry in sorted(aggregated.values(), key=lambda e: (e.get("warehouseName", ""), e.get("skuCode", ""))):
                entry["currentQty"] = _r2(entry["currentQty"])
                entry["availableQty"] = _r2(entry["availableQty"])
                grand_current += entry["currentQty"]
                grand_available += entry["availableQty"]
                parsed.append(dict(entry))

            return _rpc_result(req_id, _tool_result(
                data=f"库存查询结果（{len(parsed)} 条，已按仓库+SKU聚合）", records=parsed,
                summary={"recordCount": len(parsed), "grandCurrentQty": _r2(grand_current), "grandAvailableQty": _r2(grand_available)},
            ))

        elif name == "query_user_todos":
            import re
            from datetime import datetime

            def fetch(pi, ps):
                result = client.query_user_todos(page_no=pi, page_size=ps)
                return result.get("data", [])

            items = _paginate(arguments, 50, fetch)
            parsed = []
            for item in items:
                rich_text = re.sub(r"<[^>]+>", "", item.get("richText", "") or "").strip()
                title = item.get("title", "")
                src = item.get("approveSource", "") or ""
                service_code = item.get("serviceCode", "") or ""
                if "iKM" in title:
                    type_label = "iKM知识申请"
                elif src in TODO_TYPE_MAP_LOCAL:
                    type_label = TODO_TYPE_MAP_LOCAL[src]
                elif "expense" in service_code or "znbzbx" in service_code:
                    type_label = "报销单"
                elif "order" in service_code:
                    type_label = "销售订单"
                elif "salescontract" in service_code:
                    type_label = "销售合同"
                else:
                    type_label = title or src
                ts = item.get("commitTsLong", 0)
                commit_time = datetime.fromtimestamp(int(str(ts)[:10])).strftime("%Y-%m-%d %H:%M:%S") if ts else ""
                parsed.append({
                    "title": title, "typeLabel": type_label,
                    "content": (item.get("content", "") or "").strip(),
                    "richText": rich_text, "commitUserName": item.get("commitUserName", ""),
                    "commitTime": commit_time,
                    "taskName": item.get("businessData", {}).get("taskName") if isinstance(item.get("businessData"), dict) else "",
                })
            return _rpc_result(req_id, _tool_result(
                data=f"待办查询结果（{len(parsed)} 条）", records=parsed,
                summary={"recordCount": len(parsed)},
            ))

        elif name == "query_opportunities":
            oppt_state = arguments.get("oppt_state") or None
            win_lose_state = arguments.get("win_lose_state") or None
            date_from = arguments.get("date_from") or None
            date_to = arguments.get("date_to") or None

            def fetch(pi, ps):
                result = client.query_opportunities(page_index=pi, page_size=ps, oppt_state=oppt_state, win_lose_state=win_lose_state, is_sum=True, date_from=date_from, date_to=date_to)
                return result.get("data", {}).get("recordList", [])

            records = _paginate(arguments, 500, fetch)
            parsed = []
            for r in records:
                oppt_state_val = r.get("opptState", 0)
                win_lose_val = r.get("winLoseOrderState", 0)
                expect_money = float(r.get("expectSignMoney", 0) or 0)
                win_money = float(r.get("winOrderMoney", 0) or 0)
                amount = win_money if win_lose_val == 0 else expect_money
                parsed.append({
                    "code": r.get("code", ""), "name": r.get("name", ""),
                    "opptState": OPPT_STATE_MAP.get(oppt_state_val, str(oppt_state_val)),
                    "winLoseState": OPPT_WIN_LOSE_MAP.get(win_lose_val, str(win_lose_val)),
                    "amount": _r2(amount), "customerName": r.get("customer_name", ""),
                    "salesman": r.get("ower_name", ""), "stageName": r.get("opptStage_name", ""),
                })
            return _rpc_result(req_id, _tool_result(
                data=f"商机查询结果（{len(parsed)} 条）", records=parsed,
                summary={"recordCount": len(parsed)},
            ))

        elif name == "query_products":
            product_code = (arguments.get("product_code") or "").strip() or None
            product_name = (arguments.get("product_name") or "").strip() or None

            def fetch(pi, ps):
                return client.query_products(page_index=pi, page_size=ps,
                    product_code=product_code if product_code else None).get("data", {}).get("recordList", [])

            if product_name:
                # Fuzzy name search: auto-paginate all, then filter client-side
                records = _paginate({}, 500, fetch)
                name_lower = product_name.lower()
                records = [r for r in records if name_lower in str(r.get("name", "")).lower()]
                if product_code:
                    records = [r for r in records if r.get("code") == product_code]
            else:
                records = _paginate(arguments, 500, fetch)

            attr_map = {"1": "实物物料", "2": "虚拟物料"}
            parsed = []
            for r in records:
                parsed.append({
                    "id": r.get("id", ""), "code": r.get("code", ""), "name": r.get("name", ""),
                    "model": r.get("model", ""),
                    "productClass": r.get("manageClassName", "") or r.get("productClass", ""),
                    "unitName": r.get("unitName", "") or r.get("unit_name", ""),
                    "brand": r.get("brand", ""),
                    "productType": attr_map.get(r.get("realProductAttribute", ""), ""),
                    "status": "停用" if r.get("stopStatus") else "启用",
                })
            return _rpc_result(req_id, _tool_result(
                data=f"物料查询结果（{len(parsed)} 条）", records=parsed,
                summary={"recordCount": len(parsed)},
            ))

        elif name == "query_customers":
            customer_name = (arguments.get("customer_name") or "").strip() or None

            def fetch(pi, ps):
                return client.query_customers(page_index=pi, page_size=ps).get("data", {}).get("recordList", [])

            records = _paginate(arguments, 500, fetch)
            if customer_name:
                name_lower = customer_name.lower()
                records = [r for r in records if name_lower in _parse_name(r.get("name")).lower()]

            parsed = []
            for r in records:
                parsed.append({
                    "id": r.get("id", ""), "code": r.get("code", ""),
                    "name": _parse_name(r.get("name")),
                    "customerClass": r.get("customerClassName", ""),
                    "contactPerson": r.get("personOfContact", ""),
                    "phone": r.get("mobilePhone", "") or r.get("telephone", ""),
                })
            return _rpc_result(req_id, _tool_result(
                data=f"客户查询结果（{len(parsed)} 条）", records=parsed,
                summary={"recordCount": len(parsed)},
            ))

        elif name == "query_vendors":
            vendor_name = (arguments.get("vendor_name") or "").strip() or None

            def fetch(pi, ps):
                return client.query_vendors(page_index=pi, page_size=ps).get("data", {}).get("recordList", [])

            records = _paginate(arguments, 500, fetch)
            if vendor_name:
                name_lower = vendor_name.lower()
                records = [r for r in records if name_lower in _parse_name(r.get("name")).lower()]

            parsed = []
            for r in records:
                parsed.append({
                    "id": r.get("id", ""), "code": r.get("code", ""),
                    "name": _parse_name(r.get("name")),
                    "vendorClass": r.get("vendorClassName", ""),
                    "contactPerson": r.get("personOfContact", ""),
                    "phone": r.get("mobilePhone", "") or r.get("telephone", ""),
                    "bankName": r.get("bankName", ""), "bankAccount": r.get("bankAccount", ""),
                })
            return _rpc_result(req_id, _tool_result(
                data=f"供应商查询结果（{len(parsed)} 条）", records=parsed,
                summary={"recordCount": len(parsed)},
            ))

        elif name == "query_vouchers":
            kwargs = {}
            for key, kw in [("date_from", "voucher_date_start"), ("date_to", "voucher_date_end"),
                            ("period_start", "period_start"), ("period_end", "period_end"),
                            ("accbook_code", "accbook_code")]:
                val = (arguments.get(key) or "").strip() or None
                if val:
                    kwargs[kw] = val

            def fetch(pi, ps):
                result = client.voucher.query_vouchers_parsed(client.get_access_token(), page_size=ps, page_index=pi, **kwargs)
                return result.get("records", [])

            records = _paginate(arguments, 500, fetch)
            return _rpc_result(req_id, _tool_result(
                data=f"凭证查询结果（{len(records)} 条）", records=records,
                summary={"recordCount": len(records)},
            ))

        else:
            return _rpc_result(req_id, _tool_error(f"未知工具: {name}"))

    except Exception as e:
        return _rpc_result(req_id, _tool_error(f"查询失败: {e}"))


# ── Dispatch ────────────────────────────────────────────────────────────────

DISPATCH = {
    "initialize": handle_initialize,
    "tools/list": handle_tools_list,
    "tools/call": handle_tools_call,
}


def main():
    # Send ready signal on stderr so supervisor can detect it (not JSON-RPC)
    sys.stderr.write(f"[ys-mcp-server] started (pid={os.getpid()})\n")
    sys.stderr.flush()

    # Process JSON-RPC messages line by line from stdin
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = msg.get("id")
        method = msg.get("method", "")

        handler = DISPATCH.get(method)
        if handler is None:
            # Respond to unknown methods that have an id (skip notifications)
            if req_id is not None:
                _send(_rpc_error(req_id, -32601, f"Method not found: {method}"))
            continue

        try:
            params = msg.get("params", {})
            if method == "initialize":
                resp = handler(req_id, params)
            elif method == "tools/list":
                resp = handler(req_id)
            elif method == "tools/call":
                resp = handler(req_id, params)
            else:
                resp = handler(req_id, params)
            _send(resp)
        except Exception as e:
            _send(_rpc_error(req_id, -32603, str(e)[:500]))


if __name__ == "__main__":
    main()
