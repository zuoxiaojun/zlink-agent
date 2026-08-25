# ZLink Agent (智链 Agent)

> **Smart Link to Your Business Systems** — 把 LLM 连接到你的业务系统的智能中枢。

基于 FastAPI + React (Vite) 的独立 AI Agent，内置 YonSuite、NC 等多种 ERP 取数工具，提供 AI 驱动的取数与分析能力。

## 功能

- **AI 对话** — WebSocket 流式聊天，57 个内置工具 + YonSuite/NC 内置取数，支持推理过程实时显示
- **多 ERP 接入** — 内置 YonSuite 取数工具 + NC 取数工具（Oracle 直连，无需外部包）；新 ERP 按内置工具规范添加即可
- **配置驱动路由** — 用户在 `/settings/erp` 选择启用哪个 ERP，AI 自动从对应系统取数
- **Pydantic 配置** — 类型安全的配置模型，敏感字段以文件权限保护
- **Phase 状态机** — 4 阶段生命周期 + Envelope SSE 消息包装
- **插件系统** — 支持 entry-point 发现和目录扫描
- **技能系统** — 可扩展技能包（20 个内置技能 + 用户自定义）
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
│   ├── core/                       # Pi 风格内核 (kernel_types.py 钩子契约 + loop.py + agent.py + agent_adapter.py / llm_providers / message_builder / tool_dispatcher)
│   ├── erp_clients/                # ERP 客户端 (yonsuite)
│   │   ├── base.py                 # ERPClient Protocol + 通用异常
│   │   ├── __init__.py
│   │   └── yonsuite/               # YonSuite SDK 客户端
│   ├── tools/                      # 61 个内置工具 (file/web/skills/todo/clarify/cronjob/code_exec/project/vision/process/erp_ys/erp_nc/erp_u8)
│   ├── skills/                     # 21 个内置技能 (yonsuite/nc/u8/china-hotdata/anysearch/...)
│   ├── events/                     # EventBus + 9 个事件类型
│   └── extensions/                 # log_everything/security_event/monitoring/audit_log
├── backend/
│   ├── main.py                     # FastAPI app + CORS + 路由挂载
│   ├── api/                        # /api/chat /api/tools /api/skills /api/memory /api/mcp /api/config(含 /erp-clients) /api/cronjobs /api/extensions /api/system
│   └── schemas/                    # Pydantic 模型
├── web/                            # React + Vite (端口 8088)
│   ├── App.tsx                     # 路由: / /history /tools /skills /memory /cronjobs /mcp /settings/llm /settings/agent /settings/erp /settings/extensions
│   └── pages/                      # ChatPage / HistoryPage / ToolsPage / SkillManagerPage / MemoryPage / McpPage / CronJobPage / SettingsLLMPage / SettingsAgentPage / SettingsERPPage / SettingsExtensionsPage
├── data/                           # 运行时数据 (源码模式; .app 模式用 ~/.zlink-agent/data/)
└── tests/                          # pytest (509 个)
```

## 版本

v1.11.1 — 2026-08-25

详见 [CHANGELOG.md](CHANGELOG.md)

## License

见 `LICENSE` 文件
