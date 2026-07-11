"""
NC-MCP 查询模块 - 销售订单（精简字段版）
"""

_SO_COLS = """
h.VBILLCODE              AS "单据号",
    h.DBILLDATE               AS "单据日期",
    CASE h.FSTATUSFLAG WHEN 1 THEN '自由' WHEN 2 THEN '审批通过' WHEN 3 THEN '冻结' WHEN 4 THEN '关闭' WHEN 5 THEN '失效' WHEN 7 THEN '审批中' WHEN 8 THEN '审批不通过' END AS "单据状态",
    CASE h.FPFSTATUSFLAG WHEN 0 THEN '未提交' WHEN 1 THEN '审批中' WHEN 2 THEN '审批通过' WHEN 3 THEN '已驳回' END AS "审批流状态",
    h.VTRANTYPECODE || ' (' || btype.BILLTYPENAME || ')' AS "订单类型",
    curr.CODE || ' (' || curr.NAME || ')' AS "原币",
    h.NTOTALNUM               AS "总数量",
    h.NTOTALORIGMNY           AS "价税合计",
    h.VNOTE                   AS "备注",
    cust.CODE                 AS "客户编码",
    cust.NAME                 AS "客户名称",
    b.CROWNO                  AS "行号",
    mat.CODE                  AS "物料编码",
    mat.NAME                  AS "物料名称",
    meas.CODE || ' (' || meas.NAME || ')' AS "单位",
    b.NASTNUM                 AS "数量",
    b.NORIGPRICE              AS "无税单价",
    b.NORIGMNY                AS "无税金额",
    b.NORIGTAXPRICE           AS "含税单价",
    b.NORIGTAXMNY             AS "价税合计_行",
    b.NTAX                    AS "税额",
    b.NTAXRATE                AS "税率",
    b.DSENDDATE               AS "发货日期",
    b.DRECEIVEDATE            AS "到货日期",
    CASE b.FROWSTATUS WHEN 1 THEN '自由' WHEN 2 THEN '审批通过' WHEN 3 THEN '冻结' WHEN 4 THEN '关闭' WHEN 5 THEN '失效' WHEN 7 THEN '审批中' WHEN 8 THEN '审批不通过' END AS "行状态",
    ex.NTOTALSENDNUM          AS "累计发货数量",
    ex.NTOTALOUTNUM           AS "累计出库数量",
    ex.NTOTALINVOICENUM       AS "累计开票数量"
"""


def _so_sql(where: str, params: dict | None = None) -> tuple[str, dict | None]:
    return (
        f"""
SELECT{_SO_COLS}
FROM SO_SALEORDER h
LEFT JOIN SO_SALEORDER_B b ON b.CSALEORDERID = h.CSALEORDERID AND b.DR = 0
LEFT JOIN SO_SALEORDER_EXE ex ON ex.CSALEORDERBID = b.CSALEORDERBID
LEFT JOIN BD_CUSTOMER cust ON cust.PK_CUSTOMER = h.CCUSTOMERID
LEFT JOIN BD_MATERIAL mat ON mat.PK_MATERIAL = b.CMATERIALVID
LEFT JOIN BD_CURRTYPE curr ON curr.PK_CURRTYPE = h.CORIGCURRENCYID
LEFT JOIN BD_MEASDOC meas ON meas.PK_MEASDOC = b.CASTUNITID
LEFT JOIN (SELECT DISTINCT PK_BILLTYPECODE, BILLTYPENAME FROM BD_BILLTYPE) btype ON btype.PK_BILLTYPECODE = h.VTRANTYPECODE
WHERE h.DR = 0{where}
ORDER BY h.DBILLDATE DESC, b.CROWNO
""",
        params,
    )


def query_sales_order(start_date: str | None = None, end_date: str | None = None) -> tuple[str, dict | None]:
    where = ""
    params: dict = {}
    if start_date:
        where += " AND h.DBILLDATE >= :start_date"
        params["start_date"] = start_date + " 00:00:00"
    if end_date:
        where += " AND h.DBILLDATE <= :end_date"
        params["end_date"] = end_date + " 23:59:59"
    return _so_sql(where, params or None)


def query_sales_order_by_code(billcode: str) -> tuple[str, dict]:
    sql, _ = _so_sql(" AND h.VBILLCODE = :billcode", {"billcode": billcode})
    return sql, {"billcode": billcode}


QUERIES = {
    "sales_order": {
        "description": "销售订单查询（精简字段：单据号/日期/状态/客户/物料/数量/金额）。支持日期过滤：start_date/end_date 格式 YYYY-MM-DD",
        "handler": query_sales_order,
    },
    "sales_order_by_code": {
        "description": "按单据号查询销售订单",
        "handler": query_sales_order_by_code,
    },
}
