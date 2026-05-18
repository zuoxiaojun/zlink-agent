"""Query YonSuite sale orders with optional date filtering and summary mode."""

from ..constants import SALE_STATUS_MAP
from ..paginate import paginate
from ..utils import r2, tool_result


schema = {
    "name": "query_sale_orders",
    "description": "查询 YonSuite 销售订单。返回已解析的 29 字段记录，含税额自动计算、状态中文映射、币种嵌套解析。is_sum=False 返回逐行明细（含物料详情），is_sum=True 返回按订单汇总。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD（可选）"},
            "date_to": {"type": "string", "description": "截止日期 YYYY-MM-DD（可选）"},
            "is_sum": {"type": "boolean", "description": "是否汇总模式，默认 false"},
            "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}


def handle(client, arguments: dict) -> dict:
    is_sum = arguments.get("is_sum", False)
    date_from = arguments.get("date_from") or None
    date_to = arguments.get("date_to") or None

    def fetch(pi, ps):
        result = client.query_sale_orders(
            page_index=pi, page_size=ps, isSum=is_sum,
            date_from=date_from, date_to=date_to,
        )
        return result.get("data", {}).get("recordList", [])

    records = paginate(arguments, 500, fetch)
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
            "qty": r2(r.get("qty", 0)), "unitPrice": r2(r.get("oriTaxUnitPrice", 0)),
            "oriSum": r2(ori_sum), "tax": r2(calc_tax),
            "department": r.get("saleDepartmentId_name", ""),
            "salesman": r.get("corpContactUserName", ""),
            "warehouse": r.get("stockName", "") or None,
        })

    return tool_result(
        data=f"销售订单查询结果（{len(parsed)} 条）", records=parsed,
        summary={"recordCount": len(parsed), "grandTotal": r2(grand_total), "grandTax": r2(grand_tax)},
    )
