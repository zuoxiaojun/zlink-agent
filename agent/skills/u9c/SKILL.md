---
name: u9c
title: U9C 技能
description: U9 Cloud 业务数据查询技能（SQL Server 直连，支持自定义 SQL 查询）
---

# U9 Cloud (用友 U9 Cloud) 工具使用指南

> U9C 工具为内置工具，直接通过 `pymssql` 连接 SQL Server 数据库。

## 启用前置条件

1. 准备 SQL Server 数据库连接信息（host/port/database/user/password）

2. 在 ZLink Agent 的 设置 → ERP → U9C 页面：
   - 填写 SQL Server 连接信息
   - 点击"保存"（配置写入 `config.json`，`_apply_erp_env()` 注入环境变量 `U9C_HOST/PORT/DATABASE/USER/PASSWORD/MAX_ROWS`）
   - 点击"测试连接"验证（通过 pymssql 直连）
   - 点击"启用"→ 4 个内置工具注册进 LLM 工具列表

## 工具列表

| 工具 | 说明 |
| ------ | ------ |
| `u9c_query` | 通用查询：客户档案/供应商档案/物料档案/销售订单/销售订单行/采购订单/采购订单行/生产订单/生产订单BOM明细/生产订单产出等 10 类业务查询 |
| `u9c_list_tables` | 列出 U9C 已注册业务表（按关键字搜索表名/中文名） |
| `u9c_describe_table` | 查看某张表的中文字段对照 |
| `u9c_raw_sql` | 对 U9C 数据库执行任意只读 SELECT 查询（有安全校验，**顺序执行**） |

> 所有工具均为内置工具，注册于 `agent/tools/erp_u9c_tools.py`。

## 业务查询类型（u9c_query）

`u9c_query` 支持以下 10 类查询，通过 `query_name` 参数指定：

| query_name | 说明 | 数据表 | 主要过滤条件 |
| ------------ | ------ | -------- | ------------- |
| `customer` | 客户档案 | CBO_Customer | code, name |
| `supplier` | 供应商档案 | CBO_Supplier | code, name |
| `item` | 物料档案 | CBO_ItemMaster | code, name |
| `sales_order` | 销售订单（含行明细，62列） | SM_SO + SM_SOLine | start_date, end_date, bill_no |
| `sales_order_line` | 销售订单行 | SM_SOLine + SM_SO | start_date, end_date, bill_no |
| `purchase_order` | 采购订单（含行明细，70列） | PM_PurchaseOrder + PM_POLine | start_date, end_date, bill_no |
| `purchase_order_line` | 采购订单行 | PM_POLine + PM_PurchaseOrder | start_date, end_date, bill_no |
| `mo` | 生产订单（含产出明细，26列） | MO_MO + MO_MOOutput | start_date, end_date, mo_code |
| `mo_bom_detail` | 生产订单BOM明细 | MO_MOBOMDetail + MO_MO | mo_code |
| `mo_output` | 生产订单产出 | MO_MOOutput + MO_MO | start_date, end_date, mo_code |

## 查询优先级（重要）

查询 U9C 业务数据时，**必须按以下优先级操作**：

### 优先：使用 u9c_query 内置查询

先检查 `u9c_query` 的已有查询类型是否覆盖需求。`u9c_query` 内建了 10 类预制查询脚本，
不走数据字典，直接用优化过的 SQL 带中文字段名返回，是最快最准的路径。

### 备选：从数据字典分析取数

当 `u9c_query` 的已有类型覆盖不了需求时，才走以下流程：

1. `u9c_list_tables` — 搜索相关业务表
2. `u9c_describe_table` — 查看字段中英文对照
3. `u9c_raw_sql` — 手写 SELECT 查询

> ⚠️ 不要跳过 `u9c_query` 直接去查字典写 SQL。u9c_query 已有的查询类型经过优化，
> 字段名已中文映射、关联已预置，比手写 SQL 更可靠。

## 数据字典

内建 10 张精选业务表的字段中英文对照，涵盖：

| 模块 | 表 |
| ------ | ----- |
| 基础数据 | CBO_Customer（客户档案）、CBO_Supplier（供应商档案）、CBO_ItemMaster（物料档案） |
| 销售管理 | SM_SO（销售订单主表）、SM_SOLine（销售订单行） |
| 采购管理 | PM_PurchaseOrder（采购订单主表）、PM_POLine（采购订单行） |
| 生产制造 | MO_MO（生产订单）、MO_MOBOMDetail（生产订单BOM明细）、MO_MOOutput（生产订单产出） |

## 重要提示

> ⚠️ U9C 的数据库表结构基于 U9 Cloud 平台，与 U8+ 完全不同。
> 表名以 `CBO_`、`SM_`、`PM_`、`MO_` 等前缀标识所属模块。
> 字段名使用驼峰命名（如 `ItemInfo_ItemCode`、`OrderBy_ShortName`），
> 与 U8 的中文拼音缩写字段名完全不同。

## 常见问题

**Q: 启用 U9C 后工具不出现？**
A: 检查 `GET /api/config/erp-clients` 返回的 u9c 配置中 `enabled` 是否为 true。
`_u9c_enabled()` 门控函数读取 `config.json` 中 `erp_clients.u9c.enabled`，为 false 时工具不注册进 LLM 工具列表。

**Q: 改了 U9C 配置需要重启吗？**
A: 不需要。配置保存时 `_apply_erp_env()` 即时注入环境变量；
工具每次调用时重新读取 `os.environ`，配置变更即时生效。

**Q: U9C 和 U8 的表结构一样吗？**
A: 不一样。U9C（U9 Cloud）使用 U9 平台模型，所有表名和字段名都与 U8 不同。
例如：客户档案是 `CBO_Customer`（非 `Customer`），销售订单是 `SM_SO`（非 `SO_SOMain`）。