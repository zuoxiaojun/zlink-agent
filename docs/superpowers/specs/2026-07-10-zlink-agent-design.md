# ZLink Agent v1.5.0 — 重命名 + 多 ERP 抽象层骨架设计

> **状态**: 待用户审查（第二轮）
> **作者**: Codex (default mode)
> **日期**: 2026-07-10（首版）→ 2026-07-10（修订：NC 改为 MCP 包集成）
> **基线版本**: v1.4.1（41 测试全过，ruff 0 errors）
> **本轮变更**：用户决定 NC 走 [nc-mcp-project](https://atomgit.com/gcw_cJbJuamU/nc-mcp-project.git) 的 MCP 包，不做嵌入式 Python 客户端

---

## 1. 目标与范围

把 YS-Agent 改名为 ZLink Agent（智链 Agent），并为多 ERP 接入做架构准备。本次（v1.5.0）只做**重命名 + 声明性骨架 + NC MCP 集成入口**，**不内置 NC 业务**——NC 业务由 [nc-mcp-server](https://atomgit.com/gcw_cJbJuamU/nc-mcp-project.git) Python 包通过 stdio MCP 提供。

### 1.1 关键约束（硬性）

| 约束 | 说明 |
|------|------|
| 原 41 测试不挂 + 新增 10 测试 = **56/56 PASS** | v1.5.0 发布时 `pytest tests/ -v` 必须 56/56 全过 |
| ruff check 0 errors | `ruff check .` 保持 0 errors |
| `YonSuiteClient` 内部代码 100% 不动 | 只移动目录位置，0 行内部代码修改 |
| 数据目录双兼容 | v1.5.0 同时认 `~/.ys-agent/data/` 和 `~/.zlink-agent/data/`，老用户不丢数据 |
| MCP 工具名保持 `mcp_yonsuite_*` | 不破坏已经在用旧名的下游用户 |
| **NC 走 MCP 包集成，不做嵌入式客户端** | NC 业务由 `nc-mcp-server` Python 包提供，ZLink 只做"调用入口" |

### 1.2 不在范围

- ❌ 不实现 NC 嵌入式 Python 客户端
- ❌ 不内置 NC 业务代码（鉴权、SQL、查询模板）
- ❌ 不重写 YonSuiteClient 1055 行内部代码
- ❌ 不改 LLM provider 抽象（与本次无关）
- ❌ 不动 builtin skills 列表
- ❌ 不动 4 个 untracked Windows 文件（`packaging/installer.nsi`、`scripts/build-windows.bat`、`setup.bat`、`start.bat`）

---

## 2. 命名与品牌

### 2.1 命名（最终确定值）

| 项 | 值 | 备注 |
|----|----|------|
| 包名（pip / pyproject） | `zlink-agent` | |
| 仓库名 | `zlink-agent` | Git 远端需手工改名 |
| CLI 命令 | `zlink` | 短好记，命令为 `zlink start` / `zlink stop` |
| 数据目录 | `~/.zlink-agent/data/` | 与包名一致；旧 `~/.ys-agent/data/` 双兼容 |
| README 标题 | **ZLink Agent** | 驼峰 |
| 中文品牌 | **智链 Agent** | "智" = 智能，"链" = link |
| 英文 Tagline | "Smart Link to Your Business Systems" | |
| 版本起点 | **v1.5.0** | 架构扩展但向后兼容，按 semver 该升 minor |
| `z` 含义 | 智（智能）| 排除作者名首字母、品牌无含义等其它解读 |

### 2.2 `z` 含义的明确化

README 第一段定调：

> **ZLink Agent（智链 Agent）** — 把 LLM 连接到你的业务系统的智能中枢。

后续文案、CHANGELOG、文档统一使用"智链"或"ZLink"二选一，不再混用"link-agent"。

---

## 3. 项目结构变更

### 3.1 目录改动一览

```
YS-Agent/                                ZLink-Agent/
├── agent/                               ├── agent/
│   ├── yonsuite_client/                 │   ├── erp_clients/              [新增父目录]
│   │   ├── __init__.py                  │   │   ├── __init__.py           [新增, 注册中心]
│   │   ├── ys_client.py                 │   │   ├── base.py               [新增, ERPClient 协议]
│   │   ├── config.py                    │   │   ├── yonsuite/             [整体移动, 内部不动]
│   │   ├── cache.py                     │   │   │   ├── __init__.py
│   │   ├── exceptions.py                │   │   │   ├── ys_client.py
│   │   ├── models.py                    │   │   │   ├── config.py
│   │   ├── modules/                     │   │   │   ├── cache.py
│   │   │   ├── base.py                  │   │   │   ├── exceptions.py
│   │   │   ├── sales.py                 │   │   │   ├── models.py
│   │   │   ├── purchase.py              │   │   │   ├── modules/
│   │   │   ├── ... (11 个业务模块)      │   │   │   │   ├── base.py
│   │   ├── tests/                       │   │   │   │   ├── sales.py
│   │   ├── examples/                    │   │   │   │   └── ...
│   │   └── docs/                        │   │   │   ├── tests/
│   │                                     │   │   │   ├── examples/
│   │                                     │   │   │   └── docs/
│   ├── skills/yonsuite/...              │   ├── skills/yonsuite/...       [保留, 内部 SKILL.md 加一句版本说明]
│   │                                     │   ├── skills/nc/SKILL.md       [新增, NC 工具使用指南]
│   └── ...                              │   └── ...
├── backend/api/                         ├── backend/api/
│   ├── config_api.py                    │   ├── config_api.py             [修改: 新增 erp-clients 端点]
│   └── ...                              │   ├── erp_clients_api.py        [新增]
├── web/src/                             ├── web/src/
│   ├── App.tsx                          │   ├── App.tsx                   [修改: 新增路由]
│   └── pages/                           │   └── pages/
│                                       │       └── SettingsERPPage.tsx   [新增]
├── mcp_server/                          ├── mcp_server/
│   └── ys_mcp_server/                   │   ├── ys_mcp_server/            [保留, builtin 标记保持]
│   (无 erp_mcp_router 计划)            │   └── nc_mcp/                   [新增: NC MCP 集成入口骨架]
│                                       │       ├── __init__.py
│                                       │       ├── config.py             [ORACLE_* 环境变量转换]
│                                       │       └── mcp_starter.py        [调 mcp_manager 启动 nc-mcp-server]
├── scripts/ys-agent.sh                  ├── scripts/zlink.sh              [新增, 内容=旧 ys-agent.sh]
│                                       │   └── ys-agent.sh               [保留, 软链接/兼容 shim]
├── pyproject.toml                       ├── pyproject.toml                [name, description, version, optional nc extra]
├── README.md                            ├── README.md                     [全量重写]
├── CHANGELOG.md                         ├── CHANGELOG.md                  [追加 v1.5.0 段]
├── VERSION                              ├── VERSION                       [1.4.1 → 1.5.0]
└── ...                                  └── ...
```

### 3.2 移动操作（git mv 友好）

`agent/yonsuite_client/` → `agent/erp_clients/yonsuite/` 用 `git mv` 命令，保持文件历史连续。`modules/`、`tests/`、`examples/`、`docs/` 子目录同样整体 `git mv`。

---

## 4. 多 ERP 集成架构（重大修改）

### 4.1 架构原则

**ZLink Agent 不内置任何具体 ERP 的业务代码。** 所有 ERP 客户端都通过 MCP 协议接入，ZLink 只负责：
1. 启动/停止 MCP 服务器
2. 把用户配置（数据库连接、API 凭据）注入到 MCP 服务器的环境变量
3. 转发 LLM 的工具调用到对应 MCP 服务器
4. 把工具结果返回给 LLM

这是 v1.5.0 相对原 spec 的**根本性变更**——从"嵌入式 ERP 客户端"改为"ERP MCP 路由器"。

### 4.2 三个角色

```
┌──────────────────────────────────────────────────────┐
│  ZLink Agent (LLM Core + Tool Dispatcher)            │
│  agent/core/agent.py + agent/tools/mcp_manager.py     │
└────────┬────────────────────┬────────────────┬────────┘
         │                    │                │
         │ 启动 + 注入配置    │ 启动 + 注入配置 │
         │                    │                │
   ┌─────▼──────┐     ┌──────▼──────┐   ┌─────▼──────┐
   │ mcp-yonsuite│     │  mcp-nc     │   │ mcp-xxx    │
   │  (builtin)  │     │  (opt-in)   │   │ (未来)     │
   │             │     │             │   │            │
   │ YonSuite    │     │ nc-mcp-     │   │ sap-mcp    │
   │ Cloud API   │     │ server      │   │ kingdee-   │
   │  (内置)     │     │ (外部 pip)  │   │ mcp        │
   └─────────────┘     └─────────────┘   └────────────┘
```

**关键点**：
- 每个 ERP 客户端都是独立的 MCP 服务器进程（stdio JSON-RPC）
- 工具命名空间天然隔离（`mcp_yonsuite_query_sale_orders` vs `mcp_nc_query_sales_order`）
- 用户启用哪个 = 启动哪个 = 工具列表出现哪个

### 4.3 用户选择启用哪个 = AI 从哪取数

**这是用户消息里的核心诉求。** 实现方式：

```json
// ~/.zlink-agent/data/config.json
{
  "erp_clients": {
    "yonsuite": {
      "enabled": true,            ← 用户在前端打开
      "tenant_id": "...",
      "app_key": "encrypted:...",
      "app_secret": "encrypted:...",
      "base_url": "https://api.yonsuite.com"
    },
    "nc": {
      "enabled": false,           ← 用户没打开, AI 看不到 NC 工具
      "host": "192.168.31.96",
      "port": "1521",
      "service": "orcl",
      "user": "NC65",
      "password": "encrypted:...",
      "max_rows": 200
    }
  }
}
```

**行为**：
- `enabled=true` → mcp_manager 启动对应 MCP 服务器 → 工具被注册到 LLM 工具列表 → LLM 自动按语义选择
- `enabled=false` → MCP 服务器不启动 → 工具不在 LLM 视野 → LLM 不知道这个 ERP 存在
- 同一时刻可启用多个 → LLM 看到合并工具列表，自行决定（命名空间隔离避免冲突）

### 4.4 `agent/erp_clients/base.py`（保留，但只用于声明性 Protocol）

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


# === MCP 启动配置 schema (新增) ===

@dataclass(frozen=True)
class MCPStarterConfig:
    """
    把用户友好配置转换为 MCP server 启动参数

    用于 agent/mcp_server/nc_mcp/mcp_starter.py 等
    """
    erp_name: str            # "nc" | "sap" | ...
    enabled: bool            # 用户开关
    command: str             # 启动命令, e.g. "nc-mcp-server"
    args: list[str]          # 命令参数
    env: dict[str, str]      # 环境变量 (含 secret, 内部已加密)
    builtin: bool            # True=内置, False=用户安装
    install_hint: str | None # 未安装时的提示, e.g. "pip install nc-mcp-server"
```

### 4.5 `agent/erp_clients/__init__.py`（声明性注册中心）

```python
"""
ERP 客户端统一入口 (v1.5.0 改为"声明性"注册中心)

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

# 触发各 ERP 子包的 register() 调用 (YonSuite 仍然走 Python 类入口)
from . import yonsuite  # noqa: F401  -- YonSuiteClient 仍然从 erp_clients.yonsuite 暴露

__all__ = [
    "ERPClient",
    "ERPError", "ERPAuthError", "ERPRateLimitError", "ERPNetworkError", "ERPAPIError",
    "MCPStarterConfig",
]
```

### 4.6 `agent/erp_clients/yonsuite/__init__.py` 改造（最小化）

只做：
1. 加注释：`# 路径已迁移: agent/yonsuite_client/ → agent/erp_clients/yonsuite/ (v1.5.0)`
2. `from .ys_client import YonSuiteClient`

`YonSuiteClient` **不再注册到 `REGISTRY`**（因为 v1.5.0 走 MCP，不走 Python 类调用）。它仍然通过 `from agent.erp_clients.yonsuite import YonSuiteClient` 暴露给老代码（向后兼容）。

### 4.7 不再有 `agent/erp_clients/nc/` 目录

**重大决策**：v1.5.0 **完全不写** `agent/erp_clients/nc/` Python 包。NC 业务代码全部在 [nc-mcp-server](https://atomgit.com/gcw_cJbJuamU/nc-mcp-project.git) 那个独立包里。ZLink Agent 只做"调用方"。

---

## 5. 配置层多 ERP

### 5.1 `config.json` 形态

```json
{
  "llm": { "provider": "openai", "api_key": "encrypted:xxx", ... },

  "mcp_servers": {
    "mcp-yonsuite": {
      "transport": "stdio",
      "command": "python",
      "args": ["-m", "mcp_server.ys_mcp_server"],
      "env": {},
      "builtin": true,
      "enabled": true
    },
    "mcp-nc": {
      "transport": "stdio",
      "command": "nc-mcp-server",
      "args": [],
      "env": {
        "ORACLE_HOST": "${nc.host}",
        "ORACLE_PORT": "${nc.port}",
        "ORACLE_SERVICE": "${nc.service}",
        "ORACLE_USER": "${nc.user}",
        "ORACLE_PASSWORD": "${nc.password}",
        "NC_MCP_MAX_ROWS": "${nc.max_rows}"
      },
      "builtin": false,
      "enabled": false,
      "install_hint": "pip install zlink-agent[nc] 或 pip install git+https://atomgit.com/gcw_cJbJuamU/nc-mcp-project.git"
    }
  },

  "erp_clients": {
    "yonsuite": {
      "tenant_id": "...",
      "app_key": "encrypted:...",
      "app_secret": "encrypted:...",
      "base_url": "https://api.yonsuite.com"
    },
    "nc": {
      "host": "192.168.31.96",
      "port": "1521",
      "service": "orcl",
      "user": "NC65",
      "password": "encrypted:...",
      "max_rows": 200
    }
  },

  "yonsuite": { ... }    // [向后兼容] 旧字段保留, 启动时自动迁移到 erp_clients.yonsuite
}
```

### 5.2 `${nc.password}` 占位符机制

`mcp_servers.mcp-nc.env` 里的 `${nc.*}` 引用 `erp_clients.nc.*` 字段。`mcp_manager.py` 启动 NC MCP 时：
1. 读 `config.json` 全部内容
2. 把 `mcp_servers.mcp-nc.env` 里的 `${nc.X}` 替换为 `erp_clients.nc.X` 的实际值（已解密）
3. 启动 `nc-mcp-server` 子进程，注入解析后的 env

**好处**：用户在 `/settings/erp` 改一次密码，NC MCP 进程**自动重启加载新密码**（配置变更后 mcp_manager 检测到变化）。

### 5.3 REST API 端点

`backend/api/config_api.py` 新增：

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/config/erp-clients` | 列出所有 ERP 客户端及配置（脱敏）|
| GET | `/api/config/erp-clients/{name}` | 获取单个 ERP 客户端配置 |
| PUT | `/api/config/erp-clients/{name}` | 更新单个 ERP 客户端配置（自动加密 secret 字段）|
| POST | `/api/config/erp-clients/{name}/test` | 测试连接（YonSuite 真测，NC 通过 `mcp-nc` 进程 ping）|
| GET | `/api/config/mcp-servers` | 列出所有 MCP 服务器状态（含 builtin 标记）|
| POST | `/api/config/mcp-servers/{name}/toggle` | 启用/禁用某个 MCP 服务器 |

### 5.4 数据迁移策略

`agent/utils.py` 的 `_resolve_data_dir()` 加一级 fallback：

```python
def _resolve_data_dir() -> Path:
    # 优先级 (v1.5.0 新):
    # 1. ZLINK_DATA_DIR / YS_DATA_DIR 环境变量 (后者优先)
    # 2. ~/.zlink-agent/data/ (新默认)
    # 3. ~/.ys-agent/data/ (兼容 v1.4.x 老用户)
    # 4. 报错 (不静默建空目录)
    env = os.environ.get("ZLINK_DATA_DIR") or os.environ.get("YS_DATA_DIR")
    if env:
        return Path(env)
    new = Path.home() / ".zlink-agent" / "data"
    if new.exists():
        return new
    old = Path.home() / ".ys-agent" / "data"
    if old.exists():
        return old  # 老用户继续走老目录, 数据保留
    return new  # 新用户首次启动会创建新目录
```

**未来清理**：v2.0.0 砍掉第 3 级 fallback。

---

## 6. MCP 与工具命名

### 6.1 现有 MCP 服务保留

`mcp_server/ys_mcp_server/` **保留原样**，`builtin=True` 标记保持。工具名 `mcp_yonsuite_ys_api` / `mcp_yonsuite_query_*` 保持不变——**老用户不感知改动**。

### 6.2 NC MCP 集成入口（新增）

新增 `mcp_server/nc_mcp/` 目录——**不是实现 NC 业务**，而是把外部 `nc-mcp-server` 包集成进来：

```
mcp_server/nc_mcp/
├── __init__.py
├── config.py           # 解析 config.json 里的 erp_clients.nc → mcp-nc env
├── mcp_starter.py      # 调 mcp_manager 启动 nc-mcp-server 进程
└── tests/
    └── test_nc_mcp_config.py
```

**关键代码**（`config.py`）：

```python
"""
把 config.json 里的 erp_clients.nc 用户友好配置
转换为 nc-mcp-server 进程需要的 ORACLE_* 环境变量
"""

def build_nc_mcp_env(erp_config: dict) -> dict[str, str]:
    """转换配置: erp_clients.nc.* → ORACLE_*"""
    return {
        "ORACLE_HOST": erp_config["host"],
        "ORACLE_PORT": str(erp_config["port"]),
        "ORACLE_SERVICE": erp_config["service"],
        "ORACLE_USER": erp_config["user"],
        "ORACLE_PASSWORD": erp_config["password"],  # 调用方保证已解密
        "NC_MCP_MAX_ROWS": str(erp_config.get("max_rows", 200)),
    }


def build_nc_mcp_config(erp_config: dict, enabled: bool) -> dict:
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

**关键代码**（`mcp_starter.py`）：

```python
"""
按 config.json 里的 erp_clients.nc 状态决定 mcp-nc 是否启动
"""

import logging
from agent.config_manager import get_config
from mcp_server.nc_mcp.config import build_nc_mcp_config
from agent.tools.mcp_manager import get_server_statuses, reconnect_server

logger = logging.getLogger(__name__)

NC_MCP_NAME = "mcp-nc"


async def sync_nc_mcp() -> None:
    """
    每次配置变更后调用, 确保 mcp-nc 状态与 erp_clients.nc.enabled 一致

    行为:
    - enabled=True: 启动 nc-mcp-server, 工具自动注册到 LLM
    - enabled=False: 停止 nc-mcp-server, 工具从 LLM 视野消失
    - 命令不存在 (用户没装): 工具标记为 unavailable, 不抛错
    """
    config = get_config()
    nc_cfg = config.get("erp_clients", {}).get("nc", {})
    enabled = nc_cfg.get("host") is not None  # 简化: 填了 host 就算启用
    # 实际: 前端 PUT /api/config/erp-clients/nc 会显式设 enabled

    target = build_nc_mcp_config(nc_cfg, enabled=enabled)

    statuses = {s["name"]: s for s in get_server_statuses()}
    current = statuses.get(NC_MCP_NAME, {})

    if enabled and current.get("status") != "connected":
        logger.info("启动 mcp-nc...")
        await reconnect_server(NC_MCP_NAME, target)
    elif not enabled and current.get("status") == "connected":
        logger.info("停止 mcp-nc...")
        await reconnect_server(NC_MCP_NAME, {**target, "enabled": False})
```

### 6.3 工具命名约定

- **YonSuite**：`mcp_yonsuite_query_sale_orders`（保留旧名）
- **NC**：`mcp_nc_query_sales_order`（来自 nc-mcp-server，自带命名）
- 命名空间天然隔离，AI 工具选择按工具名/描述自动判定

### 6.4 前端 MCP 管理页（复用现有页面）

`/mcp` 页面会显示两个 MCP 服务器：
- **mcp-yonsuite** (builtin) — 启用开关
- **mcp-nc** (用户安装) — 启用开关 + "未安装"提示 + 安装命令链接

`builtin=True` 的 YonSuite 仍然禁删。NC 不是 builtin，可以独立停用/启动。

### 6.5 optional dependency 声明

`pyproject.toml` 新增：

```toml
[project.optional-dependencies]
web = ["fastapi>=0.110.0", "uvicorn[standard]>=0.27.0", "python-multipart>=0.0.0"]
all = ["zlink-agent[web]"]
nc = [
    # 通过 pip extras 装 NC 支持. 实际命令:
    # pip install "zlink-agent[nc]" @ git+https://atomgit.com/gcw_cJbJuamU/nc-mcp-project.git
    # 本次 v1.5.0 不实际依赖 nc-mcp-server (运行时按需检测);
    # 仅在文档里告诉用户怎么装.
]
dev = ["pytest>=8.0.0"]
```

**关键**：v1.5.0 的 pyproject **不强制依赖** `nc-mcp-server`。ZLink Agent 启动时检测命令是否存在：
- 存在 → 启动 NC MCP，工具可用
- 不存在 → mcp-nc 状态显示 "command not found"，前端显示安装提示，**不抛错**

---

## 7. 前端 `/settings/erp` 页面

### 7.1 路由

`web/src/App.tsx` 新增：

```tsx
<Route path="/settings/erp" element={<SettingsERPPage />} />
```

### 7.2 页面骨架

复用 `SettingsLLMPage` 的卡片式布局：

- 顶部说明：「ZLink Agent 支持连接多个 ERP 系统。当前已注册: YonSuite (内置)、NC (需安装 nc-mcp-server)。v1.5.0 启用开关即可。」
- 每个 ERP 客户端一张卡片：
  - 名称、Logo、状态（启用/禁用）、"测试连接"按钮、"编辑配置"按钮
  - 卡片底部显示已注册的 query 工具数量（从 mcp_manager 实时拿）

### 7.3 YonSuite 卡片字段

- 启用开关
- Tenant ID（文本）
- App Key（密码框）
- App Secret（密码框）
- Base URL（文本）

### 7.4 NC 卡片字段

- 启用开关
- ORACLE_HOST（文本）
- ORACLE_PORT（文本，默认 1521）
- ORACLE_SERVICE（文本）
- ORACLE_USER（文本）
- ORACLE_PASSWORD（密码框）
- NC_MCP_MAX_ROWS（数字，默认 200）
- "nc-mcp-server 未安装？" 提示框 + 安装命令（仅在命令不存在时显示）

### 7.5 复用现有组件

- 卡片样式：复用 `SettingsLLMPage` 的 `card-erppage` class
- 表单组件：复用现有 Input/Select/Button
- 加密提示：复用 `config_api` 已有的 secret 字段标记
- MCP 状态显示：复用现有 `/mcp` 页面的状态卡片

---

## 8. 数据目录兼容策略

| 用户类型 | v1.4.x 旧数据位置 | v1.5.0 行为 | 升级路径 |
|---------|------------------|------------|----------|
| 已有数据（`~/.ys-agent/data/` 存在）| 旧 | **继续读旧目录**，0 数据迁移 | 无操作 |
| 新用户 | — | 写到 `~/.zlink-agent/data/` | — |
| 想迁移到新目录 | 旧 | 手动 `mv ~/.ys-agent/data ~/.zlink-agent/data` | 一次性手工 |
| 用环境变量 | — | 尊重 `ZLINK_DATA_DIR` 或 `YS_DATA_DIR` | 任意 |

**注意**：v1.5.0 **不自动迁移**老数据（避免一次性 1.4.0 自动迁移的争议重演），用户想迁移自己 `mv`。

---

## 9. 测试策略

### 9.1 原 41 个测试照过

- 全部 41 个现有测试因 `YonSuiteClient` 内部代码不动 + 仅移动目录位置，应**全数通过**
- `tests/test_api_extensions.py` 等引用 `yonsuite_client` 路径的测试，需要更新 import 路径
- 预计改 5-8 个 test 文件的 import 行

### 9.2 新增测试（v1.5.0 必须有）

新增 `tests/test_erp_clients.py`，覆盖：

```python
def test_erp_client_protocol_yonsuite():
    """YonSuiteClient 结构子类型满足 ERPClient 协议"""
    from agent.erp_clients.yonsuite.ys_client import YonSuiteClient
    from agent.erp_clients.base import ERPClient
    # 仅作类型检查, 不强制
    assert hasattr(YonSuiteClient, "name")

def test_erp_base_exports():
    """agent.erp_clients 暴露通用异常 + Protocol"""
    from agent.erp_clients import (
        ERPError, ERPAuthError, ERPRateLimitError,
        ERPNetworkError, ERPAPIError, ERPClient, MCPStarterConfig
    )

def test_data_dir_fallback_to_old():
    """~/.ys-agent/data 存在时优先用旧目录"""
    # 临时建 ~/.ys-agent/data 模拟老用户
    # 调用 _resolve_data_dir() 验证返回旧路径

def test_erp_clients_api_get():
    """GET /api/config/erp-clients 端点"""
    # 调 API, 验证返回 yonsuite + nc 两条, secret 字段脱敏

def test_erp_clients_api_put_encrypts_secrets():
    """PUT 配置时 secret 字段被自动加密"""
    # 调 API 写 NC password, 读 config.json 验证落盘是 encrypted:xxx

def test_nc_mcp_config_translation():
    """erp_clients.nc.* 正确转换为 ORACLE_* 环境变量"""
    from mcp_server.nc_mcp.config import build_nc_mcp_env
    env = build_nc_mcp_env({
        "host": "1.2.3.4", "port": "1521", "service": "orcl",
        "user": "NC65", "password": "secret", "max_rows": 200
    })
    assert env["ORACLE_HOST"] == "1.2.3.4"
    assert env["ORACLE_PORT"] == "1521"
    assert env["NC_MCP_MAX_ROWS"] == "200"

def test_nc_mcp_starter_disabled_by_default():
    """NC MCP 默认 enabled=false, 不启动"""
    from mcp_server.nc_mcp.mcp_starter import sync_nc_mcp
    # 临时建空 config, 调用 sync_nc_mcp, 验证 mcp-nc 状态为 disconnected

def test_nc_mcp_placeholder_substitution():
    """${nc.X} 占位符正确替换为实际值"""
    config_dict = {
        "mcp_servers": {
            "mcp-nc": {
                "env": {"ORACLE_USER": "${nc.user}"}
            }
        },
        "erp_clients": {
            "nc": {"user": "NC65"}
        }
    }
    # 验证解析后 ORACLE_USER == "NC65"

def test_mcp_manager_lists_nc_when_enabled():
    """启用 NC 后, get_server_statuses() 返回 mcp-nc 条目"""
    # 写 config.json: erp_clients.nc.host = "1.2.3.4"
    # 调 sync_nc_mcp()
    # 调 get_server_statuses()
    # 验证 "mcp-nc" 在结果里

def test_nc_mcp_graceful_when_not_installed():
    """nc-mcp-server 命令不存在时, 不抛错, 状态显示 command-not-found"""
    # PATH 里去掉 nc-mcp-server (用 mock)
    # 调 sync_nc_mcp() 验证不抛异常
```

预计 +10 个新测试，总数 56/56 全过。

### 9.3 不动的测试

- `tests/test_api_extensions.py`（除 import 外）
- `tests/conftest.py`
- `tests/README.md`
- `agent/yonsuite_client/tests/test_ys_client.py`（同步移动路径即可）

---

## 10. 关键文件改动清单

按改动量级排序（高 → 低）：

| 序号 | 文件 | 改动类型 | 估时 |
|------|------|---------|------|
| 1 | `pyproject.toml` | 改 name/description/version + 加 nc extra | 2 min |
| 2 | `VERSION` | 1.4.1 → 1.5.0 | 1 min |
| 3 | `CHANGELOG.md` | 追加 v1.5.0 段 | 5 min |
| 4 | `README.md` | 全量重写（标题/tagline/克隆命令/功能列表/项目结构）| 15 min |
| 5 | `agent/yonsuite_client/` → `agent/erp_clients/yonsuite/` | `git mv` | 1 min |
| 6 | `agent/erp_clients/base.py` | 新增（声明性 Protocol）| 5 min |
| 7 | `agent/erp_clients/__init__.py` | 新增（声明性注册中心）| 2 min |
| 8 | `agent/erp_clients/yonsuite/__init__.py` | 改 1 行 | 1 min |
| 9 | `mcp_server/nc_mcp/__init__.py` + `config.py` + `mcp_starter.py` | 新增 | 15 min |
| 10 | `agent/utils.py` | `_resolve_data_dir()` 加 fallback | 5 min |
| 11 | `agent/config_manager.py` | 加 `get_erp_config()` + 占位符解析 | 15 min |
| 12 | `backend/api/config_api.py` | 加 erp-clients/mcp-servers 端点 | 15 min |
| 13 | `backend/api/erp_clients_api.py` | 新增 | 10 min |
| 14 | `agent/skills/nc/SKILL.md` | 新增 NC 工具使用指南 | 10 min |
| 15 | `scripts/zlink.sh` | 新增 | 5 min |
| 16 | `scripts/ys-agent.sh` | 改 1 行 = 软链到 zlink.sh | 1 min |
| 17 | `web/src/App.tsx` | 加路由 1 行 | 1 min |
| 18 | `web/src/pages/SettingsERPPage.tsx` | 新增 | 25 min |
| 19 | `docs/architecture.md` | 加"多 ERP 抽象"章节 | 10 min |
| 20 | `docs/extending-ys-agent.md` | 改名为 extending-zlink-agent.md + 内容更新 | 10 min |
| 21 | `AGENTS.md` | 改标题/项目名引用 | 5 min |
| 22 | 其它 200 处 `ys-agent` 字符串 | sed/手工替换 | 30 min |
| 23 | `tests/test_erp_clients.py` | 新增 10 个测试 | 25 min |
| 24 | 现有 tests/ 中 import 路径 | 改 5-8 行 | 5 min |

**总估时**：~3.5 小时（纯代码工作），含 git commit/消息/tag 推送约 4.5 小时。

---

## 11. 发布流程（按 AGENTS.md 五步规范）

1. 改 `pyproject.toml` `version` → 1.5.0 ✅（已在清单）
2. 改 `VERSION` 文件 → 1.5.0 ✅
3. 改 `CHANGELOG.md` 加 v1.5.0 段 ✅
4. 改 `README.md`（版本号 + 功能列表 + 项目结构）✅
5. `git tag v1.5.0 && git push origin v1.5.0`

**前置验证**（按 verification-before-completion）：

```bash
.venv/bin/python -m pytest tests/ -v          # 期望 56/56 PASS
ruff check . && ruff format --check .          # 期望 0 errors
.venv/bin/python -c "from agent.erp_clients import ERPError, MCPStarterConfig; print('ok')"
# 期望输出: ok
.venv/bin/python -c "from mcp_server.nc_mcp.config import build_nc_mcp_env; print(build_nc_mcp_env({'host':'x','port':'1521','service':'orcl','user':'u','password':'p'}))"
# 期望输出: {...'ORACLE_HOST': 'x'...}
.venv/bin/python -m agent.tools.registry discover_tools
# 期望无报错
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | .venv/bin/python -m mcp_server.ys_mcp_server
# 期望 MCP 初始化成功
```

---

## 12. 不做的事（YAGNI 明确清单）

| 不做 | 原因 |
|------|------|
| **不实现 NC 嵌入式 Python 客户端** | NC 走 [nc-mcp-server](https://atomgit.com/gcw_cJbJuamU/nc-mcp-project.git) 独立包，ZLink 不重复造轮子 |
| 不重写 `YonSuiteClient` 1055 行 | 风险高，v1.5.0 改了还要重测 |
| 不在 v1.5.0 加 NC 真实启用文档 | 等 v1.6.0 文档 + 端到端测试都过了再发 |
| 不实现"未启用 ERP 的工具提示" | v1.5.0 简单粗暴：禁用 = 工具消失 |
| 不实现"多 ERP 智能路由" | LLM 看到工具描述自带 ERP 上下文，自行选择足够；v1.6.0+ 观察实际使用再决定 |
| 不改 LLM provider 抽象 | 与本次无关 |
| 不动 builtin skills 列表 | 与本次无关 |
| 不动 builtin MCP server（`ys_mcp_server`）| 老用户兼容 |
| 不动 4 个 untracked Windows 文件 | 用户在做的另一件事，不污染 |
| 不自动迁移老数据目录 | 避免 1.4.0 自动迁移的争议 |
| 不砍 `~/.ys-agent/data/` 兼容 | v2.0.0 才砍 |
| 不在 pyproject 强制依赖 `nc-mcp-server` | 用 optional extras + 运行时检测 |

---

## 13. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| `git mv` 后部分 import 路径漏改 | 中 | 测试失败 | 写 spec 时已列全部 import 改动；执行时用 grep 验证 |
| 改 name 后 pip 装包冲突老 `ys-agent` | 低 | 装包报错 | 不在 PyPI 实际发布 v1.5.0；本地用 `pip install -e .` |
| 改 name 后 GitHub Action / 文档链接坏 | 中 | 文档 404 | 执行前 grep 所有 `atomgit.com/gcw_cJbJuamU/ys-agent.git` 链接 |
| nc-mcp-server 未装时用户体验差 | 中 | 启用 NC 后没反应 | 前端检测 + 安装提示；后端 graceful 降级 |
| 占位符 `${nc.X}` 解析有漏洞 | 低 | 启动失败 | 启动时校验 + 失败报错提示哪一项缺失 |
| LLM 选错 ERP 工具（用户想查 NC 但 AI 用了 YonSuite）| 中 | 错误结果 | 工具描述里强化 ERP 上下文；v1.6.0 加 router 中间件 |
| Windows 4 个 untracked 文件与本次冲突 | 低 | 编译失败 | 本次完全不动 Windows 文件 |

---

## 14. v1.6.0 路线图（仅占位，详细另写 RFC）

- 文档：`docs/nc-integration.md`（装包、配置、故障排查全流程）
- 前端 NC 卡片"测试连接"按钮真的能连（调 `mcp-nc` 的 `health` 工具）
- 多 ERP 工具智能路由中间件（如果用户问题模糊，AI 问"你想查 YonSuite 还是 NC？"）
- NC MCP server 进程监控面板（用 mcp_manager 已有 status 接口）
- nc-mcp-server 升级检测（pip check / version check）

---

## 15. 方法论总结（NC 集成模式的可复用价值）

**v1.5.0 的核心方法论**：

> ZLink Agent 是 ERP 客户端的**调度者**，不是**实现者**。
> 每个 ERP 客户端 = 一个独立的 MCP server（stdio 进程）。
> ZLink 只做"启停 + 配置注入 + 工具路由"三件事。
> 新增 ERP = 加一个 MCP 包 + 加一个 mcp_servers 配置节 + 加一个前端卡片。

**这意味着未来接入新 ERP 的成本是固定的**：
- SAP：等 sap-mcp-server 出来，加配置
- 金蝶：等 kingdee-mcp-server 出来，加配置
- Oracle EBS / 浪潮 / 航天信息：同上

每个新 ERP 不再需要改 ZLink 核心代码。这就是抽象层的真正价值——**不抽象 NC 的业务，只抽象"接入流程"**。

---

## 16. 审查清单（用户 review 时可对照）

- [ ] **第 4 节（多 ERP 集成架构）**：MCP 包集成而不是嵌入式 Python 客户端
- [ ] **第 4.3 节（用户选择启用哪个）**：enabled 字段 + mcp_manager 自动启停
- [ ] **第 4.7 节（不写 agent/erp_clients/nc/）**：NC 完全在外部包里
- [ ] **第 5.1 节（config.json 形态）**：mcp_servers + erp_clients 双段
- [ ] **第 5.2 节（${nc.X} 占位符）**：把用户配置注入 MCP 环境变量
- [ ] **第 6.2 节（NC MCP 集成入口）**：mcp_server/nc_mcp/ 目录的职责（不是实现 NC 业务）
- [ ] **第 6.5 节（optional dependency）**：不强制依赖 nc-mcp-server
- [ ] **第 7 节（前端）**：NC 卡片字段 + 未安装提示
- [ ] **第 8 节（数据目录）**：保留 `~/.ys-agent/data/` fallback
- [ ] **第 9.2 节（10 个新测试）**：覆盖 NC 配置转换、占位符、graceful 降级
- [ ] **第 12 节（YAGNI）**：明确不做嵌入式 NC 客户端
- [ ] **第 14 节（v1.6.0 路线图）**：文档 + 测试连接 + 智能路由中间件
- [ ] **第 15 节（方法论）**：MCP 包集成的可复用价值

---

**确认后我会调用 `superpowers:writing-plans` 把这份 spec 拆成可执行的分步 task 计划（约 25 个 task，每 task 2-5 分钟），再开始动代码。**
