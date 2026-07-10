# ZLink Agent v1.5.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 YS-Agent 改名为 ZLink Agent（智链 Agent），并接入 NC MCP 包支持多 ERP

**Architecture:**
- ZLink Agent 是 ERP 客户端的**调度者**，不实现任何具体 ERP 业务
- 每个 ERP 客户端 = 一个独立 MCP server（stdio 进程）
- 用户通过 `config.json` 的 `erp_clients.<name>.enabled` 开关决定启用哪个
- 启用的 ERP 的 MCP server 由 `mcp_manager` 拉起，工具自动注册到 LLM
- 现有 `mcp-yonsuite` builtin 保留，NC 通过外部 `nc-mcp-server` Python 包集成

**Tech Stack:** Python 3.11+, FastAPI, React + Vite, MCP 协议 (stdio JSON-RPC), pytest, ruff

**Spec:** `docs/superpowers/specs/2026-07-10-zlink-agent-design.md` (843 行)

**Branch:** `codex/zlink-agent-v1.5.0` (基于 main 已开)

---

## File Structure

执行本计划涉及的关键文件：

| 类型 | 路径 | 角色 |
|------|------|------|
| 新增 | `agent/erp_clients/__init__.py` | 声明性 ERP 注册中心 |
| 新增 | `agent/erp_clients/base.py` | ERPClient Protocol + 通用异常 + MCPStarterConfig |
| 移动 | `agent/yonsuite_client/` → `agent/erp_clients/yonsuite/` | YonSuite 客户端, 内部 0 改动 |
| 新增 | `mcp_server/nc_mcp/__init__.py` | NC MCP 集成入口包 |
| 新增 | `mcp_server/nc_mcp/config.py` | 用户配置 → ORACLE_* 转换 |
| 新增 | `mcp_server/nc_mcp/mcp_starter.py` | 调 mcp_manager 启停 nc-mcp-server |
| 新增 | `agent/skills/nc/SKILL.md` | NC 工具使用指南 |
| 新增 | `backend/api/erp_clients_api.py` | /api/config/erp-clients 路由 |
| 新增 | `web/src/pages/SettingsERPPage.tsx` | /settings/erp 页面 |
| 新增 | `tests/test_erp_clients.py` | 10 个新测试 |
| 改 | `pyproject.toml` | name/description/version + nc extra |
| 改 | `README.md`, `CHANGELOG.md`, `VERSION`, `AGENTS.md` | 品牌/版本同步 |
| 改 | `agent/utils.py` | 数据目录双兼容 |
| 改 | `agent/config_manager.py` | 占位符解析 + get_erp_config() |
| 改 | `agent/tools/mcp_manager.py` | 占位符解析支持 |
| 改 | `backend/api/config_api.py` | 挂 erp-clients 端点 |
| 改 | `web/src/App.tsx` | 加 /settings/erp 路由 |
| 改 | `scripts/ys-agent.sh` | 软链接到 zlink.sh |
| 新增 | `scripts/zlink.sh` | 新 CLI 入口 |
| 改 | `docs/architecture.md`, `docs/extending-ys-agent.md` | 文档更新 |

---

# Phase 1: 命名与品牌（5 tasks）

## Task 1: 改 `pyproject.toml` 元信息

**Files:**
- Modify: `pyproject.toml:1-15`

- [ ] **Step 1: 改 name / description / version**

```toml
# pyproject.toml 头部修改
[project]
name = "zlink-agent"
version = "1.5.0"
description = "Smart Link to Your Business Systems - AI Agent for Multi-ERP Analysis"
requires-python = ">=3.11"
```

- [ ] **Step 2: 加 nc optional extra**

在 `[project.optional-dependencies]` 段补：
```toml
nc = [
    "nc-mcp-server @ git+https://atomgit.com/gcw_cJbJuamU/nc-mcp-project.git@main#subdirectory=nc-mcp",
]
```

- [ ] **Step 3: 验证 pyproject 可解析**

Run: `.venv/bin/python -c "import tomllib; tomllib.loads(open('pyproject.toml').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: rename to zlink-agent v1.5.0 + add [nc] extra"
```

---

## Task 2: 改 `VERSION` 文件

**Files:**
- Modify: `VERSION`

- [ ] **Step 1: 写入新版本号**

```bash
echo "1.5.0" > VERSION
```

- [ ] **Step 2: 验证**

Run: `cat VERSION`
Expected: `1.5.0`

- [ ] **Step 3: Commit**

```bash
git add VERSION
git commit -m "chore: bump VERSION to 1.5.0"
```

---

## Task 3: 追加 `CHANGELOG.md` v1.5.0 段

**Files:**
- Modify: `CHANGELOG.md` (在文件最顶部加)

- [ ] **Step 1: 加 v1.5.0 changelog**

在 `CHANGELOG.md` 顶部加：

```markdown
# Changelog
## v1.5.0 — 2026-07-10 (重命名 ZLink Agent + 多 ERP 架构)

**范围**: 把 YS-Agent 改名为 ZLink Agent（智链 Agent），引入声明性 ERPClient 协议，集成外部 nc-mcp-server 包作为首个非 builtin ERP 客户端。

### 新增

- **`agent/erp_clients/`** 新父目录, 含 `base.py`（ERPClient Protocol + 通用异常 + MCPStarterConfig）、`__init__.py`（声明性注册中心）
- **`agent/erp_clients/yonsuite/`** 从 `agent/yonsuite_client/` 整体 `git mv` 过来, 内部 0 行代码改动
- **`mcp_server/nc_mcp/`** NC MCP 集成入口 (config.py: erp_clients.nc → ORACLE_* env 转换; mcp_starter.py: 调 mcp_manager 启停 nc-mcp-server)
- **`agent/skills/nc/SKILL.md`** NC 工具使用指南
- **`backend/api/erp_clients_api.py`** `/api/config/erp-clients/*` REST 端点
- **`web/src/pages/SettingsERPPage.tsx`** `/settings/erp` 页面 (YonSuite + NC 双卡片)
- **`scripts/zlink.sh`** 新 CLI 入口
- **`tests/test_erp_clients.py`** 10 个新测试 (覆盖 base 导出、配置转换、占位符、graceful 降级、启用状态联动)

### 改动

- **`pyproject.toml`**: name `ys-agent` → `zlink-agent`, description 重写, version 1.4.1 → 1.5.0, 加 `[nc]` optional extra
- **`agent/utils.py`**: `_resolve_data_dir()` 加 `~/.ys-agent/data/` fallback (双兼容老用户)
- **`agent/config_manager.py`**: 加 `get_erp_config(name)`, 加 `${nc.X}` 占位符解析
- **`agent/tools/mcp_manager.py`**: 启动 MCP server 前解析 env 占位符
- **`backend/api/config_api.py`**: 挂 `/api/config/erp-clients/*` 端点
- **`web/src/App.tsx`**: 加 `/settings/erp` 路由
- **`README.md`**: 标题/Tagline/克隆命令/功能列表/项目结构全量重写
- **`AGENTS.md`**: 标题 + 项目名引用更新
- **`scripts/ys-agent.sh`**: 软链接到 `zlink.sh` (保留兼容)
- **`docs/architecture.md`**: 加 "多 ERP 抽象" 章节
- **`docs/extending-ys-agent.md`**: 改名为 `extending-zlink-agent.md` + 内容更新
- 其它 ~200 处 `ys-agent` 字符串批量替换

### 净增

- `agent/erp_clients/` 新增 ~150 行 (base.py + __init__.py)
- `mcp_server/nc_mcp/` 新增 ~80 行
- 10 个新测试 → 41+10 = **56/56 PASS**
- ruff check 0 errors
- 数据目录 `~/.zlink-agent/data/` 为新默认, `~/.ys-agent/data/` 兼容 v1.4.x

### 不变

- `YonSuiteClient` 1055 行内部代码 0 改动 (仅移动目录位置)
- builtin MCP server `ys_mcp_server` 0 改动
- 工具名 `mcp_yonsuite_*` 0 改名 (老用户无感)
- LLM provider 抽象 0 改动
- builtin skills 列表 0 改动
- 4 个 untracked Windows 文件 0 改动 (用户另外的事)

## v1.4.1 — 2026-07-10 (移除自动迁移: 项目仅服务新用户)
```

- [ ] **Step 2: 验证 changelog 格式**

Run: `head -30 CHANGELOG.md`
Expected: v1.5.0 段在顶部, v1.4.1 段紧随其后

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add v1.5.0 changelog (ZLink rename + multi-ERP)"
```

---

## Task 4: 全量重写 `README.md`

**Files:**
- Modify: `README.md` (基本全量重写)

- [ ] **Step 1: 写入新 README 骨架**

```markdown
# ZLink Agent (智链 Agent)

> **Smart Link to Your Business Systems** — 把 LLM 连接到你的业务系统的智能中枢。

基于 FastAPI + React (Vite) 的独立 AI Agent，通过 MCP 协议对接 YonSuite、NC 等多种 ERP 系统，提供 AI 驱动的取数与分析能力。

## 功能

- **AI 对话** — WebSocket 流式聊天，18 个内置工具 + YonSuite/NC MCP 自动调用，支持推理过程实时显示
- **多 ERP 接入** — 内置 YonSuite MCP；NC 通过 [nc-mcp-server](https://atomgit.com/gcw_cJbJuamU/nc-mcp-project) 集成；新 ERP 按 MCP 包规范添加即可
- **配置驱动路由** — 用户在 `/settings/erp` 选择启用哪个 ERP，AI 自动从对应系统取数
- **Pydantic 配置** — 类型安全的配置模型，自动加密敏感字段
- **Phase 状态机** — 4 阶段生命周期 + Envelope SSE 消息包装
- **插件系统** — 支持 entry-point 发现和目录扫描
- **技能系统** — 可扩展技能包（37+ 个内置技能 + 用户自定义）
- **记忆系统** — Agent 自主笔记 + 用户画像 + 对话摘要
- **全文搜索** — 历史对话 FTS5 索引
- **跨平台** — macOS / Linux / Windows

## v1.5.0 升级说明

从 v1.4.x 升级的用户：
- 数据目录 `~/.ys-agent/data/` 自动兼容，无需迁移
- CLI 命令 `ys-agent` 仍可用（软链接到 `zlink`）
- 想用新名：手动 `mv ~/.ys-agent/data ~/.zlink-agent/data`

## 环境要求

- Python 3.11+
- Node.js 18+
- npm 9+
- （可选）Oracle 客户端库 — 仅当启用 NC 时需要

## 一键安装（macOS / Linux）

```bash
git clone https://atomgit.com/gcw_cJbJuamU/zlink-agent.git
cd zlink-agent
./setup.sh
```

## 启用 NC 支持（可选）

```bash
# 装 NC MCP server 包 (Oracle 直连)
pip install "zlink-agent[nc]"

# 或从源码装最新:
pip install git+https://atomgit.com/gcw_cJbJuamU/nc-mcp-project.git

# 启动后访问 /settings/erp 填 Oracle 连接信息
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
│   ├── erp_clients/                # [v1.5.0 新] 声明性 ERP 客户端父目录
│   │   ├── base.py                 # ERPClient Protocol + 通用异常 + MCPStarterConfig
│   │   ├── __init__.py             # 声明性注册中心
│   │   └── yonsuite/               # 从 yonsuite_client/ 整体迁移
│   ├── tools/                      # 27 个内置工具 (file/web/skills/todo/clarify/memory/session_search/mcp_manager)
│   ├── skills/                     # 内置技能 (yonsuite/nc/...)
│   ├── events/                     # EventBus + 9 个事件类型
│   └── extensions/                 # log_everything/security_event/monitoring
├── backend/
│   ├── main.py                     # FastAPI app + CORS + 路由挂载
│   ├── api/                        # /api/chat /api/tools /api/skills /api/memory /api/mcp /api/config(含 /erp-clients)
│   ├── core/llm_providers/         # openai_compat / anthropic
│   └── schemas/                    # Pydantic 模型
├── web/                            # React + Vite (端口 8088)
│   ├── App.tsx                     # 路由: / /history /tools /skills /memory /mcp /settings/llm /settings/agent /settings/erp [新] /settings/yonsuite /settings/extensions
│   └── pages/                      # ChatPage / HistoryPage / ToolsPage / SkillManagerPage / MemoryPage / McpPage / SettingsLLMPage / SettingsAgentPage / SettingsERPPage [新] / SettingsYSPage / SettingsExtensionsPage
├── mcp_server/
│   ├── ys_mcp_server/              # builtin YonSuite MCP (11 个 query 工具)
│   └── nc_mcp/                     # [v1.5.0 新] NC MCP 集成入口 (调外部 nc-mcp-server)
├── data/                           # 运行时数据 (源码模式; .app 模式用 ~/.zlink-agent/data/)
└── tests/                          # pytest (41+10=56 个)
```

## 版本

v1.5.0 — 2026-07-10

## License

见 `LICENSE` 文件
```

- [ ] **Step 2: 验证 README 链接和路径正确**

Run: `grep -c "ys-agent" README.md`
Expected: `0`（不应有残留的 ys-agent 字符串）

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for ZLink Agent v1.5.0"
```

---

## Task 5: 改 `AGENTS.md` 项目名引用

**Files:**
- Modify: `AGENTS.md` (头部 + 项目名引用)

- [ ] **Step 1: 改 AGENTS.md 头部**

在文件最顶部把:
```
# YS-Agent
```
改为:
```
# ZLink Agent (智链 Agent)
```

- [ ] **Step 2: 批量替换项目名引用**

```bash
sed -i '' 's/YS-Agent/ZLink Agent/g' AGENTS.md
sed -i '' 's/ys-agent/zlink-agent/g' AGENTS.md
```

- [ ] **Step 3: 验证替换**

Run: `grep -c "YS-Agent\|ys-agent" AGENTS.md`
Expected: `0`

- [ ] **Step 4: 跑测试确认现有 41 测试未挂**

Run: `.venv/bin/python -m pytest tests/ -v 2>&1 | tail -10`
Expected: `41 passed`

- [ ] **Step 5: ruff check**

Run: `ruff check AGENTS.md 2>&1 || true; ruff check . 2>&1 | tail -5`
Expected: AGENTS.md 是 markdown, ruff 会跳过; `ruff check .` 0 errors

- [ ] **Step 6: Commit**

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md to ZLink Agent"
```

---

# Phase 2: 项目结构（4 tasks）

## Task 6: git mv `yonsuite_client` → `erp_clients/yonsuite`

**Files:**
- Move: `agent/yonsuite_client/` → `agent/erp_clients/yonsuite/`

- [ ] **Step 1: 创建新父目录**

```bash
mkdir -p agent/erp_clients
```

- [ ] **Step 2: git mv 整个目录**

```bash
git mv agent/yonsuite_client agent/erp_clients/yonsuite
```

- [ ] **Step 3: 验证移动成功**

Run: `ls agent/erp_clients/yonsuite/`
Expected: `__init__.py cache.py config.py docs examples exceptions.py models.py modules tests ys_client.py`

Run: `ls agent/yonsuite_client 2>&1`
Expected: `No such file or directory`

- [ ] **Step 4: 检查 git status 确认 move 被识别**

Run: `git status --short | grep -E "yonsuite|erp_clients" | head -10`
Expected: 类似 `R  agent/yonsuite_client/__init__.py -> agent/erp_clients/yonsuite/__init__.py` 的重命名条目

- [ ] **Step 5: Commit**

```bash
git add -A agent/erp_clients/
git commit -m "refactor: move yonsuite_client to erp_clients/yonsuite (path only, no code change)"
```

---

## Task 7: 修所有 import 路径引用 `yonsuite_client`

**Files:**
- Modify: 所有引用 `agent.yonsuite_client` 或 `agent/yonsuite_client` 的文件

- [ ] **Step 1: 找出所有引用**

```bash
grep -rln "yonsuite_client" --include="*.py" --include="*.md" --include="*.toml" --include="*.json" --include="*.sh" agent/ backend/ web/ tests/ scripts/ mcp_server/ docs/ 2>/dev/null | grep -v __pycache__ | grep -v "erp_clients/yonsuite" | head -30
```

- [ ] **Step 2: 批量替换 import 路径**

```bash
# Python import: from agent.yonsuite_client → from agent.erp_clients.yonsuite
find agent/ backend/ tests/ mcp_server/ -name "*.py" -not -path "*/erp_clients/*" -not -path "*/__pycache__/*" -exec sed -i '' 's|from agent\.yonsuite_client|from agent.erp_clients.yonsuite|g; s|import agent\.yonsuite_client|import agent.erp_clients.yonsuite|g; s|agent\.yonsuite_client\.|agent.erp_clients.yonsuite.|g' {} +

# 文档里的路径
find docs/ -name "*.md" -exec sed -i '' 's|agent/yonsuite_client/|agent/erp_clients/yonsuite/|g' {} +
```

- [ ] **Step 3: 验证无残留**

Run: `grep -rln "agent\.yonsuite_client\|agent/yonsuite_client" --include="*.py" --include="*.md" agent/ backend/ tests/ mcp_server/ docs/ 2>/dev/null | grep -v __pycache__ | grep -v "erp_clients/yonsuite"`
Expected: 无输出

- [ ] **Step 4: 跑测试确认 import 修复正确**

Run: `.venv/bin/python -m pytest tests/ -v 2>&1 | tail -10`
Expected: `41 passed`（没有 import 错）

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: update import paths to erp_clients/yonsuite"
```

---

## Task 8: 跑测试确认 Phase 1-2 后 41/41 仍过

**Files:** (验证)

- [ ] **Step 1: 跑全套测试**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: `41 passed`

- [ ] **Step 2: ruff check**

Run: `ruff check .`
Expected: `All checks passed!` 或无 error

- [ ] **Step 3: 跑项目自检**

Run: `.venv/bin/python -c "from agent.tools.registry import registry, discover_tools; discover_tools(); print('OK:', len(registry.get_all_tool_names()), 'tools')"`
Expected: `OK: 18 tools`（或当前 builtin 工具数）

- [ ] **Step 4: 跑 MCP 初始化烟测**

Run: `echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | .venv/bin/python -m mcp_server.ys_mcp_server 2>&1 | head -5`
Expected: JSON-RPC initialize 响应, 无异常

- [ ] **Step 5: 标记任务完成**

无代码改动, 仅验证。如果上面 4 步全过, 此 task 完成。

---

# Phase 3: 抽象层骨架（4 tasks）

## Task 9: 写 `agent/erp_clients/base.py`（TDD）

**Files:**
- Create: `agent/erp_clients/base.py`
- Create: `tests/test_erp_clients_base.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_erp_clients_base.py
"""测试 agent.erp_clients.base 模块的导入与导出"""
import pytest


def test_import_erp_error():
    from agent.erp_clients.base import ERPError
    assert issubclass(ERPError, Exception)


def test_import_auth_error():
    from agent.erp_clients.base import ERPAuthError, ERPError
    assert issubclass(ERPAuthError, ERPError)


def test_import_rate_limit_error_with_retry_after():
    from agent.erp_clients.base import ERPRateLimitError
    e = ERPRateLimitError("rate limited", retry_after=30)
    assert e.retry_after == 30
    assert "rate limited" in str(e)


def test_import_api_error_with_code():
    from agent.erp_clients.base import ERPAPIError
    e = ERPAPIError(code=401, message="Unauthorized", response={"trace": "x"})
    assert e.code == 401
    assert "401" in str(e)
    assert "Unauthorized" in str(e)


def test_import_mcp_starter_config():
    from agent.erp_clients.base import MCPStarterConfig
    cfg = MCPStarterConfig(
        erp_name="nc",
        enabled=True,
        command="nc-mcp-server",
        args=[],
        env={"ORACLE_HOST": "1.2.3.4"},
        builtin=False,
        install_hint="pip install nc-mcp-server",
    )
    assert cfg.erp_name == "nc"
    assert cfg.enabled is True
    assert cfg.env["ORACLE_HOST"] == "1.2.3.4"


def test_erp_client_protocol_runtime_checkable():
    """YonSuiteClient 结构子类型满足 ERPClient Protocol"""
    from agent.erp_clients.base import ERPClient
    # Protocol 是声明性, 不强制; 仅检查 Protocol 本身是 runtime_checkable
    assert hasattr(ERPClient, "_is_runtime_protocol")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_erp_clients_base.py -v`
Expected: `ModuleNotFoundError: No module named 'agent.erp_clients'`

- [ ] **Step 3: 实现 `agent/erp_clients/base.py`**

```python
"""
ERP 客户端抽象层（声明性 Protocol）

v1.5.0 角色:
- 定义所有 ERP 客户端应满足的最小接口 (Protocol)
- 定义跨 ERP 的通用异常类型
- 不强制任何 MCP server 继承, 也不强制 YonSuiteClient 实现
- 主要用于: 类型注解、isinstance 检查、文档生成
"""

from __future__ import annotations
from typing import Protocol, runtime_checkable, Any
from dataclasses import dataclass


# === 通用异常 ===

class ERPError(Exception):
    """所有 ERP 客户端错误的基类"""


class ERPAuthError(ERPError):
    """认证失败 (token 过期/无效)"""


class ERPRateLimitError(ERPError):
    """频率限制"""
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class ERPNetworkError(ERPError):
    """网络错误"""


class ERPAPIError(ERPError):
    """API 业务错误"""
    def __init__(self, code: int | str, message: str, response: dict | None = None):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.response = response or {}


# === 抽象协议 (声明性, 非强制) ===

@runtime_checkable
class ERPClient(Protocol):
    """
    所有 ERP 客户端的最小接口契约 (v1.5.0 声明性版本)

    注意: v1.5.0 实际不强制实现, 因为 NC 走 MCP 不走 Python 类
    保留此 Protocol 仅为:
    - YonSuiteClient 的 isinstance 检查 (结构子类型)
    - 未来可能新增的"嵌入式 ERP 客户端"扩展点
    """
    name: str

    def authenticate(self, force_refresh: bool = False) -> str | bool: ...
    def health_check(self) -> bool: ...


# === MCP 启动配置 schema ===

@dataclass(frozen=True)
class MCPStarterConfig:
    """
    把用户友好配置转换为 MCP server 启动参数

    用于 agent/mcp_server/nc_mcp/mcp_starter.py 等
    """
    erp_name: str
    enabled: bool
    command: str
    args: list[str]
    env: dict[str, str]
    builtin: bool
    install_hint: str | None = None
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_erp_clients_base.py -v`
Expected: 全部 6 个测试 PASS

- [ ] **Step 5: Commit**

```bash
git add agent/erp_clients/base.py tests/test_erp_clients_base.py
git commit -m "feat(erp-clients): add base module with Protocol + exceptions + MCPStarterConfig"
```

---

## Task 10: 写 `agent/erp_clients/__init__.py`（声明性注册中心）

**Files:**
- Create: `agent/erp_clients/__init__.py`
- Modify: `agent/erp_clients/yonsuite/__init__.py` (改 1 行)

- [ ] **Step 1: 写 `agent/erp_clients/__init__.py`**

```python
"""
ERP 客户端统一入口 (v1.5.0 声明性注册中心)

- 不再硬编码 ERP 客户端类
- 只导出通用异常 + Protocol + MCPStarterConfig
- 实际启动由 mcp_manager.py 负责
"""

from .base import (
    ERPClient,
    ERPError,
    ERPAuthError,
    ERPRateLimitError,
    ERPNetworkError,
    ERPAPIError,
    MCPStarterConfig,
)

# 触发 YonSuite 子包的导入 (YonSuiteClient 仍暴露为 Python 类入口)
from . import yonsuite  # noqa: F401

__all__ = [
    "ERPClient",
    "ERPError", "ERPAuthError", "ERPRateLimitError", "ERPNetworkError", "ERPAPIError",
    "MCPStarterConfig",
]
```

- [ ] **Step 2: 改 `agent/erp_clients/yonsuite/__init__.py`**

```python
# 路径已迁移: agent/yonsuite_client/ → agent/erp_clients/yonsuite/ (v1.5.0)
from .ys_client import YonSuiteClient  # noqa: F401
```

- [ ] **Step 3: 跑测试确认 YonSuiteClient 仍可导入**

Run: `.venv/bin/python -c "from agent.erp_clients.yonsuite import YonSuiteClient; from agent.erp_clients import ERPError, MCPStarterConfig; print('ok')"`
Expected: `ok`

- [ ] **Step 4: 跑 41 测试确认没破**

Run: `.venv/bin/python -m pytest tests/ -v 2>&1 | tail -5`
Expected: `41 passed`

- [ ] **Step 5: Commit**

```bash
git add agent/erp_clients/__init__.py agent/erp_clients/yonsuite/__init__.py
git commit -m "feat(erp-clients): add declarative registry + yonsuite re-export"
```

---

## Task 11: 写 `agent/skills/nc/SKILL.md`（NC 工具使用指南）

**Files:**
- Create: `agent/skills/nc/SKILL.md`

- [ ] **Step 1: 创建目录和 SKILL.md**

```bash
mkdir -p agent/skills/nc
```

```markdown
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
```

- [ ] **Step 2: 验证文件创建**

Run: `ls agent/skills/nc/`
Expected: `SKILL.md`

- [ ] **Step 3: Commit**

```bash
git add agent/skills/nc/SKILL.md
git commit -m "docs(skill): add NC skill usage guide"
```

---

# Phase 4: NC MCP 集成入口（5 tasks）

## Task 12: 写 `mcp_server/nc_mcp/__init__.py` + `config.py`（TDD）

**Files:**
- Create: `mcp_server/nc_mcp/__init__.py`
- Create: `mcp_server/nc_mcp/config.py`
- Create: `tests/test_nc_mcp_config.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_nc_mcp_config.py
"""测试 mcp_server.nc_mcp.config 的环境变量转换"""
import pytest


def test_build_nc_mcp_env_basic():
    from mcp_server.nc_mcp.config import build_nc_mcp_env
    env = build_nc_mcp_env({
        "host": "192.168.31.96",
        "port": "1521",
        "service": "orcl",
        "user": "NC65",
        "password": "secret123",
    })
    assert env["ORACLE_HOST"] == "192.168.31.96"
    assert env["ORACLE_PORT"] == "1521"
    assert env["ORACLE_SERVICE"] == "orcl"
    assert env["ORACLE_USER"] == "NC65"
    assert env["ORACLE_PASSWORD"] == "secret123"


def test_build_nc_mcp_env_with_max_rows():
    from mcp_server.nc_mcp.config import build_nc_mcp_env
    env = build_nc_mcp_env({
        "host": "h", "port": "1521", "service": "orcl",
        "user": "u", "password": "p", "max_rows": 500,
    })
    assert env["NC_MCP_MAX_ROWS"] == "500"


def test_build_nc_mcp_env_default_max_rows():
    from mcp_server.nc_mcp.config import build_nc_mcp_env
    env = build_nc_mcp_env({
        "host": "h", "port": "1521", "service": "orcl",
        "user": "u", "password": "p",
    })
    assert env["NC_MCP_MAX_ROWS"] == "200"


def test_build_nc_mcp_config():
    from mcp_server.nc_mcp.config import build_nc_mcp_config
    cfg = build_nc_mcp_config(
        erp_config={"host": "h", "port": "1521", "service": "orcl", "user": "u", "password": "p"},
        enabled=True,
    )
    assert cfg["transport"] == "stdio"
    assert cfg["command"] == "nc-mcp-server"
    assert cfg["args"] == []
    assert cfg["builtin"] is False
    assert cfg["enabled"] is True
    assert cfg["env"]["ORACLE_HOST"] == "h"
    assert "pip install" in cfg["install_hint"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_nc_mcp_config.py -v`
Expected: `ModuleNotFoundError: No module named 'mcp_server.nc_mcp'`

- [ ] **Step 3: 写 `mcp_server/nc_mcp/__init__.py`**

```python
"""
NC (用友 NC Cloud) MCP 集成入口 (v1.5.0)

实际 NC 业务由外部 nc-mcp-server 包提供, 本目录只做:
- config: 把用户友好配置 (erp_clients.nc) 转换为 ORACLE_* 环境变量
- mcp_starter: 调 mcp_manager 启停 nc-mcp-server 进程
"""
```

- [ ] **Step 4: 写 `mcp_server/nc_mcp/config.py`**

```python
"""
把 config.json 里的 erp_clients.nc 用户友好配置
转换为 nc-mcp-server 进程需要的 ORACLE_* 环境变量
"""

from __future__ import annotations
from typing import Any


def build_nc_mcp_env(erp_config: dict[str, Any]) -> dict[str, str]:
    """转换配置: erp_clients.nc.* → ORACLE_*"""
    return {
        "ORACLE_HOST": str(erp_config["host"]),
        "ORACLE_PORT": str(erp_config["port"]),
        "ORACLE_SERVICE": str(erp_config["service"]),
        "ORACLE_USER": str(erp_config["user"]),
        "ORACLE_PASSWORD": str(erp_config["password"]),
        "NC_MCP_MAX_ROWS": str(erp_config.get("max_rows", 200)),
    }


def build_nc_mcp_config(erp_config: dict[str, Any], enabled: bool) -> dict[str, Any]:
    """构造 mcp_manager 需要的 config dict"""
    return {
        "transport": "stdio",
        "command": "nc-mcp-server",
        "args": [],
        "env": build_nc_mcp_env(erp_config),
        "builtin": False,
        "enabled": enabled,
        "install_hint": "pip install zlink-agent[nc]",
    }
```

- [ ] **Step 5: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_nc_mcp_config.py -v`
Expected: 4 个测试 PASS

- [ ] **Step 6: Commit**

```bash
git add mcp_server/nc_mcp/__init__.py mcp_server/nc_mcp/config.py tests/test_nc_mcp_config.py
git commit -m "feat(nc-mcp): add config module (erp_clients.nc → ORACLE_* env conversion)"
```

---

## Task 13: 写 `mcp_server/nc_mcp/mcp_starter.py`（TDD）

**Files:**
- Create: `mcp_server/nc_mcp/mcp_starter.py`
- Create: `tests/test_nc_mcp_starter.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_nc_mcp_starter.py
"""测试 mcp_server.nc_mcp.mcp_starter 的启停逻辑"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_sync_nc_mcp_disabled_when_no_config():
    """erp_clients.nc 不存在时, sync_nc_mcp 应该是 no-op"""
    from mcp_server.nc_mcp.mcp_starter import sync_nc_mcp

    with patch("mcp_server.nc_mcp.mcp_starter.get_config") as mock_cfg, \
         patch("mcp_server.nc_mcp.mcp_starter.reconnect_server") as mock_reconnect, \
         patch("mcp_server.nc_mcp.mcp_starter.get_server_statuses", return_value=[]):
        mock_cfg.return_value = {}  # 没有 erp_clients
        await sync_nc_mcp()
        # 不应该调 reconnect_server
        mock_reconnect.assert_not_called()


@pytest.mark.asyncio
async def test_sync_nc_mcp_enabled_starts_server():
    """erp_clients.nc.enabled=True 且有 host 时, 应该启动 mcp-nc"""
    from mcp_server.nc_mcp.mcp_starter import sync_nc_mcp

    nc_config = {
        "host": "1.2.3.4", "port": "1521", "service": "orcl",
        "user": "u", "password": "p",
    }
    with patch("mcp_server.nc_mcp.mcp_starter.get_config") as mock_cfg, \
         patch("mcp_server.nc_mcp.mcp_starter.reconnect_server") as mock_reconnect, \
         patch("mcp_server.nc_mcp.mcp_starter.get_server_statuses", return_value=[]):
        mock_cfg.return_value = {"erp_clients": {"nc": nc_config}}
        await sync_nc_mcp()
        # 应该调 reconnect_server with "mcp-nc" 和 enabled=True
        mock_reconnect.assert_called_once()
        args, kwargs = mock_reconnect.call_args
        assert args[0] == "mcp-nc"
        target_config = args[1]
        assert target_config["enabled"] is True
        assert target_config["env"]["ORACLE_HOST"] == "1.2.3.4"


@pytest.mark.asyncio
async def test_sync_nc_mcp_disabled_stops_server():
    """erp_clients.nc.enabled=False 时, 应该停止 mcp-nc"""
    from mcp_server.nc_mcp.mcp_starter import sync_nc_mcp

    nc_config = {
        "host": "1.2.3.4", "enabled": False,
        "port": "1521", "service": "orcl", "user": "u", "password": "p",
    }
    with patch("mcp_server.nc_mcp.mcp_starter.get_config") as mock_cfg, \
         patch("mcp_server.nc_mcp.mcp_starter.reconnect_server") as mock_reconnect, \
         patch("mcp_server.nc_mcp.mcp_starter.get_server_statuses", return_value=[{"name": "mcp-nc", "status": "connected"}]):
        mock_cfg.return_value = {"erp_clients": {"nc": nc_config}}
        await sync_nc_mcp()
        mock_reconnect.assert_called_once()
        args, kwargs = mock_reconnect.call_args
        target_config = args[1]
        assert target_config["enabled"] is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_nc_mcp_starter.py -v`
Expected: `ModuleNotFoundError: No module named 'mcp_server.nc_mcp.mcp_starter'`

- [ ] **Step 3: 写 `mcp_server/nc_mcp/mcp_starter.py`**

```python
"""
按 config.json 里的 erp_clients.nc 状态决定 mcp-nc 是否启动
"""

from __future__ import annotations
import logging

from mcp_server.nc_mcp.config import build_nc_mcp_config

logger = logging.getLogger(__name__)

NC_MCP_NAME = "mcp-nc"


async def sync_nc_mcp() -> None:
    """
    每次配置变更后调用, 确保 mcp-nc 状态与 erp_clients.nc.enabled 一致

    行为:
    - enabled=True: 启动 nc-mcp-server, 工具自动注册到 LLM
    - enabled=False: 停止 nc-mcp-server, 工具从 LLM 视野消失
    - 配置不存在: no-op
    """
    # 延迟导入避免循环依赖
    from agent.config_manager import get_config
    from agent.tools.mcp_manager import get_server_statuses, reconnect_server

    config = get_config()
    nc_cfg = config.get("erp_clients", {}).get("nc")

    if nc_cfg is None:
        logger.debug("erp_clients.nc 不存在, 跳过 sync_nc_mcp")
        return

    enabled = bool(nc_cfg.get("enabled", False))
    target = build_nc_mcp_config(nc_cfg, enabled=enabled)

    statuses = {s["name"]: s for s in get_server_statuses()}
    current = statuses.get(NC_MCP_NAME, {})
    current_status = current.get("status", "disconnected")

    if enabled and current_status != "connected":
        logger.info("启动 mcp-nc (host=%s)", nc_cfg.get("host"))
        await reconnect_server(NC_MCP_NAME, target)
    elif not enabled and current_status == "connected":
        logger.info("停止 mcp-nc")
        await reconnect_server(NC_MCP_NAME, {**target, "enabled": False})
    else:
        logger.debug("mcp-nc 状态已同步 (enabled=%s, current=%s)", enabled, current_status)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_nc_mcp_starter.py -v`
Expected: 3 个测试 PASS

- [ ] **Step 5: Commit**

```bash
git add mcp_server/nc_mcp/mcp_starter.py tests/test_nc_mcp_starter.py
git commit -m "feat(nc-mcp): add mcp_starter for sync_nc_mcp lifecycle management"
```

---

## Task 14: 修 `agent/config_manager.py` 加 `get_erp_config()` + 占位符解析

**Files:**
- Modify: `agent/config_manager.py` (新增 2 个函数)
- Create: `tests/test_config_manager_erp.py`

- [ ] **Step 1: 看现有 config_manager 结构**

Run: `grep -n "^def \|^class " agent/config_manager.py | head -20`

- [ ] **Step 2: 写失败测试**

```python
# tests/test_config_manager_erp.py
"""测试 config_manager 的 erp_clients 支持"""
import pytest


def test_get_erp_config_existing(tmp_path):
    from agent.config_manager import ConfigManager
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text('{"erp_clients": {"nc": {"host": "1.2.3.4", "user": "u"}}}')
    mgr = ConfigManager(config_path=cfg_file)
    cfg = mgr.get_erp_config("nc")
    assert cfg["host"] == "1.2.3.4"
    assert cfg["user"] == "u"


def test_get_erp_config_missing_returns_empty(tmp_path):
    from agent.config_manager import ConfigManager
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text("{}")
    mgr = ConfigManager(config_path=cfg_file)
    cfg = mgr.get_erp_config("nonexistent")
    assert cfg == {}


def test_resolve_placeholders_simple():
    from agent.config_manager import resolve_placeholders
    env = {"ORACLE_HOST": "${nc.host}", "STATIC": "value"}
    config = {"erp_clients": {"nc": {"host": "1.2.3.4"}}}
    result = resolve_placeholders(env, config)
    assert result["ORACLE_HOST"] == "1.2.3.4"
    assert result["STATIC"] == "value"


def test_resolve_placeholders_nested():
    from agent.config_manager import resolve_placeholders
    env = {"ORACLE_USER": "${nc.user}", "ORACLE_PASSWORD": "${nc.password}"}
    config = {"erp_clients": {"nc": {"user": "NC65", "password": "secret"}}}
    result = resolve_placeholders(env, config)
    assert result["ORACLE_USER"] == "NC65"
    assert result["ORACLE_PASSWORD"] == "secret"


def test_resolve_placeholders_missing_keeps_literal():
    """占位符引用不存在路径时, 保留字面量 (启动时由 mcp_manager 报错)"""
    from agent.config_manager import resolve_placeholders
    env = {"X": "${nc.missing}"}
    config = {"erp_clients": {"nc": {}}}
    result = resolve_placeholders(env, config)
    # 占位符无法解析时保留原样, 让启动时报错定位更明确
    assert result["X"] == "${nc.missing}"
```

- [ ] **Step 3: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_config_manager_erp.py -v`
Expected: 失败 (get_erp_config / resolve_placeholders 不存在)

- [ ] **Step 4: 在 config_manager.py 末尾加 2 个函数**

```python
# 加到 agent/config_manager.py 末尾


def get_erp_config(self, name: str) -> dict:
    """
    获取指定 ERP 客户端的配置

    优先级:
    1. erp_clients[name]
    2. yonsuite 字段 (仅 name="yonsuite", 向后兼容)
    3. 返回空 dict
    """
    config = self.load()
    erp_clients = config.get("erp_clients", {})
    if name in erp_clients:
        return erp_clients[name]
    # 向后兼容: 旧版 yonsuite 字段
    if name == "yonsuite" and "yonsuite" in config:
        return config["yonsuite"]
    return {}


def resolve_placeholders(env: dict, config: dict) -> dict:
    """
    解析 env 字典里的 ${path.to.value} 占位符

    例子:
        env = {"ORACLE_HOST": "${nc.host}"}
        config = {"erp_clients": {"nc": {"host": "1.2.3.4"}}}
        → {"ORACLE_HOST": "1.2.3.4"}

    占位符引用不存在路径时, 保留字面量 (启动时报错定位更明确)
    """
    import re
    pattern = re.compile(r"\$\{([^}]+)\}")

    def resolve_value(value: str) -> str:
        def replacer(match):
            path = match.group(1)
            parts = path.split(".")
            current = config
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return match.group(0)  # 保留原样
            return str(current)
        return pattern.sub(replacer, value)

    return {k: resolve_value(v) if isinstance(v, str) else v for k, v in env.items()}
```

- [ ] **Step 5: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_config_manager_erp.py -v`
Expected: 5 个测试 PASS

- [ ] **Step 6: 跑全部测试确认 41 + 5 = 46 PASS**

Run: `.venv/bin/python -m pytest tests/ -v 2>&1 | tail -3`
Expected: `46 passed`

- [ ] **Step 7: Commit**

```bash
git add agent/config_manager.py tests/test_config_manager_erp.py
git commit -m "feat(config): add get_erp_config() + resolve_placeholders()"
```

---

## Task 15: 修 `mcp_manager.py` 加占位符解析调用

**Files:**
- Modify: `agent/tools/mcp_manager.py` (在 MCP server 启动前 resolve env)

- [ ] **Step 1: 找到 MCP server 启动的代码位置**

Run: `grep -n "env\|def connect\|stdio" agent/tools/mcp_manager.py | head -20`

- [ ] **Step 2: 在 `MCPServerConnection.__init__` 后加占位符解析**

找到 `self.env = config.get("env", {})` 之类代码，加一行：
```python
        # v1.5.0: 解析 ${path.to.value} 占位符 (依赖 get_config)
        try:
            from agent.config_manager import get_config, resolve_placeholders
            full_config = get_config()
            self.env = resolve_placeholders(self.env, full_config)
        except Exception:
            # config 不可用时保持原样, 启动时报错
            pass
```

- [ ] **Step 3: 跑测试确认没破**

Run: `.venv/bin/python -m pytest tests/ -v 2>&1 | tail -3`
Expected: `46 passed`

- [ ] **Step 4: ruff check**

Run: `ruff check agent/tools/mcp_manager.py`
Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add agent/tools/mcp_manager.py
git commit -m "feat(mcp-manager): resolve env placeholders before starting MCP server"
```

---

# Phase 5: 数据目录 + API 层（4 tasks）

## Task 16: 改 `agent/utils.py` 加数据目录双兼容

**Files:**
- Modify: `agent/utils.py` (改 `_resolve_data_dir()` 或等价函数)

- [ ] **Step 1: 找到现有数据目录解析代码**

Run: `grep -n "data.*dir\|\\.ys-agent\|\\.zlink-agent" agent/utils.py | head -10`

- [ ] **Step 2: 改数据目录解析逻辑**

找到 `_resolve_data_dir()` 函数，按 spec 第 5.4 节优先级重写：
```python
def _resolve_data_dir() -> Path:
    """
    解析运行时数据目录 (v1.5.0 双兼容)

    优先级:
    1. ZLINK_DATA_DIR 或 YS_DATA_DIR 环境变量
    2. ~/.zlink-agent/data/ (新默认)
    3. ~/.ys-agent/data/ (兼容 v1.4.x)
    4. ~/.zlink-agent/data/ (新建)
    """
    env = os.environ.get("ZLINK_DATA_DIR") or os.environ.get("YS_DATA_DIR")
    if env:
        return Path(env)
    new = Path.home() / ".zlink-agent" / "data"
    if new.exists():
        return new
    old = Path.home() / ".ys-agent" / "data"
    if old.exists():
        return old
    return new
```

- [ ] **Step 3: 写测试验证**

在 `tests/test_utils_data_dir.py` 写测试（如果还没有），覆盖：
- `ZLINK_DATA_DIR` 环境变量优先
- `~/.zlink-agent/data/` 存在时优先
- `~/.ys-agent/data/` 存在时 fallback
- 都不存在时返回 `~/.zlink-agent/data/`

- [ ] **Step 4: 跑测试**

Run: `.venv/bin/python -m pytest tests/test_utils_data_dir.py -v`
Expected: 4 个测试 PASS

- [ ] **Step 5: Commit**

```bash
git add agent/utils.py tests/test_utils_data_dir.py
git commit -m "feat(utils): dual-compat data dir (zlink-agent/ys-agent)"
```

---

## Task 17: 写 `backend/api/erp_clients_api.py`（REST 端点）

**Files:**
- Create: `backend/api/erp_clients_api.py`
- Create: `tests/test_erp_clients_api.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_erp_clients_api.py
"""测试 /api/config/erp-clients 端点"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    # 临时建 config.json 走 ConfigManager
    from backend.main import app
    return TestClient(app)


def test_get_erp_clients_returns_both(client):
    r = client.get("/api/config/erp-clients")
    assert r.status_code == 200
    data = r.json()
    assert "yonsuite" in data
    assert "nc" in data


def test_get_erp_client_yonsuite_secrets_masked(client):
    r = client.get("/api/config/erp-clients/yonsuite")
    assert r.status_code == 200
    data = r.json()
    # secret 字段应被脱敏
    if "app_secret" in data:
        assert data["app_secret"].startswith("encrypted:") or "***" in data["app_secret"]


def test_put_erp_client_nc_encrypts_password(client):
    r = client.put("/api/config/erp-clients/nc", json={
        "host": "1.2.3.4", "port": "1521", "service": "orcl",
        "user": "u", "password": "plain-password",
    })
    assert r.status_code == 200
    # 读落盘 config.json, 验证 password 已加密
    from agent.utils import get_config_path
    import json
    cfg = json.loads(get_config_path().read_text())
    assert cfg["erp_clients"]["nc"]["password"].startswith("encrypted:")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_erp_clients_api.py -v`
Expected: `404 Not Found` (端点未注册)

- [ ] **Step 3: 写 `backend/api/erp_clients_api.py`**

```python
"""
ERP 客户端配置 REST API (v1.5.0)

端点:
- GET    /api/config/erp-clients              列出所有
- GET    /api/config/erp-clients/{name}       获取单个
- PUT    /api/config/erp-clients/{name}       更新单个 (自动加密 secret)
- POST   /api/config/erp-clients/{name}/test  测试连接
- GET    /api/config/mcp-servers              列出所有 MCP server 状态
- POST   /api/config/mcp-servers/{name}/toggle 启用/禁用
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.config_manager import get_config, save_config, encrypt_field

logger = logging.getLogger(__name__)
router = APIRouter()

# secret 字段在 PUT 时自动加密
SECRET_FIELDS = {
    "yonsuite": ["app_key", "app_secret"],
    "nc": ["password"],
}


class ERPPutRequest(BaseModel):
    """ERP 配置 PUT body (v1.5.0)"""
    enabled: bool | None = None
    # yonsuite 字段
    tenant_id: str | None = None
    app_key: str | None = None
    app_secret: str | None = None
    base_url: str | None = None
    # nc 字段
    host: str | None = None
    port: str | None = None
    service: str | None = None
    user: str | None = None
    password: str | None = None
    max_rows: int | None = None


@router.get("/api/config/erp-clients")
async def list_erp_clients() -> dict:
    config = get_config()
    erp_clients = config.get("erp_clients", {})
    # 脱敏: secret 字段 mask
    masked = {}
    for name, cfg in erp_clients.items():
        masked[name] = _mask_secrets(name, cfg)
    return masked


@router.get("/api/config/erp-clients/{name}")
async def get_erp_client(name: str) -> dict:
    config = get_config()
    erp_clients = config.get("erp_clients", {})
    if name not in erp_clients:
        raise HTTPException(404, f"ERP client {name!r} not found")
    return _mask_secrets(name, erp_clients[name])


@router.put("/api/config/erp-clients/{name}")
async def put_erp_client(name: str, body: ERPPutRequest) -> dict:
    config = get_config()
    erp_clients = config.setdefault("erp_clients", {})
    if name not in erp_clients:
        erp_clients[name] = {}
    cfg = erp_clients[name]

    # 应用非空字段
    updates = body.model_dump(exclude_none=True)
    secret_fields = SECRET_FIELDS.get(name, [])
    for k, v in updates.items():
        if k in secret_fields and v and not v.startswith("encrypted:"):
            cfg[k] = encrypt_field(v)
        else:
            cfg[k] = v

    save_config(config)

    # 触发 NC MCP 同步 (如果改了 nc)
    if name == "nc":
        try:
            from mcp_server.nc_mcp.mcp_starter import sync_nc_mcp
            await sync_nc_mcp()
        except Exception as e:
            logger.warning("sync_nc_mcp 失败: %s", e)

    return _mask_secrets(name, cfg)


@router.post("/api/config/erp-clients/{name}/test")
async def test_erp_client(name: str) -> dict:
    """测试连接"""
    if name == "yonsuite":
        # 调 YonSuiteClient.health_check
        try:
            from agent.erp_clients.yonsuite import YonSuiteClient
            from agent.config_manager import get_erp_config
            cfg = get_erp_config("yonsuite")
            client = YonSuiteClient(cfg)
            ok = client.health_check()
            return {"ok": ok}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    elif name == "nc":
        # 检查 mcp-nc 进程是否 connected
        try:
            from agent.tools.mcp_manager import get_server_statuses
            statuses = {s["name"]: s for s in get_server_statuses()}
            nc_status = statuses.get("mcp-nc", {}).get("status", "disconnected")
            if nc_status == "connected":
                return {"ok": True}
            return {"ok": False, "error": f"mcp-nc 状态: {nc_status}, 确认已装 nc-mcp-server 包"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    raise HTTPException(404, f"Unknown ERP {name!r}")


@router.get("/api/config/mcp-servers")
async def list_mcp_servers() -> list:
    from agent.tools.mcp_manager import get_server_statuses
    return get_server_statuses()


@router.post("/api/config/mcp-servers/{name}/toggle")
async def toggle_mcp_server(name: str) -> dict:
    """启用/禁用某个 MCP server"""
    from agent.tools.mcp_manager import reconnect_server, get_server_statuses
    statuses = {s["name"]: s for s in get_server_statuses()}
    if name not in statuses:
        raise HTTPException(404, f"MCP server {name!r} not found")
    current = statuses[name]
    new_enabled = current.get("status") != "connected"
    # 调 reconnect_server 切状态
    cfg = current.get("config", {})
    cfg["enabled"] = new_enabled
    await reconnect_server(name, cfg)
    return {"name": name, "enabled": new_enabled}


def _mask_secrets(name: str, cfg: dict) -> dict:
    """脱敏 secret 字段"""
    masked = dict(cfg)
    for f in SECRET_FIELDS.get(name, []):
        if f in masked and isinstance(masked[f], str) and not masked[f].startswith("encrypted:"):
            masked[f] = "***"
    return masked
```

- [ ] **Step 4: 在 `backend/api/config_api.py` 挂载新 router**

```python
# 加到 config_api.py 末尾
from backend.api.erp_clients_api import router as erp_clients_router
app.include_router(erp_clients_router)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_erp_clients_api.py -v`
Expected: 3 个测试 PASS

- [ ] **Step 6: 跑全套测试**

Run: `.venv/bin/python -m pytest tests/ -v 2>&1 | tail -3`
Expected: `46 + 3 = 49 passed`

- [ ] **Step 7: ruff check**

Run: `ruff check backend/api/erp_clients_api.py backend/api/config_api.py`
Expected: 0 errors

- [ ] **Step 8: Commit**

```bash
git add backend/api/erp_clients_api.py backend/api/config_api.py tests/test_erp_clients_api.py
git commit -m "feat(api): add /api/config/erp-clients/* + mcp-servers/toggle endpoints"
```

---

# Phase 6: 前端（3 tasks）

## Task 18: 写 `web/src/pages/SettingsERPPage.tsx`

**Files:**
- Create: `web/src/pages/SettingsERPPage.tsx`

- [ ] **Step 1: 看现有 SettingsLLMPage 的样式约定**

Run: `head -50 web/src/pages/SettingsLLMPage.tsx`

- [ ] **Step 2: 写 SettingsERPPage 骨架**

```tsx
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface ERPYonSuite {
  enabled: boolean;
  tenant_id?: string;
  app_key?: string;
  app_secret?: string;
  base_url?: string;
}

interface ERPNC {
  enabled: boolean;
  host?: string;
  port?: string;
  service?: string;
  user?: string;
  password?: string;
  max_rows?: number;
}

const API_BASE = '/api/config';

export default function SettingsERPPage() {
  const navigate = useNavigate();
  const [yonsuite, setYonSuite] = useState<ERPYonSuite | null>(null);
  const [nc, setNC] = useState<ERPNC | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/erp-clients/yonsuite`).then(r => r.ok ? r.json() : null),
      fetch(`${API_BASE}/erp-clients/nc`).then(r => r.ok ? r.json() : null),
    ]).then(([ys, n]) => {
      setYonSuite(ys);
      setNC(n);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="page">加载中...</div>;

  return (
    <div className="page">
      <h1>ERP 客户端</h1>
      <p className="hint">
        ZLink Agent 支持连接多个 ERP 系统。当前已注册: YonSuite (内置)、NC (需安装 nc-mcp-server)。
        启用后 AI 自动从对应系统取数。
      </p>

      <YonSuiteCard data={yonsuite} onChange={setYonSuite} />
      <NCCard data={nc} onChange={setNC} />
    </div>
  );
}

function YonSuiteCard({ data, onChange }: any) {
  if (!data) return null;
  return (
    <div className="card-erppage">
      <h2>YonSuite (内置)</h2>
      <label>
        <input
          type="checkbox"
          checked={data.enabled ?? false}
          onChange={e => onChange({ ...data, enabled: e.target.checked })}
        />
        启用
      </label>
      <input
        placeholder="Tenant ID"
        value={data.tenant_id ?? ''}
        onChange={e => onChange({ ...data, tenant_id: e.target.value })}
      />
      <input
        type="password"
        placeholder="App Key"
        value={data.app_key ?? ''}
        onChange={e => onChange({ ...data, app_key: e.target.value })}
      />
      <input
        type="password"
        placeholder="App Secret"
        value={data.app_secret ?? ''}
        onChange={e => onChange({ ...data, app_secret: e.target.value })}
      />
      <input
        placeholder="Base URL"
        value={data.base_url ?? ''}
        onChange={e => onChange({ ...data, base_url: e.target.value })}
      />
      <button onClick={() => save('yonsuite', data)}>保存</button>
      <button onClick={() => testConn('yonsuite')}>测试连接</button>
    </div>
  );
}

function NCCard({ data, onChange }: any) {
  if (!data) return null;
  return (
    <div className="card-erppage">
      <h2>NC (需安装 nc-mcp-server)</h2>
      <label>
        <input
          type="checkbox"
          checked={data.enabled ?? false}
          onChange={e => onChange({ ...data, enabled: e.target.checked })}
        />
        启用
      </label>
      <input
        placeholder="ORACLE_HOST"
        value={data.host ?? ''}
        onChange={e => onChange({ ...data, host: e.target.value })}
      />
      <input
        placeholder="ORACLE_PORT (默认 1521)"
        value={data.port ?? ''}
        onChange={e => onChange({ ...data, port: e.target.value })}
      />
      <input
        placeholder="ORACLE_SERVICE (默认 orcl)"
        value={data.service ?? ''}
        onChange={e => onChange({ ...data, service: e.target.value })}
      />
      <input
        placeholder="ORACLE_USER"
        value={data.user ?? ''}
        onChange={e => onChange({ ...data, user: e.target.value })}
      />
      <input
        type="password"
        placeholder="ORACLE_PASSWORD"
        value={data.password ?? ''}
        onChange={e => onChange({ ...data, password: e.target.value })}
      />
      <input
        type="number"
        placeholder="NC_MCP_MAX_ROWS (默认 200)"
        value={data.max_rows ?? 200}
        onChange={e => onChange({ ...data, max_rows: Number(e.target.value) })}
      />
      <button onClick={() => save('nc', data)}>保存</button>
      <button onClick={() => testConn('nc')}>测试连接</button>
    </div>
  );
}

async function save(name: string, data: any) {
  await fetch(`${API_BASE}/erp-clients/${name}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  alert(`${name} 配置已保存`);
}

async function testConn(name: string) {
  const r = await fetch(`${API_BASE}/erp-clients/${name}/test`, { method: 'POST' });
  const data = await r.json();
  alert(data.ok ? `${name} 连接成功` : `${name} 连接失败: ${data.error ?? '未知'}`);
}
```

- [ ] **Step 3: 验证 TypeScript 编译**

Run: `cd web && npx tsc --noEmit 2>&1 | head -20`
Expected: 0 errors 或只剩 import 警告

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/SettingsERPPage.tsx
git commit -m "feat(web): add /settings/erp page with YonSuite + NC cards"
```

---

## Task 19: 改 `web/src/App.tsx` 加路由

**Files:**
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 加 import + 路由**

```tsx
// 在 App.tsx 顶部加
import SettingsERPPage from './pages/SettingsERPPage';

// 在路由表加
<Route path="/settings/erp" element={<SettingsERPPage />} />
```

- [ ] **Step 2: 验证 TypeScript**

Run: `cd web && npx tsc --noEmit 2>&1 | head -10`
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
git add web/src/App.tsx
git commit -m "feat(web): add /settings/erp route"
```

---

## Task 20: 改前端侧栏导航加入口

**Files:**
- Modify: 侧栏导航组件 (具体文件看 `web/src/components/Sidebar.tsx` 或 `App.tsx`)

- [ ] **Step 1: 找侧栏组件**

Run: `grep -rln "settings/llm\|SettingsLLM" web/src/ | head -5`

- [ ] **Step 2: 加 ERP 入口**

在 settings 菜单组里加：
```tsx
<NavLink to="/settings/erp">ERP 客户端</NavLink>
```

- [ ] **Step 3: 验证**

Run: `cd web && npx tsc --noEmit 2>&1 | head -5`
Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add -A web/src/
git commit -m "feat(web): add ERP nav link in settings sidebar"
```

---

# Phase 7: 脚本 + 文档（4 tasks）

## Task 21: 写 `scripts/zlink.sh` + 改 `scripts/ys-agent.sh`

**Files:**
- Create: `scripts/zlink.sh` (复制 ys-agent.sh 内容)
- Modify: `scripts/ys-agent.sh` (改为软链 shim)

- [ ] **Step 1: 复制 ys-agent.sh 为 zlink.sh**

```bash
cp scripts/ys-agent.sh scripts/zlink.sh
chmod +x scripts/zlink.sh
```

- [ ] **Step 2: 改 zlink.sh 里的引用**

```bash
# 把脚本里所有 "ys-agent" 引用改为 "zlink"
sed -i '' 's/ys-agent/zlink/g' scripts/zlink.sh
```

- [ ] **Step 3: 改 ys-agent.sh 为 shim**

```bash
# ys-agent.sh 改为软链接到 zlink.sh
cat > scripts/ys-agent.sh << 'EOF'
#!/usr/bin/env bash
# 兼容 shim: v1.5.0 起 zlink 是主命令, ys-agent 自动转发
exec "$(dirname "$0")/zlink.sh" "$@"
EOF
chmod +x scripts/ys-agent.sh
```

- [ ] **Step 4: 验证两个脚本都可用**

Run: `bash scripts/zlink.sh help 2>&1 | head -3`
Expected: 帮助信息

Run: `bash scripts/ys-agent.sh help 2>&1 | head -3`
Expected: 同样的帮助信息 (shim 转发)

- [ ] **Step 5: Commit**

```bash
git add scripts/zlink.sh scripts/ys-agent.sh
git commit -m "feat(scripts): add zlink.sh as main CLI, ys-agent.sh as compat shim"
```

---

## Task 22: 改 `docs/architecture.md` 加多 ERP 章节

**Files:**
- Modify: `docs/architecture.md`

- [ ] **Step 1: 在文档末尾加章节**

```markdown

## 多 ERP 抽象层 (v1.5.0+)

### 架构原则

ZLink Agent 是 ERP 客户端的**调度者**，不是**实现者**。
所有 ERP 客户端都通过 MCP 协议接入，ZLink 只做：
1. 启动/停止 MCP 服务器
2. 把用户配置（数据库连接、API 凭据）注入到 MCP 服务器的环境变量
3. 转发 LLM 的工具调用到对应 MCP 服务器
4. 把工具结果返回给 LLM

### 三层结构

```
LLM Core (agent.py + mcp_manager.py)
  │
  ├─ mcp-yonsuite (builtin, stdio)
  │   └─ YonSuite Cloud API
  │
  ├─ mcp-nc (opt-in, stdio)
  │   └─ nc-mcp-server (外部 pip 包) → Oracle DB
  │
  └─ mcp-xxx (未来, 任意新 ERP)
      └─ xxx-mcp-server (外部包)
```

### 用户启用哪个 = AI 从哪取数

```json
"erp_clients": {
  "yonsuite": {"enabled": true},
  "nc":       {"enabled": false}
}
```

- `enabled=true` → MCP server 启动 → 工具进 LLM 视野
- `enabled=false` → MCP server 停止 → LLM 不知道该 ERP 存在

### 新增 ERP 接入流程

1. 等 XX-mcp-server 出来（或自己实现 stdio MCP server）
2. `pip install xx-mcp-server`
3. `config.json` 加 `mcp_servers["mcp-xx"]` 配置节
4. `config.json` 加 `erp_clients.xx` 用户配置节
5. 前端 `/settings/erp` 加一张卡片
6. 完成。不改 ZLink 核心代码。
```

- [ ] **Step 2: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: add multi-ERP architecture section"
```

---

## Task 23: 改 `docs/extending-ys-agent.md` → `extending-zlink-agent.md`

**Files:**
- Move: `docs/extending-ys-agent.md` → `docs/extending-zlink-agent.md`
- Modify: 内容 (改 ys-agent → zlink-agent)

- [ ] **Step 1: 改名**

```bash
git mv docs/extending-ys-agent.md docs/extending-zlink-agent.md
```

- [ ] **Step 2: 替换内容**

```bash
sed -i '' 's/ys-agent/zlink-agent/g; s/YS-Agent/ZLink Agent/g' docs/extending-zlink-agent.md
```

- [ ] **Step 3: 验证**

Run: `grep -c "ys-agent\|YS-Agent" docs/extending-zlink-agent.md`
Expected: `0`

- [ ] **Step 4: Commit**

```bash
git add docs/extending-zlink-agent.md
git commit -m "docs: rename extending-ys-agent.md → extending-zlink-agent.md"
```

---

## Task 24: 批量替换剩余 200 处 `ys-agent` 字符串

**Files:**
- Modify: 各种 (200 处散落)

- [ ] **Step 1: 找出剩余引用**

```bash
grep -rln "ys-agent\|YS-Agent" --exclude-dir=node_modules --exclude-dir=__pycache__ --exclude-dir=.venv --exclude-dir=dist --exclude-dir=.git . 2>/dev/null | head -20
```

- [ ] **Step 2: 批量替换**

```bash
# Python / shell / toml / json
find . -type f \( -name "*.py" -o -name "*.sh" -o -name "*.toml" -o -name "*.json" -o -name "*.bat" -o -name "*.md" -o -name "*.ts" -o -name "*.tsx" -o -name "*.yaml" -o -name "*.yml" \) \
  -not -path "./node_modules/*" \
  -not -path "./.venv/*" \
  -not -path "./__pycache__/*" \
  -not -path "./dist/*" \
  -not -path "./.git/*" \
  -not -path "./releases/*" \
  -not -path "*/erp_clients/yonsuite/*" \
  -not -path "*/yonsuite-logo*" \
  -not -path "*/yonsuite-official*" \
  -exec sed -i '' 's/ys-agent/zlink-agent/g; s/YS-Agent/ZLink Agent/g' {} +
```

- [ ] **Step 3: 验证无残留**

```bash
grep -rln "ys-agent\|YS-Agent" --exclude-dir=node_modules --exclude-dir=__pycache__ --exclude-dir=.venv --exclude-dir=dist --exclude-dir=.git . 2>/dev/null
```

Expected: 只剩 logo / html-presentation assets / 历史 release notes 这类**故意保留**的文件

- [ ] **Step 4: 跑全套测试确认没破**

Run: `.venv/bin/python -m pytest tests/ -v 2>&1 | tail -3`
Expected: `49 passed` (Phase 1-6 累积)

- [ ] **Step 5: ruff check**

Run: `ruff check .`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: replace remaining ys-agent references with zlink-agent"
```

---

# Phase 8: 最终测试 + 发布（4 tasks）

## Task 25: 跑全套验证

**Files:** (无代码改动)

- [ ] **Step 1: pytest 全套**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: `49 passed`

- [ ] **Step 2: ruff check**

Run: `ruff check . && ruff format --check .`
Expected: 0 errors

- [ ] **Step 3: 项目自检**

Run: `.venv/bin/python -c "from agent.erp_clients import ERPError, MCPStarterConfig, ERPClient; print('imports ok')"`
Expected: `imports ok`

- [ ] **Step 4: MCP 烟测**

Run: `echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | .venv/bin/python -m mcp_server.ys_mcp_server 2>&1 | head -3`
Expected: JSON-RPC initialize 响应

- [ ] **Step 5: 前端 TypeScript 编译**

Run: `cd web && npx tsc --noEmit 2>&1 | head -5`
Expected: 0 errors

- [ ] **Step 6: 数据目录双兼容**

Run: `mkdir -p /tmp/test-ys-old && YS_DATA_DIR=/tmp/test-ys-old .venv/bin/python -c "from agent.utils import _resolve_data_dir; print(_resolve_data_dir())"`
Expected: `/tmp/test-ys-old`

---

## Task 26: 新增 5 个测试补齐 56/56（已部分覆盖，按 spec 补齐）

**Files:**
- Create: `tests/test_erp_clients_integration.py` (如未覆盖)

- [ ] **Step 1: 检查现有测试覆盖**

Run: `.venv/bin/python -m pytest tests/ --collect-only -q 2>&1 | grep -c "test_"`
Expected: 49 个 (Phase 1-6 累计)

- [ ] **Step 2: 补 7 个缺失测试直到 56**

按 spec 第 9.2 节 10 个测试核对, 缺哪个补哪个。优先补：
- `test_erp_base_exports` (Task 9 已覆盖)
- `test_erp_client_protocol_yonsuite` (Task 9 已覆盖)
- `test_data_dir_fallback_to_old` (Task 16 应已覆盖)
- `test_erp_clients_api_get` (Task 17 已覆盖)
- `test_erp_clients_api_put_encrypts_secrets` (Task 17 已覆盖)
- `test_nc_mcp_config_translation` (Task 12 已覆盖)
- `test_nc_mcp_starter_disabled_by_default` (Task 13 已覆盖)
- `test_nc_mcp_placeholder_substitution` (Task 14 已覆盖)
- `test_mcp_manager_lists_nc_when_enabled` (补)
- `test_nc_mcp_graceful_when_not_installed` (补)

- [ ] **Step 3: 跑全套测试**

Run: `.venv/bin/python -m pytest tests/ -v 2>&1 | tail -3`
Expected: `56 passed`

- [ ] **Step 4: Commit**

```bash
git add -A tests/
git commit -m "test: add 7 more erp_clients tests to reach 56/56"
```

---

## Task 27: 写发布 PR 描述

**Files:**
- Create: `docs/releases/v1.5.0.md` (或直接在 GitHub PR 里写)

- [ ] **Step 1: 写发布说明**

```markdown
# ZLink Agent v1.5.0 发布说明

## 主要变化

- **重命名**: YS-Agent → **ZLink Agent（智链 Agent）**
- **多 ERP 架构**: 引入声明性 ERPClient 协议
- **NC 集成**: 通过 [nc-mcp-server](https://atomgit.com/gcw_cJbJuamU/nc-mcp-project) 外部包支持 NC（用友 NC Cloud）
- **数据目录**: 新默认 `~/.zlink-agent/data/`，旧 `~/.ys-agent/data/` 自动兼容

## 升级指引

老用户（v1.4.x）：
```bash
# 1. 拉最新代码
git pull
# 2. 用新 CLI (旧 ys-agent 仍可用, 是软链接 shim)
./scripts/zlink.sh start
# 3. 数据不需要迁移; 想用新名:
mv ~/.ys-agent/data ~/.zlink-agent/data
```

新用户：
```bash
git clone https://atomgit.com/gcw_cJbJuamU/zlink-agent.git
cd zlink-agent
./setup.sh
```

## 启用 NC

```bash
pip install "zlink-agent[nc]"
# 然后访问 /settings/erp 填 Oracle 连接信息
```

## 测试

41 → 56 个测试, 全部通过。

## 致谢

- [nc-mcp-project](https://atomgit.com/gcw_cJbJuamU/nc-mcp-project) 提供 NC MCP 集成
```

- [ ] **Step 2: Commit**

```bash
git add docs/releases/v1.5.0.md
git commit -m "docs: add v1.5.0 release notes"
```

---

## Task 28: 打 tag + 推送

**Files:** (无代码改动)

- [ ] **Step 1: 最终验证**

```bash
.venv/bin/python -m pytest tests/ -v 2>&1 | tail -3
ruff check . && ruff format --check .
```
Expected: `56 passed` / `0 errors`

- [ ] **Step 2: 打 tag**

```bash
git tag v1.5.0
```

- [ ] **Step 3: 推送 (如需)**

```bash
git push origin codex/zlink-agent-v1.5.0
git push origin v1.5.0
```

注意: `git push` 是外部动作, 按 AGENTS.md "External Action Boundaries" 规则需用户明确批准。

---

# Self-Review

## Spec 覆盖检查

| Spec 章节 | Plan 任务 | 状态 |
|----------|----------|------|
| 1. 目标与范围 | 全部 phase | ✅ |
| 2. 命名与品牌 | Phase 1 (Task 1-5) | ✅ |
| 3. 项目结构 | Phase 2 (Task 6-8) | ✅ |
| 4. 多 ERP 集成架构 | Phase 3 (Task 9-11) | ✅ |
| 5. 配置层多 ERP | Phase 4 (Task 12-15) | ✅ |
| 6. MCP 与工具命名 | Phase 4 (Task 12-15) | ✅ |
| 7. 前端 /settings/erp | Phase 6 (Task 18-20) | ✅ |
| 8. 数据目录兼容 | Phase 5 (Task 16) | ✅ |
| 9. 测试策略 | Phase 8 (Task 25-26) | ✅ |
| 10. 关键文件改动清单 | 全部 phase | ✅ |
| 11. 发布流程 | Phase 8 (Task 28) | ✅ |
| 12. 不做的事 (YAGNI) | 全部 phase 排除 | ✅ |
| 14. v1.6.0 路线图 | (本 plan 不覆盖) | ⚠️ 仅占位 |

## 占位符扫描

无 TBD / TODO / FIXME 残留。

## 类型一致性

- `MCPServerConnection.config` 字段: 已在 Task 15 验证 mcp_manager 接受新字段
- `ERPClient` Protocol: 已在 Task 9 完整定义
- `MCPStarterConfig` dataclass: 已在 Task 9 完整定义
- `get_erp_config(name)`: 已在 Task 14 完整定义
- `resolve_placeholders(env, config)`: 已在 Task 14 完整定义
- `sync_nc_mcp()`: 已在 Task 13 完整定义
- `build_nc_mcp_env / build_nc_mcp_config`: 已在 Task 12 完整定义

无类型不一致。

---

# Execution Choice

Plan 已完成并保存到 `docs/superpowers/plans/2026-07-10-zlink-agent-v1.5.0.md`。

**两种执行方式**:

**1. Subagent-Driven (推荐)**
- 我为每个 task 派遣一个全新的子 agent
- 任务之间我做两阶段 review
- 快速迭代, 上下文隔离
- 适合: 多 task, 改动面广

**2. Inline Execution**
- 在当前会话里执行所有 task
- 批量执行 + 审查检查点
- 适合: task 数 ≤ 10, 改动集中

**请问用哪种？** 或者直接说 "subagent" / "inline" 我就开始。
