"""High-level YonSuite query tools.

Each tool wraps a specific YonSuiteClient query method with proper
field parsing, tax calculation, status mapping, and clean JSON output.
Eliminates the need for LLM-written YonSuiteClient code.
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


def _r2(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return 0.0


# ── Status maps ──────────────────────────────────────────────────────────

SALE_STATUS_MAP = {
    "CONFIRMORDER": "开立", "DELIVERY_PART": "部分发货",
    "DELIVERY_TAKE_PART": "部分发货待收货", "DELIVERGOODS": "待发货",
    "TAKEDELIVERY": "待收货", "ENDORDER": "已完成", "OPPOSE": "已取消",
    "APPROVING": "审批中",
}

PURCHASE_STATUS_MAP = {0: "开立", 1: "已审核", 2: "已关闭", 3: "审核中"}

PURCHASE_ARRIVED_MAP = {1: "到货完成", 2: "未到货", 3: "部分到货", 4: "到货完成"}
PURCHASE_INWH_MAP = {1: "入库完成", 2: "未入库", 3: "部分入库", 4: "入库结束"}
PURCHASE_INVOICE_MAP = {1: "开票完成", 2: "未开票", 3: "部分开票", 4: "开票结束"}

PROD_STATUS_MAP = {0: "开立", 1: "已审核", 2: "已关闭", 3: "审核中", 4: "已锁定", 5: "已开工", 6: "生产完工"}
PROD_VERIFY_MAP = {0: "待审批", 1: "已审批"}
PROD_STOCK_MAP = {0: "未入库", 1: "部分入库", 2: "全部入库"}
PROD_FINISHED_MAP = {0: "未申请", 1: "已申请", 2: "已审批"}
PROD_MATERIAL_MAP = {0: "未领料", 1: "部分领料", 2: "已领料"}
PROD_HOLD_MAP = {0: "正常", 1: "挂起"}

TODO_TYPE_MAP = {"SCMSA": "销售订单", "SACT": "销售合同", "RBSM": "报销单", "PGRM": "项目管理"}

OPPT_STATE_MAP = {0: "进行中", 1: "暂停", 2: "作废", 3: "关闭"}
OPPT_WIN_LOSE_MAP = {0: "赢单", 1: "丢单", 2: "未定", 3: "部分赢单"}


# ═══════════════════════════════════════════════════════════════════════════
# 1. query_sale_orders
# ═══════════════════════════════════════════════════════════════════════════

def _handle_sale_orders(args: dict) -> str:
    client = _get_client()
    if client is None:
        return tool_error("YonSuite 未配置，请在设置中配置 App Key、App Secret 和 Tenant ID")

    date_from = args.get("date_from", "").strip() or None
    date_to = args.get("date_to", "").strip() or None
    is_sum = args.get("is_sum", False)
    page_index = args.get("page_index", 1)
    page_size = args.get("page_size", 500)

    try:
        result = client.query_sale_orders(
            page_index=page_index, page_size=page_size,
            isSum=is_sum, date_from=date_from, date_to=date_to,
        )
        records = result.get("data", {}).get("recordList", [])
    except Exception as e:
        return tool_error(f"查询销售订单失败: {e}")

    parsed = []
    grand_total = 0.0
    grand_tax = 0.0

    for r in records:
        code = r.get("code", "")
        if code == "合计":
            continue

        ori_sum = float(r.get("oriSum", 0) or 0)
        tax_rate = float(r.get("taxRate", 0) or 0)
        calc_tax = ori_sum / (1 + tax_rate / 100) * (tax_rate / 100) if tax_rate > 0 else 0.0
        grand_total += ori_sum
        grand_tax += calc_tax

        order_prices = r.get("orderPrices", {}) or {}
        currency = (order_prices.get("originalName") or "") if isinstance(order_prices, dict) else ""

        status_raw = r.get("nextStatus", "") or ""
        status_cn = SALE_STATUS_MAP.get(status_raw, status_raw)

        parsed.append({
            "code": code,
            "vouchdate": str(r.get("vouchdate", ""))[:10],
            "auditDate": str(r.get("auditDate", "") or "")[:10],
            "salesOrg": r.get("salesOrgId_name", ""),
            "transactionType": r.get("transactionTypeId_name", ""),
            "customer": r.get("agentId_name", ""),
            "department": r.get("saleDepartmentId_name", ""),
            "salesman": r.get("corpContactUserName", ""),
            "status": status_cn,
            "statusCode": status_raw,
            "lineno": int(float(r.get("lineno", 0) or 0)),
            "skuCode": r.get("skuCode", ""),
            "skuName": r.get("skuName", ""),
            "qty": _r2(r.get("qty", 0)),
            "unit": r.get("productUnitName", ""),
            "mainUnit": r.get("qtyName", ""),
            "currency": currency or "CNY",
            "unitPrice": _r2(r.get("oriTaxUnitPrice", 0)),
            "oriSum": _r2(ori_sum),
            "taxRate": str(r.get("taxRate", "")),
            "tax": _r2(calc_tax),
            "sendDate": str(r.get("sendDate", "") or "")[:10],
            "stockOrg": r.get("stockOrgId_name", ""),
            "warehouse": r.get("stockName", "") or None,
            "sentQty": _r2(r.get("sendQty", 0)),
            "outStockAmount": _r2(r.get("totalOutStockOriMoney", 0)),
            "invoiceQty": _r2(r.get("invoiceQty", 0)),
            "invoiceAmount": _r2(r.get("invoiceOriSum", 0)),
            "outStockConfirmQty": _r2(r.get("totalOutStockQuantity", 0)),
        })

    summary = {
        "recordCount": len(parsed),
        "grandTotal": _r2(grand_total),
        "grandTax": _r2(grand_tax),
        "dateFrom": date_from,
        "dateTo": date_to,
        "isSum": is_sum,
    }

    return tool_result(data=f"销售订单查询结果（{len(parsed)} 条）", records=parsed, summary=summary)


SALE_ORDERS_SCHEMA = {
    "name": "query_sale_orders",
    "description": (
        "查询 YonSuite 销售订单。返回已解析的 29 字段记录，含税额自动计算、状态中文映射、币种嵌套解析。"
        "is_sum=False 返回逐行明细（含物料详情），is_sum=True 返回按订单汇总（用于统计）。"
        "返回字段：code(单据编号), vouchdate(日期), customer(客户), skuCode/skuName(物料), "
        "qty(数量), unitPrice(含税单价), oriSum(含税金额), tax(税额), status(状态中文), "
        "department(部门), salesman(业务员), warehouse(发货仓库) 等。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD（可选）"},
            "date_to": {"type": "string", "description": "截止日期 YYYY-MM-DD（可选）"},
            "is_sum": {"type": "boolean", "description": "是否汇总模式，默认 false（逐行明细）"},
            "page_index": {"type": "integer", "description": "页码，默认 1"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# 2. query_purchase_orders
# ═══════════════════════════════════════════════════════════════════════════

def _handle_purchase_orders(args: dict) -> str:
    client = _get_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    date_from = args.get("date_from", "").strip() or None
    date_to = args.get("date_to", "").strip() or None
    page_index = args.get("page_index", 1)
    page_size = args.get("page_size", 500)

    try:
        if date_from and date_to:
            import urllib.parse
            token = client.get_access_token()
            url = f"{client.purchase.gateway_url}{client.purchase.base_path}/list?access_token={urllib.parse.quote(token)}"
            body = {
                "pageIndex": page_index, "pageSize": page_size, "isSum": True,
                "simpleVOs": [{"field": "vouchdate", "op": "between", "value1": date_from, "value2": date_to}],
                "queryOrders": [{"field": "vouchdate", "order": "desc"}],
            }
            result = client.purchase._http_post_raw(url, body)
        else:
            result = client.query_purchase_orders(page_index=page_index, page_size=page_size)
        records = result.get("data", {}).get("recordList", [])
    except Exception as e:
        return tool_error(f"查询采购订单失败: {e}")

    parsed = []
    grand_total = 0.0

    for r in records:
        code = r.get("code", "")
        if code == "合计":
            continue

        list_ori_sum = float(r.get("listOriSum", 0) or 0)
        grand_total += list_ori_sum
        status_raw = r.get("status", 0)
        arrived = r.get("purchaseOrders_arrivedStatus", 0)
        in_wh = r.get("purchaseOrders_inWHStatus", 0)
        invoice = r.get("purchaseOrders_invoiceStatus", 0)

        parsed.append({
            "code": code,
            "vouchdate": str(r.get("vouchdate", ""))[:10],
            "demandOrg": r.get("demandOrg_name", ""),
            "transactionType": r.get("bustype_name", ""),
            "vendor": r.get("vendor_name", ""),
            "invoiceVendor": r.get("invoiceVendor_name", ""),
            "creator": r.get("creator", ""),
            "department": r.get("department_name", ""),
            "buyer": r.get("operator_name", ""),
            "status": PURCHASE_STATUS_MAP.get(status_raw, str(status_raw)),
            "statusCode": status_raw,
            "lineno": int(float(r.get("lineno", 0) or 0)),
            "materialCode": r.get("product_cCode", ""),
            "materialName": r.get("product_cName", ""),
            "qty": _r2(r.get("subQty", 0)),
            "unit": r.get("unit_name", ""),
            "unitPrice": _r2(r.get("oriTaxUnitPrice", 0)),
            "listOriSum": _r2(list_ori_sum),
            "taxRate": str(r.get("listTaxRate", "")),
            "tax": _r2(r.get("listOriTax", 0)),
            "planArrivalDate": str(r.get("planArrivalDate", "") or "")[:10],
            "receiveOrg": r.get("inOrg_name", ""),
            "invoiceOrg": r.get("inInvoiceOrg_name", ""),
            "arrivedQty": _r2(r.get("purchaseOrders_totalConfirmInQty", 0)),
            "inWhQty": _r2(r.get("purchaseOrders_totalInSubqty", 0)),
            "invoiceQty": _r2(r.get("purchaseOrders_totalInvoiceQty", 0)),
            "arrivedStatus": PURCHASE_ARRIVED_MAP.get(arrived, str(arrived)),
            "inWhStatus": PURCHASE_INWH_MAP.get(in_wh, str(in_wh)),
            "invoiceStatus": PURCHASE_INVOICE_MAP.get(invoice, str(invoice)),
            "exchRate": str(r.get("exchRate", "")),
            "bizFlow": r.get("bizFlow_name", ""),
            "currency": r.get("currency_name", ""),
            "natCurrency": r.get("natCurrency_name", ""),
        })

    return tool_result(
        data=f"采购订单查询结果（{len(parsed)} 条）",
        records=parsed,
        summary={"recordCount": len(parsed), "grandTotal": _r2(grand_total), "dateFrom": date_from, "dateTo": date_to},
    )


PURCHASE_ORDERS_SCHEMA = {
    "name": "query_purchase_orders",
    "description": (
        "查询 YonSuite 采购订单。返回已解析的 32 字段记录，含状态中文映射（到货/入库/发票状态）。"
        "支持日期过滤（date_from + date_to 同时传才生效）。"
        "返回字段：code(订单编号), vendor(供应商), materialCode/materialName(物料), "
        "qty(采购数量), unitPrice(含税单价), listOriSum(含税金额), tax(税额), "
        "arrivedStatus(到货状态), inWhStatus(入库状态), invoiceStatus(发票状态) 等。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD，需与 date_to 同时传"},
            "date_to": {"type": "string", "description": "截止日期 YYYY-MM-DD，需与 date_from 同时传"},
            "page_index": {"type": "integer", "description": "页码，默认 1"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# 3. query_production_orders
# ═══════════════════════════════════════════════════════════════════════════

def _handle_production_orders(args: dict) -> str:
    client = _get_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    date_from = args.get("date_from", "").strip() or None
    date_to = args.get("date_to", "").strip() or None
    page_index = args.get("page_index", 1)
    page_size = args.get("page_size", 500)

    try:
        result = client.query_production_orders(page_index=page_index, page_size=page_size)
        records = result.get("data", {}).get("recordList", [])
    except Exception as e:
        return tool_error(f"查询生产订单失败: {e}")

    # Client-side date filtering (API doesn't support date_from/date_to)
    if date_from or date_to:
        filtered = []
        for r in records:
            vd = str(r.get("vouchdate", ""))[:10]
            if date_from and vd < date_from:
                continue
            if date_to and vd > date_to:
                continue
            filtered.append(r)
        records = filtered

    parsed = []
    for r in records:
        code = r.get("code", "")
        if code == "合计":
            continue

        # Skip extra fields that the skill filters out
        skip_keys = {"物料SKU编码", "物料SKU名称", "自由项特征组"}
        if code in skip_keys:
            continue

        status_raw = r.get("status", 0)
        stock_raw = r.get("OrderProduct_stockStatus", 0)
        hold_raw = r.get("OrderProduct_isHold", 0)

        parsed.append({
            "code": code,
            "factory": r.get("orgName", ""),
            "transactionType": r.get("transTypeName", ""),
            "vouchdate": str(r.get("vouchdate", ""))[:10],
            "createTime": str(r.get("createTime", ""))[:19],
            "creator": r.get("creator", ""),
            "auditTime": str(r.get("auditTime", ""))[:19],
            "verifyState": PROD_VERIFY_MAP.get(r.get("verifystate", 0), ""),
            "status": PROD_STATUS_MAP.get(status_raw, str(status_raw)),
            "statusCode": status_raw,
            "department": r.get("departmentName", ""),
            "lineno": int(float(r.get("OrderProduct_lineno", 0) or 0)),
            "materialCode": r.get("OrderProduct_productCode", ""),
            "materialName": r.get("OrderProduct_productName", ""),
            "qty": _r2(r.get("OrderProduct_quantity", 0)),
            "mainUnit": r.get("OrderProduct_mainUnitName", ""),
            "auxQty": _r2(r.get("OrderProduct_auxiliaryQuantity", 0)),
            "completedQty": _r2(r.get("OrderProduct_completedQuantity", 0)),
            "incomingQty": _r2(r.get("OrderProduct_incomingQuantity", 0) or r.get("cfmIncomingQty", 0)),
            "startDate": str(r.get("OrderProduct_startDate", ""))[:10],
            "finishDate": str(r.get("OrderProduct_finishDate", ""))[:10],
            "stockStatus": PROD_STOCK_MAP.get(stock_raw, str(stock_raw)),
            "finishedWorkStatus": PROD_FINISHED_MAP.get(r.get("OrderProduct_finishedWorkApplyStatus", 0), ""),
            "materialStatus": PROD_MATERIAL_MAP.get(r.get("OrderProduct_materialStatus", 0), ""),
            "holdStatus": PROD_HOLD_MAP.get(hold_raw, str(hold_raw)),
        })

    return tool_result(
        data=f"生产订单查询结果（{len(parsed)} 条）",
        records=parsed,
        summary={"recordCount": len(parsed), "dateFrom": date_from, "dateTo": date_to},
    )


PRODUCTION_ORDERS_SCHEMA = {
    "name": "query_production_orders",
    "description": (
        "查询 YonSuite 生产订单。返回已解析的 24 字段记录，含状态中文映射。"
        "不支持服务端日期过滤，date_from/date_to 在客户端侧过滤。"
        "返回字段：code(单据编号), factory(工厂), materialCode/materialName(物料), "
        "qty(生产数量), completedQty(已完工数量), incomingQty(累计入库数量), "
        "status(订单状态), stockStatus(入库状态), materialStatus(领料状态) 等。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD，客户端侧过滤"},
            "date_to": {"type": "string", "description": "截止日期 YYYY-MM-DD，客户端侧过滤"},
            "page_index": {"type": "integer", "description": "页码，默认 1"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# 4. query_stock
# ═══════════════════════════════════════════════════════════════════════════

def _handle_stock(args: dict) -> str:
    client = _get_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    warehouse = args.get("warehouse", "").strip() or None
    sku = args.get("sku", "").strip() or None
    product_id_raw = args.get("product_id", "").strip() or None
    page_size = args.get("page_size", 500)

    # 处理 product_id：支持单个ID或逗号分隔的批量ID，传给API的product参数（服务端过滤）
    product_param = None
    if product_id_raw:
        ids = [pid.strip() for pid in product_id_raw.split(",") if pid.strip()]
        product_param = ids if len(ids) > 1 else ids[0]

    try:
        result = client.query_current_stock(page_size=page_size, product=product_param)
        raw_data = result.get("data", [])
        records = raw_data if isinstance(raw_data, list) else []
    except Exception as e:
        return tool_error(f"查询库存失败: {e}")

    if warehouse:
        records = [r for r in records if warehouse in str(r.get("warehouse_name", ""))]
    if sku and not product_param:
        records = [r for r in records if sku in str(r.get("productsku_code", "")) or sku in str(r.get("product_code", ""))]

    # Aggregate by warehouse + SKU (or material code if no SKU)
    from collections import defaultdict
    aggregated = defaultdict(lambda: {
        "productCode": "", "productName": "", "skuCode": "", "skuName": "",
        "warehouseCode": "", "warehouseName": "", "orgName": "",
        "unitCode": "", "unitName": "", "currentQty": 0.0, "availableQty": 0.0,
        "batchNo": "", "status": "合格",
    })

    for r in records:
        sku_code = str(r.get("productsku_code", "") or "").strip()
        mat_code = str(r.get("product_code", "") or "").strip()
        wh_name = str(r.get("warehouse_name", "") or "").strip()
        agg_key = (wh_name, sku_code) if sku_code else (wh_name, mat_code)
        entry = aggregated[agg_key]

        if entry["productCode"] == "":
            entry["productCode"] = mat_code
            entry["productName"] = str(r.get("product_name", "") or "")
            entry["skuCode"] = sku_code if sku_code else "(无SKU)"
            entry["skuName"] = str(r.get("productsku_name", "") or "")
            entry["warehouseCode"] = str(r.get("warehouse_code", "") or "")
            entry["warehouseName"] = wh_name
            entry["orgName"] = str(r.get("org_name", "") or "")
            entry["unitCode"] = str(r.get("product_unitCode", "") or "")
            entry["unitName"] = str(r.get("product_unitName", "") or "")
            entry["status"] = str(r.get("stockStatusDoc_statusName", "") or "合格")
            entry["batchNo"] = str(r.get("batchno", "") or "")

        entry["currentQty"] += float(r.get("currentqty", 0) or 0)
        entry["availableQty"] += float(r.get("availableqty", 0) or 0)

    parsed = []
    grand_current = 0.0
    grand_available = 0.0
    for _key, entry in sorted(aggregated.items()):
        entry["currentQty"] = _r2(entry["currentQty"])
        entry["availableQty"] = _r2(entry["availableQty"])
        grand_current += entry["currentQty"]
        grand_available += entry["availableQty"]
        parsed.append(dict(entry))

    return tool_result(
        data=f"库存查询结果（{len(parsed)} 条，已按仓库+SKU聚合）",
        records=parsed,
        summary={"recordCount": len(parsed), "grandCurrentQty": _r2(grand_current), "grandAvailableQty": _r2(grand_available)},
    )


STOCK_SCHEMA = {
    "name": "query_stock",
    "description": (
        "查询 YonSuite 库存现存量。按仓库+SKU 聚合同物料不同批次的数据。"
        "支持按物料ID(product_id)精确查询（推荐，服务端过滤最准确），"
        "也支持按 sku 或 warehouse 模糊匹配（客户端过滤）。"
        "返回字段：productCode/productName(物料), skuCode/skuName(SKU), "
        "warehouseName(仓库), orgName(库存组织), unitName(单位), "
        "currentQty(现存量), availableQty(可用量), batchNo(批次号), status(库存状态)。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "warehouse": {"type": "string", "description": "仓库名称模糊匹配（可选）"},
            "sku": {"type": "string", "description": "SKU 编码或物料编码模糊匹配（可选，无 product_id 时生效）"},
            "product_id": {"type": "string", "description": "物料ID精确查询（推荐！从 query_products 结果中获取 id 字段），支持单个ID如 1921567765125888，也支持逗号分隔的多个ID如 1921567765125888,1921567765125889。服务端过滤，最准确高效"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# 5. query_user_todos
# ═══════════════════════════════════════════════════════════════════════════

def _handle_user_todos(args: dict) -> str:
    client = _get_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    page_no = args.get("page_no", 1)
    page_size = args.get("page_size", 50)

    try:
        result = client.query_user_todos(page_no=page_no, page_size=page_size)
        items = result.get("data", [])
    except Exception as e:
        return tool_error(f"查询待办失败: {e}")

    import re
    parsed = []
    for item in items:
        rich_text = item.get("richText", "") or ""
        rich_text_clean = re.sub(r"<[^>]+>", "", rich_text).strip()

        title = item.get("title", "")
        type_name = item.get("typeName", "")
        src = item.get("approveSource", "") or ""
        service_code = item.get("serviceCode", "") or ""

        # Type label logic from SKILL.md
        if type_name == "iKM" or "iKM" in title:
            type_label = "iKM知识申请"
        elif src in TODO_TYPE_MAP:
            type_label = TODO_TYPE_MAP[src]
        elif "expense" in service_code or "znbzbx" in service_code:
            type_label = "报销单"
        elif "order" in service_code:
            type_label = "销售订单"
        elif "salescontract" in service_code:
            type_label = "销售合同"
        else:
            type_label = title or src

        ts = item.get("commitTsLong", 0)
        from datetime import datetime
        commit_time = datetime.fromtimestamp(int(str(ts)[:10])).strftime("%Y-%m-%d %H:%M:%S") if ts else ""

        parsed.append({
            "title": title,
            "typeLabel": type_label,
            "typeName": type_name,
            "content": (item.get("content", "") or "").strip(),
            "richText": rich_text_clean,
            "doneStatus": item.get("doneStatus", 0),
            "commitUserName": item.get("commitUserName", ""),
            "commitTime": commit_time,
            "approveSource": src,
            "taskName": item.get("businessData", {}).get("taskName") if isinstance(item.get("businessData"), dict) else "",
            "webUrl": item.get("webUrl", ""),
            "mUrl": item.get("mUrl", ""),
        })

    return tool_result(
        data=f"待办查询结果（{len(parsed)} 条）",
        records=parsed,
        summary={"recordCount": len(parsed), "pageNo": page_no},
    )


TODOS_SCHEMA = {
    "name": "query_user_todos",
    "description": (
        "查询 YonSuite 用户待办事项。返回已解析的待办列表，含 richText 清洗、单据类型自动映射。"
        "接口只返回待处理数据（doneStatus=0），不返回已处理。"
        "返回字段：title(标题), typeLabel(单据类型中文), content(文本内容), "
        "richText(清洗后富文本), commitUserName(提交人), commitTime(提交时间), "
        "taskName(当前环节), webUrl(PC审批链接), approveSource(来源系统)。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "page_no": {"type": "integer", "description": "页码，默认 1"},
            "page_size": {"type": "integer", "description": "每页条数，默认 50"},
        },
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# 6. query_opportunities
# ═══════════════════════════════════════════════════════════════════════════

def _handle_opportunities(args: dict) -> str:
    client = _get_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    oppt_state = args.get("oppt_state", "") or None
    win_lose_state = args.get("win_lose_state", "") or None
    date_from = args.get("date_from", "").strip() or None
    date_to = args.get("date_to", "").strip() or None
    page_index = args.get("page_index", 1)
    page_size = args.get("page_size", 500)

    try:
        result = client.query_opportunities(
            page_index=page_index, page_size=page_size,
            oppt_state=oppt_state, win_lose_state=win_lose_state,
            is_sum=True, date_from=date_from, date_to=date_to,
        )
        records = result.get("data", {}).get("recordList", [])
    except Exception as e:
        return tool_error(f"查询商机失败: {e}")

    parsed = []
    for r in records:
        oppt_state_val = r.get("opptState", 0)
        win_lose_val = r.get("winLoseOrderState", 0)

        expect_money = float(r.get("expectSignMoney", 0) or 0)
        win_money = float(r.get("winOrderMoney", 0) or 0)

        # Pick the right amount field based on state
        amount = win_money if win_lose_val == 0 else expect_money

        parsed.append({
            "id": r.get("id", ""),
            "code": r.get("code", ""),
            "name": r.get("name", ""),
            "opptState": OPPT_STATE_MAP.get(oppt_state_val, str(oppt_state_val)),
            "opptStateCode": oppt_state_val,
            "winLoseState": OPPT_WIN_LOSE_MAP.get(win_lose_val, str(win_lose_val)),
            "winLoseStateCode": win_lose_val,
            "amount": _r2(amount),
            "expectSignMoney": _r2(expect_money),
            "winOrderMoney": _r2(win_money) if win_lose_val == 0 else None,
            "winOrderDate": r.get("winOrderDate", ""),
            "customerName": r.get("customer_name", ""),
            "salesman": r.get("ower_name", ""),
            "department": r.get("dept_name", ""),
            "stageName": r.get("opptStage_name", ""),
            "createDate": r.get("createDate", ""),
            "createTime": r.get("createTime", ""),
        })

    return tool_result(
        data=f"商机查询结果（{len(parsed)} 条）",
        records=parsed,
        summary={"recordCount": len(parsed)},
    )


OPPORTUNITIES_SCHEMA = {
    "name": "query_opportunities",
    "description": (
        "查询 YonSuite CRM 商机列表。返回已解析的商机记录，自动处理 camelCase 字段映射、"
        "金额字段选择（进行中用 expectSignMoney，赢单用 winOrderMoney）。"
        "返回字段：code(商机编码), name(商机名称), opptState(状态), "
        "winLoseState(赢丢单状态), amount(金额), customerName(客户), "
        "salesman(业务员), stageName(阶段), createDate(创建日期) 等。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "oppt_state": {"type": "string", "description": "商机状态：0-进行中, 1-暂停, 2-作废, 3-关闭"},
            "win_lose_state": {"type": "string", "description": "赢丢单状态：0-赢单, 1-丢单, 2-未定, 3-部分赢单"},
            "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
            "date_to": {"type": "string", "description": "截止日期 YYYY-MM-DD"},
            "page_index": {"type": "integer", "description": "页码，默认 1"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}

# ═══════════════════════════════════════════════════════════════════════════
#  query_products
# ═══════════════════════════════════════════════════════════════════════════

def _handle_products(args: dict) -> str:
    client = _get_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    product_code = args.get("product_code", "").strip() or None
    product_name = args.get("product_name", "").strip() or None
    page_index = args.get("page_index", 1)
    page_size = args.get("page_size", 500)

    try:
        # If fuzzy name search is needed, pull all and filter client-side
        # because the API only supports exact/prefix matching on product_name
        if product_name:
            result = client.query_products(page_index=1, page_size=500)
            all_records = result.get("data", {}).get("recordList", [])
            # Client-side fuzzy match
            name_lower = product_name.lower()
            records = [r for r in all_records if name_lower in str(r.get("name", "")).lower()]
            if product_code:
                records = [r for r in records if r.get("code") == product_code]
        elif product_code:
            result = client.query_products(product_code=product_code, page_index=page_index, page_size=page_size)
            records = result.get("data", {}).get("recordList", [])
        else:
            result = client.query_products(page_index=page_index, page_size=page_size)
            records = result.get("data", {}).get("recordList", [])
    except Exception as e:
        return tool_error(f"查询物料失败: {e}")

    parsed = []
    for r in records:
        attr_map = {"1": "实物物料", "2": "虚拟物料"}
        real_attr = r.get("realProductAttribute", "")
        parsed.append({
            "id": r.get("id", ""),
            "code": r.get("code", ""),
            "name": r.get("name", ""),
            "model": r.get("model", ""),
            "productClass": r.get("manageClassName", "") or r.get("productClass", ""),
            "unitName": r.get("unitName", "") or r.get("unit_name", ""),
            "brand": r.get("brand", ""),
            "productType": attr_map.get(real_attr, real_attr),
            "status": "停用" if r.get("stopStatus") else "启用",
            "createTime": str(r.get("createTime", "") or r.get("create_date", ""))[:19],
            "creator": r.get("creator", ""),
        })

    return tool_result(
        data=f"物料查询结果（{len(parsed)} 条）",
        records=parsed,
        summary={"recordCount": len(parsed)},
    )


PRODUCTS_SCHEMA = {
    "name": "query_products",
    "description": (
        "查询 YonSuite 物料档案。支持按物料编码（精确）或物料名称（模糊）搜索。"
        "注意：API 仅支持名称前缀/精确匹配，本工具自动做全量拉取+客户端模糊匹配。"
        "返回字段：code(物料编码), name(物料名称), model(规格型号), "
        "productClass(物料分类), unitName(主单位), brand(品牌), "
        "productType(类型：实物/虚拟), status(状态), creator(创建人) 等。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "product_code": {"type": "string", "description": "物料编码（精确匹配）"},
            "product_name": {"type": "string", "description": "物料名称（模糊匹配，自动全量拉取后客户端过滤）"},
            "page_index": {"type": "integer", "description": "页码，默认 1（模糊匹配时忽略，始终全量）"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500（模糊匹配时忽略，始终全量）"},
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════
#  query_customers
# ═══════════════════════════════════════════════════════════════════════════

def _extract_name(raw):
    """Customer/vendor name field is a nested dict, not a string."""
    if isinstance(raw, dict):
        return raw.get("simplifiedName") or raw.get("name") or ""
    return str(raw) if raw else ""


def _handle_customers(args: dict) -> str:
    client = _get_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    customer_name = args.get("customer_name", "").strip() or None
    page_index = args.get("page_index", 1)
    page_size = args.get("page_size", 500)

    try:
        result = client.query_customers(page_index=page_index, page_size=page_size)
        records = result.get("data", {}).get("recordList", [])
    except Exception as e:
        return tool_error(f"查询客户失败: {e}")

    if customer_name:
        name_lower = customer_name.lower()
        records = [r for r in records if name_lower in _extract_name(r.get("name")).lower()]

    parsed = []
    for r in records:
        parsed.append({
            "id": r.get("id", ""),
            "code": r.get("code", ""),
            "name": _extract_name(r.get("name")),
            "customerClass": r.get("customerClassName", ""),
            "contactPerson": r.get("personOfContact", ""),
            "phone": r.get("mobilePhone", "") or r.get("telephone", ""),
            "address": r.get("address", ""),
            "status": r.get("status", ""),
        })

    return tool_result(
        data=f"客户查询结果（{len(parsed)} 条）",
        records=parsed,
        summary={"recordCount": len(parsed)},
    )


CUSTOMERS_SCHEMA = {
    "name": "query_customers",
    "description": (
        "查询 YonSuite 客户档案。支持按客户名称模糊搜索（客户端过滤）。"
        "返回字段：code(客户编码), name(客户名称), customerClass(客户分类), "
        "contactPerson(联系人), phone(电话), address(地址), status(状态) 等。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "customer_name": {"type": "string", "description": "客户名称（模糊匹配，不传则返回全部）"},
            "page_index": {"type": "integer", "description": "页码，默认 1"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════
#  query_vendors
# ═══════════════════════════════════════════════════════════════════════════

def _handle_vendors(args: dict) -> str:
    client = _get_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    vendor_name = args.get("vendor_name", "").strip() or None
    page_index = args.get("page_index", 1)
    page_size = args.get("page_size", 500)

    try:
        result = client.query_vendors(page_index=page_index, page_size=page_size)
        records = result.get("data", {}).get("recordList", [])
    except Exception as e:
        return tool_error(f"查询供应商失败: {e}")

    if vendor_name:
        name_lower = vendor_name.lower()
        records = [r for r in records if name_lower in _extract_name(r.get("name")).lower()]

    parsed = []
    for r in records:
        parsed.append({
            "id": r.get("id", ""),
            "code": r.get("code", ""),
            "name": _extract_name(r.get("name")),
            "vendorClass": r.get("vendorClassName", ""),
            "contactPerson": r.get("personOfContact", ""),
            "phone": r.get("mobilePhone", "") or r.get("telephone", ""),
            "address": r.get("address", ""),
            "bankName": r.get("bankName", ""),
            "bankAccount": r.get("bankAccount", ""),
            "status": r.get("status", ""),
        })

    return tool_result(
        data=f"供应商查询结果（{len(parsed)} 条）",
        records=parsed,
        summary={"recordCount": len(parsed)},
    )


VENDORS_SCHEMA = {
    "name": "query_vendors",
    "description": (
        "查询 YonSuite 供应商档案。支持按供应商名称模糊搜索（客户端过滤）。"
        "返回字段：code(供应商编码), name(供应商名称), vendorClass(供应商分类), "
        "contactPerson(联系人), phone(电话), bankName(开户行), bankAccount(银行账号) 等。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "vendor_name": {"type": "string", "description": "供应商名称（模糊匹配，不传则返回全部）"},
            "page_index": {"type": "integer", "description": "页码，默认 1"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════
#  query_vouchers
# ═══════════════════════════════════════════════════════════════════════════

def _handle_vouchers(args: dict) -> str:
    client = _get_client()
    if client is None:
        return tool_error("YonSuite 未配置")

    date_from = args.get("date_from", "").strip() or None
    date_to = args.get("date_to", "").strip() or None
    accbook_code = args.get("accbook_code", "").strip() or None
    period_start = args.get("period_start", "").strip() or None
    period_end = args.get("period_end", "").strip() or None
    page_index = args.get("page_index", 1)
    page_size = args.get("page_size", 500)

    # Build kwargs for query_vouchers
    kwargs = {}
    if date_from:
        kwargs["voucher_date_start"] = date_from
    if date_to:
        kwargs["voucher_date_end"] = date_to
    if period_start:
        kwargs["period_start"] = period_start
    if period_end:
        kwargs["period_end"] = period_end
    if accbook_code:
        kwargs["accbook_code"] = accbook_code

    try:
        # Use parsed method which flattens header+body and handles money rounding
        result = client.voucher.query_vouchers_parsed(
            client.get_access_token(),
            page_size=page_size,
            page_index=page_index,
            **kwargs,
        )
        records = result.get("records", [])
    except Exception as e:
        return tool_error(f"查询凭证失败: {e}")

    return tool_result(
        data=f"凭证查询结果（{len(records)} 条）",
        records=records,
        summary={
            "recordCount": result.get("recordCount", len(records)),
            "pageIndex": result.get("pageIndex", 1),
            "pageSize": result.get("pageSize", page_size),
        },
    )


VOUCHERS_SCHEMA = {
    "name": "query_vouchers",
    "description": (
        "查询 YonSuite 财务凭证。支持按日期、会计期间、账簿过滤。"
        "返回字段：凭证号, 凭证字, 凭证类型, 凭证状态, 凭证日期, "
        "会计期间, 制单人, 借方总额, 贷方总额, 分录数, 来源系统 等。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date_from": {"type": "string", "description": "凭证起始日期 YYYY-MM-DD"},
            "date_to": {"type": "string", "description": "凭证截止日期 YYYY-MM-DD"},
            "accbook_code": {"type": "string", "description": "账簿编码（可从 query_accbooks 获取）"},
            "period_start": {"type": "string", "description": "会计期间起始 YYYY-MM"},
            "period_end": {"type": "string", "description": "会计期间截止 YYYY-MM"},
            "page_index": {"type": "integer", "description": "页码，默认 1"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}


# ── Register all ──────────────────────────────────────────────────────────

registry.register(name="query_sale_orders", toolset="yonsuite", schema=SALE_ORDERS_SCHEMA, handler=_handle_sale_orders, emoji="📊")
registry.register(name="query_purchase_orders", toolset="yonsuite", schema=PURCHASE_ORDERS_SCHEMA, handler=_handle_purchase_orders, emoji="📦")
registry.register(name="query_production_orders", toolset="yonsuite", schema=PRODUCTION_ORDERS_SCHEMA, handler=_handle_production_orders, emoji="🏭")
registry.register(name="query_stock", toolset="yonsuite", schema=STOCK_SCHEMA, handler=_handle_stock, emoji="📦")
registry.register(name="query_user_todos", toolset="yonsuite", schema=TODOS_SCHEMA, handler=_handle_user_todos, emoji="📋")
registry.register(name="query_opportunities", toolset="yonsuite", schema=OPPORTUNITIES_SCHEMA, handler=_handle_opportunities, emoji="💼")
registry.register(name="query_products", toolset="yonsuite", schema=PRODUCTS_SCHEMA, handler=_handle_products, emoji="📦")
registry.register(name="query_customers", toolset="yonsuite", schema=CUSTOMERS_SCHEMA, handler=_handle_customers, emoji="🏢")
registry.register(name="query_vendors", toolset="yonsuite", schema=VENDORS_SCHEMA, handler=_handle_vendors, emoji="🏭")
registry.register(name="query_vouchers", toolset="yonsuite", schema=VOUCHERS_SCHEMA, handler=_handle_vouchers, emoji="🧾")
