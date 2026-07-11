"""NC-MCP 查询模块 - 客户（精简字段版）"""

_CUST_COLS = """
    cust.CODE                 AS "客户编码",
    cust.NAME                 AS "客户名称",
    cust.SHORTNAME            AS "客户简称",
    cust.CUSTPROP             AS "客户类型",
    cust.CUSTSTATE            AS "客户状态",
    cust.ENABLESTATE          AS "启用状态",
    cls.CODE || ' (' || cls.NAME || ')' AS "客户基本分类",
    cust.TRADE                AS "所属行业",
    cust.LEGALBODY            AS "法人",
    cust.REGISTERFUND         AS "注册资金",
    cust.TAXPAYERID           AS "纳税人登记号",
    cust.TEL1                 AS "电话1",
    cust.FAX1                 AS "传真1",
    cust.EMAIL                AS "e-mail地址",
    cust.CORPADDRESS          AS "企业地址",
    cust.MEMO                 AS "备注",
    cust.ISFREECUST           AS "散户",
    cust.ISRETAILSTORE        AS "零售门店"
"""


def query_customer(code: str | None = None, name: str | None = None) -> tuple[str, dict | None]:
    sql = f"""SELECT{_CUST_COLS}
FROM BD_CUSTOMER cust
LEFT JOIN BD_CUSTCLASS cls ON cls.PK_CUSTCLASS = cust.PK_CUSTCLASS
WHERE cust.DR = 0"""
    params = {}
    if code:
        sql += " AND cust.CODE LIKE :code"
        params["code"] = f"%{code}%"
    if name:
        sql += " AND cust.NAME LIKE :name"
        params["name"] = f"%{name}%"
    sql += " ORDER BY cust.CODE"
    return sql, params or None


QUERIES = {
    "customer": {
        "description": "查询客户基本信息（精简字段：编码/名称/状态/地区/联系方式）。支持按编码/名称模糊搜索：code/name",
        "handler": query_customer,
    },
}
