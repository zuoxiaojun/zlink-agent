# ZLink Agent (智链 Agent)

> **Smart Link to Your Business Systems** — 把 LLM 连接到你的业务系统的智能中枢。

基于 FastAPI + React (Vite) 的独立 AI Agent，通过 MCP 协议对接 YonSuite、NC 等多种 ERP 系统，提供 AI 驱动的取数与分析能力。

## 功能

- **AI 对话** — WebSocket 流式聊天，41 个内置工具 + YonSuite/NC MCP 自动调用，支持推理过程实时显示
- **多 ERP 接入** — 内置 YonSuite MCP + NC MCP（Oracle 直连，无需外部包）；新 ERP 按 MCP 包规范添加即可
- **配置驱动路由** — 用户在 `/settings/erp` 选择启用哪个 ERP，AI 自动从对应系统取数
- **Pydantic 配置** — 类型安全的配置模型，自动加密敏感字段
- **Phase 状态机** — 4 阶段生命周期 + Envelope SSE 消息包装
- **插件系统** — 支持 entry-point 发现和目录扫描
- **技能系统** — 可扩展技能包（19 个内置技能 + 用户自定义）
- **记忆系统** — Agent 自主笔记 + 用户画像 + 对话摘要
- **全文搜索** — 历史对话 FTS5 索引
- **跨平台** — macOS / Linux / Windows

## 部署

- 命令: `zlink` (安装到 `~/.local/bin/zlink`)
- 数据目录: `~/.zlink-agent/data/`
- 配置目录: `ZLINK_DATA_DIR` 环境变量覆盖 (可选)

详见 `scripts/setup.sh` (Linux/macOS) 或 `setup.bat` (Windows)。

## 环境要求

- Python 3.11+
- Node.js 18+
- npm 9+

## 一键安装（macOS / Linux）

```bash
git clone https://atomgit.com/gcw_cJbJuamU/zlink-agent.git
cd zlink-agent
./setup.sh
```

## 快速启动

```bash
./start.sh            # 生产模式: 后端 Serve 前端
./start.sh --dev      # 开发模式: 后端 + Vite 热更新
./start.sh stop       # 停止服务
```

## 常用命令

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8089
cd web && npm run dev           # Vite 开发服务器
.venv/bin/python -m pytest tests/ -v
ruff check . && ruff format --check .
```

## 项目结构

```
zlink-agent/
├── agent/
│   ├── core/                       # LLM 核心 (agent.py / llm_providers/ / message_builder / tool_dispatcher)
│   ├── erp_clients/                # 声明性 ERP 客户端父目录
│   │   ├── base.py                 # ERPClient Protocol + 通用异常 + MCPStarterConfig
│   │   ├── __init__.py             # 声明性注册中心
│   │   └── yonsuite/               # 从 yonsuite_client/ 整体迁移
│   ├── tools/                      # 41 个内置工具 (file/web/browser/skills/todo/clarify/cronjob/code_exec/project/vision/process)
│   ├── skills/                     # 19 个内置技能 (yonsuite/nc/china-hotdata/anysearch/...)
│   ├── events/                     # EventBus + 9 个事件类型
│   └── extensions/                 # log_everything/security_event/monitoring
├── backend/
│   ├── main.py                     # FastAPI app + CORS + 路由挂载
│   ├── api/                        # /api/chat /api/tools /api/skills /api/memory /api/mcp /api/config(含 /erp-clients)
│   ├── core/llm_providers/         # openai_compat / anthropic
│   └── schemas/                    # Pydantic 模型
├── web/                            # React + Vite (端口 8088)
│   ├── App.tsx                     # 路由: / /history /tools /skills /memory /cronjobs /mcp /settings/llm /settings/agent /settings/erp /settings/extensions
│   └── pages/                      # ChatPage / HistoryPage / ToolsPage / SkillManagerPage / MemoryPage / McpPage / SettingsLLMPage / SettingsAgentPage / SettingsERPPage [新] / SettingsYSPage / SettingsExtensionsPage
├── mcp_server/
│   ├── ys_mcp_server/              # builtin YonSuite MCP (11 个 query 工具)
│   └── nc_mcp/                     # NC MCP 集成入口 (Oracle 直连，内置)
├── data/                           # 运行时数据 (源码模式; .app 模式用 ~/.zlink-agent/data/)
└── tests/                          # pytest (356 个)
```

## 版本

v1.7.1 — 2026-07-18

详见 [CHANGELOG.md](CHANGELOG.md)

## License

见 `LICENSE` 文件
