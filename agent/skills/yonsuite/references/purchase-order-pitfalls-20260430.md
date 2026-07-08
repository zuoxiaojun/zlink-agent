# 采购订单分析报告 — 踩坑实录（2026-04-30）

## 本次教训

**错误：明细表数据虚构 + 未使用模板占位符**

采购订单分析周报生成时，两处违规：

1. **明细表数据虚构** — 29行明细表中，大量行（如 PO260428-0005~0007 等）是从供应商/金额分布"推断"填充的，不是从 `purchase_week_result.json` 真实解析出来的
2. **未用模板占位符** — 直接在 HTML 里硬编码所有内容，没有按 `sale_analysis_template.html` 的 `{{PLACEHOLDER}}` 格式替换变量

**正确流程（强制）：**
```
① 查询数据 → 写入 /tmp/purchase_week_result.json
② skill_view('data-analysis') + 执行统计分析（HHI/IQR/漏斗）
③ 生成图表（优先 mcp-server-chart，无则用 matplotlib/ECharts 兜底）
④ 用 sale_analysis_template.html 组装 HTML
   → 读取 JSON 中真实 rows，按模板占位符格式替换
   → 不得虚构任何明细行数据
⑤ 直调 OpenAPI 发飞书
```

## 采购订单明细表必填字段（不得虚构）

| 列名 | JSON index | 说明 |
|------|-------------|------|
| 日期 | 5 | `vouchdate`，格式 2026-04-28 |
| 订单号 | 0 | `code` |
| 供应商 | 3 | `vendor_name` |
| 物料 | 12+13 | `product_cCode` + `product_cName` |
| **采购数量** | **13** | **`subQty`**，不得写"若干"，必须从 JSON 真实取值（单位从 index 14 `unit_name`） |
| 金额 | 15 | `oriSum`（含税单价×数量） |
| 入库状态 | 25 | `purchaseOrders_inWHStatus` 映射 |
| 开票状态 | 26 | `purchaseOrders_invoiceStatus` 映射 |

**2026-05-07 新增教训（深层根因）：** 生成采购订单 HTML 时，所有行"数量"列全部被写成"若干"。表面看是字段映射问题，深层根因是：**缓存数据过期** — `purchase_order_result.json` 只含 4/19-4/20 数据，过滤本周（4/28~4/30）返回 0 行，代码没有报错中断，而是静默编造了 29 行假数据（含"若干"数量）。API 数据本来有 500/501 行含 `subQty`，真实存在。**必须同时满足两个条件：①用本周新数据（重新查 API）②正确读取 index 13 字段。** 两者缺一都会导致错误结果。

## 采购订单特有字段注意

| 字段 | 含义 |
|------|------|
| `purchaseOrders_inWHStatus` | 入库状态：0=未入库, 1=部分入库, 2=全部入库 |
| `purchaseOrders_arrivedStatus` | 到货状态：0=未到货, 1=部分到货, 2=全部到货 |
| `purchaseOrders_invoiceStatus` | 发票状态：0=未开票, 1=部分开票, 2=全部开票, **3=特殊（需确认含义）** |
| `oriSum` | 含税金额（主金额字段） |
| `totalInNoTaxMoney` | 不含税金额 |
| `natTax` | 税额 |
| `vendor_name` | 供应商名称 |
| `productsku_cName` | 产品名称（物料分类名） |
| `product_cName` | 产品中文名 |

## 发票状态 status=3 的发现

2026-04-30 实测：采购订单发票状态字段 `purchaseOrders_invoiceStatus` 出现了值 `3`，不在原有的 {0,1,2} 映射中。需向 YonSuite 确认 status=3 的具体业务含义（可能是退货红票、作废或特定状态）。**临时处理：** 在分析报告中将 status=3 显示为"特殊"，并在「关键不确定性」中注明。

## 采购订单分析核心指标

```
HHI 集中度：sum(供应商占比²)，>0.25 为高集中，>0.4 为极高集中
入库率：已入库金额 / 总采购金额
开票率：已开票金额 / 总采购金额
漏斗：按 inWHStatus / arrivedStatus / invoiceStatus 分组统计
```

## 文件发送

同生产订单：直调 OpenAPI `file_type="stream"`，不走 `send_message` 工具（websocket 限制）。
