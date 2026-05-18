"""Status maps shared across query handlers."""

SALE_STATUS_MAP = {
    "CONFIRMORDER": "开立",
    "DELIVERY_PART": "部分发货",
    "DELIVERY_TAKE_PART": "部分发货待收货",
    "DELIVERGOODS": "待发货",
    "TAKEDELIVERY": "待收货",
    "ENDORDER": "已完成",
    "OPPOSE": "已取消",
    "APPROVING": "审批中",
}

PURCHASE_STATUS_MAP = {0: "开立", 1: "已审核", 2: "已关闭", 3: "审核中"}
PURCHASE_ARRIVED_MAP = {1: "到货完成", 2: "未到货", 3: "部分到货", 4: "到货完成"}
PURCHASE_INWH_MAP = {1: "入库完成", 2: "未入库", 3: "部分入库", 4: "入库结束"}
PURCHASE_INVOICE_MAP = {1: "开票完成", 2: "未开票", 3: "部分开票", 4: "开票结束"}

PROD_STATUS_MAP = {0: "开立", 1: "已审核", 2: "已关闭", 3: "审核中", 4: "已锁定", 5: "已开工", 6: "生产完工"}
PROD_STOCK_MAP = {0: "未入库", 1: "部分入库", 2: "全部入库"}

OPPT_STATE_MAP = {0: "进行中", 1: "暂停", 2: "作废", 3: "关闭"}
OPPT_WIN_LOSE_MAP = {0: "赢单", 1: "丢单", 2: "未定", 3: "部分赢单"}

TODO_TYPE_MAP = {"SCMSA": "销售订单", "SACT": "销售合同", "RBSM": "报销单", "PGRM": "项目管理"}
