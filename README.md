# YS-Agent

基于 FastAPI + React (Vite) 的独立 AI Agent，为 YonSuite（用友云 ERP）提供 AI 能力。

## 功能

- **AI 对话** — WebSocket 流式聊天，26+ 个内置工具自动调用
- **YonSuite 集成** — 销售/采购/生产订单、库存、待办、商机等 11 个查询工具
- **技能系统** — 可扩展技能包（安装/激活/停用）
- **记忆系统** — Agent 自主笔记 + 用户画像 + 对话摘要
- **全文搜索** — 历史对话 FTS5 索引

## 环境要求

- Python 3.11+
- Node.js 18+
- npm 9+

## 一键构建

```bash
git clone https://gitee.com/leftxiaojun/ys-agent.git
cd ys-agent
chmod +x setup.sh
./setup.sh
```

启动：

```bash
# 前后端一起启动
./start.sh

# 或分别启动
./run_backend.sh   # 后端 http://localhost:8089
./run_frontend.sh  # 前端 http://localhost:8088
```

## 手动构建

```bash
# 1. 克隆
git clone https://gitee.com/leftxiaojun/ys-agent.git
cd ys-agent

# 2. 后端
python3 -m venv .venv
source .venv/bin/activate
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

## 生产部署

```bash
# 前端 — nginx 托管 web/dist/，代理 /api 和 /ws 到后端
# 后端 — 多 worker 启动
uvicorn backend.main:app --host 0.0.0.0 --port 8089 --workers 4
```

nginx 配置示例：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    root /opt/ys-agent/web/dist;
    index index.html;

    location / {
        try_files $uri /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8089;
        proxy_set_header Host $host;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8089;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 配置

| 配置项 | 方式 |
|--------|------|
| 端口 | `.env` 文件（`YS_FRONTEND_PORT` / `YS_AGENT_PORT`） |
| LLM API Key | 启动后访问 `http://localhost:8088` → 设置 → LLM 配置 |
| YonSuite 密钥 | 启动后访问 `http://localhost:8088` → 设置 → YonSuite 配置 |

## 项目结构

```
ys-agent/
├── agent/                  # AI Agent 核心
│   ├── agent.py            # re-export 入口（旧循环已拆分为 core/）
│   ├── core/               # 分层引擎（agent/message_builder/llm_client/迭代预算）
│   ├── events/             # 事件总线 + 8 事件类 + Extension 系统
│   ├── tools/              # 26+ 个内置工具 + MCP 管理器
│   ├── yonsuite_client/    # YonSuite API 核心库
│   ├── skills/             # 技能包
│   ├── session_manager.py  # 会话管理
│   ├── memory_manager.py   # 对话摘要
│   └── search_index.py     # FTS5 搜索索引
├── backend/                # FastAPI 后端
│   ├── main.py             # 应用入口
│   ├── api/                # REST + WebSocket API
│   └── config.py           # 服务配置
├── web/                    # React 前端
│   ├── src/pages/          # 页面组件
│   └── vite.config.ts      # Vite 配置
├── .env.example            # 环境变量模板
├── setup.sh                # 一键构建脚本
├── start.sh                # 启动脚本
└── VERSION                 # 版本号
```

## 版本

当前版本：**v1.1.1**（2026-06-02）。v1.0 → v1.1 → v1.1.1 增量见下方「v1.1+ 新增」段与 [CHANGELOG.md](./CHANGELOG.md)。

## v1.1+ 新增（已推送，详见 commit `d18369c`）

v1.0 → v1.1.1 的重构增量（41 files / +5097 / -498）。CHANGELOG 里 v1.1.1 段记的概要：

- **M1 分层**：`agent/agent.py` (481 行) 拆为 `agent/core/{agent,message_builder,llm_client,tool_dispatcher,iteration_budget}.py`；`agent/agent.py` 缩到 40 行 re-export
- **M2 事件系统**：`agent/events/{bus,types,extensions}.py`；8 个事件类（session_start/end、user_message、before/after_llm_call、before/after_tool_call、session_before_compact）；Extension 基类 + typed handler 自动订阅
- **M3 LLM Provider 抽象**：`agent/core/llm_providers/{base,openai_compat,anthropic,factory}.py`；9 个 OpenAI-compat provider + Anthropic 原生
- **M4 压缩增强**：`compact_messages` 改吃 `summary_caller`；新增文件追踪（限 5 个/8KB）；`SessionBeforeCompactEvent` 钩子
- **M5+ Extension 配置化**：4 个 HTTP API（`/api/extensions`、`/active`、`/{name}/toggle`、`/reload`）+ Web UI「扩展管理」页（侧边栏 → 设置 → 扩展管理），状态持久化到 `config.json` 的 `disabled_extensions` 字段，runtime toggle 生效无需重启
- **pytest 套件**：`tests/` 36 个 test，0.5s 全过；事件总线 + config 双 fixture 隔离；0 新依赖

### 架构与开发文档

- 架构 HTML（含 5.6 安全守卫双防线 + 5.8 Extension 事件系统新章节）：[`architecture.html`](./architecture.html)（直接 `open` 在浏览器看）
- Markdown 架构说明：[`docs/architecture.md`](./docs/architecture.md)
- Extension 开发指南：[`docs/extending-ys-agent.md`](./docs/extending-ys-agent.md)
- pytest 套件说明：[`tests/README.md`](./tests/README.md)

### 跑 pytest

```bash
source .venv/bin/activate
.venv/bin/python -m pytest tests/ -v   # 36 tests, ~0.5s
```


### 开发工作流

仓库使用 [pre-commit](https://pre-commit.com/) 在每次 `git commit` 时自动跑代码质量钩子（ruff / ruff-format / 通用文件检查）。

**首次克隆后初始化**：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pre-commit                              # 装到项目 venv
git config core.hooksPath .githooks                 # 启用仓库内置钩子
```

**配置要点**（已提交到仓库，无需手工改）：

- `.githooks/pre-commit` — 仓库内置的钩子入口，使用 `git rev-parse --show-toplevel` 解析仓库根，**不硬编码绝对路径**，跨机器/重命名项目目录都能直接用
- `.pre-commit-config.yaml` — ruff / ruff-format 使用 `language: system`，复用项目 `.venv` 里的 ruff，**无需联网**即可工作；其他内置钩子（trailing-whitespace / end-of-file-fixer / check-yaml / check-toml / check-added-large-files / check-merge-conflict / detect-private-key）首跑后会缓存到 `~/.cache/pre-commit/`
- `.atomcode/settings.json` — `pytestRun` hook 的工作目录跟随项目实际路径

**手动跑一次全部钩子**：

```bash
.venv/bin/python -m pre_commit run --all-files
```

**绕过钩子**（不推荐，仅在紧急修复时使用）：

```bash
git commit --no-verify -m "hotfix: ..."
```
