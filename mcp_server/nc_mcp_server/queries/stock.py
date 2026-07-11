"""NC-MCP 查询模块 - 现存量查询"""

_STOCK_COLS = """
    hand.pk_org                          AS "pk_org",
    org.CODE                             AS "组织编码",
    org.NAME                             AS "组织名称",
    hand.cwarehouseid                    AS "cwarehouseid",
    wh.CODE                              AS "仓库编码",
    wh.NAME                              AS "仓库名称",
    hand.clocationid                     AS "clocationid",
    hand.cmaterialoid                    AS "cmaterialoid",
    mat.CODE                             AS "物料编码",
    mat.NAME                             AS "物料名称",
    hand.cmaterialvid                    AS "cmaterialvid",
    hand.castunitid                      AS "castunitid",
    meas.CODE                            AS "单位编码",
    meas.NAME                            AS "单位名称",
    hand.vchangerate                     AS "换算率",
    hand.vbatchcode                      AS "批次号",
    hand.pk_batchcode                    AS "pk_batchcode",
    hand.cstateid                        AS "cstateid",
    hand.nonhandnum                      AS "结存数量",
    hand.nonhandastnum                   AS "结存辅数量",
    hand.nvmionhandnum                   AS "物权结存数量",
    hand.ntplonhandnum                   AS "客户结存数量",
    hand.nvmilocknum                     AS "物权冻结数量",
    hand.ntpllocknum                     AS "客户冻结数量",
    hand.nvmionhandastnum                AS "物权结存辅数量",
    hand.ntplonhandastnum                AS "客户结存辅数量",
    hand.nvmilockastnum                  AS "物权冻结辅数量",
    hand.ntpllockastnum                  AS "客户冻结辅数量"
"""

_STOCK_FROM = """
    ic_onhandnum ic
    INNER JOIN ic_onhanddim handdim
        ON (ic.pk_onhanddim = handdim.pk_onhanddim)
    LEFT JOIN scm_batchcode scm_batchcode
        ON (handdim.pk_batchcode = scm_batchcode.pk_batchcode)
    INNER JOIN bd_stordoc bd_stordoc
        ON (handdim.cwarehouseid = bd_stordoc.pk_stordoc)
"""

_STOCK_WHERE = """
    ic.dr = 0
    AND bd_stordoc.gubflag = 'N'
    AND (COALESCE(ic.nonhandnum, 0) <> 0
        OR COALESCE(ic.nonhandastnum, 0) <> 0
        OR COALESCE(ic.ngrossnum, 0) <> 0
        OR COALESCE(ic.nlocknum, 0) <> 0
        OR COALESCE(ic.nlockastnum, 0) <> 0
        OR COALESCE(ic.nrsnum, 0) <> 0
        OR COALESCE(ic.nrsastnum, 0) <> 0)
"""


def query_stock(
    warehouse: str | None = None,
    material: str | None = None,
    batch: str | None = None,
    org: str | None = None,
) -> tuple[str, dict | None]:
    """现存量查询 - 支持按仓库/物料/批次/组织筛选，返回编码和名称"""
    sql = f"""SELECT{_STOCK_COLS}
FROM (
    SELECT
        handdim.pk_group           pk_group,
        handdim.pk_org             pk_org,
        handdim.cwarehouseid       cwarehouseid,
        handdim.cmaterialvid       cmaterialvid,
        handdim.cmaterialoid       cmaterialoid,
        handdim.castunitid         castunitid,
        handdim.clocationid        clocationid,
        handdim.pk_batchcode       pk_batchcode,
        handdim.vbatchcode         vbatchcode,
        handdim.vchangerate        vchangerate,
        handdim.cvmivenderid       cvmivenderid,
        handdim.ctplcustomerid     ctplcustomerid,
        handdim.cstateid           cstateid,
        handdim.cvendorid          cvendorid,
        handdim.cprojectid         cprojectid,
        handdim.casscustid         casscustid,
        handdim.cproductorid       cproductorid,
        handdim.cffileid           cffileid,
        handdim.vfree1             vfree1,
        handdim.vfree2             vfree2,
        handdim.vfree3             vfree3,
        handdim.vfree4             vfree4,
        handdim.vfree5             vfree5,
        handdim.vfree6             vfree6,
        handdim.vfree7             vfree7,
        handdim.vfree8             vfree8,
        handdim.vfree9             vfree9,
        handdim.vfree10            vfree10,
        ic.nonhandnum              nonhandnum,
        ic.nonhandastnum           nonhandastnum,
        ic.ngrossnum               ngrossnum,
        ic.nlocknum                nlocknum,
        ic.nlockastnum             nlockastnum,
        ic.nrsnum                  nrsnum,
        ic.nrsastnum               nrsastnum,
        ic.nrsgrossnum             nrsgrossnum,
        CASE WHEN COALESCE(handdim.cvmivenderid, '~') = '~' THEN 0.0 ELSE ic.nonhandnum  END nvmionhandnum,
        CASE WHEN COALESCE(handdim.ctplcustomerid, '~') = '~' THEN 0.0 ELSE ic.nonhandnum  END ntplonhandnum,
        CASE WHEN COALESCE(handdim.cvmivenderid, '~') = '~' THEN 0.0 ELSE ic.nlocknum    END nvmilocknum,
        CASE WHEN COALESCE(handdim.ctplcustomerid, '~') = '~' THEN 0.0 ELSE ic.nlocknum    END ntpllocknum,
        CASE WHEN COALESCE(handdim.cvmivenderid, '~') = '~' THEN 0.0 ELSE ic.nonhandastnum END nvmionhandastnum,
        CASE WHEN COALESCE(handdim.ctplcustomerid, '~') = '~' THEN 0.0 ELSE ic.nonhandastnum END ntplonhandastnum,
        CASE WHEN COALESCE(handdim.cvmivenderid, '~') = '~' THEN 0.0 ELSE ic.nlockastnum  END nvmilockastnum,
        CASE WHEN COALESCE(handdim.ctplcustomerid, '~') = '~' THEN 0.0 ELSE ic.nlockastnum  END ntpllockastnum
    FROM ic_onhandnum ic
    INNER JOIN ic_onhanddim handdim
        ON (ic.pk_onhanddim = handdim.pk_onhanddim)
    LEFT JOIN scm_batchcode scm_batchcode
        ON (handdim.pk_batchcode = scm_batchcode.pk_batchcode)
    INNER JOIN bd_stordoc bd_stordoc
        ON (handdim.cwarehouseid = bd_stordoc.pk_stordoc)
    WHERE ic.dr = 0
        AND bd_stordoc.gubflag = 'N'
        AND (COALESCE(ic.nonhandnum, 0) <> 0
            OR COALESCE(ic.nonhandastnum, 0) <> 0
            OR COALESCE(ic.ngrossnum, 0) <> 0
            OR COALESCE(ic.nlocknum, 0) <> 0
            OR COALESCE(ic.nlockastnum, 0) <> 0
            OR COALESCE(ic.nrsnum, 0) <> 0
            OR COALESCE(ic.nrsastnum, 0) <> 0)
) hand
LEFT JOIN org_orgs org ON org.pk_org = hand.pk_org
LEFT JOIN bd_stordoc wh ON wh.pk_stordoc = hand.cwarehouseid
LEFT JOIN bd_material mat ON mat.pk_material = hand.cmaterialoid
LEFT JOIN bd_measdoc meas ON meas.pk_measdoc = hand.castunitid
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


QUERIES = {
    "stock": {
        "description": "查询现存量（含仓库/物料/组织编码+名称）。支持按仓库pk/物料pk/批次/组织pk筛选：warehouse/material/batch/org",
        "handler": query_stock,
    },
}
