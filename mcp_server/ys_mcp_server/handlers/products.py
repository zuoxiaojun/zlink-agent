"""Query YonSuite product/materials with code/name search."""

from ..paginate import paginate
from ..utils import tool_result

schema = {
    "name": "query_products",
    "description": "查询 YonSuite 物料档案。支持按物料编码（精确）或物料名称（模糊）搜索。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "product_code": {"type": "string", "description": "物料编码（精确匹配）"},
            "product_name": {"type": "string", "description": "物料名称（模糊匹配）"},
            "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}

ATTR_MAP = {"1": "实物物料", "2": "虚拟物料"}


def handle(client, arguments: dict) -> dict:
    product_code = (arguments.get("product_code") or "").strip() or None
    product_name = (arguments.get("product_name") or "").strip() or None

    def fetch(pi, ps):
        return (
            client.query_products(
                page_index=pi,
                page_size=ps,
                product_code=product_code if product_code else None,
            )
            .get("data", {})
            .get("recordList", [])
        )

    if product_name:
        result = paginate({}, 500, fetch)
        name_lower = product_name.lower()
        records = [r for r in result.records if name_lower in str(r.get("name", "")).lower()]
        if product_code:
            records = [r for r in result.records if r.get("code") == product_code]
    else:
        result = paginate(arguments, 500, fetch)
        records = result.records

    parsed = []
    for r in records:
        parsed.append(
            {
                "id": r.get("id", ""),
                "code": r.get("code", ""),
                "name": r.get("name", ""),
                "model": r.get("model", ""),
                "productClass": r.get("manageClassName", "") or r.get("productClass", ""),
                "unitName": r.get("unitName", "") or r.get("unit_name", ""),
                "brand": r.get("brand", ""),
                "productType": ATTR_MAP.get(r.get("realProductAttribute", ""), ""),
                "status": "停用" if r.get("stopStatus") else "启用",
            }
        )

    return tool_result(
        data=f"物料查询结果（{len(parsed)} 条）",
        records=parsed,
        note=result.note,
        summary={"recordCount": len(parsed)},
    )
