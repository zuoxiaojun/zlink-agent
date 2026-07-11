"""
NC-MCP 查询模块 - 采购订单（精简字段版）
"""

_PO_COLS = """
    h.VBILLCODE               AS "订单编号",
    h.DBILLDATE                AS "订单日期",
    CASE h.FORDERSTATUS WHEN 0 THEN '自由' WHEN 1 THEN '提交' WHEN 2 THEN '正在审批' WHEN 3 THEN '审批' WHEN 4 THEN '审批不通过' WHEN 5 THEN '输出' END AS "单据状态",
    h.VTRANTYPECODE || ' (' || btype.BILLTYPENAME || ')' AS "订单类型",
    curr.CODE || ' (' || curr.NAME || ')' AS "币种",
    h.NTOTALASTNUM              AS "总数量",
    h.NTOTALORIGMNY            AS "价税合计",
    h.VMEMO                    AS "备注",
    sup.CODE                   AS "供应商编码",
    sup.NAME                   AS "供应商名称",
    b.CROWNO                   AS "行号",
    mat.CODE                   AS "物料编码",
    mat.NAME                   AS "物料名称",
    meas.CODE || ' (' || meas.NAME || ')' AS "单位",
    b.NASTNUM                  AS "数量",
    b.NORIGPRICE               AS "无税单价",
    b.NORIGMNY                 AS "无税金额",
    b.NORIGTAXPRICE            AS "含税单价",
    b.NORIGTAXMNY              AS "价税合计_行",
    b.NTAX                     AS "税额",
    b.NTAXRATE                 AS "税率",
    b.DPLANARRVDATE            AS "计划到货日期",
    CASE bb.FONWAYSTATUS WHEN 0 THEN '审核' WHEN 1 THEN '输出' WHEN 2 THEN '确认' WHEN 3 THEN '发货' WHEN 4 THEN '装运' WHEN 5 THEN '报关' WHEN 6 THEN '出关' WHEN 7 THEN '到货' WHEN 8 THEN '入库' END AS "在途状态",
    bb1.VBILLCODE              AS "到货计划号"
"""


def _po_sql(where: str, params: dict | None = None) -> tuple[str, dict | None]:
    return (
        f"""
SELECT{_PO_COLS}
FROM PO_ORDER h
LEFT JOIN PO_ORDER_B b ON b.PK_ORDER = h.PK_ORDER AND b.DR = 0
LEFT JOIN PO_ORDER_BB bb ON bb.PK_ORDER_B = b.PK_ORDER_B AND bb.DR = 0
LEFT JOIN PO_ORDER_BB1 bb1 ON bb1.PK_ORDER_B = b.PK_ORDER_B AND bb1.DR = 0
LEFT JOIN BD_SUPPLIER sup ON sup.PK_SUPPLIER = h.PK_SUPPLIER
LEFT JOIN BD_MATERIAL mat ON mat.PK_MATERIAL = b.PK_MATERIAL
LEFT JOIN BD_CURRTYPE curr ON curr.PK_CURRTYPE = h.CORIGCURRENCYID
LEFT JOIN BD_MEASDOC meas ON meas.PK_MEASDOC = b.CASTUNITID
LEFT JOIN (SELECT DISTINCT PK_BILLTYPECODE, BILLTYPENAME FROM BD_BILLTYPE) btype ON btype.PK_BILLTYPECODE = h.VTRANTYPECODE
WHERE h.DR = 0{where}
ORDER BY h.DBILLDATE DESC, b.CROWNO
""",
        params,
    )


def query_purchase_order(start_date: str | None = None, end_date: str | None = None) -> tuple[str, dict | None]:
    where = ""
    params: dict = {}
    if start_date:
        where += " AND h.DBILLDATE >= :start_date"
        params["start_date"] = start_date + " 00:00:00"
    if end_date:
        where += " AND h.DBILLDATE <= :end_date"
        params["end_date"] = end_date + " 23:59:59"
    return _po_sql(where, params or None)


def query_purchase_order_by_code(billcode: str) -> tuple[str, dict]:
    sql, _ = _po_sql(" AND h.VBILLCODE = :billcode", {"billcode": billcode})
    return sql, {"billcode": billcode}


QUERIES = {
    "purchase_order": {
        "description": "采购订单查询（精简字段：订单编号/日期/供应商/物料/数量/金额/在途状态）。支持日期过滤：start_date/end_date 格式 YYYY-MM-DD",
        "handler": query_purchase_order,
    },
    "purchase_order_by_code": {
        "description": "按订单编号查询采购订单",
        "handler": query_purchase_order_by_code,
    },
}
