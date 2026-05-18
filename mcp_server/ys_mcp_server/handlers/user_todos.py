"""Query YonSuite user todos with parsed richText and type mapping."""

import re
from datetime import datetime

from ..constants import TODO_TYPE_MAP
from ..paginate import paginate
from ..utils import tool_result


schema = {
    "name": "query_user_todos",
    "description": "查询 YonSuite 用户待办事项。返回已解析的待办列表，含 richText 清洗、单据类型自动映射。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
            "page_size": {"type": "integer", "description": "每页条数，默认 50"},
        },
    },
}


def _classify_todo(item: dict) -> str:
    title = item.get("title", "")
    src = item.get("approveSource", "") or ""
    service_code = item.get("serviceCode", "") or ""
    if "iKM" in title:
        return "iKM知识申请"
    if src in TODO_TYPE_MAP:
        return TODO_TYPE_MAP[src]
    if "expense" in service_code or "znbzbx" in service_code:
        return "报销单"
    if "order" in service_code:
        return "销售订单"
    if "salescontract" in service_code:
        return "销售合同"
    return title or src


def handle(client, arguments: dict) -> dict:
    def fetch(pi, ps):
        result = client.query_user_todos(page_no=pi, page_size=ps)
        return result.get("data", [])

    items = paginate(arguments, 50, fetch)
    parsed = []
    for item in items:
        rich_text = re.sub(r"<[^>]+>", "", item.get("richText", "") or "").strip()
        ts = item.get("commitTsLong", 0)
        commit_time = datetime.fromtimestamp(int(str(ts)[:10])).strftime("%Y-%m-%d %H:%M:%S") if ts else ""
        parsed.append({
            "title": item.get("title", ""),
            "typeLabel": _classify_todo(item),
            "content": (item.get("content", "") or "").strip(),
            "richText": rich_text,
            "commitUserName": item.get("commitUserName", ""),
            "commitTime": commit_time,
            "taskName": item.get("businessData", {}).get("taskName") if isinstance(item.get("businessData"), dict) else "",
        })

    return tool_result(
        data=f"待办查询结果（{len(parsed)} 条）", records=parsed,
        summary={"recordCount": len(parsed)},
    )
