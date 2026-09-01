"""U9C ERP 工具 — 注册为内置工具。

U9C (U9 Cloud) 使用 SQL Server 数据库，通过 pymssql 直连。
U9C 表结构与 U8+ 完全不同，使用 U9 Cloud 模型（CBO_*/SM_*/PM_*/MO_* 前缀）。
工具 handler 内完成配置加载 → SQL 生成 → 执行 → 格式化 全过程。
"""

from __future__ import annotations

import os

from agent.tools.registry import registry, tool_error, tool_result

# ═══════════════════════════════════════════════════════════════
# U9C 配置
# ═══════════════════════════════════════════════════════════════


def _u9c_db_config_or_none() -> dict | None:
    """Return pymssql connection config dict, or None if not configured."""
    host = os.environ.get("U9C_HOST", "")
    port = os.environ.get("U9C_PORT", "")
    database = os.environ.get("U9C_DATABASE", "")
    user = os.environ.get("U9C_USER", "")
    password = os.environ.get("U9C_PASSWORD", "")
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
        return int(os.environ.get("U9C_MAX_ROWS", "500"))
    except ValueError:
        return 500


def _u9c_enabled() -> bool:
    """工具暴露门控：仅当 config.json 中 erp_clients.u9c.enabled=true 时
    才把 U9C 工具注册进 LLM 工具列表。"""
    try:
        from agent import config_manager

        ecfg = config_manager.load().erp_clients.get("u9c", {})
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
    """SQL Server 分页（OFFSET/FETCH NEXT）。"""
    stripped = sql.strip().rstrip(";").strip()
    offset = (page - 1) * page_size
    return f"{stripped} OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY"


def _execute_query(sql: str, page: int, page_size: int, params: dict | None = None) -> dict:
    """执行 SQL 查询，返回格式化的结果。

    Args:
        sql: SELECT 语句（可含 %(name)s 占位符）
        page: 页码（从 1 开始）
        page_size: 每页行数
        params: pymssql 参数化查询参数字典，如 {"start_date": "2024-01-01 00:00:00"}
    """
    import datetime
    from decimal import Decimal

    import pymssql

    db_config = _u9c_db_config_or_none()
    if db_config is None:
        raise ValueError("U9C 数据库未配置，请在设置 → ERP → U9C 中填写连接信息")

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
        params: pymssql 参数化查询参数字典，如 {"start_date": "2024-01-01 00:00:00"}
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
    col_widths = [len(str(c)) for c in cols]
    for row in rows:
        for i, val in enumerate(row.values()):
            col_widths[i] = max(col_widths[i], len(str(val or "")))
    header = " | ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(cols))
    separator = "-+-".join("-" * w for w in col_widths)
    lines = [header, separator]
    for row in rows:
        lines.append(" | ".join(str(row.get(c, "")).ljust(col_widths[i]) for i, c in enumerate(cols)))
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
# SQL 模板 — U9C 业务查询
# ═══════════════════════════════════════════════════════════════


def _sql_customer(code: str | None = None, name: str | None = None) -> tuple[str, dict]:
    """客户档案查询（CBO_Customer）。"""
    sql = """SELECT c.Code AS 客户编码, ISNULL(ct.Name, c.ShortName) AS 客户名称, c.SearchCode AS 搜索码,
    c.ShortName AS 简称, c.CustomerCategory AS 客户分类, c.Department AS 部门, c.Saleser AS 业务员,
    c.Org AS 组织, c.MasterOrg AS 主组织,
    CASE WHEN c.Effective_IsEffective = 1 THEN '有效' ELSE '无效' END AS 状态
FROM CBO_Customer c
LEFT JOIN CBO_Customer_Trl ct ON ct.ID = c.ID
WHERE 1=1"""
    params: dict = {}
    if code:
        sql += " AND c.Code LIKE %(code)s"
        params["code"] = f"%{code}%"
    if name:
        sql += " AND c.Name LIKE %(name)s"
        params["name"] = f"%{name}%"
    sql += " ORDER BY c.Code"
    return sql, params


def _sql_supplier(code: str | None = None, name: str | None = None) -> tuple[str, dict]:
    """供应商档案查询（CBO_Supplier）。"""
    sql = """SELECT s.Code AS 供应商编码, ISNULL(st.Name, s.ShortName) AS 供应商名称, s.SearchCode AS 搜索码,
    s.ShortName AS 简称, s.Category AS 供应商分类, s.Department AS 部门,
    s.Purchaser AS 采购员, s.Org AS 组织
FROM CBO_Supplier s
LEFT JOIN CBO_Supplier_Trl st ON st.ID = s.ID
WHERE 1=1"""
    params: dict = {}
    if code:
        sql += " AND s.Code LIKE %(code)s"
        params["code"] = f"%{code}%"
    if name:
        sql += " AND s.Name LIKE %(name)s"
        params["name"] = f"%{name}%"
    sql += " ORDER BY s.Code"
    return sql, params


def _sql_item(code: str | None = None, name: str | None = None) -> tuple[str, dict]:
    """物料档案查询（CBO_ItemMaster）。"""
    sql = """SELECT im.Code AS 物料编码, im.Name AS 物料名称, im.SearchCode AS 搜索码,
    im.Segment1 AS 分类1, im.Segment2 AS 分类2, im.SPECS AS 规格型号,
    im.InventoryUOM AS 库存单位, im.Weight AS 重量,
    CASE WHEN im.IsSalesEnable = 1 THEN '是' ELSE '否' END AS 可销售,
    CASE WHEN im.IsPurchaseEnable = 1 THEN '是' ELSE '否' END AS 可采购,
    CASE WHEN im.IsBuildEnable = 1 THEN '是' ELSE '否' END AS 可生产,
    CASE WHEN im.Effective_IsEffective = 1 THEN '有效' ELSE '无效' END AS 状态
FROM CBO_ItemMaster im WHERE 1=1"""
    params: dict = {}
    if code:
        sql += " AND im.Code LIKE %(code)s"
        params["code"] = f"%{code}%"
    if name:
        sql += " AND im.Name LIKE %(name)s"
        params["name"] = f"%{name}%"
    sql += " ORDER BY im.Code"
    return sql, params


def _sql_sales_order(
    start_date: str | None = None,
    end_date: str | None = None,
    bill_no: str | None = None,
    code: str | None = None,
) -> tuple[str, dict]:
    """销售订单查询（SM_SO 主表 + SM_SOLine 行明细，默认关联行数据）。"""
    where_clause = ""
    params: dict = {}
    if start_date:
        where_clause += " AND so.BusinessDate >= %(start_date)s"
        params["start_date"] = start_date + " 00:00:00"
    if end_date:
        where_clause += " AND so.BusinessDate <= %(end_date)s"
        params["end_date"] = end_date + " 23:59:59"
    if bill_no:
        where_clause += " AND so.DocNo LIKE %(bill_no)s"
        params["bill_no"] = f"%{bill_no}%"
    sql = f"""SELECT so.DocNo AS 订单号, so.BusinessDate AS 日期,
    so.CustomerPONo AS 客户采购单号,
    so.OrderBy_Code AS 客户编码, so.OrderBy_ShortName AS 客户简称,
    so.Payer_Code AS 付款方编码, so.Payer_ShortName AS 付款方简称,
    so.BillToSite_Code AS 收货方编码, so.ShipToSite_Code AS 发货方编码,
    so.Seller AS 销售员, so.SaleDepartment AS 销售部门,
    so.BusinessType AS 业务类型, so.Status AS 订单状态,
    so.PriceListCode AS 价表编码, so.PriceListName AS 价表名称,
    so.IsPriceIncludeTax AS 含税, so.TaxRate AS 税率,

    so.TotalNetMoneyTC AS 订单净额_本币, so.TotalTaxTC AS 订单税额_本币,
    so.TotalMoneyTC AS 订单价税合计_本币,
    so.TotalNetMoneyAC AS 订单净额_会计, so.TotalTaxAC AS 订单税额_会计,
    so.TotalMoneyAC AS 订单价税合计_会计,
    so.TotalDiscountTC AS 订单折扣_本币, so.TotalFeeTC AS 订单费用_本币,
    so.PreRecMoneyTC AS 已收款_本币, so.ExePreRecMoneyTC AS 实际收款_本币,

    sol.DocLineNo AS 行号,
    sol.ItemInfo_ItemCode AS 物料编码, sol.ItemInfo_ItemName AS 物料名称,
    sol.ItemInfo_ItemVersion AS 物料版本,
    sol.Manufacturer AS 制造商, sol.ManufacturerCode AS 制造商编码,
    sol.CustomerItemNo AS 客户物料号,
    sol.OrderByQtyTU AS 数量_交易单位, sol.OrderByQtyPU AS 数量_库存单位,
    sol.OrderByQtyTBU AS 数量_基本单位, sol.OrderPriceTC AS 单价_本币,
    sol.NetMoneyTC AS 净额_本币, sol.TaxMoneyTC AS 税额_本币,
    sol.TotalMoneyTC AS 价税合计_本币,
    sol.DiscountTC AS 折扣_本币, sol.FeeTC AS 费用_本币,
    sol.TaxRate AS 行税率,
    sol.Weight AS 重量, sol.Volume AS 体积,
    sol.Project AS 项目, sol.Task AS 任务,
    sol.PreRecQtyTU AS 已发货数量_交易, sol.PreRecQtyPU AS 已发货数量_库存,
    sol.PreRecMoneyTC AS 已收款金额_本币,
    sol.SOLineSumInfo_SumShipQtyTU AS 累计发货_交易,
    sol.SOLineSumInfo_SumInvoiceQtyTU AS 累计开票_交易,
    sol.SOLineSumInfo_SumConfirmQtyTU AS 累计签收_交易,
    sol.SOLineSumInfo_SumRecQtyTU AS 累计收货_交易,
    sol.SOLineSumInfo_SumRecMoneyTC AS 累计收款_本币,
    sol.SOLineSumInfo_SumRecMoneyAC AS 累计收款_会计,
    sol.SrcDocNo AS 来源单据号, sol.SrcDocLineNo AS 来源行号,
    sol.PreDeliveryDate AS 预计发货日期, sol.PreCompleteDate AS 预计完成日期,
    sol.Status AS 行状态
FROM SM_SO so
JOIN SM_SOLine sol ON sol.SO = so.ID
WHERE 1=1{where_clause}
ORDER BY so.BusinessDate DESC, so.DocNo, sol.DocLineNo"""
    return sql, params


def _sql_sales_order_line(
    start_date: str | None = None,
    end_date: str | None = None,
    bill_no: str | None = None,
) -> tuple[str, dict]:
    """销售订单行查询（SM_SOLine 关联 SM_SO）。"""
    where_clause = ""
    params: dict = {}
    if start_date:
        where_clause += " AND so.BusinessDate >= %(start_date)s"
        params["start_date"] = start_date + " 00:00:00"
    if end_date:
        where_clause += " AND so.BusinessDate <= %(end_date)s"
        params["end_date"] = end_date + " 23:59:59"
    if bill_no:
        where_clause += " AND so.DocNo LIKE %(bill_no)s"
        params["bill_no"] = f"%{bill_no}%"
    sql = f"""SELECT so.DocNo AS 订单号, so.BusinessDate AS 日期,
    so.OrderBy_ShortName AS 客户简称,
    sol.DocLineNo AS 行号,
    sol.ItemInfo_ItemCode AS 物料编码, sol.ItemInfo_ItemName AS 物料名称,
    sol.OrderByQtyTU AS 数量_交易单位, sol.OrderByQtyPU AS 数量_库存单位,
    sol.OrderPriceTC AS 单价_本币, sol.NetMoneyTC AS 净额_本币,
    sol.TaxMoneyTC AS 税额_本币, sol.TotalMoneyTC AS 价税合计_本币,
    sol.PreRecQtyTU AS 已发货数量, sol.PreRecQtyPU AS 已发货数量_库存
FROM SM_SOLine sol
JOIN SM_SO so ON so.ID = sol.SO
WHERE 1=1{where_clause}
ORDER BY so.BusinessDate DESC, so.DocNo, sol.DocLineNo"""
    return sql, params


def _sql_purchase_order(
    start_date: str | None = None,
    end_date: str | None = None,
    bill_no: str | None = None,
) -> tuple[str, dict]:
    """采购订单查询（PM_PurchaseOrder 主表 + PM_POLine 行明细，默认关联行数据）。"""
    where_clause = ""
    params: dict = {}
    if start_date:
        where_clause += " AND po.BusinessDate >= %(start_date)s"
        params["start_date"] = start_date + " 00:00:00"
    if end_date:
        where_clause += " AND po.BusinessDate <= %(end_date)s"
        params["end_date"] = end_date + " 23:59:59"
    if bill_no:
        where_clause += " AND po.DocNo LIKE %(bill_no)s"
        params["bill_no"] = f"%{bill_no}%"
    sql = f"""SELECT po.DocNo AS 采购单号, po.BusinessDate AS 日期,
    po.Supplier_Code AS 供应商编码, po.Supplier_ShortName AS 供应商简称,
    po.ShiptoSite_Code AS 收货方编码, po.PurDept AS 采购部门, po.PurOper AS 采购员,
    po.BizType AS 业务类型, po.TradeType AS 贸易类型, po.BarginType AS 交易方式,
    po.PriceListCode AS 价表编码, po.PriceListName AS 价表名称,
    po.IsPriceIncludeTax AS 含税, po.TaxRate AS 税率,
    po.TotalNetMnyTC AS 订单净额_本币, po.TotalTaxMnyTC AS 订单税额_本币,
    po.TotalMnyTC AS 订单价税合计_本币,
    po.TotalNetMnyAC AS 订单净额_会计, po.TotalTaxMnyAC AS 订单税额_会计,
    po.TotalMnyAC AS 订单价税合计_会计,
    po.TotalDiscountTC AS 订单折扣_本币, po.TotalFeeTC AS 订单费用_本币,
    po.PrePayMoneyTC AS 预付金额_本币, po.TotalPrePayedMnyTC AS 已预付_本币,
    po.TotalPayedMnyAC AS 已付款_会计, po.UnPayedMnyAC AS 未付款_会计,
    CASE po.Status
        WHEN 0 THEN '录入' WHEN 1 THEN '审核中' WHEN 2 THEN '审核'
        WHEN 3 THEN '部分到货' WHEN 4 THEN '完成' WHEN 5 THEN '关闭'
        ELSE CAST(ISNULL(po.Status,0) AS varchar) END AS 状态,
    po.CreatedBy AS 制单人, po.CreatedOn AS 制单时间,
    po.ApprovedBy AS 审核人, po.ApprovedOn AS 审核时间,
    po.VPPublishBy AS 发布人, po.VPConfirmBy AS 确认人,

    pol.DocLineNo AS 行号,
    pol.ItemInfo_ItemCode AS 物料编码, pol.ItemInfo_ItemName AS 物料名称,
    pol.ItemInfo_ItemVersion AS 物料版本,
    pol.Payer_Code AS 付款方编码, pol.Payer_ShortName AS 付款方简称,
    pol.BilltoSite_Code AS 收票方编码,
    pol.SuppierItemCode AS 供应商物料号,
    pol.PurQtyTU AS 数量_交易单位, pol.PurQtyPU AS 数量_库存单位,
    pol.PurQtyTBU AS 数量_基本单位,
    pol.OrderPriceTC AS 单价_本币, pol.NetMnyTC AS 净额_本币,
    pol.TotalTaxTC AS 税额_本币, pol.TotalMnyTC AS 价税合计_本币,
    pol.TotalDiscountTC AS 折扣_本币, pol.NetFeeTC AS 费用_本币,
    pol.TaxRate AS 行税率,
    pol.Weight AS 重量, pol.Volume AS 体积,
    pol.Project AS 项目, pol.Task AS 任务,
    pol.ReqQtyTU AS 请购数量, pol.PrePayQtyTU AS 已预付数量,
    pol.TotalRecievedQtyTU AS 累计收货数量,
    pol.TotalConfirmedQtyTU AS 累计确认数量,
    pol.TotalMatchedQtyTU AS 累计匹配数量,
    pol.TotalPayedMnyTC AS 累计已付款_本币,
    pol.TotalPrePayedMnyTC AS 累计已预付_本币,
    pol.SOInfo_SrcDocNo AS 来源销售单号, pol.SOInfo_SrcDocLineNo AS 来源行号,
    pol.SrcDocInfo_SrcDocNo AS 来源单据号, pol.SrcDocInfo_SrcDocLineNo AS 来源行号,
    pol.PriceListCode AS 行价表编码, pol.PriceListName AS 行价表名称,
    pol.Status AS 行状态, pol.IsPresent AS 赠品
FROM PM_PurchaseOrder po
JOIN PM_POLine pol ON pol.PurchaseOrder = po.ID
WHERE 1=1{where_clause}
ORDER BY po.BusinessDate DESC, po.DocNo, pol.DocLineNo"""
    return sql, params


def _sql_purchase_order_line(
    start_date: str | None = None,
    end_date: str | None = None,
    bill_no: str | None = None,
) -> tuple[str, dict]:
    """采购订单行查询（PM_POLine 关联 PM_PurchaseOrder）。"""
    where_clause = ""
    params: dict = {}
    if start_date:
        where_clause += " AND po.BusinessDate >= %(start_date)s"
        params["start_date"] = start_date + " 00:00:00"
    if end_date:
        where_clause += " AND po.BusinessDate <= %(end_date)s"
        params["end_date"] = end_date + " 23:59:59"
    if bill_no:
        where_clause += " AND po.DocNo LIKE %(bill_no)s"
        params["bill_no"] = f"%{bill_no}%"
    sql = f"""SELECT po.DocNo AS 采购单号, po.BusinessDate AS 日期,
    po.Supplier_ShortName AS 供应商简称,
    pol.DocLineNo AS 行号,
    pol.ItemInfo_ItemCode AS 物料编码, pol.ItemInfo_ItemName AS 物料名称,
    pol.PurQtyPU AS 数量_库存单位, pol.PurQtyTU AS 数量_交易单位,
    pol.OrderPriceTC AS 单价_本币, pol.NetMnyTC AS 净额_本币,
    pol.TotalTaxTC AS 税额_本币, pol.TotalMnyTC AS 价税合计_本币
FROM PM_POLine pol
JOIN PM_PurchaseOrder po ON po.ID = pol.PurchaseOrder
WHERE 1=1{where_clause}
ORDER BY po.BusinessDate DESC, po.DocNo, pol.DocLineNo"""
    return sql, params


def _sql_mo(
    start_date: str | None = None,
    end_date: str | None = None,
    mo_code: str | None = None,
) -> tuple[str, dict]:
    """生产订单查询（MO_MO 主表 + MO_MOOutput 产出明细，默认关联产出数据）。"""
    where_clause = ""
    params: dict = {}
    if start_date:
        where_clause += " AND mo.BusinessDate >= %(start_date)s"
        params["start_date"] = start_date + " 00:00:00"
    if end_date:
        where_clause += " AND mo.BusinessDate <= %(end_date)s"
        params["end_date"] = end_date + " 23:59:59"
    if mo_code:
        where_clause += " AND mo.DocNo LIKE %(mo_code)s"
        params["mo_code"] = f"%{mo_code}%"
    sql = f"""SELECT mo.DocNo AS 生产订单号, mo.BusinessDate AS 日期,
    im.Name AS 物料名称, im.Code AS 物料编码,
    mo.ProductQty AS 计划数量, mo.TotalCompleteQty AS 累计完工数量,
    mo.TotalRcvQty AS 累计入库数量, mo.TotalScrapQty AS 累计报废数量,
    mo.StartDate AS 计划开工日期, mo.CompleteDate AS 计划完工日期,
    mo.ActualStartDate AS 实际开工日期, mo.ActualCompleteDate AS 实际完工日期,
    mo.CreatedBy AS 制单人, mo.CreatedOn AS 制单时间,
    mo.IsCancel AS 已取消,
    CASE mo.DocState
        WHEN 0 THEN '录入' WHEN 1 THEN '审核' WHEN 2 THEN '下达'
        WHEN 3 THEN '开工' WHEN 4 THEN '完工' WHEN 5 THEN '关闭'
        ELSE CAST(ISNULL(mo.DocState,0) AS varchar) END AS 状态,

    outp.OutputType AS 产出类型, outp.Item AS 产出物料ID,
    oim.Name AS 产出物料名称, oim.Code AS 产出物料编码,
    outp.PlanOutputQty AS 计划产出数量, outp.ActualCompleteQty AS 实际完工数量,
    outp.ActualReworkQty AS 返工数量, outp.ActualScrapQty AS 报废数量,
    outp.ActualRcvQty AS 入库数量, outp.ActualEligibleQty AS 合格数量
FROM MO_MO mo
LEFT JOIN CBO_ItemMaster im ON im.ID = mo.ItemMaster
LEFT JOIN MO_MOOutput outp ON outp.MO = mo.ID
LEFT JOIN CBO_ItemMaster oim ON oim.ID = outp.Item
WHERE 1=1{where_clause}
ORDER BY mo.BusinessDate DESC, mo.DocNo, outp.OutputType"""
    return sql, params


def _sql_mo_bom_detail(
    mo_code: str | None = None,
) -> tuple[str, dict]:
    """生产订单BOM明细查询（MO_MOBOMDetail 关联 MO_MO）。"""
    sql = """SELECT mo.DocNo AS 生产订单号, im.Name AS 物料名称, im.Code AS 物料编码,
    bd.ProductQty AS 数量, bd.Multiple AS 倍数, bd.BOMMaster AS BOM主档
FROM MO_MOBOMDetail bd
JOIN MO_MO mo ON mo.ID = bd.MO
LEFT JOIN CBO_ItemMaster im ON im.ID = mo.ItemMaster
WHERE 1=1"""
    params: dict = {}
    if mo_code:
        sql += " AND mo.DocNo LIKE %(mo_code)s"
        params["mo_code"] = f"%{mo_code}%"
    sql += " ORDER BY mo.DocNo"
    return sql, params


def _sql_mo_output(
    start_date: str | None = None,
    end_date: str | None = None,
    mo_code: str | None = None,
) -> tuple[str, dict]:
    """生产订单产出查询（MO_MOOutput 关联 MO_MO）。"""
    where_clause = ""
    params: dict = {}
    if start_date:
        where_clause += " AND mo.BusinessDate >= %(start_date)s"
        params["start_date"] = start_date + " 00:00:00"
    if end_date:
        where_clause += " AND mo.BusinessDate <= %(end_date)s"
        params["end_date"] = end_date + " 23:59:59"
    if mo_code:
        where_clause += " AND mo.DocNo LIKE %(mo_code)s"
        params["mo_code"] = f"%{mo_code}%"
    sql = f"""SELECT mo.DocNo AS 生产订单号,
    outp.OutputType AS 产出类型, outp.Item AS 物料ID,
    im.Name AS 物料名称, im.Code AS 物料编码,
    outp.PlanOutputQty AS 计划产出数量, outp.ActualCompleteQty AS 实际完工数量,
    outp.ActualReworkQty AS 返工数量, outp.ActualScrapQty AS 报废数量,
    outp.ActualRcvQty AS 入库数量, outp.ActualEligibleQty AS 合格数量
FROM MO_MOOutput outp
JOIN MO_MO mo ON mo.ID = outp.MO
LEFT JOIN CBO_ItemMaster im ON im.ID = outp.Item
WHERE 1=1{where_clause}
ORDER BY mo.DocNo, outp.OutputType"""
    return sql, params


# ═══════════════════════════════════════════════════════════════
# 查询类型映射
# ═══════════════════════════════════════════════════════════════

_QUERY_MAP = {
    "customer": (_sql_customer, "客户档案"),
    "supplier": (_sql_supplier, "供应商档案"),
    "item": (_sql_item, "物料档案"),
    "sales_order": (_sql_sales_order, "销售订单（含行明细）"),
    "sales_order_line": (_sql_sales_order_line, "销售订单行"),
    "purchase_order": (_sql_purchase_order, "采购订单（含行明细）"),
    "purchase_order_line": (_sql_purchase_order_line, "采购订单行"),
    "mo": (_sql_mo, "生产订单（含产出明细）"),
    "mo_bom_detail": (_sql_mo_bom_detail, "生产订单BOM明细"),
    "mo_output": (_sql_mo_output, "生产订单产出"),
}

# 各查询类型的参数说明
_QUERY_PARAM_HELP: dict[str, str] = {
    "customer": "客户编码(code)、客户名称(name) 模糊搜索",
    "supplier": "供应商编码(code)、供应商名称(name) 模糊搜索",
    "item": "物料编码(code)、物料名称(name) 模糊搜索",
    "sales_order": "日期范围(start_date, end_date)、订单号(bill_no) 模糊搜索",
    "sales_order_line": "日期范围(start_date, end_date)、订单号(bill_no) 模糊搜索",
    "purchase_order": "日期范围(start_date, end_date)、订单号(bill_no) 模糊搜索",
    "purchase_order_line": "日期范围(start_date, end_date)、订单号(bill_no) 模糊搜索",
    "mo": "日期范围(start_date, end_date)、生产订单号(mo_code) 模糊搜索",
    "mo_bom_detail": "生产订单号(mo_code) 模糊搜索",
    "mo_output": "日期范围(start_date, end_date)、生产订单号(mo_code) 模糊搜索",
}


# ═══════════════════════════════════════════════════════════════
# 数据字典
# ═══════════════════════════════════════════════════════════════

_CURATED_TABLES: dict[str, dict] = {
    "CBO_Customer": {
        "name": "客户档案",
        "module": "基础数据",
        "fields": {
            "Code": "客户编码",
            "Name": "客户名称",
            "SearchCode": "搜索码",
            "CustomerCategory": "客户分类",
            "Department": "部门",
            "Saleser": "业务员",
            "Org": "组织",
            "MasterOrg": "主组织",
            "Effective_IsEffective": "是否有效",
        },
    },
    "CBO_Supplier": {
        "name": "供应商档案",
        "module": "基础数据",
        "fields": {
            "Code": "供应商编码",
            "Name": "供应商名称",
            "SearchCode": "搜索码",
            "ShortName": "简称",
            "Category": "供应商分类",
            "Department": "部门",
            "Purchaser": "采购员",
            "Org": "组织",
        },
    },
    "CBO_ItemMaster": {
        "name": "物料档案",
        "module": "基础数据",
        "fields": {
            "Code": "物料编码",
            "Name": "物料名称",
            "SearchCode": "搜索码",
            "SPECS": "规格型号",
            "InventoryUOM": "库存单位",
            "Weight": "重量",
            "IsSalesEnable": "可销售",
            "IsPurchaseEnable": "可采购",
            "IsBuildEnable": "可生产",
            "Effective_IsEffective": "是否有效",
        },
    },
    "SM_SO": {
        "name": "销售订单主表（含行明细）",
        "module": "销售管理",
        "fields": {
            "DocNo": "订单号",
            "BusinessDate": "业务日期",
            "CustomerPONo": "客户采购单号",
            "OrderBy_Code": "客户编码",
            "OrderBy_ShortName": "客户简称",
            "Payer_Code": "付款方编码",
            "Payer_ShortName": "付款方简称",
            "BillToSite_Code": "收货方编码",
            "ShipToSite_Code": "发货方编码",
            "Seller": "销售员",
            "SaleDepartment": "销售部门",
            "BusinessType": "业务类型",
            "Status": "订单状态",
            "PriceListCode": "价表编码",
            "PriceListName": "价表名称",
            "IsPriceIncludeTax": "含税",
            "TaxRate": "税率",
            "TotalNetMoneyTC": "订单净额_本币",
            "TotalTaxTC": "订单税额_本币",
            "TotalMoneyTC": "订单价税合计_本币",
            "TotalNetMoneyAC": "订单净额_会计",
            "TotalTaxAC": "订单税额_会计",
            "TotalMoneyAC": "订单价税合计_会计",
            "TotalDiscountTC": "订单折扣_本币",
            "TotalFeeTC": "订单费用_本币",
            "PreRecMoneyTC": "已收款_本币",
            "ExePreRecMoneyTC": "实际收款_本币",
        },
    },
    "SM_SOLine": {
        "name": "销售订单行",
        "module": "销售管理",
        "fields": {
            "DocLineNo": "行号",
            "ItemInfo_ItemCode": "物料编码",
            "ItemInfo_ItemName": "物料名称",
            "ItemInfo_ItemVersion": "物料版本",
            "Manufacturer": "制造商",
            "CustomerItemNo": "客户物料号",
            "OrderByQtyTU": "数量_交易单位",
            "OrderByQtyPU": "数量_库存单位",
            "OrderByQtyTBU": "数量_基本单位",
            "OrderPriceTC": "单价_本币",
            "NetMoneyTC": "净额_本币",
            "TaxMoneyTC": "税额_本币",
            "TotalMoneyTC": "价税合计_本币",
            "DiscountTC": "折扣_本币",
            "FeeTC": "费用_本币",
            "Weight": "重量",
            "Volume": "体积",
            "Project": "项目",
            "Task": "任务",
            "PreRecQtyTU": "已发货数量_交易",
            "PreRecQtyPU": "已发货数量_库存",
            "SOLineSumInfo_SumShipQtyTU": "累计发货_交易",
            "SOLineSumInfo_SumInvoiceQtyTU": "累计开票_交易",
            "SOLineSumInfo_SumConfirmQtyTU": "累计签收_交易",
            "SOLineSumInfo_SumRecQtyTU": "累计收货_交易",
            "SOLineSumInfo_SumRecMoneyTC": "累计收款_本币",
            "SrcDocNo": "来源单据号",
            "PreDeliveryDate": "预计发货日期",
            "PreCompleteDate": "预计完成日期",
        },
    },

    "PM_PurchaseOrder": {
        "name": "采购订单主表（含行明细）",
        "module": "采购管理",
        "fields": {
            "DocNo": "采购单号",
            "BusinessDate": "业务日期",
            "Supplier_Code": "供应商编码",
            "Supplier_ShortName": "供应商简称",
            "ShiptoSite_Code": "收货方编码",
            "PurDept": "采购部门",
            "PurOper": "采购员",
            "BizType": "业务类型",
            "TradeType": "贸易类型",
            "PriceListCode": "价表编码",
            "PriceListName": "价表名称",
            "IsPriceIncludeTax": "含税",
            "TaxRate": "税率",
            "TotalNetMnyTC": "订单净额_本币",
            "TotalTaxMnyTC": "订单税额_本币",
            "TotalMnyTC": "订单价税合计_本币",
            "TotalNetMnyAC": "订单净额_会计",
            "TotalTaxMnyAC": "订单税额_会计",
            "TotalMnyAC": "订单价税合计_会计",
            "TotalDiscountTC": "订单折扣_本币",
            "TotalFeeTC": "订单费用_本币",
            "PrePayMoneyTC": "预付金额_本币",
            "TotalPrePayedMnyTC": "已预付_本币",
            "TotalPayedMnyAC": "已付款_会计",
            "UnPayedMnyAC": "未付款_会计",
            "Status": "状态",
            "CreatedBy": "制单人",
            "ApprovedBy": "审核人",
        },
    },
    "PM_POLine": {
        "name": "采购订单行",
        "module": "采购管理",
        "fields": {
            "DocLineNo": "行号",
            "ItemInfo_ItemCode": "物料编码",
            "ItemInfo_ItemName": "物料名称",
            "ItemInfo_ItemVersion": "物料版本",
            "Payer_Code": "付款方编码",
            "Payer_ShortName": "付款方简称",
            "SuppierItemCode": "供应商物料号",
            "PurQtyTU": "数量_交易单位",
            "PurQtyPU": "数量_库存单位",
            "PurQtyTBU": "数量_基本单位",
            "OrderPriceTC": "单价_本币",
            "NetMnyTC": "净额_本币",
            "TotalTaxTC": "税额_本币",
            "TotalMnyTC": "价税合计_本币",
            "TotalDiscountTC": "折扣_本币",
            "NetFeeTC": "费用_本币",
            "Weight": "重量",
            "Volume": "体积",
            "Project": "项目",
            "Task": "任务",
            "ReqQtyTU": "请购数量",
            "TotalRecievedQtyTU": "累计收货数量",
            "TotalConfirmedQtyTU": "累计确认数量",
            "TotalPayedMnyTC": "累计已付款_本币",
            "TotalPrePayedMnyTC": "累计已预付_本币",
            "SOInfo_SrcDocNo": "来源销售单号",
            "PriceListCode": "行价表编码",
            "IsPresent": "赠品",
        },
    },
    "MO_MO": {
        "name": "生产订单（含产出明细）",
        "module": "生产制造",
        "fields": {
            "DocNo": "生产订单号",
            "BusinessDate": "业务日期",
            "ItemMaster": "物料ID",
            "ProductQty": "计划数量",
            "TotalCompleteQty": "累计完工数量",
            "TotalRcvQty": "累计入库数量",
            "TotalScrapQty": "累计报废数量",
            "StartDate": "计划开工日期",
            "CompleteDate": "计划完工日期",
            "ActualStartDate": "实际开工日期",
            "ActualCompleteDate": "实际完工日期",
            "DocState": "状态",
            "IsCancel": "已取消",
        },
    },
    "MO_MOBOMDetail": {
        "name": "生产订单BOM明细",
        "module": "生产制造",
        "fields": {
            "ProductQty": "数量",
            "Multiple": "倍数",
            "BOMMaster": "BOM主档",
        },
    },
    "MO_MOOutput": {
        "name": "生产订单产出",
        "module": "生产制造",
        "fields": {
            "OutputType": "产出类型",
            "Item": "物料ID",
            "PlanOutputQty": "计划产出数量",
            "ActualCompleteQty": "实际完工数量",
            "ActualReworkQty": "返工数量",
            "ActualScrapQty": "报废数量",
            "ActualRcvQty": "入库数量",
            "ActualEligibleQty": "合格数量",
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


def _handle_u9c_query(args: dict) -> str:
    """U9C 通用查询入口。"""
    query_name = args.get("query_name", "")
    if not query_name:
        return tool_error("query_name 参数不能为空")

    query_def = _QUERY_MAP.get(query_name)
    if query_def is None:
        return tool_error(f"不支持的查询类型: {query_name}，可选: {', '.join(_QUERY_MAP.keys())}")

    sql_fn, description = query_def
    import inspect

    sig = inspect.signature(sql_fn)
    filtered = {}
    for param_name in sig.parameters:
        if param_name == "code":
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
    sql, params = sql_fn(**filtered)

    result = _run_query(sql, args, params=params)
    if isinstance(result, str):
        return result

    output_format = args.get("format", "text")
    if output_format == "json":
        return tool_result(data=result["rows"], has_more=result["has_more"])

    formatted = _format_table_result(result)
    return tool_result(data=formatted, records=result["rows"])


def _handle_u9c_list_tables(args: dict) -> str:
    """列出精选业务表。"""
    keyword = args.get("keyword", "")
    if keyword:
        matched = []
        for tname, tinfo in _CURATED_TABLES.items():
            if keyword.lower() in tname.lower() or keyword.lower() in tinfo["name"].lower():
                matched.append(f"  {tname:35s} {tinfo['name']:20s} ({tinfo.get('module', '')})")
        if not matched:
            return tool_result(data=f"未找到匹配 '{keyword}' 的表")
        return tool_result(data=f"找到 {len(matched)} 张表：\n" + "\n".join(matched))

    lines = ["U9C 已注册业务表清单：\n"]
    for tname, tinfo in sorted(_CURATED_TABLES.items()):
        lines.append(f"  {tname:35s} {tinfo['name']:20s} ({tinfo.get('module', '')})")
    lines.append(f"\n共 {len(_CURATED_TABLES)} 张表")
    return tool_result(data="\n".join(lines))


def _handle_u9c_describe_table(args: dict) -> str:
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
        lines.append(f"  {col:45s} {chn_name}")
    return tool_result(data="\n".join(lines))


def _handle_u9c_raw_sql(args: dict) -> str:
    """执行任意只读 SQL。"""
    sql = args.get("sql", "").strip()
    if not sql:
        return tool_error("sql 参数不能为空")

    db_config = _u9c_db_config_or_none()
    if db_config is None:
        return tool_error("U9C 数据库未配置，请在设置 → ERP → U9C 中填写连接信息")

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

_U9C_QUERY_PARAMS = {
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
        "code": {"type": "string", "description": "编码模糊搜索（客户/供应商/物料）"},
        "name": {"type": "string", "description": "名称模糊搜索（客户/供应商/物料）"},
        "mo_code": {"type": "string", "description": "生产订单号模糊搜索"},
        "format": {"type": "string", "enum": ["json", "text"], "description": "输出格式，默认 text"},
        "page": {"type": "integer", "description": "页码，从 1 开始"},
        "page_size": {"type": "integer", "description": "每页行数（默认 500，最大 500）", "default": 500},
    },
    "required": ["query_name"],
}

registry.register(
    name="u9c_query",
    toolset="u9c",
    check_fn=_u9c_enabled,
    schema={
        "name": "u9c_query",
        "description": "U9C 业务数据查询。支持：客户档案(customer)、供应商档案(supplier)、物料档案(item)、销售订单含行明细(sales_order)、销售订单行(sales_order_line)、采购订单含行明细(purchase_order)、采购订单行(purchase_order_line)、生产订单含产出明细(mo)、生产订单BOM明细(mo_bom_detail)、生产订单产出(mo_output)。format=json 返回结构化数据，format=text 返回表格。",
        "parameters": _U9C_QUERY_PARAMS,
    },
    handler=_handle_u9c_query,
    emoji="🗄️",
)

registry.register(
    name="u9c_list_tables",
    toolset="u9c",
    check_fn=_u9c_enabled,
    schema={
        "name": "u9c_list_tables",
        "description": "列出 U9C 已注册业务表清单。传 keyword 按表名/中文名搜索。",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "搜索关键字，如 '客户'、'SM_'、'订单'"},
            },
        },
    },
    handler=_handle_u9c_list_tables,
    emoji="📋",
)

registry.register(
    name="u9c_describe_table",
    toolset="u9c",
    check_fn=_u9c_enabled,
    schema={
        "name": "u9c_describe_table",
        "description": "查看 U9C 某张表的中文字段对照。",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "表名，如 CBO_Customer、CBO_Supplier、CBO_ItemMaster、SM_SO、SM_SOLine、PM_PurchaseOrder、PM_POLine、MO_MO、MO_MOBOMDetail、MO_MOOutput",
                },
            },
            "required": ["table_name"],
        },
    },
    handler=_handle_u9c_describe_table,
    emoji="📖",
)

registry.register(
    name="u9c_raw_sql",
    execution_mode="sequential",
    toolset="u9c",
    check_fn=_u9c_enabled,
    schema={
        "name": "u9c_raw_sql",
        "description": "对 U9C 数据库执行任意只读 SELECT 查询。写 SQL 前必须先用 u9c_list_tables / u9c_describe_table 确认已注册业务表和中文字段对照，不要猜表名和字段名。有安全校验。",
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
    handler=_handle_u9c_raw_sql,
    emoji="⚡",
)
