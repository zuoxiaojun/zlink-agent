"""YonSuite ERP 工具 — 注册为内置工具，替代 MCP 子进程。

从 mcp_server/ys_mcp_server/ 迁移而来，保持原有 handler 逻辑不变，
只适配 registry.register() 的 handler 签名 (args dict → JSON str)。
"""

from __future__ import annotations

import json
import re
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from agent.tools.registry import registry, tool_error, tool_result

# ═══════════════════════════════════════════════════════════════
# 共享辅助函数 (从 mcp_server/ys_mcp_server/utils.py 迁移)
# ═══════════════════════════════════════════════════════════════

_YSONSUITE_CONFIG_LOADED = False


def _ensure_ys_config():
    """Load YonSuite credentials from config.json into environment."""
    global _YSONSUITE_CONFIG_LOADED
    if _YSONSUITE_CONFIG_LOADED:
        return
    _YSONSUITE_CONFIG_LOADED = True
    from pathlib import Path

    from agent.utils import DATA_DIR

    config_path = DATA_DIR / "config.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            cfg = {}
    else:
        cfg = {}
    import os

    for key, env_key in [
        ("ys_app_key", "YONSUITE_APP_KEY"),
        ("ys_app_secret", "YONSUITE_APP_SECRET"),
        ("ys_tenant_id", "YONSUITE_TENANT_ID"),
        ("ys_gateway_url", "YONSUITE_GATEWAY_URL"),
    ]:
        val = cfg.get(key, "")
        # 根级为空时尝试从 erp_clients.yonsuite 读取
        if not val:
            ys_erp = cfg.get("erp_clients", {}).get("yonsuite", {})
            erp_map = {
                "ys_app_key": "app_key",
                "ys_app_secret": "app_secret",
                "ys_tenant_id": "tenant_id",
                "ys_gateway_url": "base_url",
            }
            val = ys_erp.get(erp_map[key], "")
        if val and not os.environ.get(env_key):
            os.environ[env_key] = val


_ys_client = None


def _get_ys_client():
    global _ys_client
    if _ys_client is not None:
        return _ys_client
    _ensure_ys_config()
    from agent.erp_clients.yonsuite.config import config as ys_config

    if not ys_config.is_configured():
        return None
    from agent.erp_clients.yonsuite.ys_client import YonSuiteClient

    _ys_client = YonSuiteClient()
    return _ys_client


def r2(v) -> float:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return 0.0


def _parse_name(raw) -> str:
    if isinstance(raw, dict):
        return raw.get("simplifiedName") or raw.get("name") or ""
    return str(raw) if raw else ""


# ═══════════════════════════════════════════════════════════════
# 分页辅助 (从 mcp_server/ys_mcp_server/paginate.py 迁移)
# ═══════════════════════════════════════════════════════════════

_MAX_PAGES = 200


@dataclass
class _PaginatedResult:
    records: list[dict]
    note: str


def _paginate(
    arguments: dict,
    default_page_size: int,
    fetch: Callable[[int, int], list[dict]],
) -> _PaginatedResult:
    page_index = arguments.get("page_index")
    page_size = arguments.get("page_size", default_page_size)

    if page_index is not None:
        batch = fetch(int(page_index), page_size)
        return _PaginatedResult(
            records=batch,
            note=f"单页查询结果（第 {page_index} 页，每页 {page_size} 条，返回 {len(batch)} 条）",
        )

    all_records: list[dict] = []
    pages_fetched = 0
    for pi in range(1, _MAX_PAGES + 1):
        batch = fetch(pi, page_size)
        if not batch:
            break
        all_records.extend(batch)
        pages_fetched += 1
        if len(batch) < page_size:
            break

    return _PaginatedResult(
        records=all_records,
        note=f"已自动翻页获取全部数据（共 {pages_fetched} 页，{len(all_records)} 条）",
    )


# ═══════════════════════════════════════════════════════════════
# 状态映射 (从 mcp_server/ys_mcp_server/constants.py 迁移)
# ═══════════════════════════════════════════════════════════════

_SALE_STATUS_MAP = {
    "CONFIRMORDER": "开立",
    "DELIVERY_PART": "部分发货",
    "DELIVERY_TAKE_PART": "部分发货待收货",
    "DELIVERGOODS": "待发货",
    "TAKEDELIVERY": "待收货",
    "ENDORDER": "已完成",
    "OPPOSE": "已取消",
    "APPROVING": "审批中",
}
_PURCHASE_STATUS_MAP = {0: "开立", 1: "已审核", 2: "已关闭", 3: "审核中"}
_PURCHASE_ARRIVED_MAP = {1: "到货完成", 2: "未到货", 3: "部分到货", 4: "到货完成"}
_PURCHASE_INWH_MAP = {1: "入库完成", 2: "未入库", 3: "部分入库", 4: "入库结束"}
_PURCHASE_INVOICE_MAP = {1: "开票完成", 2: "未开票", 3: "部分开票", 4: "开票结束"}
_PROD_STATUS_MAP = {0: "开立", 1: "已审核", 2: "已关闭", 3: "审核中", 4: "已锁定", 5: "已开工", 6: "生产完工"}
_PROD_STOCK_MAP = {0: "未入库", 1: "部分入库", 2: "全部入库"}
_OPPT_STATE_MAP = {0: "进行中", 1: "暂停", 2: "作废", 3: "关闭"}
_OPPT_WIN_LOSE_MAP = {0: "赢单", 1: "丢单", 2: "未定", 3: "部分赢单"}
_TODO_TYPE_MAP = {"SCMSA": "销售订单", "SACT": "销售合同", "RBSM": "报销单", "PGRM": "项目管理"}


# ═══════════════════════════════════════════════════════════════
# 工具 handler
# ═══════════════════════════════════════════════════════════════


def _handle_ys_api(args: dict) -> str:
    """YonSuite 通用 API 网关 — 通过 method 参数调用客户端方法。"""
    method = args.get("method", "")
    params = args.get("params", {}) or {}

    client = _get_ys_client()

    if method == "connection_check":
        if client is None:
            return tool_error("YonSuite 未配置，请在设置中配置 App Key、App Secret、Tenant ID")
        try:
            client.get_access_token()
            return tool_result(data="YonSuite 连接成功", connected=True)
        except Exception as e:
            return tool_result(data="YonSuite 连接失败", connected=False, message=str(e))

    _ALLOWED = frozenset({
        "query_sale_orders", "get_order_detail", "query_purchase_orders",
        "get_purchase_order_detail", "query_current_stock", "query_products",
        "query_customers", "query_vendors", "get_vendor_detail",
        "query_production_orders", "get_production_order_detail",
        "query_accbooks", "query_vouchers", "query_user_todos",
        "query_opportunities", "get_org_detail", "query_org_units",
        "format_order_info", "format_stock_info", "format_todo_info",
        "format_production_order_info", "format_org_unit_info",
    })
    if method not in _ALLOWED:
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


def _handle_query_sale_orders(args: dict) -> str:
    """查询 YonSuite 销售订单。"""
    client = _get_ys_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    is_sum = args.get("is_sum", False)
    date_from = args.get("date_from") or None
    date_to = args.get("date_to") or None

    def fetch(pi, ps):
        result = client.query_sale_orders(
            page_index=pi, page_size=ps, isSum=is_sum,
            date_from=date_from, date_to=date_to,
        )
        return result.get("data", {}).get("recordList", [])

    result = _paginate(args, 500, fetch)
    parsed = []
    grand_total = 0.0
    grand_tax = 0.0
    for r in result.records:
        if r.get("code") == "合计":
            continue
        ori_sum = float(r.get("oriSum", 0) or 0)
        tax_rate = float(r.get("taxRate", 0) or 0)
        calc_tax = ori_sum / (1 + tax_rate / 100) * (tax_rate / 100) if tax_rate > 0 else 0.0
        grand_total += ori_sum
        grand_tax += calc_tax
        status_raw = r.get("nextStatus", "") or ""
        parsed.append({
            "code": r.get("code", ""),
            "vouchdate": str(r.get("vouchdate", ""))[:10],
            "customer": r.get("agentId_name", ""),
            "status": _SALE_STATUS_MAP.get(status_raw, status_raw),
            "skuCode": r.get("skuCode", ""),
            "skuName": r.get("skuName", ""),
            "qty": r2(r.get("qty", 0)),
            "unitPrice": r2(r.get("oriTaxUnitPrice", 0)),
            "oriSum": r2(ori_sum),
            "tax": r2(calc_tax),
            "department": r.get("saleDepartmentId_name", ""),
            "salesman": r.get("corpContactUserName", ""),
            "warehouse": r.get("stockName", "") or None,
        })

    return tool_result(
        data=f"销售订单查询结果（{len(parsed)} 条）",
        records=parsed, note=result.note,
        summary={"recordCount": len(parsed), "grandTotal": r2(grand_total), "grandTax": r2(grand_tax)},
    )


def _handle_query_purchase_orders(args: dict) -> str:
    """查询 YonSuite 采购订单。"""
    client = _get_ys_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    date_from = args.get("date_from") or None
    date_to = args.get("date_to") or None

    if date_from and date_to:
        def fetch(pi, ps):
            token = client.get_access_token()
            url = f"{client.purchase.gateway_url}{client.purchase.base_path}/list?access_token={urllib.parse.quote(token)}"
            body = {
                "pageIndex": pi, "pageSize": ps, "isSum": True,
                "simpleVOs": [{"field": "vouchdate", "op": "between", "value1": date_from, "value2": date_to}],
                "queryOrders": [{"field": "vouchdate", "order": "desc"}],
            }
            return client.purchase._http_post_raw(url, body).get("data", {}).get("recordList", [])
    else:
        def fetch(pi, ps):
            return client.query_purchase_orders(page_index=pi, page_size=ps).get("data", {}).get("recordList", [])

    result = _paginate(args, 500, fetch)
    parsed = []
    grand_total = 0.0
    for r in result.records:
        if r.get("code") == "合计":
            continue
        list_ori_sum = float(r.get("listOriSum", 0) or 0)
        grand_total += list_ori_sum
        status_raw = r.get("status", 0)
        parsed.append({
            "code": r.get("code", ""),
            "vouchdate": str(r.get("vouchdate", ""))[:10],
            "vendor": r.get("vendor_name", ""),
            "materialCode": r.get("product_cCode", ""),
            "materialName": r.get("product_cName", ""),
            "qty": r2(r.get("subQty", 0)),
            "unitPrice": r2(r.get("oriTaxUnitPrice", 0)),
            "listOriSum": r2(list_ori_sum),
            "tax": r2(r.get("listOriTax", 0)),
            "status": _PURCHASE_STATUS_MAP.get(status_raw, str(status_raw)),
            "arrivedStatus": _PURCHASE_ARRIVED_MAP.get(r.get("purchaseOrders_arrivedStatus", 0), ""),
            "inWhStatus": _PURCHASE_INWH_MAP.get(r.get("purchaseOrders_inWHStatus", 0), ""),
            "invoiceStatus": _PURCHASE_INVOICE_MAP.get(r.get("purchaseOrders_invoiceStatus", 0), ""),
        })

    return tool_result(
        data=f"采购订单查询结果（{len(parsed)} 条）",
        records=parsed, note=result.note,
        summary={"recordCount": len(parsed), "grandTotal": r2(grand_total)},
    )


def _handle_query_production_orders(args: dict) -> str:
    """查询 YonSuite 生产订单。"""
    client = _get_ys_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    date_from = args.get("date_from") or None
    date_to = args.get("date_to") or None

    def fetch(pi, ps):
        return client.query_production_orders(page_index=pi, page_size=ps).get("data", {}).get("recordList", [])

    result = _paginate(args, 500, fetch)
    records = result.records
    if date_from or date_to:
        records = [
            r for r in records
            if (not date_from or str(r.get("vouchdate", ""))[:10] >= date_from)
            and (not date_to or str(r.get("vouchdate", ""))[:10] <= date_to)
        ]

    SKIP = {"合计", "物料SKU编码", "物料SKU名称", "自由项特征组"}
    parsed = []
    for r in records:
        if r.get("code") in SKIP:
            continue
        parsed.append({
            "code": r.get("code", ""),
            "factory": r.get("orgName", ""),
            "vouchdate": str(r.get("vouchdate", ""))[:10],
            "status": _PROD_STATUS_MAP.get(r.get("status", 0), ""),
            "materialCode": r.get("OrderProduct_productCode", ""),
            "materialName": r.get("OrderProduct_productName", ""),
            "qty": r2(r.get("OrderProduct_quantity", 0)),
            "completedQty": r2(r.get("OrderProduct_completedQuantity", 0)),
            "incomingQty": r2(r.get("OrderProduct_incomingQuantity", 0) or r.get("cfmIncomingQty", 0)),
            "stockStatus": _PROD_STOCK_MAP.get(r.get("OrderProduct_stockStatus", 0), ""),
        })

    return tool_result(
        data=f"生产订单查询结果（{len(parsed)} 条）",
        records=parsed, note=result.note,
        summary={"recordCount": len(parsed)},
    )


def _handle_query_stock(args: dict) -> str:
    """查询 YonSuite 库存现存量。"""
    client = _get_ys_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    product_id_raw = (args.get("product_id") or "").strip() or None
    warehouse = (args.get("warehouse") or "").strip() or None
    sku = (args.get("sku") or "").strip() or None

    product_param = None
    if product_id_raw:
        ids = [pid.strip() for pid in product_id_raw.split(",") if pid.strip()]
        product_param = ids if len(ids) > 1 else ids[0]

    def fetch(pi, ps):
        result = client.query_current_stock(page_index=pi, page_size=ps, product=product_param)
        raw_data = result.get("data", [])
        return raw_data if isinstance(raw_data, list) else []

    result = _paginate(args, 500, fetch)
    records = result.records
    if warehouse:
        records = [r for r in records if warehouse in str(r.get("warehouse_name", ""))]
    if sku and not product_param:
        records = [
            r for r in records
            if sku in str(r.get("productsku_code", "")) or sku in str(r.get("product_code", ""))
        ]

    parsed = []
    grand_current = 0.0
    grand_available = 0.0
    for r in records:
        cur = float(r.get("currentqty", 0) or 0)
        avail = float(r.get("availableqty", 0) or 0)
        grand_current += cur
        grand_available += avail
        parsed.append({
            "productCode": r.get("product_code", ""),
            "productName": r.get("product_name", ""),
            "skuCode": (r.get("productsku_code", "") or "").strip() or None,
            "warehouseName": r.get("warehouse_name", ""),
            "orgName": r.get("org_name", ""),
            "unitName": r.get("product_unitName", ""),
            "currentQty": r2(cur),
            "availableQty": r2(avail),
        })

    return tool_result(
        data=f"库存查询结果（{len(parsed)} 条）",
        records=parsed, note=result.note,
        summary={"recordCount": len(parsed), "grandCurrentQty": r2(grand_current), "grandAvailableQty": r2(grand_available)},
    )


def _handle_query_customers(args: dict) -> str:
    """查询 YonSuite 客户档案。"""
    client = _get_ys_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    customer_name = (args.get("customer_name") or "").strip() or None

    def fetch(pi, ps):
        return client.query_customers(page_index=pi, page_size=ps).get("data", {}).get("recordList", [])

    result = _paginate(args, 500, fetch)
    if customer_name:
        name_lower = customer_name.lower()
        records = [r for r in result.records if name_lower in _parse_name(r.get("name")).lower()]
    else:
        records = result.records

    parsed = []
    for r in records:
        parsed.append({
            "id": r.get("id", ""),
            "code": r.get("code", ""),
            "name": _parse_name(r.get("name")),
            "customerClass": r.get("customerClassName", ""),
            "contactPerson": r.get("personOfContact", ""),
            "phone": r.get("mobilePhone", "") or r.get("telephone", ""),
        })

    return tool_result(
        data=f"客户查询结果（{len(parsed)} 条）",
        records=parsed,
        summary={"recordCount": len(parsed)},
    )


def _handle_query_vendors(args: dict) -> str:
    """查询 YonSuite 供应商档案。"""
    client = _get_ys_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    vendor_name = (args.get("vendor_name") or "").strip() or None

    def fetch(pi, ps):
        return client.query_vendors(page_index=pi, page_size=ps).get("data", {}).get("recordList", [])

    result = _paginate(args, 500, fetch)
    if vendor_name:
        name_lower = vendor_name.lower()
        records = [r for r in result.records if name_lower in _parse_name(r.get("name")).lower()]
    else:
        records = result.records

    parsed = []
    for r in records:
        parsed.append({
            "id": r.get("id", ""),
            "code": r.get("code", ""),
            "name": _parse_name(r.get("name")),
            "vendorClass": r.get("vendorClassName", ""),
            "contactPerson": r.get("personOfContact", ""),
            "phone": r.get("mobilePhone", "") or r.get("telephone", ""),
            "bankName": r.get("bankName", ""),
            "bankAccount": r.get("bankAccount", ""),
        })

    return tool_result(
        data=f"供应商查询结果（{len(parsed)} 条）",
        records=parsed,
        summary={"recordCount": len(parsed)},
    )


def _handle_query_products(args: dict) -> str:
    """查询 YonSuite 物料档案。"""
    client = _get_ys_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    product_code = (args.get("product_code") or "").strip() or None
    product_name = (args.get("product_name") or "").strip() or None

    def fetch(pi, ps):
        return (client.query_products(page_index=pi, page_size=ps, product_code=product_code if product_code else None)
                .get("data", {}).get("recordList", []))

    if product_name:
        result = _paginate({}, 500, fetch)
        name_lower = product_name.lower()
        records = [r for r in result.records if name_lower in str(r.get("name", "")).lower()]
        if product_code:
            records = [r for r in result.records if r.get("code") == product_code]
    else:
        result = _paginate(args, 500, fetch)
        records = result.records

    ATTR_MAP = {"1": "实物物料", "2": "虚拟物料"}
    parsed = []
    for r in records:
        parsed.append({
            "id": r.get("id", ""),
            "code": r.get("code", ""),
            "name": r.get("name", ""),
            "model": r.get("model", ""),
            "productClass": r.get("manageClassName", "") or r.get("productClass", ""),
            "unitName": r.get("unitName", "") or r.get("unit_name", ""),
            "brand": r.get("brand", ""),
            "productType": ATTR_MAP.get(r.get("realProductAttribute", ""), ""),
            "status": "停用" if r.get("stopStatus") else "启用",
        })

    return tool_result(
        data=f"物料查询结果（{len(parsed)} 条）",
        records=parsed, note=result.note,
        summary={"recordCount": len(parsed)},
    )


def _handle_query_opportunities(args: dict) -> str:
    """查询 YonSuite CRM 商机。"""
    client = _get_ys_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    oppt_state = args.get("oppt_state") or None
    win_lose_state = args.get("win_lose_state") or None
    date_from = args.get("date_from") or None
    date_to = args.get("date_to") or None

    def fetch(pi, ps):
        result = client.query_opportunities(
            page_index=pi, page_size=ps,
            oppt_state=oppt_state, win_lose_state=win_lose_state,
            is_sum=True, date_from=date_from, date_to=date_to,
        )
        return result.get("data", {}).get("recordList", [])

    result = _paginate(args, 500, fetch)
    parsed = []
    for r in result.records:
        oppt_state_val = r.get("opptState", 0)
        win_lose_val = r.get("winLoseOrderState", 0)
        expect_money = float(r.get("expectSignMoney", 0) or 0)
        win_money = float(r.get("winOrderMoney", 0) or 0)
        amount = win_money if win_lose_val == 0 else expect_money
        parsed.append({
            "code": r.get("code", ""),
            "name": r.get("name", ""),
            "opptState": _OPPT_STATE_MAP.get(oppt_state_val, str(oppt_state_val)),
            "winLoseState": _OPPT_WIN_LOSE_MAP.get(win_lose_val, str(win_lose_val)),
            "amount": r2(amount),
            "customerName": r.get("customer_name", ""),
            "salesman": r.get("ower_name", ""),
            "stageName": r.get("opptStage_name", ""),
        })

    return tool_result(
        data=f"商机查询结果（{len(parsed)} 条）",
        records=parsed, note=result.note,
        summary={"recordCount": len(parsed)},
    )


def _handle_query_vouchers(args: dict) -> str:
    """查询 YonSuite 财务凭证。"""
    client = _get_ys_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    kwargs = {}
    for key, kw in [("date_from", "voucher_date_start"), ("date_to", "voucher_date_end"),
                    ("period_start", "period_start"), ("period_end", "period_end"),
                    ("accbook_code", "accbook_code")]:
        val = (args.get(key) or "").strip() or None
        if val:
            kwargs[kw] = val

    def fetch(pi, ps):
        result = client.voucher.query_vouchers_parsed(
            client.get_access_token(), page_size=ps, page_index=pi, **kwargs)
        return result.get("records", [])

    result = _paginate(args, 500, fetch)
    return tool_result(
        data=f"凭证查询结果（{len(result.records)} 条）",
        records=result.records, note=result.note,
        summary={"recordCount": len(result.records)},
    )


def _handle_query_user_todos(args: dict) -> str:
    """查询 YonSuite 用户待办。"""
    client = _get_ys_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    def _classify(item: dict) -> str:
        title = item.get("title", "")
        src = item.get("approveSource", "") or ""
        service_code = item.get("serviceCode", "") or ""
        if "iKM" in title:
            return "iKM知识申请"
        if src in _TODO_TYPE_MAP:
            return _TODO_TYPE_MAP[src]
        if "expense" in service_code or "znbzbx" in service_code:
            return "报销单"
        if "order" in service_code:
            return "销售订单"
        if "salescontract" in service_code:
            return "销售合同"
        return title or src

    def fetch(pi, ps):
        result = client.query_user_todos(page_no=pi, page_size=ps)
        return result.get("data", [])

    result = _paginate(args, 50, fetch)
    parsed = []
    for item in result.records:
        rich_text = re.sub(r"<[^>]+>", "", item.get("richText", "") or "").strip()
        ts = item.get("commitTsLong", 0)
        commit_time = datetime.fromtimestamp(int(str(ts)[:10])).strftime("%Y-%m-%d %H:%M:%S") if ts else ""
        parsed.append({
            "title": item.get("title", ""),
            "typeLabel": _classify(item),
            "content": (item.get("content", "") or "").strip(),
            "richText": rich_text,
            "commitUserName": item.get("commitUserName", ""),
            "commitTime": commit_time,
            "taskName": item.get("businessData", {}).get("taskName") if isinstance(item.get("businessData"), dict) else "",
        })

    return tool_result(
        data=f"待办查询结果（{len(parsed)} 条）",
        records=parsed, note=result.note,
        summary={"recordCount": len(parsed)},
    )


# ═══════════════════════════════════════════════════════════════
# Schema 定义 + 注册
# ═══════════════════════════════════════════════════════════════

registry.register(
    name="ys_api",
    toolset="yonsuite",
    schema={
        "name": "ys_api",
        "description": "执行 YonSuite API 调用。支持查询销售订单、采购订单、客户、供应商、库存、生产订单、物料、凭证、待办、商机、组织等业务数据。",
        "parameters": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "description": "API 方法名"},
                "params": {"type": "object", "description": "方法参数"},
            },
            "required": ["method"],
        },
    },
    handler=_handle_ys_api,
    emoji="🔌",
)

registry.register(
    name="query_sale_orders",
    toolset="yonsuite",
    schema={
        "name": "query_sale_orders",
        "description": "查询 YonSuite 销售订单。返回已解析的字段记录，含税额自动计算、状态中文映射、币种嵌套解析。is_sum=False 返回逐行明细，is_sum=True 返回按订单汇总。",
        "parameters": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "截止日期 YYYY-MM-DD"},
                "is_sum": {"type": "boolean", "description": "是否汇总模式，默认 false"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        },
    },
    handler=_handle_query_sale_orders,
    emoji="📋",
)

registry.register(
    name="query_purchase_orders",
    toolset="yonsuite",
    schema={
        "name": "query_purchase_orders",
        "description": "查询 YonSuite 采购订单。返回已解析的记录，含状态中文映射（到货/入库/发票状态）。支持日期过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "截止日期 YYYY-MM-DD"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        },
    },
    handler=_handle_query_purchase_orders,
    emoji="📋",
)

registry.register(
    name="query_production_orders",
    toolset="yonsuite",
    schema={
        "name": "query_production_orders",
        "description": "查询 YonSuite 生产订单。返回已解析的记录，含状态中文映射。date_from/date_to 在客户端侧过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "截止日期 YYYY-MM-DD"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        },
    },
    handler=_handle_query_production_orders,
    emoji="🏭",
)

registry.register(
    name="query_stock",
    toolset="yonsuite",
    schema={
        "name": "query_stock",
        "description": "查询 YonSuite 库存现存量，返回逐批次明细。支持按物料ID、仓库、SKU 过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "物料ID精确查询，支持逗号分隔多个ID"},
                "warehouse": {"type": "string", "description": "仓库名称模糊匹配"},
                "sku": {"type": "string", "description": "SKU 编码或物料编码模糊匹配"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        },
    },
    handler=_handle_query_stock,
    emoji="📦",
)

registry.register(
    name="query_customers",
    toolset="yonsuite",
    schema={
        "name": "query_customers",
        "description": "查询 YonSuite 客户档案。支持按客户名称模糊搜索。",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string", "description": "客户名称（模糊匹配）"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        },
    },
    handler=_handle_query_customers,
    emoji="👤",
)

registry.register(
    name="query_vendors",
    toolset="yonsuite",
    schema={
        "name": "query_vendors",
        "description": "查询 YonSuite 供应商档案。支持按供应商名称模糊搜索。",
        "parameters": {
            "type": "object",
            "properties": {
                "vendor_name": {"type": "string", "description": "供应商名称（模糊匹配）"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        },
    },
    handler=_handle_query_vendors,
    emoji="🏢",
)

registry.register(
    name="query_products",
    toolset="yonsuite",
    schema={
        "name": "query_products",
        "description": "查询 YonSuite 物料档案。支持按物料编码（精确）或物料名称（模糊）搜索。",
        "parameters": {
            "type": "object",
            "properties": {
                "product_code": {"type": "string", "description": "物料编码（精确匹配）"},
                "product_name": {"type": "string", "description": "物料名称（模糊匹配）"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        },
    },
    handler=_handle_query_products,
    emoji="🔧",
)

registry.register(
    name="query_opportunities",
    toolset="yonsuite",
    schema={
        "name": "query_opportunities",
        "description": "查询 YonSuite CRM 商机列表。返回已解析的商机记录，自动处理金额字段选择。",
        "parameters": {
            "type": "object",
            "properties": {
                "oppt_state": {"type": "string", "description": "商机状态：0-进行中, 1-暂停, 2-作废, 3-关闭"},
                "win_lose_state": {"type": "string", "description": "赢丢单状态：0-赢单, 1-丢单, 2-未定, 3-部分赢单"},
                "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "截止日期 YYYY-MM-DD"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        },
    },
    handler=_handle_query_opportunities,
    emoji="🎯",
)

registry.register(
    name="query_vouchers",
    toolset="yonsuite",
    schema={
        "name": "query_vouchers",
        "description": "查询 YonSuite 财务凭证。支持按日期、会计期间、账簿过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "凭证起始日期 YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "凭证截止日期 YYYY-MM-DD"},
                "accbook_code": {"type": "string", "description": "账簿编码"},
                "period_start": {"type": "string", "description": "会计期间起始 YYYY-MM"},
                "period_end": {"type": "string", "description": "会计期间截止 YYYY-MM"},
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页"},
                "page_size": {"type": "integer", "description": "每页条数，默认 500"},
            },
        },
    },
    handler=_handle_query_vouchers,
    emoji="🧾",
)

registry.register(
    name="query_user_todos",
    toolset="yonsuite",
    schema={
        "name": "query_user_todos",
        "description": "查询 YonSuite 用户待办事项。返回已解析的待办列表，含 richText 清洗、单据类型自动映射。",
        "parameters": {
            "type": "object",
            "properties": {
                "page_index": {"type": "integer", "description": "页码。不传则自动翻页"},
                "page_size": {"type": "integer", "description": "每页条数，默认 50"},
            },
        },
    },
    handler=_handle_query_user_todos,
    emoji="📌",
)