"""NC-MCP 查询模块 - 物料（精简字段版）"""

_MAT_COLS = """
    mat.CODE              AS "物料编码",
    mat.NAME              AS "物料名称",
    mat.MATERIALSPEC      AS "规格",
    mat.MATERIALTYPE      AS "型号",
    mat.MATERIALSHORTNAME AS "物料简称",
    cls.CODE || ' (' || cls.NAME || ')' AS "物料分类",
    meas.CODE || ' (' || meas.NAME || ')' AS "主计量单位",
    mat.PRODAREA          AS "产地",
    mat.GRAPHID           AS "图号",
    mat.MATERIALBARCODE   AS "条形码",
    mat.UNITWEIGHT        AS "单位重量",
    mat.UNITVOLUME        AS "单位体积",
    mat.MEMO              AS "备注",
    mat.VERSION           AS "版本号"
"""


def query_material(code: str | None = None, name: str | None = None) -> tuple[str, dict | None]:
    sql = f"""SELECT{_MAT_COLS}
FROM BD_MATERIAL mat
LEFT JOIN BD_MARBASCLASS cls ON cls.PK_MARBASCLASS = mat.PK_MARBASCLASS
LEFT JOIN BD_MEASDOC meas ON meas.PK_MEASDOC = mat.PK_MEASDOC
WHERE mat.DR = 0"""
    params = {}
    if code:
        sql += " AND mat.CODE LIKE :code"
        params["code"] = f"%{code}%"
    if name:
        sql += " AND mat.NAME LIKE :name"
        params["name"] = f"%{name}%"
    sql += " ORDER BY mat.CODE"
    return sql, params or None


QUERIES = {
    "material": {
        "description": "查询物料基本信息（精简字段：编码/名称/规格/型号/单位/分类）。支持按编码/名称模糊搜索：code/name",
        "handler": query_material,
    },
}
