# AGENTS.md 重写设计

> **状态**: 待用户审查
> **作者**: Superpowers Primary
> **日期**: 2026-07-11
> **基线**: v1.5.3（65 测试全过）

---

## 1. 目标与范围

### 1.1 目标

将当前 226 行的 `AGENTS.md` 重写为一份**双区块文档**，同时服务于 AI agent（精准技术参考）和人类开发者（上手指南），以支撑后续的持续开发。

### 1.2 关键约束

| 约束 | 说明 |
|------|------|
| Part 1 每条信息必须可被 AI 精确理解执行 | 不能有模糊表述，目录路径、函数签名、配置项必须精准 |
| Part 2 保持可读性 | 人类部分简洁明了，适合新贡献者快速上手 |
| 不替换 `CONTRIBUTING.md` | Part 2 不重复 CONTRIBUTING.md 已有内容 |
| 保持 1 个文件 | AGENTS.md 本身是入口，不分拆 |
| 不降低现有信息量 | 现有所有有用信息必须保留或升级 |

### 1.3 不在范围

- ❌ 不改 `CONTRIBUTING.md`、`README.md` 等其它文档
- ❌ 不改任何源码
- ❌ 不添加新的 CI/CD 配置

---

## 2. 文档结构

### 2.1 总体布局

```
┌─────────────────────────────────────────────┐
│  # ZLink Agent (智链 Agent)                  │
│  Part 1: AI Agent Technical Reference        │
│  Part 2: Human Developer Guide               │
└─────────────────────────────────────────────┘
```

两部分用醒目分隔线隔开，Part 1 在前（AI 优先读取）。

### 2.2 Part 1 内容规划

#### 1.1 项目速览（3-5 行）
一句话定位 + 技术栈标签（Python 3.11+ / FastAPI / React + Vite / MCP / SQLite / pytest）。

#### 1.2 目录结构 + 文件职责
以树形目录列出每个文件/目录，标注：
- ✅ 可安全修改
- ⚠️ 修改需谨慎（有依赖约束）
- ❌ 不可修改（builtin 保护、外部接口约定）

关键模块分组说明（core、tools、erp_clients、mcp_server）。

#### 1.3 模块依赖关系
ASCII 依赖图，标注核心调用链：

```
chat.py → AIAgent.run_conversation() → LLMClient.chat() → LLMProvider
                                       → ToolDispatcher.dispatch() → registry
                                       → mcp_manager (MCP tool calls)
```

标注哪些模块是"叶子节点"（可独立修改）、哪些是"枢纽节点"（改一个影响一片）。

#### 1.4 核心数据流
4 条关键路径：

| 路径 | 起点 | 终点 | 涉及文件 |
|------|------|------|---------|
| 聊天 | WebSocket → chat.py | AIAgent → LLM | 10+ 文件 |
| MCP 工具 | AIAgent → dispatch | MCP server 进程 | 4 文件 |
| ERP 配置 | ERP 页面 → API | config.json → mcp_starter | 6 文件 |
| 技能注入 | 用户输入 → skill_manager | system prompt | 3 文件 |

每条路径用编号步骤列出每个环节的文件和函数。

#### 1.5 关键类/方法签名速查
列出开发中最常调用的类和函数及其签名：

- `AIAgent.__init__(...)` / `run_conversation(...)` / `_take_snapshot()`
- `LLMClient.chat(model, messages, tools, ...) → LLMResponse`
- `ToolRegistry` 单例模式：`get_definitions()` / `dispatch()` / hook 链
- `MCPServerConnection.connect()` / `_connect_stdio()`
- `config_manager.get_config()` / `save()` / `encrypt_secret()` / `decrypt_secret()`
- `build_system_prompt(base, memory_store, ...) → str | None`

#### 1.6 开发约束
- 不可改区域列表（`agent/erp_clients/yonsuite/` 内部、`agent/skills/` builtin）
- 命名约定（MCP 工具 `mcp_*` 前缀、API 路由 `/api/*`）
- 安全约束：三层防护概要
- 配置加解密约定（`encrypted:` 前缀、fernet 密钥派生）

#### 1.7 测试体系
每个测试文件对应哪个模块：

| 测试文件 | 测试模块 | Mock 模式 |
|---------|---------|----------|
| `test_agent_loop.py` | core/agent.py | 全 mock LLM |
| `test_nc_mcp_starter.py` | mcp_starter.py | patch config_manager |
| ... | ... | ... |

覆盖率目标 70%+，运行命令。

#### 1.8 常见修改模式
- **新增 ERP**：改 ERP_REGISTRY → 建 MCP server → 注册 API
- **新增工具**：写 tool 函数 → registry.register() → 加到 enabled_tools
- **新增 MCP server**：写 server → 配 mcp_servers → toggle 启停
- **新增 API 路由**：建 router → 挂到 main.py

### 2.3 Part 2 内容规划

继承现有 AGENTS.md 的实用内容，重组为：

#### 2.1 快速上手
clone → 创建 venv → pip install → npm ci → 启动 → 验证

#### 2.2 常用命令速查表
命令 | 说明 | 何时使用

#### 2.3 架构概览
精简版架构图 + 组件说明（保留当前图但更新）

#### 2.4 ERP 接入指南
YonSuite / NC 的配置步骤 + 测试方法

#### 2.5 构建 & 发布
版本号五步同步法、build-app.sh 用法、.app 产出

#### 2.6 调试技巧
日志位置、WebSocket 抓包、MCP stderr 查看、config.json 直接编辑

---

## 3. 写作规范

- **代码引用**：反引号包裹文件路径、函数名、变量
- **表格**：同当前风格（`|` 分隔）
- **重要约束**：加粗或 `⚠️` 前缀
- **AI 指令**：Part 1 中直接以祈使句写（"改 X 时先确认 Y"）
- **多级标题**：`##` → `###` → `####`，不跳级
- **不引入 emoji 装饰**：除非用户要求

---

## 4. 验证标准

| 检查项 | 标准 |
|--------|------|
| Part 1 覆盖 | 8 个小节齐全，无遗漏 |
| Part 2 覆盖 | 6 个小节齐全，无遗漏 |
| 信息保真 | 现有 226 行所有有用信息已保留/升级 |
| 路径准确性 | 每个文件路径都经过真实目录核对 |
| AI 可执行性 | AI 按文档指示应能正确完成常见修改 |
