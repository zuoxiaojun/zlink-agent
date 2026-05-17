# YS-Agent

基于 FastAPI + React (Vite) 的独立 AI Agent，为 YonSuite（用友云 ERP）提供 AI 能力。

## 功能

- **AI 对话** — WebSocket 流式聊天，36 个内置工具自动调用
- **YonSuite 集成** — 销售/采购/生产订单、库存、待办、商机等 11 个查询工具
- **技能系统** — 可扩展技能包（安装/激活/停用）
- **记忆系统** — Agent 自主笔记 + 用户画像 + 对话摘要
- **全文搜索** — 历史对话 FTS5 索引

## 环境要求

- Python 3.10+
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
│   ├── agent.py            # Agent 循环 + LLM 调用
│   ├── tools/              # 36 个内置工具
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

当前版本：**v1.0**

详见 [CHANGELOG.md](./CHANGELOG.md)
