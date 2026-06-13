"""Query YonSuite vendors with fuzzy name search."""

from ..paginate import paginate
from ..utils import parse_name, tool_result

schema = {
    "name": "query_vendors",
    "description": "查询 YonSuite 供应商档案。支持按供应商名称模糊搜索。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "vendor_name": {"type": "string", "description": "供应商名称（模糊匹配）"},
            "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}


def handle(client, arguments: dict) -> dict:
    vendor_name = (arguments.get("vendor_name") or "").strip() or None

    def fetch(pi, ps):
        return client.query_vendors(page_index=pi, page_size=ps).get("data", {}).get("recordList", [])

    records = paginate(arguments, 500, fetch)
    if vendor_name:
        name_lower = vendor_name.lower()
        records = [r for r in records if name_lower in parse_name(r.get("name")).lower()]

    parsed = []
    for r in records:
        parsed.append(
            {
                "id": r.get("id", ""),
                "code": r.get("code", ""),
                "name": parse_name(r.get("name")),
                "vendorClass": r.get("vendorClassName", ""),
                "contactPerson": r.get("personOfContact", ""),
                "phone": r.get("mobilePhone", "") or r.get("telephone", ""),
                "bankName": r.get("bankName", ""),
                "bankAccount": r.get("bankAccount", ""),
            }
        )

    return tool_result(
        data=f"供应商查询结果（{len(parsed)} 条）",
        records=parsed,
        summary={"recordCount": len(parsed)},
    )
