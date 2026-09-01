"""U8 ERP 工具 — 注册为内置工具。

U8 使用 SQL Server 数据库，通过 pymssql 直连。
工具 handler 内完成配置加载 → SQL 生成 → 执行 → 格式化 全过程。
"""

from __future__ import annotations

import os

from agent.tools.registry import registry, tool_error, tool_result

# ═══════════════════════════════════════════════════════════════
# U8 配置
# ═══════════════════════════════════════════════════════════════


def _u8_db_config_or_none() -> dict | None:
    """Return pymssql connection config dict, or None if not configured."""
    host = os.environ.get("U8_HOST", "")
    port = os.environ.get("U8_PORT", "")
    database = os.environ.get("U8_DATABASE", "")
    user = os.environ.get("U8_USER", "")
    password = os.environ.get("U8_PASSWORD", "")
    if not all([host, port, database, user, password]):
        return None
    try:
        port_int = int(port)
    except ValueError:
        return None
    return {
        "server": host,
        "port": port_int,
        "database": database,
        "user": user,
        "password": password,
        "timeout": 30,
    }


def _get_max_rows() -> int:
    try:
        return int(os.environ.get("U8_MAX_ROWS", "500"))
    except ValueError:
        return 500


def _u8_enabled() -> bool:
    """工具暴露门控：仅当 config.json 中 erp_clients.u8.enabled=true 时
    才把 U8 工具注册进 LLM 工具列表。"""
    try:
        from agent import config_manager

        ecfg = config_manager.load().erp_clients.get("u8", {})
        return bool(ecfg.get("enabled", False)) if isinstance(ecfg, dict) else False
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# SQL 安全校验 + 分页
# ═══════════════════════════════════════════════════════════════


def _validate_select(sql: str) -> str:
    """校验 SQL 为只读查询。"""
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


def _paginate_sql(sql: str, page: int, page_size: int) -> str:
    """SQL Server 分页（OFFSET/FETCH NEXT，直接追加到原始 SQL）。

    注意：不能包装在子查询中，因为 SQL Server 不允许子查询/派生表
    内的 ORDER BY 不附带 TOP/OFFSET/FETCH。
    """
    stripped = sql.strip().rstrip(";").strip()
    offset = (page - 1) * page_size
    return f"{stripped} OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY"


def _execute_query(sql: str, page: int, page_size: int, params: dict | None = None) -> dict:
    """执行 SQL 查询，返回格式化的结果。

    Args:
        sql: SELECT 语句（可含 %(name)s 占位符）
        page: 页码（从 1 开始）
        page_size: 每页行数
        params: pymssql 参数化查询参数字典

    Returns:
        {"rows": [...], "cols": [...], "has_more": bool, "total_count": int}
    """
    import datetime
    from decimal import Decimal

    import pymssql

    db_config = _u8_db_config_or_none()
    if db_config is None:
        raise ValueError("U8 数据库未配置，请在设置 → ERP → U8 中填写连接信息")

    conn = pymssql.connect(**db_config)
    try:
        paginated_sql = _paginate_sql(sql, page=page, page_size=page_size + 1)
        with conn.cursor(as_dict=False) as cur:
            cur.execute(paginated_sql, params)
            desc = cur.description
            if desc is None:
                return {"rows": [], "cols": [], "has_more": False, "total_count": 0}
            cols = [str(d[0]) for d in desc]
            rows: list[tuple] = cur.fetchall() or []
            has_more = len(rows) > page_size
            rows = rows[:page_size]

            def _serialize(val):
                if isinstance(val, (datetime.datetime, datetime.date, datetime.time)):
                    return val.isoformat()
                if isinstance(val, Decimal):
                    return float(val)
                return val

            return {
                "cols": cols,
                "rows": [{c: _serialize(row[i]) for i, c in enumerate(cols)} for row in rows],
                "has_more": has_more,
                "total_count": len(rows),
            }
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# 通用查询工具 handler
# ═══════════════════════════════════════════════════════════════


def _run_query(sql: str, args: dict, params: dict | None = None) -> dict:
    """执行 SQL 并返回分页结果。

    Args:
        sql: SELECT 语句
        args: 工具参数字典（含 page/page_size）
        params: pymssql 参数化查询参数字典
    """
    try:
        page = int(args.get("page", 1))
        page_size = min(int(args.get("page_size", _get_max_rows())), _get_max_rows())
    except (ValueError, TypeError):
        page = 1
        page_size = _get_max_rows()
    return _execute_query(sql, page=page, page_size=page_size, params=params)


def _format_table_result(result: dict) -> str:
    """将查询结果格式化为表格文本。"""
    if not result["rows"]:
        return "查询结果为空"
    cols = result["cols"]
    rows = result["rows"]
    # 列宽（取列名和数据最长值 + 2）
    col_widths = [len(str(c)) for c in cols]
    for row in rows:
        for i, val in enumerate(row.values()):
            col_widths[i] = max(col_widths[i], len(str(val or "")))
    # 表头
    header = " | ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(cols))
    separator = "-+-".join("-" * w for w in col_widths)
    lines = [header, separator]
    for row in rows:
        lines.append(" | ".join(str(row.get(c, "")).ljust(col_widths[i]) for i, c in enumerate(cols)))
    # 分页提示
    more = "（显示" + str(len(rows)) + "行，还有更多数据，使用 page/page_size 翻页）" if result["has_more"] else ""
    return "\n".join(lines) + more


def _date_where(field: str, start_date: str | None, end_date: str | None) -> tuple[str, dict]:
    """生成日期范围 WHERE 条件（SQL Server 用参数化查询）。"""
    clauses = []
    params: dict = {}
    if start_date:
        clauses.append(f" AND {field} >= %(start_date)s")
        params["start_date"] = start_date + " 00:00:00"
    if end_date:
        clauses.append(f" AND {field} <= %(end_date)s")
        params["end_date"] = end_date + " 23:59:59"
    return "".join(clauses), params


# ═══════════════════════════════════════════════════════════════
# SQL 模板 — 主数据
# ═══════════════════════════════════════════════════════════════


def _sql_customer(code: str | None = None, name: str | None = None) -> tuple[str, dict]:
    """客户档案查询。"""
    sql = "SELECT cCusCode AS 客户编码, cCusName AS 客户名称, cCusAbbName AS 客户简称, cCusPerson AS 联系人, cCusPhone AS 电话, cCusAddress AS 地址, cCusHand AS 分管部门 FROM Customer WHERE 1=1"
    params: dict = {}
    if code:
        sql += " AND cCusCode LIKE %(code)s"
        params["code"] = f"%{code}%"
    if name:
        sql += " AND cCusName LIKE %(name)s"
        params["name"] = f"%{name}%"
    sql += " ORDER BY cCusCode"
    return sql, params


def _sql_vendor(code: str | None = None, name: str | None = None) -> tuple[str, dict]:
    """供应商档案查询。"""
    sql = "SELECT cVenCode AS 供应商编码, cVenName AS 供应商名称, cVenAbbName AS 供应商简称, cVenPerson AS 联系人, cVenPhone AS 电话, cVenAddress AS 地址 FROM Vendor WHERE 1=1"
    params: dict = {}
    if code:
        sql += " AND cVenCode LIKE %(code)s"
        params["code"] = f"%{code}%"
    if name:
        sql += " AND cVenName LIKE %(name)s"
        params["name"] = f"%{name}%"
    sql += " ORDER BY cVenCode"
    return sql, params


def _sql_warehouse(code: str | None = None, name: str | None = None) -> tuple[str, dict]:
    """仓库档案查询。"""
    sql = "SELECT cWhCode AS 仓库编码, cWhName AS 仓库名称, cWhAddress AS 仓库地址, cDepCode AS 部门编码, cWhPerson AS 库管员 FROM Warehouse WHERE 1=1"
    params: dict = {}
    if code:
        sql += " AND cWhCode LIKE %(code)s"
        params["code"] = f"%{code}%"
    if name:
        sql += " AND cWhName LIKE %(name)s"
        params["name"] = f"%{name}%"
    sql += " ORDER BY cWhCode"
    return sql, params


def _sql_code(acc_code: str | None = None) -> tuple[str, dict]:
    """会计科目查询。code 表字段全小写：ccode, ccode_name, cclass, igrade, bproperty。"""
    sql = "SELECT ccode AS 科目编码, ccode_name AS 科目名称, cclass AS 科目类别, igrade AS 级次, bproperty AS 科目性质 FROM code WHERE 1=1"
    params: dict = {}
    if acc_code:
        sql += " AND ccode LIKE %(code)s"
        params["code"] = f"%{acc_code}%"
    sql += " ORDER BY ccode"
    return sql, params


def _sql_inventory(code: str | None = None, name: str | None = None) -> tuple[str, dict]:
    """存货档案查询（财务供应链用）。
    实际字段：cInvCode, cInvName, cInvStd, cInvCCode, bSale, bPurchase, bSelf, bProducing
    """
    sql = """SELECT inv.cInvCode AS 存货编码, inv.cInvName AS 存货名称, inv.cInvStd AS 规格型号,
    inv.cInvCCode AS 存货分类编码, inv.cVenCode AS 供应商编码,
    inv.bSale AS 可销售, inv.bPurchase AS 可采购, inv.bSelf AS 自制,
    inv.bProducing AS 可生产
FROM Inventory inv WHERE 1=1"""
    params: dict = {}
    if code:
        sql += " AND inv.cInvCode LIKE %(code)s"
        params["code"] = f"%{code}%"
    if name:
        sql += " AND inv.cInvName LIKE %(name)s"
        params["name"] = f"%{name}%"
    sql += " ORDER BY inv.cInvCode"
    return sql, params


def _sql_bas_part(code: str | None = None, name: str | None = None) -> tuple[str, dict]:
    """物料表查询（生产制造用）。bas_part 只有 InvCode，没有 InvName/WhCode。
    通过 Inventory.cInvCode = bas_part.InvCode 关联获取名称。
    """
    sql = """SELECT bp.InvCode AS 物料编码, inv.cInvName AS 物料名称, inv.cInvStd AS 规格型号,
    bp.PartId AS 物料ID, bp.SafeQty AS 安全库存, bp.MinQty AS 最低库存,
    bp.MulQty AS 批量, bp.Free1 AS 自由项1
FROM bas_part bp
LEFT JOIN Inventory inv ON inv.cInvCode = bp.InvCode
WHERE 1=1"""
    params: dict = {}
    if code:
        sql += " AND bp.InvCode LIKE %(code)s"
        params["code"] = f"%{code}%"
    if name:
        sql += " AND inv.cInvName LIKE %(name)s"
        params["name"] = f"%{name}%"
    sql += " ORDER BY bp.InvCode"
    return sql, params


# ═══════════════════════════════════════════════════════════════
# SQL 模板 — 业务单据
# ═══════════════════════════════════════════════════════════════


def _sql_sales_order(
    start_date: str | None = None,
    end_date: str | None = None,
    bill_no: str | None = None,
    code: str | None = None,
) -> tuple[str, dict]:
    """销售订单查询（主表 + 子表 + 客户 + 存货关联）。"""
    where_clause, params = _date_where("h.dDate", start_date, end_date)
    if bill_no:
        where_clause += " AND h.cSOCode LIKE %(bill_no)s"
        params["bill_no"] = f"%{bill_no}%"
    sql = f"""SELECT h.cSOCode AS 订单号, h.dDate AS 日期, h.cCusCode AS 客户编码,
    cus.cCusName AS 客户名称,
    CASE h.iStatus
        WHEN 1 THEN '审核' WHEN 0 THEN '未审核' ELSE CAST(ISNULL(h.iStatus,0) AS varchar) END AS 状态,
    b.cInvCode AS 存货编码, inv.cInvName AS 存货名称,
    b.iQuantity AS 数量, b.iQuotedPrice AS 报价, b.iUnitPrice AS 单价,
    b.iMoney AS 金额, b.iTax AS 税额, b.iSum AS 价税合计
FROM SO_SOMain h
LEFT JOIN SO_SODetails b ON b.ID = h.ID
LEFT JOIN Customer cus ON cus.cCusCode = h.cCusCode
LEFT JOIN Inventory inv ON inv.cInvCode = b.cInvCode
WHERE 1=1{where_clause}
ORDER BY h.dDate DESC, h.cSOCode"""
    return sql, params


def _sql_purchase_order(
    start_date: str | None = None,
    end_date: str | None = None,
    bill_no: str | None = None,
    code: str | None = None,
) -> tuple[str, dict]:
    """采购订单查询（主表 + 子表 + 供应商 + 存货关联）。"""
    where_clause, params = _date_where("h.dPODate", start_date, end_date)
    if bill_no:
        where_clause += " AND h.cPOID LIKE %(bill_no)s"
        params["bill_no"] = f"%{bill_no}%"
    sql = f"""SELECT h.cPOID AS 订单号, h.dPODate AS 日期, h.cVenCode AS 供应商编码,
    ven.cVenName AS 供应商名称,
    CASE h.cState
        WHEN 0 THEN '输入' WHEN 1 THEN '审批中' WHEN 2 THEN '审核'
        ELSE CAST(ISNULL(h.cState,0) AS varchar) END AS 状态,
    b.cInvCode AS 存货编码, inv.cInvName AS 存货名称,
    b.iQuantity AS 数量, b.iUnitPrice AS 单价, b.iMoney AS 金额,
    b.iTax AS 税额, b.iSum AS 价税合计
FROM PO_Pomain h
LEFT JOIN PO_Podetails b ON b.POID = h.POID
LEFT JOIN Vendor ven ON ven.cVenCode = h.cVenCode
LEFT JOIN Inventory inv ON inv.cInvCode = b.cInvCode
WHERE 1=1{where_clause}
ORDER BY h.dPODate DESC, h.cPOID"""
    return sql, params


def _sql_gl_voucher(
    start_date: str | None = None,
    end_date: str | None = None,
    num: str | None = None,
) -> tuple[str, dict]:
    """总账凭证查询。GL_accvouch 是平铺表，每行一条分录，csign+ino_id 标识同一张凭证。"""
    where_clause, params = _date_where("h.dbill_date", start_date, end_date)
    if num:
        where_clause += " AND CAST(h.ino_id AS varchar) LIKE %(num)s"
        params["num"] = f"%{num}%"
    sql = f"""SELECT h.csign AS 凭证类别, h.ino_id AS 凭证号, h.dbill_date AS 日期,
    h.cdigest AS 摘要,
    h.ccode AS 科目编码, cd.ccode_name AS 科目名称,
    h.md AS 借方金额, h.mc AS 贷方金额,
    h.cdept_id AS 部门, h.cperson_id AS 个人,
    h.iperiod AS 期间
FROM GL_accvouch h
LEFT JOIN code cd ON cd.ccode = h.ccode
WHERE 1=1{where_clause}
ORDER BY h.dbill_date DESC, h.csign, h.ino_id"""
    return sql, params


def _sql_mom_orderdetail(
    start_date: str | None = None,
    end_date: str | None = None,
    mo_code: str | None = None,
) -> tuple[str, dict]:
    """生产订单母件行查询（产品级）。"""
    where_clause = ""
    params: dict = {}
    if start_date:
        where_clause += " AND h.RelsDate >= %(start_date)s"
        params["start_date"] = start_date + " 00:00:00"
    if end_date:
        where_clause += " AND h.RelsDate <= %(end_date)s"
        params["end_date"] = end_date + " 23:59:59"
    if mo_code:
        where_clause += " AND o.MoCode LIKE %(mo_code)s"
        params["mo_code"] = f"%{mo_code}%"
    sql = f"""SELECT o.MoCode AS 生产订单号, h.SortSeq AS 行号, h.Qty AS 数量,
    inv.cInvCode AS 存货编码, inv.cInvName AS 存货名称,
    h.InvCode AS 母件存货编码, h.RelsDate AS 开工日期, h.CloseDate AS 完工日期,
    CASE h.Status WHEN 4 THEN '已下达' ELSE CAST(ISNULL(h.Status,0) AS varchar) END AS 状态,
    h.WhCode AS 仓库编码, h.MoDId AS 明细ID
FROM mom_orderdetail h
LEFT JOIN mom_order o ON o.MoId = h.MoId
LEFT JOIN Inventory inv ON inv.cInvCode = h.InvCode
WHERE 1=1{where_clause}
ORDER BY o.MoCode DESC, h.SortSeq"""
    return sql, params


def _sql_mom_moallocate(
    mo_code: str | None = None,
    inv_code: str | None = None,
    mod_id: str | None = None,
) -> tuple[str, dict]:
    """生产订单子件用料查询。mom_moallocate 通过 MoDId 关联到 mom_orderdetail。
    ComponentId 对应 bas_part.PartId，再联 Inventory 取存货名称。"""
    sql = """SELECT a.AllocateId AS 分配ID, a.MoDId AS 母件行ID,
    a.ComponentId AS 物料ID, bp.InvCode AS 物料编码, inv.cInvName AS 物料名称,
    a.Qty AS 计划用量, a.IssQty AS 已发量,
    a.WhCode AS 仓库编码, a.LotNo AS 批次,
    a.StartDemDate AS 需求日期, a.EndDemDate AS 到货日期
FROM mom_moallocate a
LEFT JOIN bas_part bp ON bp.PartId = a.ComponentId
LEFT JOIN Inventory inv ON inv.cInvCode = bp.InvCode
WHERE 1=1"""
    params: dict = {}
    if mo_code:
        sql += " AND a.MoDId IN (SELECT h.MoDId FROM mom_orderdetail h JOIN mom_order o ON o.MoId = h.MoId WHERE o.MoCode LIKE %(mo_code)s)"
        params["mo_code"] = f"%{mo_code}%"
    if mod_id:
        try:
            params["mod_id"] = int(mod_id)
        except (ValueError, TypeError):
            raise ValueError(f"mod_id must be int, got: {mod_id}")
        sql += " AND a.MoDId = %(mod_id)s"
    sql += " ORDER BY a.MoDId, a.SortSeq"
    return sql, params


def _sql_current_stock(
    wh_code: str | None = None,
    inv_code: str | None = None,
) -> tuple[str, dict]:
    """现存量查询。"""
    sql = """SELECT cs.cWhCode AS 仓库编码, wh.cWhName AS 仓库名称,
    cs.cInvCode AS 存货编码, inv.cInvName AS 存货名称,
    cs.iQuantity AS 现存量, cs.iNum AS 可用量,
    cs.cBatch AS 批次, cs.cFree1 AS 自由项1,
    cs.fInQuantity AS 入库累计, cs.fOutQuantity AS 出库累计
FROM CurrentStock cs
LEFT JOIN Warehouse wh ON wh.cWhCode = cs.cWhCode
LEFT JOIN Inventory inv ON inv.cInvCode = cs.cInvCode
WHERE 1=1"""
    params: dict = {}
    if wh_code:
        sql += " AND cs.cWhCode LIKE %(wh_code)s"
        params["wh_code"] = f"%{wh_code}%"
    if inv_code:
        sql += " AND cs.cInvCode LIKE %(inv_code)s"
        params["inv_code"] = f"%{inv_code}%"
    sql += " ORDER BY cs.cWhCode, cs.cInvCode"
    return sql, params


# ═══════════════════════════════════════════════════════════════
# 查询类型映射
# ═══════════════════════════════════════════════════════════════

_QUERY_MAP = {
    "customer": (_sql_customer, "客户档案"),
    "vendor": (_sql_vendor, "供应商档案"),
    "warehouse": (_sql_warehouse, "仓库档案"),
    "code": (_sql_code, "会计科目"),
    "inventory": (_sql_inventory, "存货档案（供应链用）"),
    "bas_part": (_sql_bas_part, "物料表（生产制造用）"),
    "sales_order": (_sql_sales_order, "销售订单"),
    "purchase_order": (_sql_purchase_order, "采购订单"),
    "gl_voucher": (_sql_gl_voucher, "总账凭证"),
    "mom_orderdetail": (_sql_mom_orderdetail, "生产订单母件行"),
    "mom_moallocate": (_sql_mom_moallocate, "生产订单子件用料"),
    "current_stock": (_sql_current_stock, "现存量"),
}

# 各查询类型的参数说明（用于 schema description）
_QUERY_PARAM_HELP: dict[str, str] = {
    "customer": "客户编码(code)、客户名称(name) 模糊搜索",
    "vendor": "供应商编码(code)、供应商名称(name) 模糊搜索",
    "warehouse": "仓库编码(code)、仓库名称(name) 模糊搜索",
    "code": "科目编码(code) 模糊搜索",
    "inventory": "存货编码(code)、存货名称(name) 模糊搜索",
    "bas_part": "物料编码(code)、物料名称(name) 模糊搜索",
    "sales_order": "日期范围(start_date, end_date)、订单号(bill_no) 模糊搜索",
    "purchase_order": "日期范围(start_date, end_date)、订单号(bill_no) 模糊搜索",
    "gl_voucher": "日期范围(start_date, end_date)、凭证号(num) 模糊搜索",
    "mom_orderdetail": "日期范围(start_date, end_date)、生产订单号(mo_code) 模糊搜索",
    "mom_moallocate": "生产订单号(mo_code)、物料编码(inv_code) 模糊搜索",
    "current_stock": "仓库编码(wh_code)、存货编码(inv_code) 模糊搜索",
}


# ═══════════════════════════════════════════════════════════════
# 数据字典
# ═══════════════════════════════════════════════════════════════

_CURATED_TABLES: dict[str, dict] = {
    "Customer": {
        "name": "客户档案",
        "module": "公用目录",
        "fields": {
            "cCusCode": "客户编码",
            "cCusName": "客户名称",
            "cCusAbbName": "客户简称",
            "cCusPerson": "联系人",
            "cPhone": "电话",
            "cAddress": "地址",
            "cCusHand": "分管部门",
        },
    },
    "Vendor": {
        "name": "供应商档案",
        "module": "公用目录",
        "fields": {
            "cVenCode": "供应商编码",
            "cVenName": "供应商名称",
            "cVenAbbName": "供应商简称",
            "cVenPerson": "联系人",
            "cPhone": "电话",
            "cAddress": "地址",
        },
    },
    "Warehouse": {
        "name": "仓库档案",
        "module": "公用目录",
        "fields": {
            "cWhCode": "仓库编码",
            "cWhName": "仓库名称",
            "cWhAddress": "仓库地址",
            "cDepCode": "部门编码",
            "cWhPerson": "库管员",
        },
    },
    "code": {
        "name": "会计科目",
        "module": "总账",
        "fields": {
            "cCode": "科目编码",
            "cCodeName": "科目名称",
            "cClass": "科目类别",
            "iGrade": "级次",
            "bEnd": "末级",
            "bProperty": "科目性质",
        },
    },
    "Inventory": {
        "name": "存货档案",
        "module": "公用目录",
        "fields": {
            "cInvCode": "存货编码",
            "cInvName": "存货名称",
            "cInvStd": "规格型号",
            "cInvCCode": "存货分类编码",
            "cComUnitName": "计量单位",
            "bInvSale": "可销售",
            "bInvPurchase": "可采购",
            "bInvProduce": "可生产",
            "bInvSelf": "自制",
        },
    },
    "bas_part": {
        "name": "物料表（生产制造）",
        "module": "生产制造",
        "fields": {
            "InvCode": "物料编码",
            "InvName": "物料名称",
            "InvStd": "规格型号",
            "WhCode": "默认仓库",
            "UnitCode": "单位",
            "EngUnitCode": "计量单位",
        },
    },
    "GL_accvouch": {
        "name": "总账凭证表",
        "module": "总账",
        "fields": {
            "iID": "凭证号",
            "cCode": "凭证类别",
            "dDate": "日期",
            "cDigest": "摘要",
            "cSubCode": "科目编码",
            "md": "借方金额",
            "mc": "贷方金额",
            "cMaker": "制单人",
            "cAuditor": "审核人",
            "cDeptID": "部门",
            "cPersonID": "个人",
            "iperiod": "会计期间",
        },
    },
    "SO_SOMain": {
        "name": "销售订单主表",
        "module": "销售管理",
        "fields": {
            "cSOCode": "订单号",
            "dDate": "日期",
            "cCusCode": "客户编码",
            "cState": "状态",
            "cDepCode": "部门编码",
            "cPersonCode": "业务员",
            "cMaker": "制单人",
            "cVerifier": "审核人",
        },
    },
    "SO_SODetails": {
        "name": "销售订单子表",
        "module": "销售管理",
        "fields": {
            "cInvCode": "存货编码",
            "iQuantity": "数量",
            "iQuotedPrice": "报价",
            "iUnitPrice": "单价",
            "iNatSum": "金额",
            "iTax": "税额",
            "iNatSumTax": "价税合计",
            "dDate": "预发货日期",
        },
    },
    "PO_Pomain": {
        "name": "采购订单主表",
        "module": "采购管理",
        "fields": {
            "cPOCode": "订单号",
            "dDate": "日期",
            "cVenCode": "供应商编码",
            "cState": "状态",
            "cDepCode": "部门编码",
            "cPersonCode": "业务员",
            "cMaker": "制单人",
            "cVerifier": "审核人",
        },
    },
    "PO_Podetails": {
        "name": "采购订单子表",
        "module": "采购管理",
        "fields": {
            "cInvCode": "存货编码",
            "iQuantity": "数量",
            "iUnitPrice": "单价",
            "iNatSum": "金额",
            "iTax": "税额",
            "iNatSumTax": "价税合计",
            "dArriveDate": "预计到货日期",
        },
    },
    "mom_orderdetail": {
        "name": "生产订单明细表",
        "module": "生产制造",
        "fields": {
            "MoCode": "生产订单号",
            "MoSeq": "行号",
            "InvCode": "母件存货编码",
            "Qty": "数量",
            "StartDate": "开工日期",
            "DueDate": "完工日期",
            "Status": "状态",
            "WhCode": "仓库编码",
        },
    },
    "mom_moallocate": {
        "name": "生产订单子件用料表",
        "module": "生产制造",
        "fields": {
            "MoCode": "生产订单号",
            "SeqId": "子件行号",
            "InvCode": "物料编码",
            "Qty": "计划用量",
            "RealQty": "实际用量",
            "WhCode": "仓库编码",
            "UnitCode": "单位",
            "Remark": "备注",
        },
    },
    "CurrentStock": {
        "name": "现存量表",
        "module": "库存管理",
        "fields": {
            "cWhCode": "仓库编码",
            "cInvCode": "存货编码",
            "iQuantity": "现存量",
            "iNum": "可用量",
            "iBeginQuantity": "期初数量",
            "iReceiveQuantity": "入库数量",
            "iSendQuantity": "出库数量",
            "cBatch": "批次",
            "cFree1": "自由项1",
        },
    },
}


def get_table_summary() -> str:
    """返回精选表清单摘要，供 system prompt 注入。"""
    curated = [t for t in _CURATED_TABLES.values()]
    modules: dict[str, list[str]] = {}
    for t in curated:
        mod = t.get("module", "其他")
        modules.setdefault(mod, []).append(t["name"])
    parts = []
    for mod, tables in sorted(modules.items()):
        parts.append(f"    {mod}：{'、'.join(tables)}")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# Handler 函数
# ═══════════════════════════════════════════════════════════════


def _handle_u8_query(args: dict) -> str:
    """U8 通用查询入口。"""
    query_name = args.get("query_name", "")
    if not query_name:
        return tool_error("query_name 参数不能为空")

    query_def = _QUERY_MAP.get(query_name)
    if query_def is None:
        return tool_error(f"不支持的查询类型: {query_name}，可选: {', '.join(_QUERY_MAP.keys())}")

    sql_fn, description = query_def
    # 只传函数接受的参数，避免多余参数导致 TypeError
    import inspect

    sig = inspect.signature(sql_fn)
    filtered = {}
    for param_name in sig.parameters:
        if param_name == "code":
            filtered[param_name] = args.get("code")
        elif param_name == "acc_code":
            filtered[param_name] = args.get("code")
        elif param_name == "start_date":
            filtered[param_name] = args.get("start_date")
        elif param_name == "end_date":
            filtered[param_name] = args.get("end_date")
        elif param_name == "bill_no":
            filtered[param_name] = args.get("bill_no")
        elif param_name == "name":
            filtered[param_name] = args.get("name")
        elif param_name == "mo_code":
            filtered[param_name] = args.get("mo_code")
        elif param_name == "inv_code":
            filtered[param_name] = args.get("inv_code")
        elif param_name == "wh_code":
            filtered[param_name] = args.get("wh_code")
        elif param_name == "num":
            filtered[param_name] = args.get("num")
        elif param_name == "year":
            filtered[param_name] = args.get("year")
    sql, params = sql_fn(**filtered)

    result = _run_query(sql, args, params=params)
    if isinstance(result, str):
        return result

    output_format = args.get("format", "text")
    if output_format == "json":
        return tool_result(data=result["rows"], has_more=result["has_more"])

    formatted = _format_table_result(result)
    return tool_result(data=formatted, records=result["rows"])


def _handle_u8_list_tables(args: dict) -> str:
    """列出精选业务表。"""
    keyword = args.get("keyword", "")
    if keyword:
        matched = []
        for tname, tinfo in _CURATED_TABLES.items():
            if keyword.lower() in tname.lower() or keyword.lower() in tinfo["name"].lower():
                matched.append(f"  {tname:30s} {tinfo['name']:20s} ({tinfo.get('module', '')})")
        if not matched:
            return tool_result(data=f"未找到匹配 '{keyword}' 的表")
        return tool_result(data=f"找到 {len(matched)} 张表：\n" + "\n".join(matched))

    lines = ["U8 已注册业务表清单：\n"]
    for tname, tinfo in sorted(_CURATED_TABLES.items()):
        lines.append(f"  {tname:30s} {tinfo['name']:20s} ({tinfo.get('module', '')})")
    lines.append(f"\n共 {len(_CURATED_TABLES)} 张表")
    return tool_result(data="\n".join(lines))


def _handle_u8_describe_table(args: dict) -> str:
    """查看某张表的中文字段对照。"""
    tname = args.get("table_name", "").strip()
    if not tname:
        return tool_error("table_name 参数不能为空")

    tinfo = _CURATED_TABLES.get(tname)
    if tinfo is None:
        return tool_error(f"未注册表: {tname}，可选表: {', '.join(_CURATED_TABLES.keys())}")

    lines = [f"{tname}（{tinfo['name']}，{tinfo.get('module', '')}）\n"]
    fields = tinfo.get("fields", {})
    for col, chn_name in fields.items():
        lines.append(f"  {col:25s} {chn_name}")
    return tool_result(data="\n".join(lines))


def _handle_u8_raw_sql(args: dict) -> str:
    """执行任意只读 SQL。"""
    sql = args.get("sql", "").strip()
    if not sql:
        return tool_error("sql 参数不能为空")

    db_config = _u8_db_config_or_none()
    if db_config is None:
        return tool_error("U8 数据库未配置，请在设置 → ERP → U8 中填写连接信息")

    try:
        validated = _validate_select(sql)
    except ValueError as e:
        return tool_error(str(e))

    result = _run_query(validated, args)
    if isinstance(result, str):
        return result

    output_format = args.get("format", "text")
    if output_format == "text":
        return tool_result(data=_format_table_result(result), records=result["rows"])
    return tool_result(data="SQL 查询完成", records=result["rows"])


# ═══════════════════════════════════════════════════════════════
# Schema + 注册
# ═══════════════════════════════════════════════════════════════

_U8_QUERY_PARAMS = {
    "type": "object",
    "properties": {
        "query_name": {
            "type": "string",
            "enum": list(_QUERY_MAP.keys()),
            "description": "查询类型。" + " ".join(f"{k}: {v[1]}" for k, v in _QUERY_MAP.items()),
        },
        "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
        "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
        "bill_no": {"type": "string", "description": "单据号模糊搜索"},
        "code": {"type": "string", "description": "编码模糊搜索（客户/供应商/仓库/存货/科目）"},
        "name": {"type": "string", "description": "名称模糊搜索（客户/供应商/仓库/存货）"},
        "mo_code": {"type": "string", "description": "生产订单号模糊搜索"},
        "inv_code": {"type": "string", "description": "物料/存货编码模糊搜索"},
        "wh_code": {"type": "string", "description": "仓库编码模糊搜索"},
        "num": {"type": "string", "description": "凭证号模糊搜索"},
        "format": {"type": "string", "enum": ["json", "text"], "description": "输出格式，默认 text"},
        "page": {"type": "integer", "description": "页码，从 1 开始"},
        "page_size": {"type": "integer", "description": "每页行数（默认 500，最大 500）", "default": 500},
    },
    "required": ["query_name"],
}

registry.register(
    name="u8_query",
    toolset="u8",
    check_fn=_u8_enabled,
    schema={
        "name": "u8_query",
        "description": "U8 业务数据查询。支持：客户档案(customer)、供应商档案(vendor)、仓库档案(warehouse)、会计科目(code)、存货档案(inventory)、物料表(bas_part)、销售订单(sales_order)、采购订单(purchase_order)、总账凭证(gl_voucher)、生产订单母件行(mom_orderdetail)、生产订单子件用料(mom_moallocate)、现存量(current_stock)。format=json 返回结构化数据，format=text 返回表格。",
        "parameters": _U8_QUERY_PARAMS,
    },
    handler=_handle_u8_query,
    emoji="🗄️",
)

registry.register(
    name="u8_list_tables",
    toolset="u8",
    check_fn=_u8_enabled,
    schema={
        "name": "u8_list_tables",
        "description": "列出 U8 已注册业务表清单。传 keyword 按表名/中文名搜索。",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "搜索关键字，如 '存货'、'SO_'、'凭证'"},
            },
        },
    },
    handler=_handle_u8_list_tables,
    emoji="📋",
)

registry.register(
    name="u8_describe_table",
    toolset="u8",
    check_fn=_u8_enabled,
    schema={
        "name": "u8_describe_table",
        "description": "查看 U8 某张表的中文字段对照。",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "表名，如 Customer、Inventory、SO_SOMain、PO_Pomain、GL_accvouch、CurrentStock、mom_orderdetail、mom_moallocate",
                },
            },
            "required": ["table_name"],
        },
    },
    handler=_handle_u8_describe_table,
    emoji="📖",
)

registry.register(
    name="u8_raw_sql",
    execution_mode="sequential",
    toolset="u8",
    check_fn=_u8_enabled,
    schema={
        "name": "u8_raw_sql",
        "description": "对 U8 数据库执行任意只读 SELECT 查询。写 SQL 前必须先用 u8_list_tables / u8_describe_table 确认已注册业务表和中文字段对照，不要猜表名和字段名。有安全校验。",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SELECT 语句"},
                "format": {"type": "string", "enum": ["json", "text"], "description": "输出格式，默认 text"},
                "page": {"type": "integer", "description": "页码"},
                "page_size": {"type": "integer", "description": "每页行数（默认 500，最大 500）", "default": 500},
            },
            "required": ["sql"],
        },
    },
    handler=_handle_u8_raw_sql,
    emoji="⚡",
)
