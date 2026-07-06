# YS-Agent

基于 FastAPI + React (Vite) 的独立 AI Agent，为 YonSuite（用友云 ERP）提供 AI 能力。

## 功能

- **AI 对话** — WebSocket 流式聊天，26+ 个内置工具自动调用，支持推理过程实时显示
- **YonSuite 集成** — 销售/采购/生产订单、库存、待办、商机等 11 个查询工具
- **Pydantic 配置** — 类型安全的配置模型，自动加密敏感字段，属性访问替代字典操作
- **Phase 状态机** — 4 阶段生命周期（idle/turn/compaction/retry）+ Envelope SSE 消息包装
- **插件系统** — 支持 entry-point 发现和目录扫描，第三方扩展可独立安装
- **技能系统** — 可扩展技能包（安装/激活/停用），37+ 个内置技能
- **记忆系统** — Agent 自主笔记 + 用户画像 + 对话摘要
- **全文搜索** — 历史对话 FTS5 索引
- **配置加密** — 敏感字段自动 AES 加密存储
- **跨平台** — 支持 macOS / Linux / Windows

## 环境要求

- Python 3.11+
- Node.js 18+
- npm 9+

## 一键构建

```bash
git clone https://atomgit.com/gcw_cJbJuamU/ys-agent.git
cd ys-agent
./setup.sh
```

启动：

```bash
# 生产模式（后端 Serve 前端，自动打开浏览器）
./start.sh

# 开发模式（后端 + Vite 热更新）
./start.sh --dev
```

> 支持 macOS / Linux / Windows (Git Bash)，脚本自动识别系统环境。

## 手动构建

```bash
# 1. 克隆
git clone https://atomgit.com/gcw_cJbJuamU/ys-agent.git
cd ys-agent

# 2. 后端
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. 配置端口
cp .env.example .env
# 编辑 .env 修改端口（可选）

# 4. 前端
cd web
npm ci
npm run build     # 输出到 web/dist/
cd ..

# 5. 启动
./start.sh
```

## 配置

| 配置项 | 方式 |
|--------|------|
| 端口 | `.env` 文件（`YS_FRONTEND_PORT` / `YS_AGENT_PORT`） |
| LLM API Key | 启动后访问 `http://localhost:8088` → 设置 → LLM 配置（自动加密存储） |
| YonSuite 密钥 | 启动后访问 `http://localhost:8088` → 设置 → YonSuite 配置 |

## 项目结构

```
ys-agent/
├── agent/                  # AI Agent 核心
│   ├── agent.py            # re-export 入口（旧循环已拆分为 core/）
│   ├── config_model.py     # Pydantic 配置模型（AppConfig + MCPServerEntry）
│   ├── config_manager.py   # 持久化配置（加密存储 + 类型安全）
│   ├── core/               # 分层引擎（agent/message_builder/llm_client/Phase 状态机）
│   ├── events/             # 事件总线 + 8 事件类 + Extension 系统
│   ├── extensions/         # 内置扩展（日志/监控/安全）
│   ├── plugin_system/      # 插件发现（entry-point + 目录扫描）
│   ├── tools/              # 26+ 个内置工具 + MCP 管理器
│   ├── yonsuite_client/    # YonSuite API 核心库
│   ├── skills/             # 技能包
│   ├── session_manager.py  # 会话管理
│   ├── memory_manager.py   # 对话摘要
│   ├── fact_memory.py      # 自主记忆（笔记 + 用户画像）
│   └── search_index.py     # FTS5 搜索索引
├── backend/                # FastAPI 后端
│   ├── main.py             # 应用入口（lifespan 上下文管理器）
│   ├── api/                # REST + WebSocket API
│   ├── schemas/            # Pydantic 响应模型
│   ├── llm_providers.py    # 9 家 LLM 厂商配置
│   └── config.py           # 服务配置
├── web/                    # React 前端
│   ├── src/pages/          # 页面组件（Chat/History/Tools/Skills/Memory/MCP/Settings）
│   └── vite.config.ts      # Vite 配置
├── mcp_server/             # 内置 MCP 服务器（yonsuite）
├── data/                   # 运行时数据（config.json / 会话 / 记忆 / 日志 / 插件）
├── tests/                  # pytest 套件（41 tests）
├── .env.example            # 环境变量模板
├── setup.sh                # 一键构建脚本
├── start.sh                # 启动脚本
└── VERSION                 # 版本号
```

## 版本

当前版本：**v1.3.0**（2026-07-04）。完整变更日志见 [CHANGELOG.md](./CHANGELOG.md)。

## v1.3+ 新增

- **Pydantic 配置化**：`agent/config_model.py` 新增 `AppConfig` 模型，类型安全 + 加密字段自动处理
- **Phase 状态机**：`Phase` 枚举 + `Envelope` SSE 包装器，前端可追踪 agent 生命周期
- **插件系统**：`agent/plugin_system/` 支持 entry-point 发现和目录扫描
- **Windows 兼容**：terminal_tool 跨平台 shell 检测（cmd/powershell/bash），路径正则支持 `C:\...`
- Agent 配置可 Web UI 调整（`/settings/agent`），Extension 可 UI toggle（`/settings/extensions`）

## v1.1+ 新增（已推送，详见 commit `d18369c`）

v1.0 → v1.1.1 的重构增量（41 files / +5097 / -498）。CHANGELOG 里 v1.1.1 段记的概要：

- **M1 分层**：`agent/agent.py` (481 行) 拆为 `agent/core/{agent,message_builder,llm_client,tool_dispatcher,iteration_budget}.py`；`agent/agent.py` 缩到 40 行 re-export
- **M2 事件系统**：`agent/events/{bus,types,extensions}.py`；8 个事件类（session_start/end、user_message、before/after_llm_call、before/after_tool_call、session_before_compact）；Extension 基类 + typed handler 自动订阅
- **M3 LLM Provider 抽象**：`agent/core/llm_providers/{base,openai_compat,anthropic,factory}.py`；9 个 OpenAI-compat provider + Anthropic 原生
- **M4 压缩增强**：`compact_messages` 改吃 `summary_caller`；新增文件追踪（限 5 个/8KB）；`SessionBeforeCompactEvent` 钩子
- **M5+ Extension 配置化**：4 个 HTTP API（`/api/extensions`、`/active`、`/{name}/toggle`、`/reload`）+ Web UI「扩展管理」页（侧边栏 → 设置 → 扩展管理），状态持久化到 `config.json` 的 `disabled_extensions` 字段，runtime toggle 生效无需重启
- **v1.1.2**：跨平台脚本适配（macOS / Linux / Windows Git Bash），`llm_api_key` Fernet 加密存储，自动打开浏览器
- **pytest 套件**：`tests/` 36 个 test，0.5s 全过；事件总线 + config 双 fixture 隔离；0 新依赖

### 开发参考

- Extension 开发指南：[`docs/extending-ys-agent.md`](./docs/extending-ys-agent.md)
- pytest 套件说明：[`tests/README.md`](./tests/README.md)

### 跑 pytest

```bash
source .venv/bin/activate
.venv/bin/python -m pytest tests/ -v   # 36 tests, ~0.5s
```
