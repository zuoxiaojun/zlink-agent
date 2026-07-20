---
name: yonsuite-skill
title: yonsuite-skill
description: YS系统业务数据查询技能（销售/采购/生产订单、库存、商机、待办）
---

# yonsuite-skill - 用友 YonSuite 系统综合技能

**定位：** YS 系统业务数据查询 + 分析报表生成，支持销售/采购/生产订单、库存、商机、待办等核心模块。

**版本：** v9.2（2026-05-19 移除：删除"销售订单创建"章节，跑不通；技能专注查询）

---

## 🔑 配置获取方式

本技能在 **ZLink Agent** 环境中运行时，所需的 YonSuite 凭证统一通过系统左侧导航 → **「YonSuite 配置」** 页面设置，保存后自动注入环境变量供内置工具使用。

- 如果调用 YonSuite API 时提示「未配置」或认证失败，引导用户在左侧 **⚙️ 设置 → YonSuite 配置** 中填写并保存相关密钥即可
- 配置持久化在 `data/config.json`，重启后不丢失

---

## 🔧 内置查询工具（直接调用，无需手写代码）

以下工具为 ZLink Agent 内置工具（v1.7.0 起由 YonSuite MCP Server 迁移而来），**直接调用，不需要手写 Python 代码**。需手动传 `page_index` 逐页获取数据。

| 工具名 | 用途 | 关键参数 |
|--------|------|---------|
| `query_sale_orders` | 销售订单查询 | `date_from`, `date_to`, `is_sum`, `page_index`, `page_size` |
| `query_purchase_orders` | 采购订单查询 | `date_from`, `date_to`, `page_index`, `page_size` |
| `query_production_orders` | 生产工单查询 | `date_from`, `date_to`, `page_index`, `page_size` |
| `query_stock` | 库存现存量查询 | `warehouse`, `sku`, `product_id`, `page_size` |
| `query_user_todos` | 用户待办查询 | `page_no`, `page_size` |
| `query_opportunities` | CRM 商机查询 | `oppt_state`, `win_lose_state`, `date_from`, `date_to`, `page_index`, `page_size` |
| `query_products` | 物料档案查询 | `product_code`, `product_name`, `page_index`, `page_size` |
| `query_customers` | 客户档案查询 | `customer_name`, `page_index`, `page_size` |
| `query_vendors` | 供应商档案查询 | `vendor_name`, `page_index`, `page_size` |
| `query_vouchers` | 财务凭证查询 | `date_from`, `date_to`, `accbook_code`, `period_start`, `period_end`, `page_index`, `page_size` |
| `ys_api` | 通用 YonSuite API 调用 | `method`, `params` |

每个工具返回的 JSON 已包含**解析后的中文字段名、状态文本、计算好的税额**，无需再做字段映射或公式计算。

**`is_sum` 参数说明（销售订单）：**
- `is_sum=True`：按订单汇总（一单一行），用于客户/商品统计和整体分析
- `is_sum=False`：按商品明细分列，用于逐单明细查看

**分页翻页：** 所有支持分页的工具都需手动传 `page_index` 逐页获取。不传 `page_index` 默认返回第 1 页，传指定页码返回对应页。

---


## ⚠️ 核心概念：主子表结构

所有三种订单（销售/采购/生产）均为**主子表结构**：

| 层级 | 说明 |
|-----|------|
| **主表**（每订单一条） | 订单头信息（编号、日期、客户、状态等） |
| **明细表**（每行一个物料） | 商品行信息（物料编码、数量、金额等） |

---

## 🔄 库存查询标准流程（两步查询法）

**核心原则：先查物料档案拿到 ID，再查库存。两步不能跳步。**

### 流程

```
用户问"XXX的库存是多少"
  ↓
① query_products(product_name="XXX")
  → 获取物料编码 + 物料 ID（id 字段）
  ↓
② query_stock(product_id="物料ID")
  → 获取该物料在所有仓库的逐批次库存明细
  ↓
③ 汇总展示：总现存量、总可用量，按仓库/组织分组表格
```

### 为什么分两步？

- `query_products` 的 `product_name` 参数是**精确/前缀匹配**，不是模糊匹配，需拉全量自行过滤
- `query_stock` 的 `product_id` 参数是**服务端精确过滤**，比客户端按 sku 过滤更高效
- 支持单个 ID（如 `"2038946642929280"`）或逗号分隔批量

### 回答格式规范

查询结果展示格式：
```
物料名称 | 总现存量 | 总可用量
多仓库按仓库分行列出明细
```
- 多批次分布在多个仓库/组织时，按仓库+组织分行展示
- 末尾汇总合计行
- 锁定数量为零时注明"全部可用"

---

## 📂 输出与交付规范（跑通确认）

### 文件保存位置
- **默认保存到桌面**：`~/Desktop/YS_YYYY-MM-DD_类型.html`
- 不保存到 `~/Documents/` 或 `~/Documents/PPT/`
- 覆盖之前的命名规范中的路径

### 自动打开展示
- 生成 HTML 报告后，**直接调用浏览器打开**展示给用户
- 不需要询问用户"是否要打开"

### 自动生成（不询问）
- 用户要求分析业务数据后，**自动生成 HTML 报告**
- 不需要询问"是否需要生成报告"

### 文件发送方式
- 直接告知用户完整文件路径即可
---

## 📊 分析报表流水线

### 触发条件

分析用友 YonSuite 销售、采购或生产数据，生成可视化 HTML 报告。

### 标准流程

```
1. 调用内置查询工具获取数据（query_sale_orders / query_purchase_orders / query_production_orders）
2. Python 聚合分析 → 按客户/商品/日期分组统计
3. 调用 mcp-server-chart 生成图表（theme=academy）
4. 必须调用 data-analysis 技能执行统计分析（HHI/IQR/漏斗）
5. 拼装 HTML 报告 → 写入文件 → 发送/打开
```

### 图表生成

**优先使用 `@antv/mcp-server-chart` MCP 工具**（用友品牌风格，theme=academy）。
如果用户没有装 chart MCP（v1.3.1+ 默认不内置），可用其他方式兜底：
- Python `matplotlib` / `plotly` 静态图
- HTML + ECharts 前端渲染

不要因为没有 chart MCP 就报错，应该选择可用的方式出图。

支持以下图表类型（theme=academy 用友品牌风格）：

| 图表工具 | 适用场景 |
|---------|---------|
| `generate_column_chart` | 柱状对比（客户排行、产品排行） |
| `generate_bar_chart` | 水平条形（适合长标签） |
| `generate_pie_chart` | 分布占比（`innerRadius=0.4` 环形图） |
| `generate_line_chart` | 每日趋势 |
| `generate_dual_axes_chart` | 金额/税额双轴对比 |
| `generate_scatter_chart` | 相关性散点图 |
| `generate_funnel_chart` | 漏斗转化分析 |

**标准用法：**
```python
# 4张图表按 2×2 网格布局生成
# 图表 height=260, theme='academy'
# 将生成的图片URL嵌入 HTML 的 <img src="..."> 中
```

### HTML 报告标准布局（强制）

```
┌──────────────────────────────────────┐
│  Hero区（标题 + 统计总金额 + Logo右上角）│
├──────────────────────────────────────┤
│  KPI卡片行（状态分布/客户数/税额估算）  │
├──────────────────────────────────────┤
│  图表区（2×2网格，每图高260px）        │
├──────────────────────────────────────┤
│  决策简报（核心结论 + 证据 + 建议 + 不确定性）│
├──────────────────────────────────────┤
│  订单明细表格（全量数据，平铺无汇总行）  │
├──────────────────────────────────────┤
│  品牌脚注（右下角）                    │
```

### 图表布局规范

- 每行放 2 个图表，`display: flex; gap: 14px`
- 每个图表宽度 `calc(50% - 7px)`，高度 260px，`object-fit: contain`
- 4 个图表分 2 行排列

### HTML 品牌规范

- 白底用友品牌风
- 顶部三色装饰线：`linear-gradient(90deg, #E60012, #FF6A00, #0071E3)`
- Logo URL：`https://gitee.com/leftxiaojun/yonyou-html-presentation/raw/main/assets/logo/current-logo.png`
- Logo 位置：分析报表 Hero 区**右上角**，待办类左上角
- 右下角品牌位：仅文字 `YonSuite · 用友网络科技股份有限公司`
- 金额列右对齐加粗：`color: #1a4db8; font-weight: 600`
- 状态 tag 色值：
  - 待发货 → `#FFF0E0` 底 `#FF6A00` 字
  - 待收货 → `#E8F0FF` 底 `#0071E3` 字
  - 已完成 → `#E8F8EF` 底 `#2EBB59` 字
  - 开立 → `#F0F0FF` 底 `#6B5BFF` 字

### 订单明细表格规范

- **列出全部订单明细**，不截断，`max-height: 420px; overflow-y: auto`
- 表头 sticky 固定 + 内容区独立滚动
- 必须用 `<colgroup>` 指定列宽，`table-layout: fixed`
- 拖拽列宽功能（JS 监听 mousedown/mousemove/mouseup）
- **平铺展示**：每行独立显示完整信息，订单编号/客户等表头字段**每行都重复**
- **不做合并样式**：不加"—"灰色标识，不做首行蓝色高亮
- **禁止手动录入数据** → 必须程序化从工具返回的 JSON 生成

---

## ⚡ 强制规则：必须调用 data-analysis 技能

**每次分析报告生成，必须包含统计分析步骤，结果写入 HTML「决策简报」区块。**

⚠️ **禁止直接用 LLM 推理输出"洞察"，必须经过以下数据分析流程。**

| 步骤 | 操作 |
|------|------|
| 1 | `skill_view(name='data-analysis')` 加载 techniques.md + decision-briefs.md |
| 2 | 数据异常预检：按日期分组统计，IQR 异常检测（>Q3+1.5×IQR 标记异常） |
| 3 | Python 执行统计分析（HHI/IQR/漏斗/分段） |
| 4 | 按 decision-briefs.md 格式输出 Decision Brief |
| 5 | 将 Decision Brief 写入 HTML「决策简报」区块 |

### 分析维度速查

| 分析维度 | 方法 | 阈值 |
|---------|------|------|
| 客户集中度 | HHI 指数 | >0.25 高集中，>0.4 极高 |
| 日销售异常 | IQR | >Q3+1.5×IQR |
| 订单执行率 | 漏斗占比 | 已完成/总额 |
| 产品集中度 | TOP5 占比 | >80% 需关注 |

---

## 📌 命名规范

- 输出文件：`~/Desktop/YS_YYYY-MM-DD_类型.html`
- 销售合计行过滤：`vouchdate == "合计"` 的汇总行
- 采购/生产合计行过滤：`单据编号 == "合计"` 的汇总行
- 分析报表文件：`~/Desktop/YS_YYYY-MM-DD_本月销售分析报表.html`

---

## ⚡ 常见错误（真实踩坑）

| 错误 | 正确做法 |
|------|---------|
| 跳过 JSON 直接硬编码数据 | 明细表全部数据必须从工具返回的 JSON 程序化读取 |
| 跳过 data-analysis 技能 | 每次报告生成必须先 `skill_view('data-analysis')` + 执行统计分析 |
| 自写 HTML 不用模板 | 参考 `templates/` 目录下的模板骨架 |
| 手动录入明细数据 | **禁止手动输入任何数据** → 必须程序化生成 |
| 用假数据冒充真实数据 | 无法查真实数据时明确告知用户，不能静默编造 |
| 飞书文件发链接而非附件 | 飞书会话中生成的文件 → 直调 OpenAPI `file_type="stream"` |
| HTML Logo 位置错误 | 分析报表 Logo 放 Hero 区**右上角**，待办类放左上角 |
| `is_sum=True` 查订单明细 | 必须用 `is_sum=False`，否则订单去重丢失数据 |
| 只发文字不生成 HTML | **双轨输出**：聊天框展示 + HTML 文件 |
| `query_products` 物料模糊匹配 | `product_name` 参数是精确/前缀匹配，工具自动全量拉取后过滤 |

---

## 📌 API 参考（内置工具底层接口，AI 无需直接调用）

> 以下 API 均由对应的内置工具封装调用，**AI 不要直接手写 HTTP 请求**，统一走内置工具。

| 业务 | 内置工具 | 底层 API |
|------|---------|---------|
| 销售订单 | `query_sale_orders` | `POST /yonbip/sd/voucherorder/list` |
| 采购订单 | `query_purchase_orders` | `POST /yonbip/scm/purchaseorder/list` |
| 生产订单 | `query_production_orders` | `POST /yonbip/mfg/productionorder/list` |
| 库存现存量 | `query_stock` | `POST /yonbip/scm/stock/QueryCurrentStocksByCondition` |
| 商机 | `query_opportunities` | `POST /yonbip/crm/oppt/bill/list` |
| 创建销售订单 | `ys_api(method="yonbip/sd/voucherorder/save")` | `POST /yonbip/sd/voucherorder/save` |

- 官方文档：https://open.yonyoudcloud.com/#/doc-center/docDes/api
