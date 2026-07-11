"""NC-MCP 查询模块 - 组织（精简字段版）"""

_ORG_COLS = """
    org.CODE              AS "组织编码",
    org.NAME              AS "组织名称",
    org.SHORTNAME         AS "组织简称",
    org.ORGTYPE2          AS "法人公司",
    org.ORGTYPE4          AS "人力资源",
    org.ORGTYPE5          AS "财务组织",
    org.ORGTYPE29         AS "行政组织",
    org.ENABLESTATE       AS "启用状态",
    f.CODE || ' (' || f.NAME || ')' AS "上级组织",
    org.ADDRESS           AS "地址",
    org.TEL               AS "电话",
    org.PRINCIPAL         AS "负责人",
    org.MEMO              AS "说明",
    org.INNERCODE         AS "内部编码",
    org.VSTARTDATE        AS "版本生效日期",
    org.VENDDATE          AS "版本失效日期"
"""


def query_organization(code: str | None = None, name: str | None = None) -> tuple[str, dict | None]:
    sql = f"""SELECT{_ORG_COLS}
FROM ORG_ORGS org
LEFT JOIN ORG_ORGS f ON f.PK_ORG = org.PK_FATHERORG
WHERE org.DR = 0"""
    params = {}
    if code:
        sql += " AND org.CODE LIKE :code"
        params["code"] = f"%{code}%"
    if name:
        sql += " AND org.NAME LIKE :name"
        params["name"] = f"%{name}%"
    sql += " ORDER BY org.CODE"
    return sql, params or None


QUERIES = {
    "organization": {
        "description": "查询组织信息（精简字段：编码/名称/类型/上级组织/联系方式）。支持按编码/名称模糊搜索：code/name",
        "handler": query_organization,
    },
}
