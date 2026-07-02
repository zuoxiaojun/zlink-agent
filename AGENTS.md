# YS-Agent

## 常用命令

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8089
cd web && npm run dev
pip install -r requirements.txt
cd web && npm install
python -c "from agent.tools.registry import registry, discover_tools; discover_tools(); print('OK:', len(registry.get_all_tool_names()), 'tools')"
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | .venv/bin/python -m mcp_server.ys_mcp_server
.venv/bin/python -m pytest tests/ -v
ruff check . && ruff format --check .
```

## 架构

```
web/ (React + Vite, 端口 8088)         backend/ (FastAPI, 端口 8089)
  ├── App.tsx → React Router               ├── main.py — FastAPI app + CORS + 路由挂载
  │    ├── /              → ChatPage       │     ├── /api/chat       — WebSocket 聊天
  │    ├── /history       → HistoryPage    │     ├── /api/tools      — 工具列表
  │    ├── /tools         → ToolsPage      │     ├── /api/sessions   — 会话管理
  │    ├── /skills        → SkillManagerPage│    ├── /api/skills     — 技能安装/管理
  │    ├── /memory        → MemoryPage     │     ├── /api/memory     — 记忆管理
  │    ├── /mcp           → McpPage        │     ├── /api/mcp        — MCP 服务器管理
  │    ├── /settings/llm  → SettingsLLMPage│     ├── /api/config     — 配置读写
  │    ├── /settings/yonsuite → SettingsYSPage│  └── /api/metrics    — 指标
  │    └── /settings/extensions → SettingsExtensionsPage
                                           │
  └─ vite.config.ts                        └─ core/agent.py (AIAgent.run_conversation)
       proxy: /api → localhost:8089              │    ├── core/agent.py — M7 多层循环
       proxy: /ws  → ws://localhost:8089         │    ├── core/llm_providers/ — 多供应商抽象
                                                  │    │    ├── base.py — LLMProvider 基类 + 重试
                                                  │    │    ├── openai_compat.py — httpx 直发(保留 reasoning_content)
                                                  │    │    └── anthropic.py — Anthropic 适配器
                                                  │    ├── core/message_builder.py — 系统提示组装
                                                  │    ├── core/tool_dispatcher.py — 工具分发
                                                  │    ├── core/iteration_budget.py — 迭代预算
                                                  │    ├── core/snapshot.py — 配置快照
                                                  │    ├── events/ — EventBus + 8 个事件类型
                                                  │    └── extensions/ — log_everything, security_event, monitoring
                                                  │
                                                  ├─ session_manager.py  — data/sessions/
                                                  ├─ search_index.py     — SQLite+FTS5 全文搜索
                                                  ├─ memory_manager.py   — 对话摘要，data/memory/
                                                  ├─ fact_memory.py      — 自主记忆（笔记+用户画像）
                                                  ├─ context_compactor.py— 上下文压缩（M6 三级压缩）
                                                  ├─ slash_commands.py   — /help /model /compact /clear /login /cost
                                                  │
                                                  ├─ tools/ — 22 个内置工具
                                                  │    ├─ registry.py — ToolRegistry 单例 + Hook 链
                                                  │    ├─ security_hooks.py — 三层安全拦截
                                                  │    ├─ terminal_tool.py / file_tools.py / web_tools.py
                                                  │    ├─ browser_tool.py — Playwright 浏览器控制
                                                  │    ├─ skills_tool.py / todo_tool.py / clarify_tool.py
                                                  │    ├─ memory_tool.py / session_search_tool.py
                                                  │    └─ mcp_manager.py — MCP 服务器生命周期
                                                  │
                                                  ├─ yonsuite_client/ — YonSuite SDK
                                                  ├─ config_manager.py — 配置加解密(fernet)
                                                  └─ skills/ — 已安装技能 (data-analysis, plan, yonsuite 等)
```

## SSE 解析说明

`openai_compat.py` 的流式解析兼容两种 SSE 格式：
- `data: {json}` — 标准 OpenAI 格式（冒号后有空格）
- `data:{json}` — 部分自定义网关格式（冒号后无空格）
- 两种都正确解析 `content`、`reasoning_content`、`tool_calls`

## 核心组件

- **`core/agent.py`** — M7 架构。`AIAgent.run_conversation()` 同步工具调用循环，含快照/重试/Token追踪/多阶段
- **`core/llm_providers/`** — 多供应商 LLM 抽象。OpenAI-compat 用 `httpx` 直发（避免 SDK 丢字段），Anthropic 专用适配器
- **`context_compactor.py`** — M6 三级压缩：工具结果截断 → LLM 摘要 → 丢弃早期工具调用
- **`events/` + `extensions/`** — EventBus 事件总线 + 插件式扩展

## 工具清单

| 工具集 | 工具 |
|---------|------|
| `terminal` | `terminal` |
| `file` | `read_file`, `write_file`, `patch`, `search_files`, `ls` |
| `web` | `web_search`, `web_extract` |
| `browser` | `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`, `browser_scroll`, `browser_back`, `browser_press`, `browser_get_images`, `browser_console` |
| `skills` | `skill_list`, `skill_view`, `skill_activate`, `skill_deactivate`, `skill_install`, `skill_export` |
| `mcp-yonsuite` | `mcp_yonsuite_ys_api`, query 系列(销售/采购/生产/库存/待办/商机/产品/客户/供应商/凭证) |
| `mcp-mcp-server-chart` | 27 种图表工具 (柱状/折线/饼图/散点/地图/思维导图等) |
| `todo` | `todo` |
| `clarify` | `clarify` |
| `memory` | `memory` |
| `session_search` | `session_search` |

## MCP 服务器管理

- stdio: `asyncio.create_subprocess_exec(command, *args)`
- 自动重连，熔断器 3 次连续失败 → 60s 冷却
- 内置 yonsuite MCP Server（11 个查询 handler）
- 内置 chart MCP Server（27 种图表）

## 安全规则

三层防护：系统提示词 → `security_hooks.py` before-hook → `SecurityEventExtension` 事件层

## 配置

`data/config.json`，API Key 用 `cryptography.fernet` 加密存储。

## 前端特殊适配

- 表格：`table-layout: fixed` 固定列宽 + `overflow-x: auto` 水平滚动
- 消息气泡：`overflow-x: auto` 防止被大表格撑宽
