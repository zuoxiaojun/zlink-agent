"""NC-MCP 查询模块 - 供应商（精简字段版）"""

_SUPP_COLS = """
    sup.CODE              AS "供应商编码",
    sup.NAME              AS "供应商名称",
    sup.SHORTNAME         AS "供应商简称",
    sup.SUPSTATE          AS "供应商状态",
    sup.ENABLESTATE       AS "启用状态",
    cls.CODE || ' (' || cls.NAME || ')' AS "供应商分类",
    sup.TRADE             AS "所属行业",
    sup.LEGALBODY         AS "法人",
    sup.REGISTERFUND      AS "注册资金",
    sup.TAXPAYERID        AS "纳税人登记号",
    sup.TEL1              AS "电话1",
    sup.FAX1              AS "传真1",
    sup.EMAIL             AS "e-mail地址",
    sup.CORPADDRESS       AS "企业地址",
    sup.MEMO              AS "备注",
    sup.ESTABLISHDATE     AS "成立日期",
    sup.BUSLICENSENUM     AS "营业执照号"
"""


def query_supplier(code: str | None = None, name: str | None = None) -> tuple[str, dict | None]:
    sql = f"""SELECT{_SUPP_COLS}
FROM BD_SUPPLIER sup
LEFT JOIN BD_SUPPLIERCLASS cls ON cls.PK_SUPPLIERCLASS = sup.PK_SUPPLIERCLASS
WHERE sup.DR = 0"""
    params = {}
    if code:
        sql += " AND sup.CODE LIKE :code"
        params["code"] = f"%{code}%"
    if name:
        sql += " AND sup.NAME LIKE :name"
        params["name"] = f"%{name}%"
    sql += " ORDER BY sup.CODE"
    return sql, params or None


QUERIES = {
    "supplier": {
        "description": "查询供应商基本信息（精简字段：编码/名称/状态/地区/联系方式）。支持按编码/名称模糊搜索：code/name",
        "handler": query_supplier,
    },
}
