"""Query YonSuite financial vouchers with date/period/accbook filters."""

from ..paginate import paginate
from ..utils import tool_result

schema = {
    "name": "query_vouchers",
    "description": "查询 YonSuite 财务凭证。支持按日期、会计期间、账簿过滤。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "date_from": {"type": "string", "description": "凭证起始日期 YYYY-MM-DD"},
            "date_to": {"type": "string", "description": "凭证截止日期 YYYY-MM-DD"},
            "accbook_code": {"type": "string", "description": "账簿编码"},
            "period_start": {"type": "string", "description": "会计期间起始 YYYY-MM"},
            "period_end": {"type": "string", "description": "会计期间截止 YYYY-MM"},
            "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}


def handle(client, arguments: dict) -> dict:
    kwargs = {}
    for key, kw in [
        ("date_from", "voucher_date_start"),
        ("date_to", "voucher_date_end"),
        ("period_start", "period_start"),
        ("period_end", "period_end"),
        ("accbook_code", "accbook_code"),
    ]:
        val = (arguments.get(key) or "").strip() or None
        if val:
            kwargs[kw] = val

    def fetch(pi, ps):
        result = client.voucher.query_vouchers_parsed(
            client.get_access_token(),
            page_size=ps,
            page_index=pi,
            **kwargs,
        )
        return result.get("records", [])

    result = paginate(arguments, 500, fetch)
    return tool_result(
        data=f"凭证查询结果（{len(result.records)} 条）",
        records=result.records,
        note=result.note,
        summary={"recordCount": len(result.records)},
    )
