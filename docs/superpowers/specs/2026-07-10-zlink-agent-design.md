# ZLink Agent v1.5.0 — 重命名 + 多 ERP 抽象层骨架设计

> **状态**: 待用户审查
> **作者**: Codex (default mode)
> **日期**: 2026-07-10
> **基线版本**: v1.4.1（41 测试全过，ruff 0 errors）

---

## 1. 目标与范围

把 YS-Agent 改名为 ZLink Agent（智链 Agent），并为多 ERP 接入做架构准备。本次（v1.5.0）只做**重命名 + 声明性骨架**，**不实现 NC 实际业务**（NC 业务在 v1.6.0）。

### 1.1 关键约束（硬性）

| 约束 | 说明 |
|------|------|
| 原 41 测试不挂 + 新增 5 测试 = **46/46 PASS** | v1.5.0 发布时 `pytest tests/ -v` 必须 46/46 全过 |
| ruff check 0 errors | `ruff check .` 保持 0 errors |
| `YonSuiteClient` 内部代码 100% 不动 | 只移动目录位置，0 行内部代码修改 |
| 数据目录双兼容 | v1.5.0 同时认 `~/.ys-agent/data/` 和 `~/.zlink-agent/data/`，老用户不丢数据 |
| MCP 工具名保持 `mcp_yonsuite_*` | 不破坏已经在用旧名的下游用户 |

### 1.2 不在范围

- ❌ 不实现 NC 真实鉴权、API、query 工具
- ❌ 不重写 YonSuiteClient 1055 行内部代码
- ❌ 不改 LLM provider 抽象（与本次无关）
- ❌ 不改内置 skills 列表
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
│   │   ├── __init__.py                  │   │   ├── __init__.py           [新增, 空]
│   │   ├── ys_client.py                 │   │   ├── base.py               [新增, 抽象层]
│   │   ├── config.py                    │   │   ├── exceptions.py         [新增, 通用异常]
│   │   ├── cache.py                     │   │   ├── yonsuite/             [整体移动, 内部不动]
│   │   ├── exceptions.py                │   │   │   ├── __init__.py
│   │   ├── models.py                    │   │   │   ├── ys_client.py
│   │   ├── modules/                     │   │   │   ├── config.py
│   │   │   ├── base.py                  │   │   │   ├── cache.py
│   │   │   ├── sales.py                 │   │   │   ├── exceptions.py
│   │   │   ├── purchase.py              │   │   │   ├── models.py
│   │   │   ├── ... (11 个业务模块)      │   │   │   ├── modules/
│   │   ├── tests/                       │   │   │   │   ├── base.py
│   │   ├── examples/                    │   │   │   │   ├── sales.py
│   │   └── docs/                        │   │   │   │   └── ...
│   │                                     │   │   │   ├── tests/
│   │                                     │   │   │   ├── examples/
│   │                                     │   │   │   └── docs/
│   │                                     │   │   └── nc/                  [新增骨架]
│   │                                     │   │       ├── __init__.py       [空]
│   │                                     │   │       └── nc_client.py      [空壳类]
│   ├── skills/yonsuite/...              │   ├── skills/yonsuite/...       [保留, 内部 SKILL.md 加一句版本说明]
│   └── ...                              │   └── ...
├── backend/api/                         ├── backend/api/
│   ├── config_api.py                    │   ├── config_api.py             [修改: 新增 erp-clients 端点]
│   └── ...                              │   ├── erp_clients_api.py        [新增]
├── web/src/                             ├── web/src/
│   ├── App.tsx                          │   ├── App.tsx                   [修改: 新增路由]
│   └── pages/                           │   └── pages/
│                                       │       └── SettingsERPPage.tsx   [新增]
├── mcp_server/                          ├── mcp_server/
│   ├── ys_mcp_server/                   │   ├── ys_mcp_server/            [保留, builtin 标记保持]
│   └── erp_mcp_router/                  │   └── erp_mcp_router/           [新增, 多 ERP 路由器骨架]
├── scripts/ys-agent.sh                  ├── scripts/zlink.sh              [新增, 内容=旧 ys-agent.sh]
│                                       │   └── ys-agent.sh               [保留, 软链接/兼容 shim]
├── pyproject.toml                       ├── pyproject.toml                [name, description, version]
├── README.md                            ├── README.md                     [全量重写]
├── CHANGELOG.md                         ├── CHANGELOG.md                  [追加 v1.5.0 段]
├── VERSION                              ├── VERSION                       [1.4.1 → 1.5.0]
└── ...                                  └── ...
```

### 3.2 移动操作（git mv 友好）

`agent/yonsuite_client/` → `agent/erp_clients/yonsuite/` 用 `git mv` 命令，保持文件历史连续。`modules/`、`tests/`、`examples/`、`docs/` 子目录同样整体 `git mv`。

---

## 4. 抽象层设计（声明性骨架）

### 4.1 设计原则

- **YAGNI**：v1.5.0 不强制 YonSuiteClient 改造，只声明"接口长什么样"
- **可插拔**：v1.6.0+ 新增 ERP 时，加一个 `agent/erp_clients/<name>/` 子目录 + 一个 `__init__.py` 注册条目即可
- **零侵入**：`YonSuiteClient` 不继承 `ERPClient`，也不实现 `ERPClient` 协议。两者通过 `agent/erp_clients/__init__.py` 的注册机制关联
- **测试覆盖**：v1.5.0 加新测试验证"YonSuiteClient 实例满足 ERPClient 协议"（结构性子类型 / duck typing）

### 4.2 `agent/erp_clients/base.py` 内容

```python
"""
ERP 客户端抽象层（声明性骨架）

v1.5.0 设计目标:
- 定义所有 ERP 客户端应满足的最小接口
- 定义跨 ERP 的通用异常类型
- 不强制 YonSuiteClient 继承; 通过 isinstance_check 验证结构子类型
- 未来 ERP (NC/SAP/金蝶) 加 erp_clients/<name>/ 子目录即可
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


# === 通用配置 ===

@dataclass(frozen=True)
class ERPClientConfig:
    """ERP 客户端配置 (脱敏: 实际 secret 在 config_manager 加密)"""
    name: str            # "yonsuite" | "nc" | ...
    enabled: bool        # 用户是否启用此 ERP
    base_url: str        # API 网关根 URL
    extra: dict[str, Any]  # ERP-specific 字段 (tenant_id / app_key / host / token / ...)


# === 抽象协议 (声明性, 非强制) ===

@runtime_checkable
class ERPClient(Protocol):
    """
    所有 ERP 客户端的最小接口契约 (v1.5.0 声明性版本)

    实现要求:
    - 必须有 name 属性, 等于注册名 ("yonsuite" | "nc" | ...)
    - 必须有 authenticate() 方法, 返回 token 或 True
    - 必须有 close() / __aexit__ 类清理方法 (未来用, v1.5.0 可空)
    - query_* 方法不强求统一, 各 ERP 自己定 (因业务差异大)
    """
    name: str

    def authenticate(self, force_refresh: bool = False) -> str | bool: ...
    def health_check(self) -> bool: ...


# === 注册表 ===

REGISTRY: dict[str, type] = {}

def register(name: str):
    """ERP 客户端注册装饰器"""
    def decorator(cls: type) -> type:
        if name in REGISTRY:
            raise ValueError(f"ERP client {name!r} already registered")
        REGISTRY[name] = cls
        cls.name = name  # 类属性注入
        return cls
    return decorator

def get_client_class(name: str) -> type:
    """按名称获取已注册的 ERP 客户端类"""
    if name not in REGISTRY:
        raise KeyError(
            f"ERP client {name!r} not registered. "
            f"Available: {sorted(REGISTRY.keys())}"
        )
    return REGISTRY[name]

def list_registered() -> list[str]:
    """列出所有已注册的 ERP 客户端名"""
    return sorted(REGISTRY.keys())
```

### 4.3 `agent/erp_clients/__init__.py` 内容

```python
"""
ERP 客户端统一入口 (v1.5.0 新增)

提供:
- 列出已注册的 ERP 客户端
- 校验 YonSuiteClient 等老客户端是否满足 ERPClient 协议
- 工厂方法 get_client(name, config) -> 实例
"""

from .base import (
    ERPClient,
    ERPClientConfig,
    ERPError,
    ERPAuthError,
    ERPRateLimitError,
    ERPNetworkError,
    ERPAPIError,
    REGISTRY,
    register,
    get_client_class,
    list_registered,
)

# 触发各 ERP 子包的 register() 调用
from . import yonsuite  # noqa: F401  -- 注册 YonSuiteClient
from . import nc        # noqa: F401  -- 注册 NCClient (v1.5.0 空壳)

__all__ = [
    "ERPClient", "ERPClientConfig",
    "ERPError", "ERPAuthError", "ERPRateLimitError", "ERPNetworkError", "ERPAPIError",
    "REGISTRY", "register", "get_client_class", "list_registered",
]
```

### 4.4 `agent/erp_clients/yonsuite/__init__.py` 改造（最小化）

只做两件事：
1. 加一行 `# 路径已迁移: agent/yonsuite_client/ → agent/erp_clients/yonsuite/ (v1.5.0)`
2. `from .ys_client import YonSuiteClient`
3. 在末尾加注册调用：`from ..base import register; register("yonsuite")(YonSuiteClient)`

**注意**：第 3 步的 `register` 会修改 `YonSuiteClient.name = "yonsuite"`，这是注入，不会破坏现有 41 个测试（v1.5.0 加 5 个新测试到 46）（测试不依赖这个属性）。

### 4.5 `agent/erp_clients/nc/__init__.py` 和 `nc_client.py`（v1.5.0 空壳）

```python
# agent/erp_clients/nc/__init__.py
"""
NC (用友 NC Cloud) 客户端 - v1.5.0 骨架

v1.5.0: 仅空壳, 实际业务在 v1.6.0 接入
"""
from .nc_client import NCClient  # noqa: F401

# agent/erp_clients/nc/nc_client.py
"""
NC 客户端空壳 - v1.5.0

正式实现 (鉴权/API/query tools) 在 v1.6.0
"""
from __future__ import annotations
from ..base import ERPError, register


class NCClient:
    """v1.5.0 占位类, v1.6.0 实现完整业务"""
    name = "nc"

    def __init__(self, config=None):
        self.config = config
        raise NotImplementedError(
            "NCClient 实际业务在 v1.6.0 接入. "
            "v1.5.0 仅占位, 不会在任何 API 路径中被调用."
        )

    def authenticate(self, force_refresh: bool = False) -> str | bool:
        raise NotImplementedError("NCClient.authenticate 待 v1.6.0 实现")

    def health_check(self) -> bool:
        return False  # v1.5.0 永远不健康


# v1.5.0 不注册, 因为 NotImplementedError 会导致 import 失败
# register("nc")(NCClient)  # v1.6.0 取消注释
```

**关键决策**：v1.5.0 **不注册** `NCClient`（注释掉 register 调用），原因：
- `NotImplementedError` 在 `__init__` 抛，注册后任何 import `agent.erp_clients` 都会触发失败
- v1.5.0 的 `list_registered()` 只返回 `["yonsuite"]`
- v1.6.0 取消注释，NC 客户端"自然出现"在注册表里

---

## 5. 配置层多 ERP

### 5.1 `config.json` 形态

```json
{
  "llm": { "provider": "openai", "api_key": "encrypted:xxx", ... },
  "erp_clients": {
    "yonsuite": {
      "enabled": true,
      "tenant_id": "...",
      "app_key": "encrypted:...",
      "app_secret": "encrypted:...",
      "base_url": "https://api.yonsuite.com"
    },
    "nc": {
      "enabled": false,
      "host": "https://nc.example.com",
      "account": "...",
      "token": "encrypted:..."
    }
  },
  "yonsuite": { ... }    // [向后兼容] 旧字段保留, 启动时自动迁移到 erp_clients.yonsuite
}
```

### 5.2 加载与迁移逻辑

`agent/config_manager.py` 新增方法 `get_erp_config(name: str) -> ERPClientConfig`：
- 优先读 `erp_clients[name]`
- 缺失时回退读旧字段 `yonsuite`（仅 `name == "yonsuite"`）
- 自动加密 `app_key` / `app_secret` / `token` 字段

`backend/api/config_api.py` 新增端点：

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/config/erp-clients` | 列出所有 ERP 客户端及配置（脱敏）|
| GET | `/api/config/erp-clients/{name}` | 获取单个 ERP 客户端配置 |
| PUT | `/api/config/erp-clients/{name}` | 更新单个 ERP 客户端配置（自动加密 secret 字段）|
| POST | `/api/config/erp-clients/{name}/test` | 测试连接（v1.5.0 YonSuite 真测，NC 返 501）|

### 5.3 数据迁移策略

`agent/utils.py` 的 `_resolve_data_dir()` 加一级 fallback：

```python
def _resolve_data_dir() -> Path:
    # 优先级 (v1.5.0 新):
    # 1. YS_DATA_DIR / ZLINK_DATA_DIR 环境变量 (后者优先)
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

**未来清理**：v2.0.0 砍掉第 3 级 fallback（已在 1.4.0 数据目录统一那个 PR 的精神里）。

---

## 6. MCP 与工具命名

### 6.1 现有 MCP 服务保留

`mcp_server/ys_mcp_server/` **保留原样**，`builtin=True` 标记保持。工具名 `mcp_yonsuite_ys_api` / `mcp_yonsuite_query_*` 保持不变——**老用户不感知改动**。

### 6.2 新增多 ERP 路由器（v1.5.0 骨架）

新增 `mcp_server/erp_mcp_router/` 目录：

```
mcp_server/erp_mcp_router/
├── __init__.py
├── server.py          # MCP 服务器入口
├── router.py          # 按 erp_name 分发到具体客户端
└── tools.py           # 工具定义 (v1.5.0 仅暴露 erp_list / erp_get_config)
```

v1.5.0 工具集（最小可用）：

| 工具名 | 用途 | v1.5.0 行为 |
|--------|------|------------|
| `erp_list` | 列出已注册 ERP 客户端 | 返回 `["yonsuite"]`（NC 注册在 v1.6.0）|
| `erp_get_config` | 获取某 ERP 配置（脱敏）| YonSuite 真返回，NC 返 501 |
| `erp_test_connection` | 测试连接 | YonSuite 真测，NC 返 501 |

`builtin=True` 标记，**前端 MCP 管理页禁删**。

### 6.3 工具命名约定（给 v1.6.0 留位）

未来新增工具按 `<scope>_<erp>_<verb>` 三段式：
- `mcp_erp_yonsuite_query_sale_orders`（v1.6.0 把 `mcp_yonsuite_query_sale_orders` 别名同步过去）
- `mcp_erp_nc_query_sale_orders`（v1.6.0）

v1.5.0 **不动现有工具名**，避免破坏下游。

---

## 7. 前端 `/settings/erp` 页面

### 7.1 路由

`web/src/App.tsx` 新增：

```tsx
<Route path="/settings/erp" element={<SettingsERPPage />} />
```

### 7.2 页面骨架

复用 `SettingsLLMPage` 的卡片式布局：

- 顶部说明：「ZLink Agent 支持连接多个 ERP 系统。当前已注册: YonSuite。v1.6.0 起支持 NC。」
- 每个 ERP 客户端一张卡片：
  - 名称、Logo、状态（启用/禁用）、"测试连接"按钮、"编辑配置"按钮
  - 卡片底部显示已注册的 query 工具数量
- 底部「+ 添加 ERP」按钮（v1.5.0 显示但点击弹 "v1.6.0 上线" toast）

### 7.3 复用现有组件

- 卡片样式：复用 `SettingsLLMPage` 的 `card-erppage` class
- 表单组件：复用现有 Input/Select/Button
- 加密提示：复用 `config_api` 已有的 secret 字段标记

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
    assert isinstance(YonSuiteClient, ERPClient)  # 协议检查

def test_erp_registry_only_yonsuite_v150():
    """v1.5.0 注册表只含 yonsuite（NC 留 v1.6.0）"""
    from agent.erp_clients import list_registered
    assert list_registered() == ["yonsuite"]

def test_data_dir_fallback_to_old():
    """~/.ys-agent/data 存在时优先用旧目录"""
    # 临时建 ~/.ys-agent/data 模拟老用户
    # 调用 _resolve_data_dir() 验证返回旧路径

def test_erp_clients_api_get():
    """GET /api/config/erp-clients 端点"""
    # 调 API, 验证返回 yonsuite 条目, secret 字段脱敏

def test_erp_clients_api_put_encrypts_secrets():
    """PUT 配置时 secret 字段被自动加密"""
    # 调 API 写, 读 config.json 验证落盘是 encrypted:xxx
```

预计 +5 个新测试，总数 46/46 全过。

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
| 1 | `pyproject.toml` | 改 name/description/version | 1 min |
| 2 | `VERSION` | 1.4.1 → 1.5.0 | 1 min |
| 3 | `CHANGELOG.md` | 追加 v1.5.0 段 | 5 min |
| 4 | `README.md` | 全量重写（标题/tagline/克隆命令/功能列表/项目结构）| 15 min |
| 5 | `agent/yonsuite_client/` → `agent/erp_clients/yonsuite/` | `git mv` | 1 min |
| 6 | `agent/erp_clients/base.py` | 新增 | 5 min |
| 7 | `agent/erp_clients/exceptions.py` | 新增（可合并到 base.py）| 2 min |
| 8 | `agent/erp_clients/__init__.py` | 新增 | 2 min |
| 9 | `agent/erp_clients/nc/__init__.py` + `nc_client.py` | 新增空壳 | 3 min |
| 10 | `agent/erp_clients/yonsuite/__init__.py` | 改 1 行 + 加 register | 2 min |
| 11 | `agent/utils.py` | `_resolve_data_dir()` 加 fallback | 5 min |
| 12 | `agent/config_manager.py` | 加 `get_erp_config()` | 10 min |
| 13 | `backend/api/config_api.py` | 加 erp-clients 路由 | 10 min |
| 14 | `backend/api/erp_clients_api.py` | 新增（可合并到 config_api.py）| 10 min |
| 15 | `mcp_server/erp_mcp_router/{__init__,server,router,tools}.py` | 新增 | 15 min |
| 16 | `scripts/zlink.sh` | 新增 | 5 min |
| 17 | `scripts/ys-agent.sh` | 改 1 行 = 软链到 zlink.sh | 1 min |
| 18 | `web/src/App.tsx` | 加路由 1 行 | 1 min |
| 19 | `web/src/pages/SettingsERPPage.tsx` | 新增 | 20 min |
| 20 | `docs/architecture.md` | 加"多 ERP 抽象"章节 | 10 min |
| 21 | `docs/extending-ys-agent.md` | 改名为 extending-zlink-agent.md + 内容更新 | 10 min |
| 22 | `AGENTS.md` | 改标题/项目名引用 | 5 min |
| 23 | 其它 200 处 `ys-agent` 字符串 | sed/手工替换 | 30 min |
| 24 | `tests/test_erp_clients.py` | 新增 5 个测试 | 15 min |
| 25 | 现有 tests/ 中 import 路径 | 改 5-8 行 | 5 min |

**总估时**：~3 小时（纯代码工作），含 git commit/消息/tag 推送约 4 小时。

---

## 11. 发布流程（按 AGENTS.md 五步规范）

1. 改 `pyproject.toml` `version` → 1.5.0 ✅（已在清单）
2. 改 `VERSION` 文件 → 1.5.0 ✅
3. 改 `CHANGELOG.md` 加 v1.5.0 段 ✅
4. 改 `README.md`（版本号 + 功能列表 + 项目结构）✅
5. `git tag v1.5.0 && git push origin v1.5.0`

**前置验证**（按 verification-before-completion）：

```bash
.venv/bin/python -m pytest tests/ -v          # 期望 46/46 PASS
ruff check . && ruff format --check .          # 期望 0 errors
.venv/bin/python -c "from agent.erp_clients import list_registered; print(list_registered())"
# 期望输出: ['yonsuite']
.venv/bin/python -m agent.tools.registry discover_tools
# 期望无报错
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | .venv/bin/python -m mcp_server.ys_mcp_server
# 期望 MCP 初始化成功
```

---

## 12. 不做的事（YAGNI 明确清单）

| 不做 | 原因 |
|------|------|
| 不重写 `YonSuiteClient` 1055 行 | 风险高，v1.5.0 改了还要重测 |
| 不实现 NC 实际业务 | v1.6.0 才做，v1.5.0 只留空壳 |
| 不改 LLM provider 抽象 | 与本次无关 |
| 不动 builtin skills 列表 | 与本次无关 |
| 不动 builtin MCP server（`ys_mcp_server`）| 老用户兼容 |
| 不动 4 个 untracked Windows 文件 | 用户在做的另一件事，不污染 |
| 不自动迁移老数据目录 | 避免 1.4.0 自动迁移的争议 |
| 不砍 `~/.ys-agent/data/` 兼容 | v2.0.0 才砍 |

---

## 13. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| `git mv` 后部分 import 路径漏改 | 中 | 测试失败 | 写 spec 时已列全部 import 改动；执行时用 grep 验证 |
| 改 name 后 pip 装包冲突老 `ys-agent` | 低 | 装包报错 | 不在 PyPI 实际发布 v1.5.0；本地用 `pip install -e .` |
| 改 name 后 GitHub Action / 文档链接坏 | 中 | 文档 404 | 执行前 grep 所有 `atomgit.com/gcw_cJbJuamU/ys-agent.git` 链接 |
| 抽象层 v1.5.0 留空壳，v1.6.0 反推需要改 base.py | 高 | v1.6.0 工作量 | YAGNI 接受；v1.6.0 再说 |
| 前端 `/settings/erp` 页面 v1.5.0 只展示无功能 | 低 | 用户迷惑 | README/页面顶部写明"v1.5.0 预览，v1.6.0 启用" |
| Windows 4 个 untracked 文件与本次冲突 | 低 | 编译失败 | 本次完全不动 Windows 文件 |

---

## 14. v1.6.0 路线图（仅占位，详细另写 RFC）

- NC OAuth/Token 鉴权实现
- NC OpenAPI 适配（11+ 个 query 工具对齐 YonSuite）
- `agent/erp_clients/nc/nc_client.py` 实装 + 取消 register 注释
- `mcp_erp_nc_*` 工具集实装
- 前端 `/settings/erp` 页面 NC 配置/连接测试真功能
- 文档：`docs/nc-integration.md`
- 测试：NC 单元测试 + 集成测试

---

## 15. 审查清单（用户 review 时可对照）

- [ ] 命名与品牌（第 2 节）：`zlink-agent` / 智链 / `zlink` CLI 是否 OK
- [ ] 项目结构（第 3 节）：`agent/erp_clients/yonsuite/` 路径是否 OK
- [ ] 抽象层设计（第 4 节）：声明性骨架 + 协议是否够用
- [ ] NC v1.5.0 空壳不注册（第 4.5 节）：是否接受
- [ ] 配置层多 ERP（第 5 节）：单一 `config.json` 多 section 是否 OK
- [ ] 数据目录双兼容（第 8 节）：保留 `~/.ys-agent/data/` fallback 是否 OK
- [ ] MCP 命名空间（第 6 节）：v1.5.0 保留 `mcp_yonsuite_*` 旧名是否 OK
- [ ] 新增 5 个测试（第 9.2 节）：覆盖范围是否够
- [ ] 不做的事（第 12 节）：YAGNI 清单是否同意
- [ ] v1.6.0 路线图（第 14 节）：是否需要提前细化

---

**确认后我会调用 `superpowers:writing-plans` 把这份 spec 拆成可执行的分步 task 计划（约 25 个 task，每 task 2-5 分钟），再开始动代码。**
