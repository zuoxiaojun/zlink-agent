# NC (用友 NC Cloud) 工具使用指南

> 自 v1.5.0 起，ZLink Agent 通过 [nc-mcp-server](https://atomgit.com/gcw_cJbJuamU/nc-mcp-project) 集成 NC。

## 启用前置条件

1. 装 `nc-mcp-server` 包：
   ```bash
   pip install "zlink-agent[nc]"
   # 或从源码:
   pip install git+https://atomgit.com/gcw_cJbJuamU/nc-mcp-project.git
   ```

2. 准备 Oracle 数据库连接信息（host/port/service/user/password）

3. 在 ZLink Agent 的 `/settings/erp` 页面：
   - 打开 NC 卡片
   - 填写 Oracle 连接信息
   - 点击"启用"
   - 点击"测试连接"验证

## 工具列表（来自 nc-mcp-server）

| 工具 | 说明 |
|------|------|
| `query_sales_order` | 销售订单完整链路（含客户名称 + 物料名称） |
| `query_purchase_order` | 采购订单查询 |
| `query_material` | 物料主数据 |
| `query_organization` | 组织架构 |
| `query_customer` | 客户主数据 |
| `query_supplier` | 供应商主数据 |
| ... 11 个工具全部来自 nc-mcp-server 包 |

## 与 YonSuite 工具的区别

| 维度 | YonSuite | NC |
|------|----------|-----|
| 接入方式 | builtin MCP (内置) | 外部 pip 包 (按需装) |
| 工具命名 | `mcp_yonsuite_query_*` | `mcp_nc_*` |
| 数据源 | YonSuite Cloud API | Oracle 数据库直连 |
| 启用开关 | 默认启用 | 默认禁用 |

## 常见问题

**Q: 没装 nc-mcp-server 就启用 NC 会怎样？**
A: 前端检测到命令不存在，显示安装提示，启用操作不报错但工具不可用。

**Q: 改了 NC 配置需要重启吗？**
A: 不需要。mcp_manager 检测到配置变更会自动重启 NC MCP server。
