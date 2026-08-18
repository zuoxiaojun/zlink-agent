---
name: nc
title: NC 技能
description: NC系统业务数据查询技能（Oracle 直连，支持自定义 SQL 查询）
---

# NC (用友 NC Cloud) 工具使用指南

> 自 v1.7.0 起，NC 工具从外部 MCP 子进程[迁移为内置工具](https://atomgit.com/gcw_cJbJuamU/zlink-agent)，
> 直接通过 `oracledb` 连接 Oracle 数据库，不再依赖 `nc-mcp-server` 包。

## 启用前置条件

1. 准备 Oracle 数据库连接信息（host/port/service/user/password）

2. 在 ZLink Agent 的 设置 → ERP → NC 页面：
   - 填写 Oracle 连接信息
   - 点击"保存"（配置写入 `config.json`，`_apply_erp_env()` 注入环境变量 `ORACLE_HOST/PORT/SERVICE/USER/PASSWORD`）
   - 点击"测试连接"验证（通过 oracledb 直连）
   - 点击"启用"→ 4 个内置工具注册进 LLM 工具列表

## 工具列表

| 工具 | 说明 |
| ------ | ------ |
| `nc_query` | 通用查询：销售订单/采购订单/物料/客户/供应商/组织/库存/总账余额等 8 类业务查询 |
| `nc_list_tables` | 列出 NC 业务表（精选表 + 500+ 张扩展字典搜索） |
| `nc_describe_table` | 查看某张表的中文字段对照（含类型/枚举/参照） |
| `nc_raw_sql` | 对 NC 数据库执行任意只读 SELECT 查询（有安全校验，**顺序执行**） |

> 所有工具均为内置工具，注册于 `agent/tools/erp_nc_tools.py`，不在外部 MCP 中。

## 与 YonSuite 工具的区别

| 维度 | YonSuite | NC |
| ------ | ---------- | ----- |
| 接入方式 | 内置工具（YonSuite Cloud API） | 内置工具（Oracle 直连） |
| 工具命名 | `ys_*`（如 `ys_api`） | `nc_*`（如 `nc_query`） |
| 数据源 | YonSuite Cloud API（HTTP） | Oracle 数据库（oracledb） |
| 启用开关 | 默认启用 | 默认禁用 |
| 依赖 | 无（内置） | 无（内置，需 `oracledb`） |

## 查询优先级（重要）

查询 NC 业务数据时，**必须按以下优先级操作**：

### 优先：使用 nc_query 内置查询

先检查 `nc_query` 的已有查询类型是否覆盖需求。`nc_query` 内建了 8 类预制查询脚本，
不走数据字典，直接用优化过的 SQL 带中文字段名返回，是最快最准的路径。

### 备选：从数据字典分析取数

当 `nc_query` 的已有类型覆盖不了需求时（如查应收应付、现金管理、自定义报表等模块），
才走以下流程：

1. `nc_list_tables` — 搜索相关业务表
2. `nc_describe_table` — 查看字段中英文对照
3. `nc_raw_sql` — 手写 SELECT 查询

> ⚠️ 不要跳过 `nc_query` 直接去查字典写 SQL。nc_query 已有的查询类型经过优化，
> 字段名已中文映射、关联已预置，比手写 SQL 更可靠。

## 业务查询类型（nc_query）

`nc_query` 支持以下 8 类查询，通过 `query_name` 参数指定：

| query_name | 说明 | 主要过滤条件 |
| ------------ | ------ | ------------ |
| `sale_order` | 销售订单（含客户/物料名称） | bill_no, begin_date, end_date, status, code, org |
| `purchase_order` | 采购订单 | bill_no, begin_date, end_date, status, code, org |
| `material` | 物料主数据 | code, name, org |
| `customer` | 客户主数据 | code, name |
| `supplier` | 供应商主数据 | code, name |
| `organization` | 组织架构 | code, name |
| `stock` | 库存现存量 | warehouse, material, batch, org |
| `gl_balance` | 总账科目余额 | period_start, period_end, code |

## 数据字典

字典内建 20+ 张精选业务表的字段中英文对照（`SO_SALEORDER`、`PO_ORDER`、`BD_MATERIAL`、`ORG_ORGANIZATIONS` 等），
完整字典约 500+ 张表，通过 `nc_list_tables` 搜索、`nc_describe_table` 查看详情。

## 数据分析与 HTML 报告生成

对 NC 数据做分析时，调用 **与 YonSuite 相同的分析流水线和 HTML 品牌规范**。

### 分析流水线

```
1. 调用 nc_query / nc_raw_sql 获取 Oracle 数据
2. Python 聚合分析 → 按客户/商品/日期/组织分组统计
3. 调用 @antv/mcp-server-chart 生成图表（theme=academy）
4. 必须调用 data-analysis 技能执行统计分析（HHI/IQR/漏斗）
5. 拼装 HTML 报告 → 写入文件 → 自动打开
```

> 具体流程、分析维度速查表、强制规则与 YonSuite 完全一致，详见 `agent/skills/yonsuite/SKILL.md` → 「分析报表流水线」「强制规则：必须调用 data-analysis 技能」章节。

### HTML 报告标准布局

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
│  数据明细表格（全量数据，平铺无汇总行）  │
├──────────────────────────────────────┤
│  品牌脚注（右下角：YonSuite · 用友网络） │
```

### HTML 品牌规范（与 YonSuite 共用）

- 白底用友品牌风，顶部三色装饰线 `linear-gradient(90deg, #E60012, #FF6A00, #0071E3)`
- Logo URL：`https://gitee.com/leftxiaojun/yonyou-html-presentation/raw/main/assets/logo/current-logo.png`
- Logo 位置：分析报表 Hero 区**右上角**
- 右下角品牌位：`YonSuite · 用友网络科技股份有限公司`
- 金额列右对齐加粗：`color: #1a4db8; font-weight: 600`
- 状态 tag 色值、表格样式、列宽拖拽等详细规范 → 见 `agent/skills/yonsuite/SKILL.md` → 「HTML 报告标准布局」「HTML 品牌规范」

### 输出规范

- 默认保存到桌面：`~/Desktop/NC_YYYY-MM-DD_类型.html`
- 生成后自动通过浏览器打开，不询问用户
- 直接告知用户完整文件路径

## 常见问题

**Q: 启用 NC 后工具不出现？**
A: 检查 `GET /api/config/erp-clients` 返回的 nc 配置中 `enabled` 是否为 true。
`_nc_enabled()` 门控函数读取 `config.json` 中 `erp_clients.nc.enabled`，为 false 时工具不注册进 LLM 工具列表。

**Q: 改了 NC 配置需要重启吗？**
A: 不需要。配置保存时 `_apply_erp_env()` 即时注入环境变量；
工具每次调用时重新读取 `os.environ`，配置变更即时生效。

**Q: `nc_raw_sql` 安全吗？**
A: 三层防护：`sqlparse` AST 级别校验只允许 SELECT；`_validate_select()` 拦截 INSERT/UPDATE/DELETE/DROP/ALTER 等危险关键词；
`security_hooks.py` 作为全局第二层防线。

**Q: 需要装 `nc-mcp-server` 包吗？**
A: 不需要。v1.7.0 起 NC 是内置工具，无需额外安装任何 pip 包。
系统依赖 `oracledb`（已包含在 `zlink-agent` 基础依赖中）。
