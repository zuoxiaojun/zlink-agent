"""
NC-MCP Server
=============
Oracle NC65 数据库 MCP Service，通过 stdio JSON-RPC 2.0 暴露查询工具。

工具列表：
- query_sales_order           -> 销售订单完整链路（含客户+物料名称）
- query_sales_order_by_code   -> 按单据号查询销售订单
- query_purchase_order        -> 采购订单完整链路（含供应商+物料名称）
- query_purchase_order_by_code -> 按订单编号查询采购订单
- query_customer              -> 客户基本信息查询
- query_supplier              -> 供应商基本信息查询
- query_material              -> 物料基本信息查询
- query_organization          -> 组织信息查询
- query_stock                 -> 现存量多维度查询（仓库/物料/批次/组织）
- list_business_tables        -> 列出已注册的业务表
- describe_business_table     -> 查看某张表的中文字段对照
- query_raw_sql               -> 执行任意只读 SQL（安全校验）
"""

import asyncio
import json
from collections.abc import Callable
from typing import Any

import mcp.types as types
import sqlparse
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .config import config
from .data_dictionary import ALL_TABLES
from .queries.customer import QUERIES as CUST_QUERIES
from .queries.material import QUERIES as MAT_QUERIES
from .queries.organization import QUERIES as ORG_QUERIES
from .queries.purchase_order import QUERIES as PO_QUERIES
from .queries.sales_order import QUERIES as SO_QUERIES
from .queries.stock import QUERIES as STOCK_QUERIES
from .queries.supplier import QUERIES as SUPP_QUERIES

QUERIES = {**SO_QUERIES, **PO_QUERIES, **CUST_QUERIES, **SUPP_QUERIES, **MAT_QUERIES, **ORG_QUERIES, **STOCK_QUERIES}

MAX_ROWS = config.MAX_ROWS


async def _run_db(func: Callable, *args: Any, **kwargs: Any) -> Any:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


def validate_select(sql: str) -> str:
    """校验 SQL 为只读查询（AST 级别校验）"""
    stripped = sql.strip().rstrip(";").strip()
    parsed = sqlparse.parse(stripped)
    if not parsed:
        raise ValueError("无法解析 SQL")

    for stmt in parsed:
        if stmt.get_type() not in ("SELECT", "UNKNOWN"):
            raise ValueError(f"只允许 SELECT 查询，检测到: {stmt.get_type()}")

    upper = stripped.upper()
    dangerous = [
        "INSERT ",
        "UPDATE ",
        "DELETE ",
        "MERGE ",
        "ALTER ",
        "DROP ",
        "TRUNCATE ",
        "CREATE ",
        "GRANT ",
        "REVOKE ",
        "EXEC ",
        "EXECUTE ",
        "CALL ",
        "INTO ",
        "COMMENT ",
    ]
    for kw in dangerous:
        if kw in (" " + upper + " "):
            raise ValueError(f"检测到危险关键词 {kw.strip()}，已拦截")

    return stripped


# ============ MCP Server ============
server = Server("nc-mcp")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    tools: list[types.Tool] = []

    for qname, qinfo in QUERIES.items():
        tools.append(
            types.Tool(
                name=f"query_{qname}",
                description=qinfo["description"],
                inputSchema={
                    "type": "object",
                    "properties": _query_params(qname),
                },
            )
        )

    tools.append(
        types.Tool(
            name="list_business_tables",
            description="列出 NC-MCP 已注册的所有业务表及中文字段数",
            inputSchema={"type": "object", "properties": {}},
        )
    )
    tools.append(
        types.Tool(
            name="describe_business_table",
            description="查看某张注册表的中文字段对照。输入表名，如 SO_SALEORDER",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "表名（大写），如 SO_SALEORDER",
                    }
                },
                "required": ["table_name"],
            },
        )
    )
    tools.append(
        types.Tool(
            name="query_raw_sql",
            description="执行任意只读 SELECT 查询。有安全校验，仅供高级使用。支持分页。",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SELECT 语句"},
                    "page": {"type": "integer", "description": "页码，从 1 开始（默认 1）"},
                    "page_size": {"type": "integer", "description": "每页行数，默认 50"},
                },
                "required": ["sql"],
            },
        )
    )

    return tools


def _add_pagination_params(params: dict[str, Any]) -> dict[str, Any]:
    """Add page/page_size pagination parameters to a params dict."""
    params["page"] = {
        "type": "integer",
        "description": "页码，从 1 开始（默认 1）。当返回结果标记「还有更多」时可递增 page 获取下一页",
    }
    params["page_size"] = {
        "type": "integer",
        "description": "每页行数，默认 {MAX_ROWS}，最大 {MAX_ROWS}",
    }
    return params


def _query_params(qname: str) -> dict[str, Any]:
    params = {
        "format": {
            "type": "string",
            "enum": ["text", "json"],
            "description": "输出格式：text（表格）或 json（结构化数据，适合图表分析），默认 text",
        }
    }
    if qname == "sales_order_by_code":
        params["billcode"] = {
            "type": "string",
            "description": "单据号，如 SO302020072500000001",
        }
        return _add_pagination_params(params)
    if qname == "purchase_order_by_code":
        params["billcode"] = {
            "type": "string",
            "description": "订单编号，如 CD2020072500000001",
        }
        return _add_pagination_params(params)
    if qname in ("sales_order", "purchase_order"):
        params["start_date"] = {
            "type": "string",
            "description": "开始日期，格式 YYYY-MM-DD（可选）",
        }
        params["end_date"] = {
            "type": "string",
            "description": "结束日期，格式 YYYY-MM-DD（可选）",
        }
        return _add_pagination_params(params)
    if qname in ("customer", "supplier", "material", "organization"):
        params["code"] = {
            "type": "string",
            "description": "编码（模糊搜索，可选）",
        }
        params["name"] = {
            "type": "string",
            "description": "名称（模糊搜索，可选）",
        }
        return _add_pagination_params(params)
    if qname == "stock":
        params["warehouse"] = {
            "type": "string",
            "description": "仓库主键（pk_stordoc，可选）",
        }
        params["material"] = {
            "type": "string",
            "description": "物料主键（pk_material，可选）",
        }
        params["batch"] = {
            "type": "string",
            "description": "批次号（模糊搜索，可选）",
        }
        params["org"] = {
            "type": "string",
            "description": "库存组织主键（pk_org，可选）",
        }
        return _add_pagination_params(params)
    return params


def _paginate_sql(sql: str, page: int, page_size: int) -> tuple[str, dict[str, int]]:
    """Wrap a SELECT SQL with Oracle 12c+ pagination (OFFSET/FETCH NEXT).

    Returns (paginated_sql, bind_params) where bind_params contains
    ``offset`` and ``limit`` values for the Oracle bind variables.
    """
    stripped = sql.strip().rstrip(";").strip()
    paginated = f"SELECT * FROM ({stripped}) OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"
    offset = (page - 1) * page_size
    limit = page_size
    return paginated, {"offset": offset, "limit": limit}


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if not name.startswith("query_") and name not in (
        "list_business_tables",
        "describe_business_table",
        "query_raw_sql",
    ):
        raise ValueError(f"未知工具: {name}")

    if name == "list_business_tables":
        lines = ["NC-MCP 已注册业务表：\n"]
        for tname, tinfo in ALL_TABLES.items():
            lines.append(f"  {tname:25s} -> {tinfo['name']}（{len(tinfo['fields'])} 个字段）")
        return [types.TextContent(type="text", text="\n".join(lines))]

    if name == "describe_business_table":
        tname = arguments["table_name"].upper()
        tinfo = ALL_TABLES.get(tname)
        if not tinfo:
            return [types.TextContent(type="text", text=f"未注册表: {tname}")]
        lines = [f"{tname} -> {tinfo['name']}（{len(tinfo['fields'])} 个字段）\n"]
        for fname, fcn in tinfo["fields"].items():
            lines.append(f"  {fname:30s} -> {fcn}")
        return [types.TextContent(type="text", text="\n".join(lines))]

    if name == "query_raw_sql":
        sql = validate_select(arguments["sql"])
        page = max(1, arguments.get("page", 1))
        page_size = min(max(1, arguments.get("max_rows", 50)), MAX_ROWS)
        output_format = arguments.get("format", "text")

        def _q() -> str:
            import oracledb

            conn = oracledb.connect(**config.db_config)
            try:
                paginated_sql, bind_params = _paginate_sql(sql, page=page, page_size=page_size + 1)
                with conn.cursor() as cur:
                    cur.execute(paginated_sql, bind_params)
                    desc = cur.description
                    if desc is None:
                        return "（无返回列）"
                    cols = [str(d[0]) for d in desc]
                    rows: list[tuple] = cur.fetchall() or []
                    has_more = len(rows) > page_size
                    rows = rows[:page_size]
                    if output_format == "json":
                        return json.dumps([dict(zip(cols, row)) for row in rows], ensure_ascii=False, default=str)
                    return _fmt_result(rows, cols, page=page, page_size=page_size, has_more=has_more)
            finally:
                conn.close()

        result = await _run_db(_q)
        return [types.TextContent(type="text", text=result)]

    qname = name[len("query_") :]
    qinfo = QUERIES.get(qname)
    if not qinfo:
        raise ValueError(f"未知查询: {qname}")

    output_format = arguments.pop("format", "text")
    page = max(1, arguments.pop("page", 1))
    page_size = min(max(1, arguments.pop("page_size", MAX_ROWS)), MAX_ROWS)

    def _q() -> str:
        import oracledb

        conn = oracledb.connect(**config.db_config)
        try:
            with conn.cursor() as cur:
                sql, params = qinfo["handler"](**arguments)
                paginated_sql, bind_params = _paginate_sql(sql, page=page, page_size=page_size + 1)
                merged_params = {**(params or {}), **bind_params}
                cur.execute(paginated_sql, merged_params)
                desc = cur.description
                if desc is None:
                    return "（无返回列）"
                cols = [str(d[0]) for d in desc]
                rows: list[tuple] = cur.fetchall() or []
                has_more = len(rows) > page_size
                rows = rows[:page_size]
                if output_format == "json":
                    return json.dumps([dict(zip(cols, row)) for row in rows], ensure_ascii=False, default=str)
                return _fmt_result(rows, cols, page=page, page_size=page_size, has_more=has_more)
        finally:
            conn.close()

    result = await _run_db(_q)
    return [types.TextContent(type="text", text=result)]


def _fmt_result(
    rows: list[tuple], cols: list[str], *, page: int = 1, page_size: int = 0, has_more: bool = False
) -> str:
    if not rows:
        return "（空结果）"

    if has_more:
        lines = [
            f"第 {page} 页，返回 {len(rows)} 行，共 {len(cols)} 列（还有更多，请使用 page={page + 1} 获取下一页）\n"
        ]
    else:
        lines = [f"第 {page} 页，返回 {len(rows)} 行，共 {len(cols)} 列（已是最后一页）\n"]

    widths = {c: len(c) for c in cols}
    for row in rows:
        for i, c in enumerate(cols):
            v = str(row[i]) if row[i] is not None else ""
            widths[c] = max(widths[c], min(len(v), 50))

    header = "| " + " | ".join(c.ljust(widths[c]) for c in cols) + " |"
    sep = "| " + " | ".join("-" * widths[c] for c in cols) + " |"
    lines.append(header)
    lines.append(sep)

    for row in rows:
        vals: list[str] = []
        for i, c in enumerate(cols):
            v = str(row[i]) if row[i] is not None else ""
            if len(v) > widths[c]:
                v = v[: widths[c] - 3] + "..."
            vals.append(v.ljust(widths[c]))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def cli():
    """CLI entry point for pip-installed nc-mcp-server command."""
    asyncio.run(main())


async def main():
    config.validate()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    cli()
