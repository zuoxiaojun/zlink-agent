"""Query YonSuite customers with fuzzy name search."""

from ..paginate import paginate
from ..utils import parse_name, tool_result

schema = {
    "name": "query_customers",
    "description": "查询 YonSuite 客户档案。支持按客户名称模糊搜索。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "customer_name": {"type": "string", "description": "客户名称（模糊匹配）"},
            "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}


def handle(client, arguments: dict) -> dict:
    customer_name = (arguments.get("customer_name") or "").strip() or None

    def fetch(pi, ps):
        return client.query_customers(page_index=pi, page_size=ps).get("data", {}).get("recordList", [])

    result = paginate(arguments, 500, fetch)
    if customer_name:
        name_lower = customer_name.lower()
        records = [r for r in result.records if name_lower in parse_name(r.get("name")).lower()]
    else:
        records = result.records

    parsed = []
    for r in records:
        parsed.append(
            {
                "id": r.get("id", ""),
                "code": r.get("code", ""),
                "name": parse_name(r.get("name")),
                "customerClass": r.get("customerClassName", ""),
                "contactPerson": r.get("personOfContact", ""),
                "phone": r.get("mobilePhone", "") or r.get("telephone", ""),
            }
        )

    return tool_result(
        data=f"客户查询结果（{len(parsed)} 条）",
        records=parsed,
        summary={"recordCount": len(parsed)},
    )
