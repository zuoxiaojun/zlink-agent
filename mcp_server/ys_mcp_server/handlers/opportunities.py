"""Query YonSuite CRM opportunities with state filtering."""

from ..constants import OPPT_STATE_MAP, OPPT_WIN_LOSE_MAP
from ..paginate import paginate
from ..utils import r2, tool_result

schema = {
    "name": "query_opportunities",
    "description": "查询 YonSuite CRM 商机列表。返回已解析的商机记录，自动处理金额字段选择。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "oppt_state": {
                "type": "string",
                "description": "商机状态：0-进行中, 1-暂停, 2-作废, 3-关闭",
            },
            "win_lose_state": {
                "type": "string",
                "description": "赢丢单状态：0-赢单, 1-丢单, 2-未定, 3-部分赢单",
            },
            "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
            "date_to": {"type": "string", "description": "截止日期 YYYY-MM-DD"},
            "page_index": {"type": "integer", "description": "页码。不传则自动翻页获取全部数据"},
            "page_size": {"type": "integer", "description": "每页条数，默认 500"},
        },
    },
}


def handle(client, arguments: dict) -> dict:
    oppt_state = arguments.get("oppt_state") or None
    win_lose_state = arguments.get("win_lose_state") or None
    date_from = arguments.get("date_from") or None
    date_to = arguments.get("date_to") or None

    def fetch(pi, ps):
        result = client.query_opportunities(
            page_index=pi,
            page_size=ps,
            oppt_state=oppt_state,
            win_lose_state=win_lose_state,
            is_sum=True,
            date_from=date_from,
            date_to=date_to,
        )
        return result.get("data", {}).get("recordList", [])

    records = paginate(arguments, 500, fetch)
    parsed = []
    for r in records:
        oppt_state_val = r.get("opptState", 0)
        win_lose_val = r.get("winLoseOrderState", 0)
        expect_money = float(r.get("expectSignMoney", 0) or 0)
        win_money = float(r.get("winOrderMoney", 0) or 0)
        amount = win_money if win_lose_val == 0 else expect_money
        parsed.append(
            {
                "code": r.get("code", ""),
                "name": r.get("name", ""),
                "opptState": OPPT_STATE_MAP.get(oppt_state_val, str(oppt_state_val)),
                "winLoseState": OPPT_WIN_LOSE_MAP.get(win_lose_val, str(win_lose_val)),
                "amount": r2(amount),
                "customerName": r.get("customer_name", ""),
                "salesman": r.get("ower_name", ""),
                "stageName": r.get("opptStage_name", ""),
            }
        )

    return tool_result(
        data=f"商机查询结果（{len(parsed)} 条）",
        records=parsed,
        summary={"recordCount": len(parsed)},
    )
