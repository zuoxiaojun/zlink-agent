# ZLink Agent (智链 Agent)

> **Smart Link to Your Business Systems** — 把 LLM 连接到你的业务系统的智能中枢。

基于 FastAPI + React (Vite) 的独立 AI Agent，内置 YonSuite、NC、U8+、U9 Cloud 多 ERP 取数与分析能力。

## 功能

- **AI 对话** — WebSocket 流式聊天，65+ 内置工具，推理过程实时显示
- **多 ERP 接入** — 内置 YonSuite / NC / U8+ / U9 Cloud 取数工具，设置页选择启用即可使用
- **图文报告** — 集成数据分析与图表生成能力，支持销售/采购/生产报表的智能分析
- **技能系统** — 24 个内置技能，支持自定义扩展
- **记忆系统** — Agent 自主笔记 + 用户画像 + 对话摘要
- **全文搜索** — 历史对话 FTS5 索引
- **跨平台** — macOS / Linux / Windows

## 一键安装

```bash
git clone https://atomgit.com/gcw_cJbJuamU/zlink-agent.git
cd zlink-agent
./setup.sh
```

## 快速启动

```bash
./start.sh            # 生产模式
./start.sh --dev      # 开发模式（Vite 热更新）
./start.sh stop       # 停止服务
```

## 环境要求

- Python 3.11+ / Node.js 18+ / npm 9+

## 常用命令

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8089
cd web && npm run dev
.venv/bin/python -m pytest tests/ -v
ruff check . && ruff format --check .
```

## License

见 `LICENSE` 文件
