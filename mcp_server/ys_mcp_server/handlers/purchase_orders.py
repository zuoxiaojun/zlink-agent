"""Query YonSuite purchase orders with date filtering."""

import urllib.parse

from ..constants import (
    PURCHASE_ARRIVED_MAP,
    PURCHASE_INVOICE_MAP,
    PURCHASE_INWH_MAP,
    PURCHASE_STATUS_MAP,
)
from ..paginate import paginate
from ..utils import r2, tool_result

schema = {
    "name": "query_purchase_orders",
    "description": "查询 YonSuite 采购订单。返回已解析的 32 字段记录，含状态中文映射（到货/入库/发票状态）。支持日期过滤。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
            "date_to": {"type": "string", "description": "截止日期 YYYY-MM-DD"},
            "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}


def handle(client, arguments: dict) -> dict:
    date_from = arguments.get("date_from") or None
    date_to = arguments.get("date_to") or None

    if date_from and date_to:

        def fetch(pi, ps):
            token = client.get_access_token()
            url = f"{client.purchase.gateway_url}{client.purchase.base_path}/list?access_token={urllib.parse.quote(token)}"
            body = {
                "pageIndex": pi,
                "pageSize": ps,
                "isSum": True,
                "simpleVOs": [{"field": "vouchdate", "op": "between", "value1": date_from, "value2": date_to}],
                "queryOrders": [{"field": "vouchdate", "order": "desc"}],
            }
            return client.purchase._http_post_raw(url, body).get("data", {}).get("recordList", [])
    else:

        def fetch(pi, ps):
            return client.query_purchase_orders(page_index=pi, page_size=ps).get("data", {}).get("recordList", [])

    result = paginate(arguments, 500, fetch)
    parsed = []
    grand_total = 0.0
    for r in result.records:
        if r.get("code") == "合计":
            continue
        list_ori_sum = float(r.get("listOriSum", 0) or 0)
        grand_total += list_ori_sum
        status_raw = r.get("status", 0)
        parsed.append(
            {
                "code": r.get("code", ""),
                "vouchdate": str(r.get("vouchdate", ""))[:10],
                "vendor": r.get("vendor_name", ""),
                "materialCode": r.get("product_cCode", ""),
                "materialName": r.get("product_cName", ""),
                "qty": r2(r.get("subQty", 0)),
                "unitPrice": r2(r.get("oriTaxUnitPrice", 0)),
                "listOriSum": r2(list_ori_sum),
                "tax": r2(r.get("listOriTax", 0)),
                "status": PURCHASE_STATUS_MAP.get(status_raw, str(status_raw)),
                "arrivedStatus": PURCHASE_ARRIVED_MAP.get(r.get("purchaseOrders_arrivedStatus", 0), ""),
                "inWhStatus": PURCHASE_INWH_MAP.get(r.get("purchaseOrders_inWHStatus", 0), ""),
                "invoiceStatus": PURCHASE_INVOICE_MAP.get(r.get("purchaseOrders_invoiceStatus", 0), ""),
            }
        )

    return tool_result(
        data=f"采购订单查询结果（{len(parsed)} 条）",
        records=parsed,
        note=result.note,
        summary={"recordCount": len(parsed), "grandTotal": r2(grand_total)},
    )
