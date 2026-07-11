"""Query YonSuite stock levels — returns raw detail records with auto-pagination."""

from ..paginate import paginate
from ..utils import r2, tool_result

schema = {
    "name": "query_stock",
    "description": "查询 YonSuite 库存现存量，返回逐批次明细。支持按物料ID、仓库、SKU 过滤。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "product_id": {
                "type": "string",
                "description": "物料ID精确查询（从 query_products 结果中获取 id 字段），支持逗号分隔多个ID",
            },
            "warehouse": {"type": "string", "description": "仓库名称模糊匹配（可选）"},
            "sku": {"type": "string", "description": "SKU 编码或物料编码模糊匹配（可选）"},
            "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}


def handle(client, arguments: dict) -> dict:
    product_id_raw = (arguments.get("product_id") or "").strip() or None
    warehouse = (arguments.get("warehouse") or "").strip() or None
    sku = (arguments.get("sku") or "").strip() or None

    product_param = None
    if product_id_raw:
        ids = [pid.strip() for pid in product_id_raw.split(",") if pid.strip()]
        product_param = ids if len(ids) > 1 else ids[0]

    def fetch(pi, ps):
        result = client.query_current_stock(page_index=pi, page_size=ps, product=product_param)
        raw_data = result.get("data", [])
        return raw_data if isinstance(raw_data, list) else []

    result = paginate(arguments, 500, fetch)

    records = result.records
    if warehouse:
        records = [r for r in result.records if warehouse in str(r.get("warehouse_name", ""))]
    if sku and not product_param:
        records = [
            r
            for r in result.records
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
        parsed.append(
            {
                "productCode": r.get("product_code", ""),
                "productName": r.get("product_name", ""),
                "skuCode": (r.get("productsku_code", "") or "").strip() or None,
                "warehouseName": r.get("warehouse_name", ""),
                "orgName": r.get("org_name", ""),
                "unitName": r.get("product_unitName", ""),
                "currentQty": r2(cur),
                "availableQty": r2(avail),
            }
        )

    return tool_result(
        data=f"库存查询结果（{len(parsed)} 条）",
        records=parsed,
        note=result.note,
        summary={
            "recordCount": len(parsed),
            "grandCurrentQty": r2(grand_current),
            "grandAvailableQty": r2(grand_available),
        },
    )
