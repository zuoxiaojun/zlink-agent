"""Query YonSuite stock levels with warehouse/SKU aggregation."""

from collections import defaultdict

from ..utils import r2, tool_result


schema = {
    "name": "query_stock",
    "description": "查询 YonSuite 库存现存量。按仓库+SKU 聚合同物料不同批次的数据。支持按物料ID精确查询。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "warehouse": {"type": "string", "description": "仓库名称模糊匹配（可选）"},
            "sku": {"type": "string", "description": "SKU 编码或物料编码模糊匹配（可选）"},
            "product_id": {"type": "string", "description": "物料ID精确查询（推荐！从 query_products 结果中获取 id 字段），支持逗号分隔多个ID"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}


def handle(client, arguments: dict) -> dict:
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
        entry["currentQty"] = r2(entry["currentQty"])
        entry["availableQty"] = r2(entry["availableQty"])
        grand_current += entry["currentQty"]
        grand_available += entry["availableQty"]
        parsed.append(dict(entry))

    return tool_result(
        data=f"库存查询结果（{len(parsed)} 条，已按仓库+SKU聚合）", records=parsed,
        summary={"recordCount": len(parsed), "grandCurrentQty": r2(grand_current), "grandAvailableQty": r2(grand_available)},
    )
