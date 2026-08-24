---
name: u8
title: U8 技能
description: U8+ 业务数据查询技能（SQL Server 直连，支持自定义 SQL 查询）
---

# U8+ (用友 U8+) 工具使用指南

> U8 工具为内置工具，直接通过 `pymssql` 连接 SQL Server 数据库。

## 启用前置条件

1. 准备 SQL Server 数据库连接信息（host/port/database/user/password）

2. 在 ZLink Agent 的 设置 → ERP → U8 页面：
   - 填写 SQL Server 连接信息
   - 点击"保存"（配置写入 `config.json`，`_apply_erp_env()` 注入环境变量 `U8_HOST/PORT/DATABASE/USER/PASSWORD/MAX_ROWS`）
   - 点击"测试连接"验证（通过 pymssql 直连）
   - 点击"启用"→ 4 个内置工具注册进 LLM 工具列表

## 工具列表

| 工具 | 说明 |
| ------ | ------ |
| `u8_query` | 通用查询：客户/供应商/仓库/会计科目/存货/物料/销售订单/采购订单/总账凭证/生产订单/现存量等 12 类业务查询 |
| `u8_list_tables` | 列出 U8 已注册业务表（按关键字搜索表名/中文名） |
| `u8_describe_table` | 查看某张表的中文字段对照 |
| `u8_raw_sql` | 对 U8 数据库执行任意只读 SELECT 查询（有安全校验，**顺序执行**） |

> 所有工具均为内置工具，注册于 `agent/tools/erp_u8_tools.py`。

## 业务查询类型（u8_query）

`u8_query` 支持以下 12 类查询，通过 `query_name` 参数指定：

| query_name | 说明 | 主要过滤条件 |
| ------------ | ------ | ------------- |
| `customer` | 客户档案 | code, name |
| `vendor` | 供应商档案 | code, name |
| `warehouse` | 仓库档案 | code, name |
| `code` | 会计科目 | code |
| `inventory` | 存货档案（供应链用） | code, name |
| `bas_part` | 物料表（生产制造用） | code, name |
| `sales_order` | 销售订单（含客户/存货） | start_date, end_date, bill_no |
| `purchase_order` | 采购订单（含供应商/存货） | start_date, end_date, bill_no |
| `gl_voucher` | 总账凭证 | start_date, end_date, num |
| `mom_orderdetail` | 生产订单母件行 | start_date, end_date, mo_code |
| `mom_moallocate` | 生产订单子件用料 | mo_code, inv_code |
| `current_stock` | 现存量 | wh_code, inv_code |

## 查询优先级（重要）

查询 U8 业务数据时，**必须按以下优先级操作**：

### 优先：使用 u8_query 内置查询

先检查 `u8_query` 的已有查询类型是否覆盖需求。`u8_query` 内建了 12 类预制查询脚本，
不走数据字典，直接用优化过的 SQL 带中文字段名返回，是最快最准的路径。

### 备选：从数据字典分析取数

当 `u8_query` 的已有类型覆盖不了需求时，才走以下流程：

1. `u8_list_tables` — 搜索相关业务表
2. `u8_describe_table` — 查看字段中英文对照
3. `u8_raw_sql` — 手写 SELECT 查询

> ⚠️ 不要跳过 `u8_query` 直接去查字典写 SQL。u8_query 已有的查询类型经过优化，
> 字段名已中文映射、关联已预置，比手写 SQL 更可靠。

## 数据字典

内建 16 张精选业务表的字段中英文对照，涵盖：

| 模块 | 表 |
| ------ | ----- |
| 公用目录 | Customer（客户档案）、Vendor（供应商档案）、Warehouse（仓库档案）、Inventory（存货档案） |
| 总账 | code（会计科目）、GL_accvouch（总账凭证） |
| 销售管理 | SO_SOMain（销售订单主表）、SO_SODetails（销售订单子表） |
| 采购管理 | PO_Pomain（采购订单主表）、PO_Podetails（采购订单子表） |
| 生产制造 | bas_part（物料表）、mom_orderdetail（生产订单明细）、mom_moallocate（子件用料） |
| 库存管理 | CurrentStock（现存量表） |

## 与 NC/YonSuite 工具的区别

| 维度 | YonSuite | NC | U8 |
| ------ | ---------- | ----- | ----- |
| 接入方式 | 内置工具（Cloud API） | 内置工具（Oracle 直连） | 内置工具（SQL Server 直连） |
| 工具命名 | `ys_*` | `nc_*` | `u8_*` |
| 数据源 | YonSuite Cloud API | Oracle 数据库（oracledb） | SQL Server 数据库（pymssql） |
| 分页语法 | API 分页 | Oracle OFFSET/FETCH | SQL Server OFFSET/FETCH |
| 参数绑定 | — | `:param` | `%(param)s` |
| 启用开关 | 默认启用 | 默认禁用 | 默认禁用 |

## 数据分析与 HTML 报告生成

对 U8 数据做分析时，调用 **与 YonSuite/NC 相同的分析流水线和 HTML 品牌规范**。

### 分析流水线

```
1. 调用 u8_query / u8_raw_sql 获取 SQL Server 数据
2. Python 聚合分析 → 按客户/商品/供应商/日期/仓库/科目分组统计
3. 调用 @antv/mcp-server-chart 生成图表（theme=academy）
4. 拼装 HTML 报告 → 写入文件 → 自动打开
```

### HTML 报告标准布局

```
┌──────────────────────────────────────┐
│  Hero区（标题 + 统计总金额 + Logo右上角）│
├──────────────────────────────────────┤
│  KPI卡片行（汇总数/客户数/订单数等）   │
├──────────────────────────────────────┤
│  图表区（2×2网格，每图高260px）        │
├──────────────────────────────────────┤
│  决策简报（核心结论 + 证据 + 建议）    │
├──────────────────────────────────────┤
│  数据明细表格（全量数据，平铺无汇总行）  │
├──────────────────────────────────────┤
│  品牌脚注（右下角：YonSuite · 用友网络） │
```

### HTML 品牌规范（与 YonSuite/NC 共用）

- 白底用友品牌风，顶部三色装饰线 `linear-gradient(90deg, #E60012, #FF6A00, #0071E3)`
- Logo URL：`https://gitee.com/leftxiaojun/yonyou-html-presentation/raw/main/assets/logo/current-logo.png`
- Logo 位置：分析报表 Hero 区**右上角**
- 右下角品牌位：`YonSuite · 用友网络科技股份有限公司`
- 金额列右对齐加粗：`color: #1a4db8; font-weight: 600`
- 状态 tag 色值、表格样式、列宽拖拽等详细规范 → 见 `agent/skills/yonsuite/SKILL.md` → 「HTML 报告标准布局」「HTML 品牌规范」

### 输出规范

- 默认保存到桌面：`~/Desktop/U8_YYYY-MM-DD_类型.html`
- 生成后自动通过浏览器打开，不询问用户
- 直接告知用户完整文件路径

## 常见问题

**Q: 启用 U8 后工具不出现？**
A: 检查 `GET /api/config/erp-clients` 返回的 u8 配置中 `enabled` 是否为 true。
`_u8_enabled()` 门控函数读取 `config.json` 中 `erp_clients.u8.enabled`，为 false 时工具不注册进 LLM 工具列表。

**Q: 改了 U8 配置需要重启吗？**
A: 不需要。配置保存时 `_apply_erp_env()` 即时注入环境变量；
工具每次调用时重新读取 `os.environ`，配置变更即时生效。

**Q: `u8_raw_sql` 安全吗？**
A: 三层防护：`sqlparse` AST 级别校验只允许 SELECT；`_validate_select()` 拦截 INSERT/UPDATE/DELETE/DROP/ALTER 等危险关键词；
`security_hooks.py` 作为全局第二层防线。

**Q: U8 和生产制造数据怎么关联？**
A: Inventory（供应链用）和 bas_part（生产制造用）通过 `Inventory.cInvCode = bas_part.InvCode` 关联。查询时如果发现两个表字段不同，用这个关联关系做 JOIN。
