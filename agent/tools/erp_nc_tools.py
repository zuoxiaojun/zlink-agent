"""NC ERP 工具 — 注册为内置工具，替代 MCP 子进程。

从 mcp_server/nc_mcp_server 迁移而来。NC 不走客户端 SDK，
直接通过 oracledb 查 Oracle 数据库，工具 handler 内完成
配置加载 → SQL 生成 → 执行 → 格式化 全过程。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from agent.tools.registry import registry, tool_error, tool_result

# ═══════════════════════════════════════════════════════════════
# NC 配置 (从 mcp_server/nc_mcp_server/config.py 迁移)
# ═══════════════════════════════════════════════════════════════


def _nc_db_config_or_none() -> dict | None:
    """Return oracledb connection config dict, or None if not configured."""
    host = os.environ.get("ORACLE_HOST", "")
    port = os.environ.get("ORACLE_PORT", "")
    user = os.environ.get("ORACLE_USER", "")
    password = os.environ.get("ORACLE_PASSWORD", "")
    service = os.environ.get("ORACLE_SERVICE", "")
    if not all([host, port, user, password, service]):
        return None
    try:
        port_int = int(port)
    except ValueError:
        return None
    return {
        "user": user,
        "password": password,
        "host": host,
        "port": port_int,
        "service_name": service,
    }


def _get_max_rows() -> int:
    try:
        return int(os.environ.get("NC_MCP_MAX_ROWS", "200"))
    except ValueError:
        return 200


def _nc_enabled() -> bool:
    """工具暴露门控：仅当 config.json 中 erp_clients.nc.enabled=true 时
    才把 NC 工具注册进 LLM 工具列表（registry.get_definitions 的 check_fn）。
    读取失败时按未启用处理（fail closed）。"""
    try:
        from agent import config_manager

        ecfg = config_manager.load().erp_clients.get("nc", {})
        return bool(ecfg.get("enabled", False)) if isinstance(ecfg, dict) else False
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# SQL 分页 + 安全校验 (从 mcp_server/nc_mcp_server/server.py 迁移)
# ═══════════════════════════════════════════════════════════════


def _validate_select(sql: str) -> str:
    """校验 SQL 为只读查询（AST 级别校验）。"""
    import sqlparse

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


def _paginate_sql(sql: str, page: int, page_size: int) -> tuple[str, dict[str, int]]:
    """Oracle 12c+ OFFSET/FETCH 分页。"""
    stripped = sql.strip().rstrip(";").strip()
    paginated = f"SELECT * FROM ({stripped}) OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"
    return paginated, {"offset": (page - 1) * page_size, "limit": page_size}


def _execute_query(sql: str, params: dict | None, page: int, page_size: int) -> dict:
    """执行 SQL 查询，返回格式化的结果。

    Returns:
        {"rows": [...], "cols": [...], "has_more": bool, "total_count": int}
    """
    import oracledb

    db_config = _nc_db_config_or_none()
    if db_config is None:
        raise ValueError("NC 数据库未配置，请在设置 → ERP → NC 中填写连接信息")

    conn = oracledb.connect(**db_config)
    try:
        paginated_sql, bind_params = _paginate_sql(sql, page=page, page_size=page_size + 1)
        merged = {**(params or {}), **bind_params}
        with conn.cursor() as cur:
            cur.execute(paginated_sql, merged)
            desc = cur.description
            if desc is None:
                return {"rows": [], "cols": [], "has_more": False, "total_count": 0}
            cols = [str(d[0]) for d in desc]
            rows: list[tuple] = cur.fetchall() or []
            has_more = len(rows) > page_size
            rows = rows[:page_size]
            return {
                "cols": cols,
                "rows": [dict(zip(cols, row, strict=False)) for row in rows],
                "has_more": has_more,
                "total_count": len(rows),
            }
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# 数据字典 (从 mcp_server/nc_mcp_server/data_dictionary.py 迁移)
# ═══════════════════════════════════════════════════════════════

_ALL_TABLES: dict[str, dict] = {}


def _get_data_dictionary() -> dict[str, dict]:
    """懒加载 NC 数据字典。"""
    if not _ALL_TABLES:
        _init_data_dictionary()
    return _ALL_TABLES


def _init_data_dictionary():
    """初始化数据字典表映射表。"""
    global _ALL_TABLES
    # 只加载关键业务表的字段对照，完整版在 data_dictionary.py (1000+ 行)
    _ALL_TABLES = {
        "SO_SALEORDER": {
            "name": "销售订单主表",
            "curated": True,
            "fields": {
                "VBILLCODE": "单据号",
                "DBILLDATE": "单据日期",
                "FSTATUSFLAG": "单据状态",
                "CCUSTOMERID": "客户",
                "NTOTALORIGMNY": "价税合计",
                "NTOTALNUM": "总数量",
            },
        },
        "PO_ORDER": {
            "name": "采购订单主表",
            "curated": True,
            "fields": {
                "VBILLCODE": "订单编号",
                "DBILLDATE": "订单日期",
                "FORDERSTATUS": "订单状态",
                "PK_SUPPLIER": "供应商",
                "NTOTALORIGMNY": "价税合计",
                "NTOTALASTNUM": "总数量",
            },
        },
        "BD_CUSTOMER": {
            "name": "客户基本档案",
            "curated": True,
            "fields": {
                "CODE": "客户编码",
                "NAME": "客户名称",
                "CUSTPROP": "客户类型",
                "ENABLESTATE": "启用状态",
            },
        },
        "BD_SUPPLIER": {
            "name": "供应商基本档案",
            "curated": True,
            "fields": {
                "CODE": "供应商编码",
                "NAME": "供应商名称",
                "SUPSTATE": "供应商状态",
                "ENABLESTATE": "启用状态",
            },
        },
        "BD_MATERIAL": {
            "name": "物料基本档案",
            "curated": True,
            "fields": {"CODE": "物料编码", "NAME": "物料名称", "MATERIALSPEC": "规格"},
        },
        "ORG_ORGS": {
            "name": "组织信息",
            "curated": True,
            "fields": {"CODE": "组织编码", "NAME": "组织名称", "ENABLESTATE": "启用状态"},
        },
    }
    # 合并扩展字典（scripts/parse_nc_dict_chm.py 解析 NC65 CHM 的产物）；
    # 字段级以扩展字典为准（带类型/枚举/参照），精选层价值在表筛选和表名
    for tname, tinfo in _load_ext_dictionary().items():
        if tname in _ALL_TABLES:
            _ALL_TABLES[tname]["fields"] = {**_ALL_TABLES[tname]["fields"], **tinfo.get("fields", {})}
        else:
            _ALL_TABLES[tname] = tinfo


def _load_ext_dictionary() -> dict[str, dict]:
    """加载扩展字典。优先 DATA_DIR/nc_dictionary.json（本地重导覆盖），
    否则用随包捆绑的 agent/tools/nc_dictionary.json；失败返回 {}。"""
    candidates = []
    try:
        from agent.utils import DATA_DIR, get_base_dir

        candidates.append(DATA_DIR / "nc_dictionary.json")
        # PyInstaller 冻结时指向 _MEIPASS，源码运行时为项目根
        candidates.append(get_base_dir() / "agent" / "tools" / "nc_dictionary.json")
    except Exception:
        candidates.append(Path(__file__).with_name("nc_dictionary.json"))
    for path in candidates:
        try:
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            tables = data.get("tables")
            if isinstance(tables, dict):
                return tables
        except Exception:
            continue
    return {}


# ═══════════════════════════════════════════════════════════════
# SQL 模板 (从 mcp_server/nc_mcp_server/queries/ 迁移)
# ═══════════════════════════════════════════════════════════════


def _sql_sales_order(start_date: str | None = None, end_date: str | None = None) -> tuple[str, dict | None]:
    where = ""
    params: dict = {}
    if start_date:
        where += " AND h.DBILLDATE >= :start_date"
        params["start_date"] = start_date + " 00:00:00"
    if end_date:
        where += " AND h.DBILLDATE <= :end_date"
        params["end_date"] = end_date + " 23:59:59"
    sql = f"""SELECT
    h.VBILLCODE AS "单据号",
    h.DBILLDATE AS "单据日期",
    CASE h.FSTATUSFLAG WHEN 1 THEN '自由' WHEN 2 THEN '审批通过' WHEN 3 THEN '冻结' WHEN 4 THEN '关闭' WHEN 5 THEN '失效' WHEN 7 THEN '审批中' WHEN 8 THEN '审批不通过' END AS "单据状态",
    h.VTRANTYPECODE || ' (' || btype.BILLTYPENAME || ')' AS "订单类型",
    h.NTOTALNUM AS "总数量", h.NTOTALORIGMNY AS "价税合计",
    cust.CODE AS "客户编码", cust.NAME AS "客户名称",
    b.CROWNO AS "行号", mat.CODE AS "物料编码", mat.NAME AS "物料名称",
    b.NASTNUM AS "数量", b.NORIGPRICE AS "无税单价", b.NORIGMNY AS "无税金额",
    b.NORIGTAXPRICE AS "含税单价", b.NORIGTAXMNY AS "价税合计_行",
    b.NTAX AS "税额", b.NTAXRATE AS "税率"
FROM SO_SALEORDER h
LEFT JOIN SO_SALEORDER_B b ON b.CSALEORDERID = h.CSALEORDERID AND b.DR = 0
LEFT JOIN BD_CUSTOMER cust ON cust.PK_CUSTOMER = h.CCUSTOMERID
LEFT JOIN BD_MATERIAL mat ON mat.PK_MATERIAL = b.CMATERIALVID
LEFT JOIN (SELECT DISTINCT PK_BILLTYPECODE, BILLTYPENAME FROM BD_BILLTYPE) btype ON btype.PK_BILLTYPECODE = h.VTRANTYPECODE
WHERE h.DR = 0{where}
ORDER BY h.DBILLDATE DESC, b.CROWNO"""
    return sql, params or None


def _sql_sales_order_by_code(billcode: str) -> tuple[str, dict]:
    sql, _ = _sql_sales_order()
    sql += " AND h.VBILLCODE = :billcode" if "VBILLCODE =" not in sql else " AND h.VBILLCODE = :billcode"
    return sql.replace(
        "ORDER BY h.DBILLDATE DESC, b.CROWNO", ""
    ) + " AND h.VBILLCODE = :billcode ORDER BY h.DBILLDATE DESC, b.CROWNO", {"billcode": billcode}


def _sql_purchase_order(start_date: str | None = None, end_date: str | None = None) -> tuple[str, dict | None]:
    where = ""
    params: dict = {}
    if start_date:
        where += " AND h.DBILLDATE >= :start_date"
        params["start_date"] = start_date + " 00:00:00"
    if end_date:
        where += " AND h.DBILLDATE <= :end_date"
        params["end_date"] = end_date + " 23:59:59"
    sql = f"""SELECT
    h.VBILLCODE AS "订单编号", h.DBILLDATE AS "订单日期",
    CASE h.FORDERSTATUS WHEN 0 THEN '自由' WHEN 1 THEN '提交' WHEN 2 THEN '正在审批' WHEN 3 THEN '审批' WHEN 4 THEN '审批不通过' WHEN 5 THEN '输出' END AS "单据状态",
    h.VTRANTYPECODE || ' (' || btype.BILLTYPENAME || ')' AS "订单类型",
    h.NTOTALASTNUM AS "总数量", h.NTOTALORIGMNY AS "价税合计",
    sup.CODE AS "供应商编码", sup.NAME AS "供应商名称",
    b.CROWNO AS "行号", mat.CODE AS "物料编码", mat.NAME AS "物料名称",
    b.NASTNUM AS "数量", b.NORIGPRICE AS "无税单价", b.NORIGMNY AS "无税金额",
    b.NORIGTAXPRICE AS "含税单价", b.NORIGTAXMNY AS "价税合计_行",
    b.NTAX AS "税额", b.NTAXRATE AS "税率"
FROM PO_ORDER h
LEFT JOIN PO_ORDER_B b ON b.PK_ORDER = h.PK_ORDER AND b.DR = 0
LEFT JOIN BD_SUPPLIER sup ON sup.PK_SUPPLIER = h.PK_SUPPLIER
LEFT JOIN BD_MATERIAL mat ON mat.PK_MATERIAL = b.PK_MATERIAL
LEFT JOIN (SELECT DISTINCT PK_BILLTYPECODE, BILLTYPENAME FROM BD_BILLTYPE) btype ON btype.PK_BILLTYPECODE = h.VTRANTYPECODE
WHERE h.DR = 0{where}
ORDER BY h.DBILLDATE DESC, b.CROWNO"""
    return sql, params or None


def _sql_purchase_order_by_code(billcode: str) -> tuple[str, dict]:
    sql, _ = _sql_purchase_order()
    return sql.replace(
        "ORDER BY h.DBILLDATE DESC, b.CROWNO", ""
    ) + " AND h.VBILLCODE = :billcode ORDER BY h.DBILLDATE DESC, b.CROWNO", {"billcode": billcode}


def _sql_customer(code: str | None = None, name: str | None = None) -> tuple[str, dict | None]:
    sql = """SELECT cust.CODE AS "客户编码", cust.NAME AS "客户名称",
    cust.SHORTNAME AS "客户简称", cust.CUSTPROP AS "客户类型",
    cust.ENABLESTATE AS "启用状态", cust.TEL1 AS "电话1",
    cust.CORPADDRESS AS "企业地址", cust.MEMO AS "备注"
FROM BD_CUSTOMER cust WHERE cust.DR = 0"""
    params = {}
    if code:
        sql += " AND cust.CODE LIKE :code"
        params["code"] = f"%{code}%"
    if name:
        sql += " AND cust.NAME LIKE :name"
        params["name"] = f"%{name}%"
    sql += " ORDER BY cust.CODE"
    return sql, params or None


def _sql_supplier(code: str | None = None, name: str | None = None) -> tuple[str, dict | None]:
    sql = """SELECT sup.CODE AS "供应商编码", sup.NAME AS "供应商名称",
    sup.SHORTNAME AS "供应商简称", sup.SUPSTATE AS "供应商状态",
    sup.ENABLESTATE AS "启用状态", sup.TEL1 AS "电话1",
    sup.CORPADDRESS AS "企业地址", sup.MEMO AS "备注"
FROM BD_SUPPLIER sup WHERE sup.DR = 0"""
    params = {}
    if code:
        sql += " AND sup.CODE LIKE :code"
        params["code"] = f"%{code}%"
    if name:
        sql += " AND sup.NAME LIKE :name"
        params["name"] = f"%{name}%"
    sql += " ORDER BY sup.CODE"
    return sql, params or None


def _sql_material(code: str | None = None, name: str | None = None) -> tuple[str, dict | None]:
    sql = """SELECT mat.CODE AS "物料编码", mat.NAME AS "物料名称",
    mat.MATERIALSPEC AS "规格", mat.MATERIALTYPE AS "型号",
    mat.MEMO AS "备注"
FROM BD_MATERIAL mat WHERE mat.DR = 0"""
    params = {}
    if code:
        sql += " AND mat.CODE LIKE :code"
        params["code"] = f"%{code}%"
    if name:
        sql += " AND mat.NAME LIKE :name"
        params["name"] = f"%{name}%"
    sql += " ORDER BY mat.CODE"
    return sql, params or None


def _sql_organization(code: str | None = None, name: str | None = None) -> tuple[str, dict | None]:
    sql = """SELECT org.CODE AS "组织编码", org.NAME AS "组织名称",
    org.SHORTNAME AS "组织简称", org.ENABLESTATE AS "启用状态",
    org.ADDRESS AS "地址", org.TEL AS "电话"
FROM ORG_ORGS org WHERE org.DR = 0"""
    params = {}
    if code:
        sql += " AND org.CODE LIKE :code"
        params["code"] = f"%{code}%"
    if name:
        sql += " AND org.NAME LIKE :name"
        params["name"] = f"%{name}%"
    sql += " ORDER BY org.CODE"
    return sql, params or None


def _sql_stock(
    warehouse: str | None = None,
    material: str | None = None,
    batch: str | None = None,
    org: str | None = None,
) -> tuple[str, dict | None]:
    sql = """SELECT
    org.CODE AS "组织编码", org.NAME AS "组织名称",
    wh.CODE AS "仓库编码", wh.NAME AS "仓库名称",
    mat.CODE AS "物料编码", mat.NAME AS "物料名称",
    hand.vbatchcode AS "批次号",
    hand.nonhandnum AS "结存数量", hand.nonhandastnum AS "结存辅数量",
    hand.nvmionhandnum AS "物权结存数量", hand.ntplonhandnum AS "客户结存数量"
FROM (
    SELECT handdim.pk_org, handdim.cwarehouseid, handdim.cmaterialoid,
        handdim.vbatchcode,
        ic.nonhandnum, ic.nonhandastnum,
        CASE WHEN COALESCE(handdim.cvmivenderid, '~') = '~' THEN 0.0 ELSE ic.nonhandnum END AS nvmionhandnum,
        CASE WHEN COALESCE(handdim.ctplcustomerid, '~') = '~' THEN 0.0 ELSE ic.nonhandnum END AS ntplonhandnum
    FROM ic_onhandnum ic
    INNER JOIN ic_onhanddim handdim ON (ic.pk_onhanddim = handdim.pk_onhanddim)
    INNER JOIN bd_stordoc bd_stordoc ON (handdim.cwarehouseid = bd_stordoc.pk_stordoc)
    WHERE ic.dr = 0 AND bd_stordoc.gubflag = 'N'
) hand
LEFT JOIN org_orgs org ON org.pk_org = hand.pk_org
LEFT JOIN bd_stordoc wh ON wh.pk_stordoc = hand.cwarehouseid
LEFT JOIN bd_material mat ON mat.pk_material = hand.cmaterialoid
WHERE 1=1"""
    params: dict[str, str] = {}
    if warehouse:
        sql += " AND hand.cwarehouseid = :warehouse"
        params["warehouse"] = warehouse
    if material:
        sql += " AND hand.cmaterialoid = :material"
        params["material"] = material
    if batch:
        sql += " AND hand.vbatchcode LIKE :batch"
        params["batch"] = f"%{batch}%"
    if org:
        sql += " AND hand.pk_org = :org"
        params["org"] = org
    sql += " ORDER BY wh.CODE, mat.CODE"
    return sql, params or None


def _sql_gl_voucher(
    start_date: str | None = None, end_date: str | None = None, num: str | None = None
) -> tuple[str, dict | None]:
    """总账凭证查询：凭证头 + 分录 + 科目编码名称（GL_VOUCHER/GL_DETAIL/BD_ACCASOA/BD_ACCOUNT）。"""
    where = ""
    params: dict = {}
    if start_date:
        where += " AND h.PREPAREDDATE >= :start_date"
        params["start_date"] = start_date + " 00:00:00"
    if end_date:
        where += " AND h.PREPAREDDATE <= :end_date"
        params["end_date"] = end_date + " 23:59:59"
    if num:
        where += " AND h.NUM = :num"
        params["num"] = num
    sql = f"""SELECT
    h.YEAR AS "年度", h.PERIOD AS "期间", h.NUM AS "凭证号",
    h.PREPAREDDATE AS "制单日期",
    d.DETAILINDEX AS "分录号", d.EXPLANATION AS "摘要",
    acc.CODE AS "科目编码", acc.NAME AS "科目名称",
    d.LOCALDEBITAMOUNT AS "借方金额", d.LOCALCREDITAMOUNT AS "贷方金额",
    CASE WHEN h.DISCARDFLAG = 'Y' THEN '已作废' ELSE '正常' END AS "状态"
FROM GL_VOUCHER h
JOIN GL_DETAIL d ON d.PK_VOUCHER = h.PK_VOUCHER AND d.DR = 0
LEFT JOIN BD_ACCASOA asoa ON asoa.PK_ACCASOA = d.PK_ACCASOA
LEFT JOIN BD_ACCOUNT acc ON acc.PK_ACCOUNT = asoa.PK_ACCOUNT
WHERE h.DR = 0{where}
ORDER BY h.YEAR DESC, h.PERIOD DESC, h.NUM DESC, d.DETAILINDEX"""
    return sql, params or None


def _sql_gl_balance(
    year: str,
    period_start: str | None = None,
    period_end: str | None = None,
    code: str | None = None,
) -> tuple[str, dict]:
    """科目余额查询：GL_BALANCE 只有期间发生额，余额 = 累计净发生（借-贷）。"""
    ps = (period_start or "01").zfill(2)
    pe = (period_end or "12").zfill(2)
    where = ""
    params = {"year": year, "ps": ps, "pe": pe}
    if code:
        where += " AND acc.CODE LIKE :code"
        params["code"] = f"%{code}%"
    sql = f"""SELECT
    acc.CODE AS "科目编码", acc.NAME AS "科目名称",
    SUM(CASE WHEN b.PERIOD < :ps THEN b.LOCALDEBITAMOUNT - b.LOCALCREDITAMOUNT ELSE 0 END) AS "期初净额",
    SUM(CASE WHEN b.PERIOD BETWEEN :ps AND :pe THEN b.LOCALDEBITAMOUNT ELSE 0 END) AS "本期借方",
    SUM(CASE WHEN b.PERIOD BETWEEN :ps AND :pe THEN b.LOCALCREDITAMOUNT ELSE 0 END) AS "本期贷方",
    SUM(CASE WHEN b.PERIOD <= :pe THEN b.LOCALDEBITAMOUNT - b.LOCALCREDITAMOUNT ELSE 0 END) AS "期末净额"
FROM GL_BALANCE b
LEFT JOIN BD_ACCASOA asoa ON asoa.PK_ACCASOA = b.PK_ACCASOA
LEFT JOIN BD_ACCOUNT acc ON acc.PK_ACCOUNT = asoa.PK_ACCOUNT
WHERE b.DR = 0 AND b.YEAR = :year{where}
GROUP BY acc.CODE, acc.NAME
ORDER BY acc.CODE"""
    return sql, params


# ═══════════════════════════════════════════════════════════════
# 工具 handler
# ═══════════════════════════════════════════════════════════════


def _run_query(sql: str, params: dict | None, args: dict, default_page_size: int | None = None) -> dict | str:
    """执行查询并返回 JSON 格式结果。"""
    max_rows = _get_max_rows()
    page = max(1, args.get("page", 1))
    page_size = min(max(1, args.get("page_size", default_page_size or max_rows)), max_rows)
    output_format = args.get("format", "json")

    result = _execute_query(sql, params, page=page, page_size=page_size)
    if output_format == "json":
        return {
            "rows": result["rows"],
            "columns": result["cols"],
            "page": page,
            "page_size": page_size,
            "has_more": result["has_more"],
            "total_count": result["total_count"],
        }
    return result


def _format_table_result(result: dict) -> str:
    """Format query result as text table (compatible with LLM reading)."""
    rows = result["rows"]
    if not rows:
        return "（空结果）"
    cols = [k for k in rows[0].keys()] if isinstance(rows[0], dict) else result.get("columns", [])
    has_more = result.get("has_more", False)
    page = result.get("page", 1)

    lines = [f"第 {page} 页，返回 {len(rows)} 行，共 {len(cols)} 列"]
    if has_more:
        lines[0] += f"（还有更多，请使用 page={page + 1} 获取下一页）"
    else:
        lines[0] += "（已是最后一页）"

    widths = {c: len(c) for c in cols}
    for row in rows:
        for c in cols:
            v = str(row.get(c, "")) if row.get(c) is not None else ""
            widths[c] = max(widths[c], min(len(v), 50))

    header = "| " + " | ".join(c.ljust(widths[c]) for c in cols) + " |"
    sep = "| " + " | ".join("-" * widths[c] for c in cols) + " |"
    lines.append(header)
    lines.append(sep)

    for row in rows:
        vals: list[str] = []
        for c in cols:
            v = str(row.get(c, "")) if row.get(c) is not None else ""
            if len(v) > widths[c]:
                v = v[: widths[c] - 3] + "..."
            vals.append(v.ljust(widths[c]))
        lines.append("| " + " | ".join(vals) + " |")

    return "\n".join(lines)


def _handle_nc_query(args: dict) -> str:
    """NC 查询通用入口，根据 query_name 路由到对应的 SQL 模板。"""
    query_name = args.get("query_name", "")
    params = dict(args)
    params.pop("query_name", None)
    params.pop("format", None)
    params.pop("page", None)
    params.pop("page_size", None)

    db_config = _nc_db_config_or_none()
    if db_config is None:
        return tool_error("NC 数据库未配置，请在设置 → ERP → NC 中填写连接信息")

    queries = {
        "sales_order": (_sql_sales_order, ["start_date", "end_date"]),
        "sales_order_by_code": (_sql_sales_order_by_code, ["billcode"]),
        "purchase_order": (_sql_purchase_order, ["start_date", "end_date"]),
        "purchase_order_by_code": (_sql_purchase_order_by_code, ["billcode"]),
        "customer": (_sql_customer, ["code", "name"]),
        "supplier": (_sql_supplier, ["code", "name"]),
        "material": (_sql_material, ["code", "name"]),
        "organization": (_sql_organization, ["code", "name"]),
        "stock": (_sql_stock, ["warehouse", "material", "batch", "org"]),
        "gl_voucher": (_sql_gl_voucher, ["start_date", "end_date", "num"]),
        "gl_balance": (_sql_gl_balance, ["year", "period_start", "period_end", "code"]),
    }

    info = queries.get(query_name)
    if not info:
        return tool_error(f"未知查询: {query_name}")

    sql_fn, allowed = info
    cleaned = {k: v for k, v in params.items() if k in allowed and v is not None and v != ""}
    try:
        sql, bind_params = sql_fn(**cleaned)
    except TypeError as e:
        return tool_error(f"参数错误: {e}")

    output_format = args.get("format", "json")
    result = _run_query(sql, bind_params, args)
    if isinstance(result, str):
        return result

    if output_format == "text":
        return tool_result(data=_format_table_result(result), records=result["rows"])
    return tool_result(
        data=f"NC 查询完成（{result['total_count']} 条）",
        records=result["rows"],
        has_more=result["has_more"],
        page=result["page"],
    )


def get_table_summary() -> str:
    """紧凑表清单（表名(中文名)），供 system prompt 注入（Level 0，仅精选表）。"""
    tables = _get_data_dictionary()
    return "、".join(f"{t}({info['name']})" for t, info in tables.items() if info.get("curated"))


def _handle_nc_list_tables(args: dict) -> str:
    """列出 NC 业务表：默认只列精选表，keyword 搜索整个扩展字典。"""
    tables = _get_data_dictionary()
    keyword = str(args.get("keyword") or "").strip().upper()
    if not keyword:
        lines = ["NC 精选业务表：\n"]
        for tname, tinfo in tables.items():
            if tinfo.get("curated"):
                lines.append(f"  {tname:25s} -> {tinfo['name']}（{len(tinfo['fields'])} 个字段）")
        lines.append(f'\n扩展字典共 {len(tables)} 张表，用 keyword 参数按表名/中文名搜索（如 keyword="发货"）')
        return tool_result(data="\n".join(lines))
    hits = [(t, i) for t, i in tables.items() if keyword in t or keyword in str(i.get("name", "")).upper()][:50]
    if not hits:
        return tool_error(f'未找到匹配 "{keyword}" 的表')
    lines = [f'匹配 "{keyword}" 的表（{len(hits)} 张，最多显示 50）：\n']
    for tname, tinfo in hits:
        lines.append(f"  {tname:25s} -> {tinfo['name']}（{len(tinfo['fields'])} 个字段）")
    return tool_result(data="\n".join(lines))


def _handle_nc_describe_table(args: dict) -> str:
    """查看 NC 某张表的字段对照；字典外的表实时查数据库目录兜底。"""
    tname = args.get("table_name", "").upper()
    tables = _get_data_dictionary()
    tinfo = tables.get(tname)
    if not tinfo:
        return _describe_table_live(tname)
    lines = [f"{tname} -> {tinfo['name']}（{len(tinfo['fields'])} 个字段）\n"]
    for fname, finfo in tinfo["fields"].items():
        if isinstance(finfo, dict):
            extra = f"  {finfo['type']}" if finfo.get("type") else ""
            if finfo.get("ref"):
                extra += f"  参照: {finfo['ref']}"
            if finfo.get("enum"):
                extra += f"  枚举: {finfo['enum']}"
            lines.append(f"  {fname:30s} -> {finfo.get('name', '')}{extra}")
        else:
            lines.append(f"  {fname:30s} -> {finfo}")
    return tool_result(data="\n".join(lines))


def _describe_table_live(tname: str) -> str:
    """字典外的表：实时查 ALL_TAB_COLUMNS（无中文名，仅有注释）。"""
    if not re.fullmatch(r"[A-Z0-9_$#]+", tname):
        return tool_error(f"非法表名: {tname}")
    db_config = _nc_db_config_or_none()
    if db_config is None:
        return tool_error(f"未注册表: {tname}，且数据库未配置无法实时查询")
    import oracledb

    try:
        conn = oracledb.connect(**db_config)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT c.COLUMN_NAME, c.DATA_TYPE, c.DATA_LENGTH, m.COMMENTS
FROM ALL_TAB_COLUMNS c
LEFT JOIN ALL_COL_COMMENTS m
  ON m.OWNER = c.OWNER AND m.TABLE_NAME = c.TABLE_NAME AND m.COLUMN_NAME = c.COLUMN_NAME
WHERE c.OWNER = USER AND c.TABLE_NAME = :tname
ORDER BY c.COLUMN_ID""",
                    {"tname": tname},
                )
                rows = cur.fetchall() or []
        finally:
            conn.close()
    except Exception as e:
        return tool_error(f"实时查询表结构失败: {e}")
    if not rows:
        return tool_error(f"未找到表: {tname}（扩展字典和数据库目录中都不存在）")
    lines = [f"{tname}（未入字典，实时取自数据库目录，共 {len(rows)} 列，无中文名）\n"]
    for col, dtype, dlen, comment in rows[:200]:
        lines.append(f"  {col:30s} {dtype}({dlen})  {comment or ''}")
    return tool_result(data="\n".join(lines))


def _handle_nc_raw_sql(args: dict) -> str:
    """执行任意只读 SQL。"""
    sql = args.get("sql", "").strip()
    if not sql:
        return tool_error("sql 参数不能为空")

    db_config = _nc_db_config_or_none()
    if db_config is None:
        return tool_error("NC 数据库未配置，请在设置 → ERP → NC 中填写连接信息")

    try:
        validated = _validate_select(sql)
    except ValueError as e:
        return tool_error(str(e))

    result = _run_query(validated, None, args)
    if isinstance(result, str):
        return result
    output_format = args.get("format", "text")
    if output_format == "text":
        return tool_result(data=_format_table_result(result), records=result["rows"])
    return tool_result(data="SQL 查询完成", records=result["rows"])


# ═══════════════════════════════════════════════════════════════
# Schema + 注册
# ═══════════════════════════════════════════════════════════════

registry.register(
    name="nc_query",
    toolset="nc",
    check_fn=_nc_enabled,
    schema={
        "name": "nc_query",
        "description": "NC 业务数据查询。支持 销售订单(sales_order)、销售订单按单据号(sales_order_by_code)、采购订单(purchase_order)、采购订单按编号(purchase_order_by_code)、客户(customer)、供应商(supplier)、物料(material)、组织(organization)、现存量(stock)、总账凭证(gl_voucher)、科目余额(gl_balance) 查询。format=json 返回结构化数据，format=text 返回表格。",
        "parameters": {
            "type": "object",
            "properties": {
                "query_name": {
                    "type": "string",
                    "enum": [
                        "sales_order",
                        "sales_order_by_code",
                        "purchase_order",
                        "purchase_order_by_code",
                        "customer",
                        "supplier",
                        "material",
                        "organization",
                        "stock",
                        "gl_voucher",
                        "gl_balance",
                    ],
                    "description": "查询类型",
                },
                "start_date": {
                    "type": "string",
                    "description": "开始日期 YYYY-MM-DD（sales_order/purchase_order/gl_voucher 用）",
                },
                "end_date": {
                    "type": "string",
                    "description": "结束日期 YYYY-MM-DD（sales_order/purchase_order/gl_voucher 用）",
                },
                "billcode": {
                    "type": "string",
                    "description": "单据号（sales_order_by_code/purchase_order_by_code 用）",
                },
                "num": {"type": "string", "description": "凭证号（gl_voucher 用）"},
                "year": {"type": "string", "description": "会计年度 YYYY（gl_balance 必填）"},
                "period_start": {"type": "string", "description": "开始期间 1-12（gl_balance 用，默认 1）"},
                "period_end": {"type": "string", "description": "结束期间 1-12（gl_balance 用，默认 12）"},
                "code": {
                    "type": "string",
                    "description": "编码模糊搜索（customer/supplier/material/organization 用；gl_balance 按科目编码过滤）",
                },
                "name": {"type": "string", "description": "名称模糊搜索（customer/supplier/material/organization 用）"},
                "warehouse": {"type": "string", "description": "仓库主键（stock 用）"},
                "material": {"type": "string", "description": "物料主键（stock 用）"},
                "batch": {"type": "string", "description": "批次号模糊（stock 用）"},
                "org": {"type": "string", "description": "库存组织主键（stock 用）"},
                "format": {"type": "string", "enum": ["json", "text"], "description": "输出格式，默认 json"},
                "page": {"type": "integer", "description": "页码，从 1 开始"},
                "page_size": {"type": "integer", "description": "每页行数"},
            },
            "required": ["query_name"],
        },
    },
    handler=_handle_nc_query,
    emoji="🗄️",
)

registry.register(
    name="nc_list_tables",
    toolset="nc",
    check_fn=_nc_enabled,
    schema={
        "name": "nc_list_tables",
        "description": "列出 NC 业务表。默认只列精选表；传 keyword 按表名/中文名搜索扩展字典（500+ 张表，含销售/采购/库存/总账/应收应付/现金管理模块）。",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": '搜索关键字，如 "发货"、"SO_"、"凭证"'},
            },
        },
    },
    handler=_handle_nc_list_tables,
    emoji="📋",
)

registry.register(
    name="nc_describe_table",
    toolset="nc",
    check_fn=_nc_enabled,
    schema={
        "name": "nc_describe_table",
        "description": "查看 NC 某张表的中文字段对照（含类型/枚举/参照）。字典外的表会实时查数据库目录兜底。",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "表名（大写），如 SO_SALEORDER"},
            },
            "required": ["table_name"],
        },
    },
    handler=_handle_nc_describe_table,
    emoji="📖",
)

registry.register(
    name="nc_raw_sql",
    execution_mode="sequential",
    toolset="nc",
    check_fn=_nc_enabled,
    schema={
        "name": "nc_raw_sql",
        "description": "对 NC 数据库执行任意只读 SELECT 查询。写 SQL 前必须先用 nc_list_tables / nc_describe_table 确认已注册业务表和中文字段对照，不要猜表名和字段名。有安全校验。",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SELECT 语句"},
                "format": {"type": "string", "enum": ["json", "text"], "description": "输出格式，默认 text"},
                "page": {"type": "integer", "description": "页码"},
                "page_size": {"type": "integer", "description": "每页行数"},
            },
            "required": ["sql"],
        },
    },
    handler=_handle_nc_raw_sql,
    emoji="⚡",
)
