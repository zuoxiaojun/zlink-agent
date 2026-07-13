# ERP 数据源路由 — LLM 正确选择 ERP 取数

## 问题

当多个 ERP 系统（YonSuite、NC）同时启用时，LLM 在未明确用户意图的情况下可能**擅自猜测**用哪个 ERP 取数，导致返回错误系统的数据。

## 目标

1. 只启用一个 ERP → LLM 自动使用该系统的工具取数，无需用户指定
2. 多个 ERP 启用 + 用户已指定系统 → 直接执行正确的 ERP
3. 多个 ERP 启用 + 用户未指定系统 → LLM 必须询问"查哪个系统"
4. 尽可能轻量，不改动现有 MCP 连接/注册/调度架构

## 设计：两层加固

### Layer 1 — System Prompt 动态注入 ERP 状态（核心层）

#### 改动范围

| 文件 | 改动 |
|------|------|
| `agent/core/message_builder.py` | `build_system_prompt()` 新增 `erp_context` 参数 |
| `agent/core/agent.py` | `AIAgent._build_system_prompt()` 读取 ERP 配置并格式化 |

#### 方案

`build_system_prompt()` 新增可选参数 `erp_context: str = ""`，在已有 fragment 列表末尾追加。

生成的文本示例：

**只有一个 ERP 启用时：**
```
## 可用数据源
当前已启用的 ERP 系统：
  • YonSuite ✅ — 可查询销售订单、客户等数据
  • NC        ❌ — 未启用

规则：
- 使用已启用 ✅ 系统的对应工具取数
```

**多个 ERP 同时启用时：**
```
## 可用数据源
当前已启用的 ERP 系统：
  • YonSuite ✅ — 可查询销售订单、客户等数据
  • NC        ✅ — 可查询销售订单、客户等数据

规则：
- 如果用户未指明系统 → 必须先询问"查哪个系统的数据"
- 如果用户已指定系统名称（如"查 NC 的销售订单"）→ 直接执行
```

`AIAgent._build_system_prompt()` 注入过程：
1. 调用 `config_manager.load()` 读取 `erp_clients`（字典，key 为 ERP 名称）
2. 遍历 `erp_clients` 所有 key，检查每个的 `enabled` 状态
3. 格式化为带 ✅/❌ 标记的列表文本
4. 若有任意 ERP 启用，则附带规则说明
5. 传递给 `build_system_prompt(erp_context=...)`

ERP 显示名称也来自配置（`erp_clients` 本身无 label 字段），所以动态使用 name 作为显示名（yonsuite → "YonSuite"，nc → "NC"），通过一个小的静态映射表：`ERP_LABELS = {"yonsuite": "YonSuite", "nc": "NC", "mcp-nc": "NC"}`

#### 关键约束

- 仅读取 `erp_clients`，不改写任何配置
- 格式化文本固化在 `agent.py` 中，不新增配置项
- 每一轮对话 `_build_system_prompt` 都会重新读取，开关 ERP 后即时生效
- 已启用的工具列表（`tool defs`）由 MCP 连接状态自然决定，不做额外过滤

### Layer 2 — 工具描述标注数据源归属（辅助层）

#### 改动范围

| 文件 | 改动 |
|------|------|
| `agent/tools/mcp_manager.py` | `MCPServerConnection._register_tools()` 追加数据源标签 |

#### 方案

在 `_register_tools()` 中注册每个 MCP 工具时，自动在 `description` 末尾追加数据源标识：

```python
# 只在已知 ERP 映射内才加标签
ERP_SOURCE_LABELS = {"yonsuite": "YonSuite", "mcp-nc": "NC"}
source_label = ERP_SOURCE_LABELS.get(self.name)
if source_label:
    schema["description"] = (schema.get("description", "") + f" 【数据源：{source_label}】").strip()
```

效果示例：
```
mcp_yonsuite_ys_api
  description: "调用 YonSuite 开放 API 接口... 【数据源：YonSuite】"

mcp_mcp-nc_query_sales_orders
  description: "查询 NC 销售订单... 【数据源：NC】"
```

这些 description 最终会出现在 LLM 的 `tools` 参数中，LLM 在函数调用时直接可见。

#### 关键约束

- 仅修改 description 字符串，不改变 schema 结构
- 自动识别内置 ERP 的 MCP 服务器名称 → 友好标签的映射
- 非 ERP 的 MCP 服务器（如 chart server）不会被打上误标记
- 如果 description 为空字符串，也正常追加

## 不做的事情（按 YAGNI）

- 不改 `registry.py` — 工具注册机制不动
- 不改 `config_manager.py` / `config_model.py` — 配置模型不动
- 不新增 API 端点
- 不改 MCP 连接/断开的既有通知流程
- 不加运行时 before-hook 拦截（Layer 3 暂不实现）
- 不加 ERP 标签到前端 UI

## 测试策略

- **message_builder 测试**：验证带 `erp_context` 参数时输出包含 ERP 状态文本
- **agent.py 测试**：Mock `config_manager.load()`，验证 `_build_system_prompt()` 返回正确的格式化文本
- **mcp_manager 测试**：验证 `_register_tools()` 后工具的 description 包含数据源标签
- **无需新增集成测试**：该功能不涉及网络/LLM 调用
