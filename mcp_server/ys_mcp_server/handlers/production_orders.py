"""Query YonSuite production orders with client-side date filtering."""

from ..constants import PROD_STATUS_MAP, PROD_STOCK_MAP
from ..paginate import paginate
from ..utils import r2, tool_result

schema = {
    "name": "query_production_orders",
    "description": "查询 YonSuite 生产订单。返回已解析的 24 字段记录，含状态中文映射。date_from/date_to 在客户端侧过滤。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD，客户端侧过滤"},
            "date_to": {"type": "string", "description": "截止日期 YYYY-MM-DD，客户端侧过滤"},
            "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}


def handle(client, arguments: dict) -> dict:
    date_from = arguments.get("date_from") or None
    date_to = arguments.get("date_to") or None

    def fetch(pi, ps):
        return client.query_production_orders(page_index=pi, page_size=ps).get("data", {}).get("recordList", [])

    records = paginate(arguments, 500, fetch)
    if date_from or date_to:
        records = [
            r
            for r in records
            if (
                (not date_from or str(r.get("vouchdate", ""))[:10] >= date_from)
                and (not date_to or str(r.get("vouchdate", ""))[:10] <= date_to)
            )
        ]

    SKIP_CODES = {"合计", "物料SKU编码", "物料SKU名称", "自由项特征组"}
    parsed = []
    for r in records:
        if r.get("code") in SKIP_CODES:
            continue
        parsed.append(
            {
                "code": r.get("code", ""),
                "factory": r.get("orgName", ""),
                "vouchdate": str(r.get("vouchdate", ""))[:10],
                "status": PROD_STATUS_MAP.get(r.get("status", 0), ""),
                "materialCode": r.get("OrderProduct_productCode", ""),
                "materialName": r.get("OrderProduct_productName", ""),
                "qty": r2(r.get("OrderProduct_quantity", 0)),
                "completedQty": r2(r.get("OrderProduct_completedQuantity", 0)),
                "incomingQty": r2(r.get("OrderProduct_incomingQuantity", 0) or r.get("cfmIncomingQty", 0)),
                "stockStatus": PROD_STOCK_MAP.get(r.get("OrderProduct_stockStatus", 0), ""),
            }
        )

    return tool_result(
        data=f"生产订单查询结果（{len(parsed)} 条）",
        records=parsed,
        summary={"recordCount": len(parsed)},
    )
