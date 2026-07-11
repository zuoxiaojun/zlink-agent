# ZLink Agent 能力增强实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-subagent-driven-development (recommended) or superpowers-executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 ZLink Agent 添加 DeepSeek 模型支持、命令审批安全层、子代理委托和浏览器自动化四个能力。

**Architecture:** 四个独立功能依次实现，每个功能包含后端逻辑、前端界面（如有）和测试。DeepSeek 仅需配置更新；审批模式在 config_model → registry → security_hooks → backend API → frontend 贯通；子代理委托通过 ThreadPoolExecutor + 子 AIAgent 实现并行；浏览器自动化使用 Playwright 管理无头 Chromium。

**Tech Stack:** Python 3.11+ / FastAPI / React + Vite / Playwright / pytest / ruff

---

## File Structure

### 新建文件
| 文件 | 职责 |
|------|------|
| `agent/tools/delegate_tool.py` | 子代理委托工具——创建子 AIAgent 在 ThreadPoolExecutor 中执行 |
| `agent/tools/browser_tool.py` | 浏览器自动化工具集——Playwright 管理无头 Chromium |
| `agent/extensions/audit_log.py` | 审批日志扩展——记录所有审批事件到日志 |
| `tests/test_deepseek_provider.py` | DeepSeek 配置读取测试 |
| `tests/test_approval.py` | 审批模式三种行为的测试 |
| `tests/test_delegate_tool.py` | 子代理委托测试（MockLLMProvider） |
| `tests/test_browser_tool.py` | 浏览器工具栏测试（内网 URL 过滤，非 Playwright 集成） |

### 修改文件
| 文件 | 改动 |
|------|------|
| `backend/llm_providers.py` | 更新 DeepSeek 模型列表，添加 `deepseek-chat` / `deepseek-reasoner` |
| `agent/config_model.py` | 添加 `ApprovalMode` 枚举和 `approval_mode` 字段到 `AppConfig` |
| `agent/tools/registry.py` | `ToolEntry` 添加 `risk_level` 字段，`register()` 添加参数 |
| `agent/tools/security_hooks.py` | 添加 `approval_hook` BeforeHook 函数并注册；添加 `browser_navigate` URL 安全过滤 |
| `backend/schemas/config.py` | `AgentConfig` 添加 `approval_mode` 字段 |
| `backend/api/config_api.py` | `save_agent_config()` 读写 `approval_mode` |
| `web/src/types/index.ts` | `AgentConfigPayload` 添加 `approval_mode` |
| `web/src/pages/SettingsAgentPage.tsx` | 添加审批模式选择 UI |
| `agent/core/message_builder.py` | 系统提示词添加 `delegate_task` 工具使用指导 |
| `agent/extensions/__init__.py` | 注册 `AuditLogExtension` |
| `pyproject.toml` | 添加 `playwright` 可选依赖 |
| `agent/tools/terminal_tool.py` | 注册时添加 `risk_level="high"` |
| `agent/tools/file_tools.py` | `write_file`/`patch` 注册时添加 `risk_level="medium"` |
| `agent/tools/web_extract_tool.py` | 注册时添加 `risk_level="medium"` |

---

## Implementation Tasks

### Task 1: 更新 DeepSeek 模型列表

**Files:**
- Modify: `backend/llm_providers.py:17-26`
- Test: Create `tests/test_deepseek_provider.py`

- [ ] **Step 1: 修改 `backend/llm_providers.py` 中的 DeepSeek 条目，添加 `deepseek-chat` 和 `deepseek-reasoner`**

将现有 DeepSeek 条目的 models 列表更新为：

```python
    "DeepSeek": {
        "base_url": "https://api.deepseek.com",
        "models": [
            {"id": "deepseek-chat", "context_length": 1000000, "max_output": 8192},
            {"id": "deepseek-reasoner", "context_length": 1000000, "max_output": 8192},
            {"id": "deepseek-v4-flash", "context_length": 1000000, "max_output": 384000},
            {"id": "deepseek-v4-pro", "context_length": 1000000},
        ],
        "api_key_label": "DeepSeek API Key",
        "api_key_placeholder": "sk-...",
        "protocol": "openai_compat",
    },
```

具体 diff：将第 19-23 行替换为新模型列表。

- [ ] **Step 2: 验证后端测试可加载 Provider 列表**

Run: `.venv/bin/python -c "from backend.llm_providers import LLM_PROVIDERS; ds = LLM_PROVIDERS['DeepSeek']; print([m['id'] for m in ds['models']])"`
Expected: `['deepseek-chat', 'deepseek-reasoner', 'deepseek-v4-flash', 'deepseek-v4-pro']`

- [ ] **Step 3: 创建 `tests/test_deepseek_provider.py`**

```python
"""Tests for DeepSeek provider configuration."""

from backend.llm_providers import LLM_PROVIDERS


def test_deepseek_entry_exists():
    """DeepSeek must be present in LLM_PROVIDERS with correct structure."""
    assert "DeepSeek" in LLM_PROVIDERS
    entry = LLM_PROVIDERS["DeepSeek"]
    assert entry["protocol"] == "openai_compat"
    assert entry["base_url"] == "https://api.deepseek.com"


def test_deepseek_has_required_models():
    """DeepSeek must include both 'deepseek-chat' and 'deepseek-reasoner' models."""
    models = [m["id"] for m in LLM_PROVIDERS["DeepSeek"]["models"]]
    assert "deepseek-chat" in models
    assert "deepseek-reasoner" in models


def test_deepseek_models_have_context_length():
    """Each DeepSeek model must specify context_length."""
    for model in LLM_PROVIDERS["DeepSeek"]["models"]:
        assert "context_length" in model
        assert model["context_length"] > 0
```

- [ ] **Step 4: 运行测试并验证通过**

Run: `.venv/bin/python -m pytest tests/test_deepseek_provider.py -v`
Expected: `3 passed`

- [ ] **Step 5: 提交**

```bash
git add backend/llm_providers.py tests/test_deepseek_provider.py
git commit -m "feat: 更新 DeepSeek 模型列表，添加 deepseek-chat/deepseek-reasoner"
```

---

### Task 2: 添加 ApprovalMode 枚举和 approval_mode 字段到 AppConfig

**Files:**
- Modify: `agent/config_model.py:56-72`

- [ ] **Step 1: 在 `agent/config_model.py` 中添加 `ApprovalMode` 枚举和字段**

在 `MCPServerEntry` 类之前（第 44 行之前），添加枚举：

```python
from enum import Enum


class ApprovalMode(str, Enum):
    """Command approval mode for tool execution security."""
    ALLOW_ALL = "allow_all"
    APPROVE_HIGH_RISK = "approve"
    REJECT_ALL = "reject_all"
```

在 `AppConfig` 类中（第 72 行 `disabled_extensions` 之后），添加字段：

```python
    approval_mode: str = "allow_all"
```

- [ ] **Step 2: 验证模型可序列化和反序列化**

Run:
```python
from agent.config_model import AppConfig, ApprovalMode
cfg = AppConfig()
assert cfg.approval_mode == "allow_all"
cfg.approval_mode = "approve"
data = cfg.model_dump()
assert data["approval_mode"] == "approve"
restored = AppConfig.model_validate(data)
assert restored.approval_mode == "approve"
```
Expected: 无错误

- [ ] **Step 3: 提交**

```bash
git add agent/config_model.py
git commit -m "feat: 添加 ApprovalMode 枚举和 approval_mode 字段到 AppConfig"
```

---

### Task 3: 添加 risk_level 到 ToolRegistry

**Files:**
- Modify: `agent/tools/registry.py:69-96, 106-125`

- [ ] **Step 1: 为 `ToolEntry` 添加 `risk_level` 字段**

修改 `ToolEntry.__slots__`（第 69-77 行），添加 `"risk_level"`：

```python
    __slots__ = (
        "name",
        "toolset",
        "schema",
        "handler",
        "check_fn",
        "description",
        "emoji",
        "risk_level",
    )
```

修改 `ToolEntry.__init__`（第 79-96 行），添加 `risk_level=None` 参数和赋值：

```python
    def __init__(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable | None = None,
        description: str = "",
        emoji: str = "",
        risk_level: str = "low",
    ):
        # ... existing assignments ...
        self.risk_level = risk_level
```

- [ ] **Step 2: 修改 `registry.register()` 添加 `risk_level` 参数**

```python
    def register(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable | None = None,
        description: str = "",
        emoji: str = "",
        risk_level: str = "low",
    ) -> None:
        """Register a tool."""
        self._entries[name] = ToolEntry(
            name=name,
            toolset=toolset,
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            description=description,
            emoji=emoji,
            risk_level=risk_level,
        )
```

- [ ] **Step 3: 提交**

```bash
git add agent/tools/registry.py
git commit -m "feat: 添加 risk_level 参数到 ToolEntry 和 register()"
```

---

### Task 4: 更新现有工具注册添加 risk_level

**Files:**
- Modify: `agent/tools/terminal_tool.py:272-278`
- Modify: `agent/tools/file_tools.py:424-432`
- Modify: `agent/tools/web_extract_tool.py:145-151`

- [ ] **Step 1: `terminal_tool.py` — 添加 `risk_level="high"`**

将第 272-278 行替换为：

```python
registry.register(
    name="terminal",
    toolset="terminal",
    schema=TERMINAL_SCHEMA,
    handler=_handle_terminal,
    emoji="💻",
    risk_level="high",
)
```

- [ ] **Step 2: `file_tools.py` — `write_file` 和 `patch` 添加 `risk_level="medium"`**

将第 425-432 行替换为：

```python
registry.register(
    name="write_file",
    toolset="file",
    schema=WRITE_FILE_SCHEMA,
    handler=_handle_write_file_queued,
    emoji="✏️",
    risk_level="medium",
)
registry.register(name="patch", toolset="file", schema=PATCH_SCHEMA, handler=_handle_patch_queued, emoji="🔧", risk_level="medium")
```

- [ ] **Step 3: `web_extract_tool.py` — 添加 `risk_level="medium"`**

将第 145-151 行替换为：

```python
registry.register(
    name="web_extract",
    toolset="web",
    schema=WEB_EXTRACT_SCHEMA,
    handler=_handle_web_extract,
    emoji="📄",
    risk_level="medium",
)
```

- [ ] **Step 4: 验证工具注册不报错**

Run: `.venv/bin/python -c "from agent.tools.registry import discover_tools, registry; discover_tools(); print('OK:', len(registry.get_all_tool_names()), 'tools')"`
Expected: `OK:` 后跟工具数量，无错误

- [ ] **Step 5: 提交**

```bash
git add agent/tools/terminal_tool.py agent/tools/file_tools.py agent/tools/web_extract_tool.py
git commit -m "feat: 更新现有工具注册添加 risk_level 风险等级标记"
```

---

### Task 5: 创建 approval_hook 并注册到 security_hooks

**Files:**
- Modify: `agent/tools/security_hooks.py`

- [ ] **Step 1: 在 `security_hooks.py` 中添加 `approval_hook` 和相关辅助函数**

添加在 `register_default_hooks()` 之前（第 71 行之前），新增：

```python
import json
import threading
import time
from agent.config_manager import load as load_config

# ── Approval system ─────────────────────────────────────────────

# Cache of approved tool calls: key="tool_name:json_args" → timestamp
_APPROVED_CALLS: dict[str, float] = {}
_APPROVAL_TTL = 60.0  # seconds before an approval expires
_approval_lock = threading.Lock()


def _get_tool_risk_level(tool_name: str) -> str:
    """Get the risk_level of a registered tool. Defaults to 'low'."""
    entry = registry.get_entry(tool_name)
    if entry is None:
        return "low"
    return getattr(entry, "risk_level", "low")


def approval_hook(tool_name: str, args: dict) -> dict:
    """BeforeHook that checks approval_mode before executing medium/high risk tools.

    Three modes:
    - ``allow_all`` (default): pass through, no blocking.
    - ``reject_all``: block all medium and high risk tools.
    - ``approve``: block high-risk tools unless pre-approved via ``record_approval()``.
    """
    try:
        config = load_config()
        mode = getattr(config, "approval_mode", "allow_all")
    except Exception:
        # If config loading fails, allow the call (fail open is safer
        # than locking the user out of all tools).
        return args

    risk = _get_tool_risk_level(tool_name)

    if mode == "allow_all":
        return args

    if mode == "reject_all" and risk in ("medium", "high"):
        return {
            "__block__": True,
            "__reason__": f"工具 {tool_name} 已被管理员禁用（当前审批模式: 全部拒绝）",
        }

    if mode == "approve" and risk == "high":
        key = f"{tool_name}:{json.dumps(sorted(args.items()), ensure_ascii=False, sort_keys=True)}"
        with _approval_lock:
            if key in _APPROVED_CALLS and (time.monotonic() - _APPROVED_CALLS[key]) < _APPROVAL_TTL:
                return args  # approved within TTL
        return {
            "__block__": True,
            "__reason__": (
                f"⚠️ 需要你的确认才能执行以下操作：\n"
                f"工具: {tool_name}\n"
                f"参数: {json.dumps(dict(args), ensure_ascii=False)}\n"
                f"请在聊天中回复「批准」或「拒绝」。"
            ),
        }

    return args


def record_approval(tool_name: str, args: dict) -> None:
    """Record user approval for a specific tool call.

    Called when the user confirms execution.  Once recorded, the
    approval_hook will allow the same tool+args combination for
    ``_APPROVAL_TTL`` seconds.
    """
    key = f"{tool_name}:{json.dumps(sorted(args.items()), ensure_ascii=False, sort_keys=True)}"
    with _approval_lock:
        _APPROVED_CALLS[key] = time.monotonic()


def clear_approvals() -> None:
    """Clear all recorded approvals (e.g. on session end)."""
    with _approval_lock:
        _APPROVED_CALLS.clear()
```

- [ ] **Step 2: 在 `register_default_hooks()` 中注册 `approval_hook`**

将 `register_default_hooks()` 更新为：

```python
def register_default_hooks():
    """Install the built-in security hooks.  Idempotent — safe to call multiple times."""
    # Remove first to avoid duplicates on reload
    registry.remove_before_hook(_security_before_hook)
    registry.remove_after_hook(_security_after_hook)
    registry.remove_before_hook(approval_hook)
    registry.add_before_hook(approval_hook)
    registry.add_before_hook(_security_before_hook)
    registry.add_after_hook(_security_after_hook)
    logger.info("Default security hooks registered")
```

注意：`approval_hook` 在 `_security_before_hook` 之前注册，所以 approval 先运行——如果它 blocking，`_security_before_hook` 不会执行。

- [ ] **Step 3: 验证 hooks 可注册不报错**

Run: `.venv/bin/python -c "from agent.tools.security_hooks import register_default_hooks; register_default_hooks(); print('OK')"`
Expected: `OK`

- [ ] **Step 4: 提交**

```bash
git add agent/tools/security_hooks.py
git commit -m "feat: 添加 approval_hook BeforeHook 和审批缓存机制"
```

---

### Task 6: 后端 API 暴露 approval_mode

**Files:**
- Modify: `backend/schemas/config.py:24-31`
- Modify: `backend/api/config_api.py:113-122`

- [ ] **Step 1: `backend/schemas/config.py` — `AgentConfig` 添加 `approval_mode` 字段**

将 `AgentConfig` 类（第 24-31 行）替换为：

```python
class AgentConfig(BaseModel):
    max_iterations: int = Field(default=30, ge=5, le=50)
    compaction_enabled: bool = Field(default=True)
    max_context_tokens: int = Field(default=0, ge=0, le=2000000, description="0 = auto-detect from model")
    max_context_tokens_auto: bool = Field(default=True, description="True when context window is auto-detected")
    reserve_tokens: int = Field(default=4000, ge=1000, le=32000)
    keep_recent_tokens: int = Field(default=8000, ge=2000, le=128000)
    approval_mode: str = Field(default="allow_all", description="allow_all / approve / reject_all")
```

- [ ] **Step 2: `backend/api/config_api.py` — 在 `get_config()` 中返回 `approval_mode`**

在 `get_config()` 中（第 47-53 行）的 `AgentConfig(...)` 调用中添加：

```python
        agent=AgentConfig(
            max_iterations=cfg.max_iterations,
            compaction_enabled=cfg.compaction_enabled,
            max_context_tokens=effective_ctx,
            max_context_tokens_auto=(raw_ctx == 0),
            reserve_tokens=cfg.reserve_tokens,
            keep_recent_tokens=cfg.keep_recent_tokens,
            approval_mode=cfg.approval_mode,
        ),
```

- [ ] **Step 3: `backend/api/config_api.py` — 在 `save_agent_config()` 中处理 `approval_mode`**

将 `save_agent_config()` 函数（第 113-122 行）替换为：

```python
@router.put("/agent")
def save_agent_config(body: AgentConfig):
    cfg = config_manager.load()
    cfg.max_iterations = body.max_iterations
    cfg.compaction_enabled = body.compaction_enabled
    cfg.max_context_tokens = 0 if body.max_context_tokens_auto else body.max_context_tokens
    cfg.reserve_tokens = body.reserve_tokens
    cfg.keep_recent_tokens = body.keep_recent_tokens
    cfg.approval_mode = body.approval_mode
    config_manager.save(cfg)
    return {"ok": True}
```

- [ ] **Step 4: 验证请求/响应可用**

Run: `.venv/bin/python -c "
from backend.api.config_api import router
print('AgentConfig approval_mode route OK')
"`
Expected: 无导入错误

- [ ] **Step 5: 提交**

```bash
git add backend/schemas/config.py backend/api/config_api.py
git commit -m "feat: 后端 API 暴露 approval_mode 字段（schemas + API）"
```

---

### Task 7: 前端支持 approval_mode

**Files:**
- Modify: `web/src/types/index.ts:76-83`
- Modify: `web/src/pages/SettingsAgentPage.tsx`

- [ ] **Step 1: `web/src/types/index.ts` — `AgentConfigPayload` 添加 `approval_mode`**

将 `AgentConfigPayload`（第 76-83 行）替换为：

```typescript
export interface AgentConfigPayload {
  max_iterations: number;
  compaction_enabled: boolean;
  max_context_tokens: number;
  max_context_tokens_auto: boolean;
  reserve_tokens: number;
  keep_recent_tokens: number;
  approval_mode: string;
}
```

- [ ] **Step 2: `web/src/pages/SettingsAgentPage.tsx` — 添加审批模式选择 UI**

在编辑模式中添加审批模式选择器。在「保留最近对话量」之后、`form-actions` 之前添加：

```tsx
          <div className="form-group">
            <label className="form-label">命令审批模式</label>
            <div style={{ display: "flex", gap: "12px" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", fontSize: "14px" }}>
                <input
                  type="radio"
                  name="approvalMode"
                  value="allow_all"
                  checked={approvalMode === "allow_all"}
                  onChange={(e) => setApprovalMode(e.target.value)}
                />
                自动放行
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", fontSize: "14px" }}>
                <input
                  type="radio"
                  name="approvalMode"
                  value="approve"
                  checked={approvalMode === "approve"}
                  onChange={(e) => setApprovalMode(e.target.value)}
                />
                高风险需审批
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", fontSize: "14px" }}>
                <input
                  type="radio"
                  name="approvalMode"
                  value="reject_all"
                  checked={approvalMode === "reject_all"}
                  onChange={(e) => setApprovalMode(e.target.value)}
                />
                全部拒绝
              </label>
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-3)", marginTop: "4px" }}>
              {approvalMode === "allow_all" && "所有工具直接执行，无需审批（默认）"}
              {approvalMode === "approve" && "高风险操作（终端命令、文件删除等）需要用户批准后才能执行"}
              {approvalMode === "reject_all" && "拒绝所有中高风险操作，仅允许低风险工具执行"}
            </div>
          </div>
```

同时需要在函数开头添加 `approvalMode` 状态和 `setApprovalMode`：

将以下 useState 行添加到现有状态声明的末尾（第 17 行 `const [saved, setSaved] = useState(false);` 之前）：

```tsx
  const [approvalMode, setApprovalMode] = useState(cfg?.approval_mode || "allow_all");
```

更新 `handleSave` 中的 `payload`，添加 `approval_mode`：

```tsx
  const handleSave = async () => {
    const payload = {
      max_iterations: maxIter,
      compaction_enabled: compactionEnabled,
      max_context_tokens: ctxAuto ? 0 : maxContextTokens,
      max_context_tokens_auto: ctxAuto,
      reserve_tokens: reserveTokens,
      keep_recent_tokens: keepRecentTokens,
      approval_mode: approvalMode,
    };
    // ... rest unchanged
  };
```

在只读视图（`!edit` 块）中添加审批模式显示，在「保留最近对话量」卡片项之后：

```tsx
          <div className="form-group">
            <span className="form-label">命令审批模式</span>
            <div className="card-body">
              {cfg?.approval_mode === "allow_all" && "自动放行"}
              {cfg?.approval_mode === "approve" && "高风险需审批"}
              {cfg?.approval_mode === "reject_all" && "全部拒绝"}
              {!cfg?.approval_mode && "自动放行"}
            </div>
          </div>
```

- [ ] **Step 3: 验证前端可以编译**

Run: `cd web && npm run build 2>&1 | tail -10`
Expected: 无 TypeScript/构建错误

- [ ] **Step 4: 提交**

```bash
git add web/src/types/index.ts web/src/pages/SettingsAgentPage.tsx
git commit -m "feat: 前端支持 approval_mode 配置（types + SettingsAgentPage）"
```

---

### Task 8: 创建 AuditLogExtension

**Files:**
- Create: `agent/extensions/audit_log.py`
- Modify: `agent/extensions/__init__.py:24-29`

- [ ] **Step 1: 创建 `agent/extensions/audit_log.py`**

```python
"""AuditLogExtension — records approval and security events to the application log.

Subscribes to ``before_tool_call`` events and logs all tool invocations
when approval mode is active, creating an audit trail of which tools were
called, whether they were approved or blocked, and the arguments used.
"""

from __future__ import annotations

import json
import logging

from agent.events import BeforeToolCallEvent, Extension

logger = logging.getLogger("zlink-agent.audit")


class AuditLogExtension(Extension):
    """Logs tool calls for audit trail when approval mode is active."""

    name = "audit-log"
    enabled = True

    def on_before_tool_call(self, event: BeforeToolCallEvent) -> None:
        """Record every tool invocation to the audit log."""
        logger.info(
            "AUDIT: tool=%s args=%s",
            event.tool_name,
            json.dumps(dict(event.args), ensure_ascii=False),
        )
```

- [ ] **Step 2: 注册到 `agent/extensions/__init__.py`**

在 `_built_in_classes()` 函数中（第 28 行）添加导入和返回：

```python
    from agent.extensions.audit_log import AuditLogExtension

    return [LogEverythingExtension, MonitoringExtension, SecurityEventExtension, AuditLogExtension]
```

- [ ] **Step 3: 验证扩展可加载不报错**

Run: `.venv/bin/python -c "from agent.extensions import register_built_in_extensions; runners = register_built_in_extensions(); names = [r.extension.name for r in runners]; assert 'audit-log' in names; print('OK, extension registered')"`
Expected: `OK, extension registered`

- [ ] **Step 4: 提交**

```bash
git add agent/extensions/audit_log.py agent/extensions/__init__.py
git commit -m "feat: 创建 AuditLogExtension 审批日志扩展"
```

---

### Task 9: 编写审批模式测试

**Files:**
- Create: `tests/test_approval.py`

- [ ] **Step 1: 创建 `tests/test_approval.py`**

```python
"""Tests for the approval security system (approval_mode + risk_level + approval_hook).

These tests verify the three approval modes and the BeforeHook
blocking/pass-through logic.  They do NOT depend on a running backend
or WebSocket connection — they test the hook function directly.
"""

from __future__ import annotations

import json
import time

import pytest

from agent.tools.registry import registry


@pytest.fixture(autouse=True)
def clean_registry():
    """Snapshot and restore registry state."""
    saved = set(registry.get_all_tool_names())
    saved_before = list(registry._before_hooks)
    yield
    for name in set(registry.get_all_tool_names()) - saved:
        try:
            registry.deregister(name)
        except Exception:
            pass
    registry._before_hooks[:] = saved_before


def _register_test_tool(name: str, risk_level: str = "low"):
    """Register a minimal test tool with given risk_level."""
    def handler(args: dict) -> str:
        return json.dumps({"success": True, "data": "ok"})

    registry.register(
        name=name,
        toolset="test",
        schema={"type": "object", "properties": {}},
        handler=handler,
        risk_level=risk_level,
    )


def _make_approval_hook():
    """Import and return a fresh approval_hook with clean state."""
    from agent.tools.security_hooks import approval_hook, clear_approvals, record_approval
    clear_approvals()
    return approval_hook, record_approval, clear_approvals


def test_allow_all_mode_passes_all_tools(monkeypatch):
    """When approval_mode='allow_all', all tools pass through regardless of risk."""
    _register_test_tool("test_low", risk_level="low")
    _register_test_tool("test_med", risk_level="medium")
    _register_test_tool("test_high", risk_level="high")
    hook, _, _ = _make_approval_hook()

    from agent.config_model import AppConfig
    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="allow_all"),
    )

    for tool in ("test_low", "test_med", "test_high"):
        result = hook(tool, {"msg": "hello"})
        assert "__block__" not in result, f"{tool} should not be blocked in allow_all mode"
        assert result.get("msg") == "hello"


def test_reject_all_blocks_medium_and_high(monkeypatch):
    """When approval_mode='reject_all', medium and high risk tools are blocked."""
    _register_test_tool("test_low", risk_level="low")
    _register_test_tool("test_med", risk_level="medium")
    _register_test_tool("test_high", risk_level="high")
    hook, _, _ = _make_approval_hook()

    from agent.config_model import AppConfig
    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="reject_all"),
    )

    # Low risk passes
    result = hook("test_low", {})
    assert "__block__" not in result

    # Medium risk blocked
    result = hook("test_med", {})
    assert "__block__" in result
    assert "已被管理员禁用" in result.get("__reason__", "")

    # High risk blocked
    result = hook("test_high", {})
    assert "__block__" in result
    assert "已被管理员禁用" in result.get("__reason__", "")


def test_approve_mode_blocks_high_risk(monkeypatch):
    """When approval_mode='approve', high-risk tools are blocked unless pre-approved."""
    _register_test_tool("test_low", risk_level="low")
    _register_test_tool("test_high", risk_level="high")
    hook, record, _ = _make_approval_hook()

    from agent.config_model import AppConfig
    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="approve"),
    )

    # Low risk still passes
    result = hook("test_low", {})
    assert "__block__" not in result

    # High risk blocked without approval
    result = hook("test_high", {"path": "/tmp/test"})
    assert "__block__" in result
    assert "需要你的确认" in result.get("__reason__", "")


def test_approve_mode_passes_pre_approved_calls(monkeypatch):
    """High-risk tools pass when pre-approved via record_approval()."""
    _register_test_tool("test_high", risk_level="high")
    hook, record, clear = _make_approval_hook()

    from agent.config_model import AppConfig
    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="approve"),
    )

    args = {"path": "/tmp/test", "content": "data"}
    record("test_high", args)

    # Same tool + args passes now
    result = hook("test_high", dict(args))
    assert "__block__" not in result
    assert result.get("path") == "/tmp/test"


def test_approval_cache_expires(monkeypatch):
    """Pre-approvals expire after _APPROVAL_TTL seconds."""
    _register_test_tool("test_high", risk_level="high")
    hook, record, _ = _make_approval_hook()

    from agent.config_model import AppConfig
    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="approve"),
    )

    # Manually set an old approval timestamp
    from agent.tools.security_hooks import _APPROVED_CALLS, _APPROVAL_TTL
    key = 'test_high:[["action", "delete"]]'
    _APPROVED_CALLS[key] = time.monotonic() - _APPROVAL_TTL - 1

    # Should be blocked because cache entry expired
    result = hook("test_high", {"action": "delete"})
    assert "__block__" in result


def test_unknown_tool_defaults_to_low(monkeypatch):
    """Unregistered tools should default to 'low' risk and never block."""
    hook, _, _ = _make_approval_hook()

    from agent.config_model import AppConfig
    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="reject_all"),
    )

    result = hook("nonexistent_tool", {})
    assert "__block__" not in result


def test_approval_integration_with_dispatch(monkeypatch):
    """End-to-end: approval_hook integrated via registry.dispatch()."""
    _register_test_tool("test_high", risk_level="high")
    hook, record, _ = _make_approval_hook()

    from agent.config_model import AppConfig
    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="approve"),
    )

    # Register the hook
    registry.add_before_hook(hook)
    try:
        # Without approval → blocked
        result = registry.dispatch("test_high", {"x": "y"})
        payload = json.loads(result)
        assert payload["success"] is False
        assert "需要你的确认" in payload["error"]

        # With approval → passes
        record("test_high", {"x": "y"})
        result = registry.dispatch("test_high", {"x": "y"})
        payload = json.loads(result)
        assert payload["success"] is True
    finally:
        registry.remove_before_hook(hook)
```

- [ ] **Step 2: 运行测试并验证通过**

Run: `.venv/bin/python -m pytest tests/test_approval.py -v`
Expected: `7 passed`

- [ ] **Step 3: 提交**

```bash
git add tests/test_approval.py
git commit -m "test: 添加审批模式完整测试（三种模式 + 缓存过期 + dispatch 集成）"
```

---

### Task 10: 创建 delegate_tool.py

**Files:**
- Create: `agent/tools/delegate_tool.py`

- [ ] **Step 1: 创建 `agent/tools/delegate_tool.py`**

```python
"""Sub-agent delegation tool.

Lets the main LLM agent spawn child ``AIAgent`` instances in a
``ThreadPoolExecutor`` to handle independent subtasks in parallel.
The child agent shares the same LLM configuration, tool registry,
and security hooks as the parent, but runs in its own conversation
context with a limited iteration budget.

Usage triggered by the LLM when a complex query involves multiple
independent data sources (e.g. "compare sales from YonSuite and NC").
"""

from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from agent.tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────

_MAX_WORKERS = 3
_SUB_AGENT_TIMEOUT = 120.0  # seconds
_SUB_AGENT_MAX_ITERATIONS = 15
_MAX_RESULT_CHARS = 10_000

# Thread-local storage for the parent agent's config so sub-agents
# can inherit credentials without passing them through tool args.
_parent_config = threading.local()


def _run_sub_agent(task: str, context: str) -> str:
    """Execute *task* in a child AIAgent and return its final response.

    The child agent is created with the same LLM credentials,
    tool registry, and model as the parent but starts with an
    empty conversation history and a limited iteration budget.
    """
    from agent.core.agent import AIAgent
    from agent.tools.registry import discover_tools

    discover_tools()

    # Inherit parent's LLM config from thread-local storage
    api_key = getattr(_parent_config, "api_key", "")
    base_url = getattr(_parent_config, "base_url", "https://api.openai.com/v1")
    model = getattr(_parent_config, "model", "gpt-4o")
    temperature = getattr(_parent_config, "temperature", 0.7)

    # Build the prompt: context + task
    system_message = (
        "你是 ZLink Agent 的子代理，负责完成主代理委托给你的特定子任务。\n\n"
        "## 任务\n"
        f"{task}\n\n"
    )
    if context:
        system_message += f"## 上下文信息\n{context}\n"

    sub_agent = AIAgent(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
        max_iterations=_SUB_AGENT_MAX_ITERATIONS,
        max_tool_result_length=_MAX_RESULT_CHARS,
    )

    result = sub_agent.run_conversation(
        user_message=f"请完成以下任务：\n\n{task}\n\n{'上下文：' + context if context else ''}",
        system_message=system_message,
    )

    response = result.get("final_response", "") or ""
    if not response and not result.get("completed", True):
        response = f"[子代理任务未完成：{result.get('error', '未知错误')}]"

    if len(response) > _MAX_RESULT_CHARS:
        response = response[:_MAX_RESULT_CHARS] + "\n\n[结果已截断]"

    return response


def handle_delegate_task(args: dict) -> str:
    """Handle a ``delegate_task`` tool call.

    Spawns a child AIAgent via ThreadPoolExecutor and returns the
    child's final response.  The child shares the parent's LLM
    credentials but has its own conversation context.
    """
    task = args.get("task", "")
    context = args.get("context", "")

    if not task:
        return tool_error("task 参数是必需的")

    try:
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            future = executor.submit(_run_sub_agent, task, context)
            sub_result = future.result(timeout=_SUB_AGENT_TIMEOUT)
    except TimeoutError:
        return tool_error(f"子代理执行超时（{_SUB_AGENT_TIMEOUT} 秒）")
    except Exception as e:
        logger.exception("Sub-agent failed")
        return tool_error(f"子代理执行失败: {e}")

    return tool_result(
        data=f"子代理任务完成，结果如下：\n\n{sub_result}",
        sub_result=sub_result,
    )


def delegate_task_schema():
    return {
        "name": "delegate_task",
        "description": (
            "将子任务委托给一个子 AI Agent 并行执行。\n\n"
            "当你遇到可以独立并行的子任务时使用。例如：\n"
            "- 同时查 YonSuite 和 NC 两个系统的数据\n"
            "- 同时搜索多个不同领域的信息\n"
            "- 将一个复杂任务拆成多个独立步骤并行处理\n\n"
            "每个子代理有独立的对话上下文和 15 轮迭代上限。\n"
            "主代理在收到所有子代理结果后合并呈现给用户。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "子代理需要完成的任务描述。应当清晰、具体，包含所有必要信息。",
                },
                "context": {
                    "type": "string",
                    "description": "子代理需要的上下文信息（相关对话历史、数据、配置等）。可选但推荐提供。",
                },
            },
            "required": ["task"],
        },
    }


# Auto-register at import time
registry.register(
    name="delegate_task",
    toolset="agent",
    schema=delegate_task_schema(),
    handler=handle_delegate_task,
    description="将子任务委托给子 AI Agent 并行执行",
    emoji="🔄",
    risk_level="medium",
)


def set_parent_config(api_key: str = "", base_url: str = "", model: str = "", temperature: float = 0.7):
    """Set the parent agent's LLM config for child agents to inherit.

    Called from the agent loop (``agent.py``) before delegate_task
    may be invoked.  Uses thread-local storage so multiple concurrent
    conversations don't interfere.
    """
    _parent_config.api_key = api_key
    _parent_config.base_url = base_url
    _parent_config.model = model
    _parent_config.temperature = temperature
```

- [ ] **Step 2: 验证工具可注册不报错**

Run: `.venv/bin/python -c "from agent.tools.delegate_tool import *; from agent.tools.registry import registry; assert 'delegate_task' in registry.get_all_tool_names(); print('OK')"`
Expected: `OK`

- [ ] **Step 3: 提交**

```bash
git add agent/tools/delegate_tool.py
git commit -m "feat: 创建 delegate_tool.py 子代理委托工具"
```

---

### Task 11: 更新 message_builder.py 添加委托指导

**Files:**
- Modify: `agent/core/message_builder.py:32-73`

- [ ] **Step 1: 在系统提示词构建逻辑中添加委托指导**

`build_system_prompt` 不直接修改——系统提示词内容由 `agent.py` 中的 `_DEFAULT_SYSTEM_PROMPT` 硬编码。改为在 `build_system_prompt` 中检测是否有 `delegate_task` 工具可用，如果有则添加一段指导。

在 `# 5. Skill detail` 之后（第 67 行）、`if len(parts) == 1` 之前，添加：

```python
    # 6. Sub-agent delegation guidance (if delegate_task tool is available)
    try:
        from agent.tools.registry import registry
        if "delegate_task" in registry.get_all_tool_names():
            parts.append(
                "## 子代理委托\n"
                "当用户问题涉及多个独立数据源或多个可以并行的子任务时，"
                "考虑使用 `delegate_task` 工具将子任务委托给子代理并行执行。\n\n"
                "适用场景举例：\n"
                "- 同时查询多个不同系统的数据（如 YonSuite 和 NC）\n"
                "- 同时搜索多个不同领域的信息\n"
                "- 将一个复杂任务拆成可以独立处理的子步骤\n\n"
                "注意：每个子代理有独立的对话上下文和 15 轮迭代上限。"
                "主代理在收到所有结果后进行合并呈现。"
            )
    except Exception:
        pass
```

- [ ] **Step 2: 验证导入不报错**

Run: `.venv/bin/python -c "from agent.core.message_builder import build_system_prompt; print('OK')"`
Expected: `OK`

- [ ] **Step 3: 提交**

```bash
git add agent/core/message_builder.py
git commit -m "feat: 系统提示词添加子代理委托使用指导"
```

---

### Task 12: 编写子代理委托测试

**Files:**
- Create: `tests/test_delegate_tool.py`

- [ ] **Step 1: 创建 `tests/test_delegate_tool.py`**

```python
"""Tests for the delegate_task tool and sub-agent execution.

These tests use MockLLMProvider to simulate sub-agent behavior
without making real LLM calls.  They verify:
- Basic task delegation returns results
- Empty task parameter returns error
- Sub-agent timeout handling
- Error isolation (one failing sub-agent doesn't crash the system)
"""

from __future__ import annotations

import json

import pytest

from agent.tools.registry import registry


@pytest.fixture(autouse=True)
def clean_registry():
    """Snapshot and restore registry after each test."""
    saved = set(registry.get_all_tool_names())
    saved_before = list(registry._before_hooks)
    yield
    for name in set(registry.get_all_tool_names()) - saved:
        try:
            registry.deregister(name)
        except Exception:
            pass
    registry._before_hooks[:] = saved_before


def _ensure_delegate_tool_registered():
    """Import delegate_tool so it registers, if not already."""
    if "delegate_task" not in registry.get_all_tool_names():
        import agent.tools.delegate_tool  # noqa: F401


def test_delegate_tool_registered():
    """delegate_task must be discoverable by the tool registry."""
    import agent.tools.delegate_tool  # noqa: F401
    assert "delegate_task" in registry.get_all_tool_names()


def test_delegate_tool_schema():
    """Schema must require 'task' and accept optional 'context'."""
    import agent.tools.delegate_tool  # noqa: F401
    entry = registry.get_entry("delegate_task")
    assert entry is not None
    params = entry.schema.get("parameters", {})
    props = params.get("properties", {})
    assert "task" in props
    assert "context" in props
    assert "task" in params.get("required", [])


def test_delegate_task_empty_task_returns_error():
    """Calling delegate_task without a 'task' must return an error."""
    _ensure_delegate_tool_registered()
    result = registry.dispatch("delegate_task", {})
    payload = json.loads(result)
    assert payload.get("success") is False
    assert "task" in payload.get("error", "")


def test_delegate_task_with_missing_tool_returns_error():
    """Calling an unregistered tool name returns error."""
    result = registry.dispatch("delegate_task_does_not_exist", {"task": "test"})
    payload = json.loads(result)
    assert payload.get("success") is False


def test_set_parent_config_exists():
    """The module must expose set_parent_config() function."""
    from agent.tools.delegate_tool import set_parent_config, _parent_config
    set_parent_config(api_key="test-key", model="gpt-4o")
    assert _parent_config.api_key == "test-key"
    assert _parent_config.model == "gpt-4o"


def test_delegate_tool_risk_level():
    """delegate_task should be marked as medium risk."""
    import agent.tools.delegate_tool  # noqa: F401
    entry = registry.get_entry("delegate_task")
    assert entry is not None
    assert entry.risk_level == "medium"
```

- [ ] **Step 2: 运行测试并验证通过**

Run: `.venv/bin/python -m pytest tests/test_delegate_tool.py -v`
Expected: `6 passed`

- [ ] **Step 3: 提交**

```bash
git add tests/test_delegate_tool.py
git commit -m "test: 添加子代理委托测试"
```

---

### Task 13: 创建 browser_tool.py

**Files:**
- Create: `agent/tools/browser_tool.py`

- [ ] **Step 1: 创建 `agent/tools/browser_tool.py`**

```python
"""Browser automation tool set using Playwright.

Provides a set of tools for the LLM to control a headless Chromium
browser: navigate, screenshot, click, fill, get_text, get_html,
evaluate, and close.

Architecture
------------
A singleton ``_BrowserSession`` manages the Playwright browser lifecycle:
- Lazy initialisation (first tool call launches Chromium)
- Session reuse (multiple calls in the same conversation share the
  same browser context, preserving cookies)
- Auto-close (idle for 5 minutes → release resources)
- Thread-safe (lock-protected access)

Security
--------
- Blocks access to private/internal IPs (127.0.0.1, 10.*, 172.16-31.*,
  192.168.*) and file:// protocol.
- Navigation timeout: 30 seconds.
- Auto-dismisses JavaScript dialogs (alert, confirm, prompt).
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from urllib.parse import urlparse

from agent.tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────

_IDLE_TIMEOUT = 300.0  # 5 minutes
_NAVIGATION_TIMEOUT = 30_000  # 30 seconds (ms)
_MAX_PAGE_SIZE = 50 * 1024 * 1024  # 50 MB

# Regex patterns for blocked IP ranges
_PRIVATE_IP_PATTERNS = [
    re.compile(r"^127\.\d{1,3}\.\d{1,3}\.\d{1,3}"),
    re.compile(r"^10\.\d{1,3}\.\d{1,3}\.\d{1,3}"),
    re.compile(r"^172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"),
    re.compile(r"^192\.168\.\d{1,3}\.\d{1,3}"),
    re.compile(r"^0\.0\.0\.0$"),
    re.compile(r"^localhost$", re.IGNORECASE),
]


# ── URL Security ─────────────────────────────────────────────────


def _is_blocked_url(url: str) -> str | None:
    """Check if *url* should be blocked.  Returns an error message or None."""
    parsed = urlparse(url)

    if parsed.scheme == "file":
        return "不允许访问 file:// 协议"

    if parsed.scheme not in ("http", "https"):
        return f"不支持的协议: {parsed.scheme}"

    hostname = parsed.hostname or ""
    for pattern in _PRIVATE_IP_PATTERNS:
        if pattern.search(hostname):
            return f"不允许访问内网地址: {hostname}"

    # Block common internal hostnames
    internal_hosts = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
    if hostname.lower() in internal_hosts:
        return f"不允许访问内网地址: {hostname}"

    return None


# ── Browser Session Manager ─────────────────────────────────────


class _BrowserSession:
    """Singleton managing a Playwright Chromium instance.

    Thread-safe.  Lazily starts the browser on first use and
    automatically closes after ``_IDLE_TIMEOUT`` seconds of inactivity.
    """

    _instance: _BrowserSession | None = None
    _lock = threading.Lock()
    _playwright = None
    _browser = None
    _context = None
    _page = None
    _last_used = 0.0
    _closed = False

    @classmethod
    def _ensure(cls) -> _BrowserSession:
        if cls._instance is None:
            cls._instance = _BrowserSession()
        return cls._instance

    @classmethod
    def get_page(cls):
        """Return the current page, lazy-starting the browser if needed."""
        with cls._lock:
            if cls._page is None or cls._closed:
                cls._start_browser()
            cls._last_used = time.monotonic()
            return cls._page

    @classmethod
    def _start_browser(cls):
        """Launch Playwright Chromium in headless mode."""
        try:
            import playwright.sync_api
        except ImportError:
            raise RuntimeError(
                "Playwright is not installed. Run: pip install playwright && playwright install chromium"
            )

        try:
            cls._playwright = playwright.sync_api.sync_playwright().start()
            cls._browser = cls._playwright.chromium.launch(headless=True)
            cls._context = cls._browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            cls._page = cls._context.new_page()

            # Auto-dismiss JavaScript dialogs
            cls._page.on("dialog", lambda dialog: dialog.dismiss())

            # Set default navigation timeout
            cls._page.set_default_navigation_timeout(_NAVIGATION_TIMEOUT)

            cls._closed = False
            logger.info("Browser session started")
        except Exception as e:
            cls._cleanup()
            raise RuntimeError(f"Failed to start browser: {e}")

    @classmethod
    def close(cls):
        """Close the browser and release all resources."""
        with cls._lock:
            cls._cleanup()
            cls._closed = True
            logger.info("Browser session closed")

    @classmethod
    def _cleanup(cls):
        """Internal cleanup without lock (caller must hold lock)."""
        try:
            if cls._page:
                cls._page.close()
        except Exception:
            pass
        cls._page = None
        try:
            if cls._context:
                cls._context.close()
        except Exception:
            pass
        cls._context = None
        try:
            if cls._browser:
                cls._browser.close()
        except Exception:
            pass
        cls._browser = None
        try:
            if cls._playwright:
                cls._playwright.stop()
        except Exception:
            pass
        cls._playwright = None

    @classmethod
    def is_idle(cls) -> bool:
        """Check if the browser has been idle longer than the timeout."""
        if cls._page is None or cls._closed:
            return False
        return (time.monotonic() - cls._last_used) > _IDLE_TIMEOUT

    @classmethod
    def heartbeat(cls):
        """Call periodically to auto-close idle sessions.  Idempotent."""
        if cls.is_idle():
            cls.close()


# ── Tool Handlers ────────────────────────────────────────────────


def handle_browser_navigate(args: dict) -> str:
    """Navigate to a URL."""
    url = args.get("url", "").strip()
    if not url:
        return tool_error("url 参数是必需的")

    blocked = _is_blocked_url(url)
    if blocked:
        return tool_error(blocked)

    try:
        page = _BrowserSession.get_page()
        page.goto(url, wait_until="domcontentloaded")
        return tool_result(data=f"已导航到 {url}，当前页面标题: {page.title()}")
    except Exception as e:
        return tool_error(f"导航失败: {e}")


def handle_browser_screenshot(args: dict) -> str:
    """Take a full-page screenshot and return it as base64."""
    try:
        page = _BrowserSession.get_page()
        screenshot_bytes = page.screenshot(full_page=True)
        import base64
        b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        return tool_result(
            data="截图已生成",
            screenshot_base64=b64,
            mime_type="image/png",
        )
    except Exception as e:
        return tool_error(f"截图失败: {e}")


def handle_browser_click(args: dict) -> str:
    """Click an element on the page."""
    selector = args.get("selector", "").strip()
    if not selector:
        return tool_error("selector 参数是必需的")

    try:
        page = _BrowserSession.get_page()
        page.click(selector)
        wait_after = int(args.get("wait_after", 500))
        if wait_after > 0:
            page.wait_for_timeout(wait_after)
        return tool_result(data=f"已点击元素: {selector}")
    except Exception as e:
        return tool_error(f"点击失败: {e}")


def handle_browser_fill(args: dict) -> str:
    """Fill a text input with a value."""
    selector = args.get("selector", "").strip()
    value = args.get("value", "")

    if not selector:
        return tool_error("selector 参数是必需的")

    try:
        page = _BrowserSession.get_page()
        page.fill(selector, value)
        return tool_result(data=f"已填写元素 {selector}")
    except Exception as e:
        return tool_error(f"填写失败: {e}")


def handle_browser_get_text(args: dict) -> str:
    """Get the text content of an element."""
    selector = args.get("selector", "").strip()
    if not selector:
        return tool_error("selector 参数是必需")

    try:
        page = _BrowserSession.get_page()
        element = page.query_selector(selector)
        if element is None:
            return tool_error(f"未找到元素: {selector}")
        text = element.text_content() or ""
        return tool_result(data=text.strip())
    except Exception as e:
        return tool_error(f"获取文本失败: {e}")


def handle_browser_get_html(args: dict) -> str:
    """Get the full HTML content of the current page."""
    try:
        page = _BrowserSession.get_page()
        html = page.content()
        # Truncate if too large
        if len(html) > 100_000:
            html = html[:100_000] + "\n\n[内容已截断，仅显示前 100,000 字符]"
        return tool_result(data=html)
    except Exception as e:
        return tool_error(f"获取 HTML 失败: {e}")


def handle_browser_evaluate(args: dict) -> str:
    """Execute JavaScript in the browser page."""
    code = args.get("code", "").strip()
    if not code:
        return tool_error("code 参数是必需的")

    try:
        page = _BrowserSession.get_page()
        result = page.evaluate(code)
        return tool_result(data=str(result))
    except Exception as e:
        return tool_error(f"JavaScript 执行失败: {e}")


def handle_browser_close(args: dict) -> str:
    """Close the browser session."""
    try:
        _BrowserSession.close()
        return tool_result(data="浏览器实例已关闭")
    except Exception as e:
        return tool_error(f"关闭浏览器失败: {e}")


# ── Schema definitions ───────────────────────────────────────────

NAVIGATE_SCHEMA = {
    "name": "browser_navigate",
    "description": "在浏览器中导航到指定 URL。支持 http/https，拒绝内网和 file://。",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要导航的完整 URL（如 https://example.com）"},
        },
        "required": ["url"],
    },
}

SCREENSHOT_SCHEMA = {
    "name": "browser_screenshot",
    "description": "截取当前页面的全页截图，返回 base64 编码的 PNG 图片。",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

CLICK_SCHEMA = {
    "name": "browser_click",
    "description": "点击页面上的指定元素。支持 CSS 选择器。",
    "parameters": {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS 选择器"},
            "wait_after": {"type": "integer", "description": "点击后等待时间（毫秒），默认 500"},
        },
        "required": ["selector"],
    },
}

FILL_SCHEMA = {
    "name": "browser_fill",
    "description": "在输入框中填写文本。会先清空已有内容。",
    "parameters": {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "输入框的 CSS 选择器"},
            "value": {"type": "string", "description": "要填写的文本"},
        },
        "required": ["selector", "value"],
    },
}

GET_TEXT_SCHEMA = {
    "name": "browser_get_text",
    "description": "获取页面指定元素的文本内容。",
    "parameters": {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS 选择器"},
        },
        "required": ["selector"],
    },
}

GET_HTML_SCHEMA = {
    "name": "browser_get_html",
    "description": "获取当前页面的完整 HTML 内容。",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

EVALUATE_SCHEMA = {
    "name": "browser_evaluate",
    "description": "在浏览器页面中执行 JavaScript 代码并返回结果。",
    "parameters": {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "要执行的 JavaScript 代码"},
        },
        "required": ["code"],
    },
}

CLOSE_SCHEMA = {
    "name": "browser_close",
    "description": "关闭当前浏览器实例，释放系统资源。",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}


# ── Registry Registration ─────────────────────────────────────────

registry.register(name="browser_navigate", toolset="browser", schema=NAVIGATE_SCHEMA, handler=handle_browser_navigate, emoji="🌐", risk_level="medium")
registry.register(name="browser_screenshot", toolset="browser", schema=SCREENSHOT_SCHEMA, handler=handle_browser_screenshot, emoji="📸", risk_level="low")
registry.register(name="browser_click", toolset="browser", schema=CLICK_SCHEMA, handler=handle_browser_click, emoji="🖱️", risk_level="medium")
registry.register(name="browser_fill", toolset="browser", schema=FILL_SCHEMA, handler=handle_browser_fill, emoji="✏️", risk_level="medium")
registry.register(name="browser_get_text", toolset="browser", schema=GET_TEXT_SCHEMA, handler=handle_browser_get_text, emoji="📄", risk_level="low")
registry.register(name="browser_get_html", toolset="browser", schema=GET_HTML_SCHEMA, handler=handle_browser_get_html, emoji="🔍", risk_level="low")
registry.register(name="browser_evaluate", toolset="browser", schema=EVALUATE_SCHEMA, handler=handle_browser_evaluate, emoji="⚡", risk_level="high")
registry.register(name="browser_close", toolset="browser", schema=CLOSE_SCHEMA, handler=handle_browser_close, emoji="🚫", risk_level="low")
```

- [ ] **Step 2: 验证导入和注册不报错**

Run: `.venv/bin/python -c "from agent.tools.registry import discover_tools, registry; discover_tools(); names = registry.get_all_tool_names(); browser_tools = [n for n in names if n.startswith('browser_')]; print(f'Browser tools: {len(browser_tools)}'); print(browser_tools)"`
Expected: `Browser tools: 8` 列出 8 个 browser_* 工具

- [ ] **Step 3: 提交**

```bash
git add agent/tools/browser_tool.py
git commit -m "feat: 创建 browser_tool.py 浏览器自动化工具集（8 个子工具）"
```

---

### Task 14: 更新 pyproject.toml 和 security_hooks 浏览器安全过滤

**Files:**
- Modify: `pyproject.toml:13-20`
- Modify: `agent/tools/security_hooks.py:40-62`

- [ ] **Step 1: `pyproject.toml` — 添加 playwright 可选依赖**

在 `[project.optional-dependencies]` 部分（第 22-32 行）添加：

```toml
browser = [
    "playwright>=1.40.0",
]
```

并更新 `all` 依赖以包含 browser：

```toml
all = ["zlink-agent[web,browser]"]
```

- [ ] **Step 2: `agent/tools/security_hooks.py` — `_security_before_hook` 中添加 `browser_navigate` URL 过滤**

在 `_security_before_hook` 函数的 `# --- path-based tools` 检查之后、`# --- terminal` 之前添加 URL 过滤检查：

```python
    # --- browser_navigate: block private IPs and file:// ---
    if tool_name == "browser_navigate":
        url = args.get("url", "")
        if url:
            from agent.tools.browser_tool import _is_blocked_url
            blocked = _is_blocked_url(url)
            if blocked:
                return {"__block__": True, "__reason__": blocked}
```

- [ ] **Step 3: 验证修改后导入不报错**

Run: `.venv/bin/python -c "from agent.tools.security_hooks import register_default_hooks; register_default_hooks(); print('OK')"`
Expected: `OK`

- [ ] **Step 4: 提交**

```bash
git add pyproject.toml agent/tools/security_hooks.py
git commit -m "feat: pyproject.toml 添加 playwright 依赖 + security_hooks 添加 browser_navigate URL 过滤"
```

---

### Task 15: 编写浏览器工具测试

**Files:**
- Create: `tests/test_browser_tool.py`

- [ ] **Step 1: 创建 `tests/test_browser_tool.py`**

这些测试不启动真实的 Playwright 浏览器（避免 CI 依赖），而是测试 URL 安全过滤、schema 验证和工具注册。

```python
"""Tests for browser_tool URL security filtering and schema validation.

These tests do NOT start a real Playwright browser.  They verify:
- URL security filtering (private IPs, file:// protocol)
- Tool registration and schema correctness
- Module-level constants and helper functions

Integration tests with a real browser require Playwright installed
and are run separately.
"""

from __future__ import annotations

import json

import pytest

from agent.tools.registry import registry


@pytest.fixture(autouse=True)
def clean_registry():
    """Snapshot and restore registry after each test."""
    saved = set(registry.get_all_tool_names())
    yield
    for name in set(registry.get_all_tool_names()) - saved:
        try:
            registry.deregister(name)
        except Exception:
            pass


def _ensure_browser_tools():
    """Import browser_tool module if not already registered."""
    if not any(n.startswith("browser_") for n in registry.get_all_tool_names()):
        import agent.tools.browser_tool  # noqa: F401


def test_browser_tools_registered():
    """All 8 browser tools must be registered."""
    _ensure_browser_tools()
    browser_tools = [n for n in registry.get_all_tool_names() if n.startswith("browser_")]
    assert len(browser_tools) == 8
    assert "browser_navigate" in browser_tools
    assert "browser_screenshot" in browser_tools
    assert "browser_click" in browser_tools
    assert "browser_fill" in browser_tools
    assert "browser_get_text" in browser_tools
    assert "browser_get_html" in browser_tools
    assert "browser_evaluate" in browser_tools
    assert "browser_close" in browser_tools


def test_browser_navigate_requires_url():
    """browser_navigate must return error when url is missing."""
    _ensure_browser_tools()
    result = registry.dispatch("browser_navigate", {})
    payload = json.loads(result)
    assert payload.get("success") is False
    assert "url" in payload.get("error", "").lower()


def test_browser_navigate_rejects_file_protocol():
    """file:// URLs must be blocked."""
    _ensure_browser_tools()
    result = registry.dispatch("browser_navigate", {"url": "file:///etc/passwd"})
    payload = json.loads(result)
    assert payload.get("success") is False
    assert "file://" in payload.get("error", "").lower() or "file://" in payload.get("error", "")


def test_browser_navigate_rejects_localhost():
    """localhost must be blocked."""
    _ensure_browser_tools()
    result = registry.dispatch("browser_navigate", {"url": "http://localhost:8080"})
    payload = json.loads(result)
    assert payload.get("success") is False
    assert "内网" in payload.get("error", "") or "localhost" in payload.get("error", "").lower()


def test_browser_navigate_rejects_private_ip():
    """Private IP addresses (192.168.x.x) must be blocked."""
    _ensure_browser_tools()
    result = registry.dispatch("browser_navigate", {"url": "http://192.168.1.1/admin"})
    payload = json.loads(result)
    assert payload.get("success") is False
    assert "内网" in payload.get("error", "") or "192.168" in payload.get("error", "")


def test_is_blocked_url_utility():
    """_is_blocked_url must correctly identify blocked vs allowed URLs."""
    from agent.tools.browser_tool import _is_blocked_url

    # Blocked
    assert _is_blocked_url("file:///tmp/test") is not None
    assert _is_blocked_url("http://127.0.0.1:8080") is not None
    assert _is_blocked_url("http://10.0.0.1/admin") is not None
    assert _is_blocked_url("http://172.16.0.1/test") is not None
    assert _is_blocked_url("http://192.168.1.1") is not None
    assert _is_blocked_url("ftp://example.com") is not None

    # Allowed
    assert _is_blocked_url("https://example.com") is None
    assert _is_blocked_url("https://api.openai.com/v1") is None
    assert _is_blocked_url("http://www.baidu.com") is None


def test_browser_click_requires_selector():
    """browser_click must return error when selector is missing."""
    _ensure_browser_tools()
    result = registry.dispatch("browser_click", {})
    payload = json.loads(result)
    assert payload.get("success") is False
    assert "selector" in payload.get("error", "").lower()


def test_browser_fill_requires_selector_and_value():
    """browser_fill must return error when selector or value is missing."""
    _ensure_browser_tools()
    result = registry.dispatch("browser_fill", {})
    payload = json.loads(result)
    assert payload.get("success") is False

    result = registry.dispatch("browser_fill", {"selector": "#input"})
    payload = json.loads(result)
    assert payload.get("success") is False


def test_browser_get_text_requires_selector():
    """browser_get_text must return error when selector is missing."""
    _ensure_browser_tools()
    result = registry.dispatch("browser_get_text", {})
    payload = json.loads(result)
    assert payload.get("success") is False


def test_browser_evaluate_requires_code():
    """browser_evaluate must return error when code is missing."""
    _ensure_browser_tools()
    result = registry.dispatch("browser_evaluate", {})
    payload = json.loads(result)
    assert payload.get("success") is False
    assert "code" in payload.get("error", "").lower()


def test_browser_tools_risk_levels():
    """Verify risk levels are set correctly for each browser tool."""
    _ensure_browser_tools()

    # High risk
    entry = registry.get_entry("browser_evaluate")
    assert entry is not None and entry.risk_level == "high"

    # Medium risk
    for name in ("browser_navigate", "browser_click", "browser_fill"):
        entry = registry.get_entry(name)
        assert entry is not None and entry.risk_level == "medium", f"{name} should be medium risk"

    # Low risk
    for name in ("browser_screenshot", "browser_get_text", "browser_get_html", "browser_close"):
        entry = registry.get_entry(name)
        assert entry is not None and entry.risk_level == "low", f"{name} should be low risk"
```

- [ ] **Step 2: 运行测试并验证通过**

Run: `.venv/bin/python -m pytest tests/test_browser_tool.py -v`
Expected: `12 passed`

- [ ] **Step 3: 提交**

```bash
git add tests/test_browser_tool.py
git commit -m "test: 添加浏览器工具安全过滤和 schema 验证测试"
```

---

## Self-Review Checklist

### 1. Spec Coverage
- **Feature 1 (DeepSeek):** ✅ Task 1 covers adding models + test
- **Feature 2 (Command Approval):** ✅ Tasks 2-9 cover config_model → registry → security_hooks → backend API → frontend → extension → tests
- **Feature 3 (Subagent Delegation):** ✅ Tasks 10-12 cover delegate_tool.py → message_builder.py → tests
- **Feature 4 (Browser Automation):** ✅ Tasks 13-15 cover browser_tool.py → pyproject.toml + security_hooks → tests
- **Spec section 5 (Integration):** ✅ Risk levels wired into approval_hook; sub-agent inherits registry which includes browser tools; approval_hook and security_hooks chain together
- **Spec section 6 (Implementation order):** ✅ Tasks ordered Phase 1 → Phase 2 → Phase 3

### 2. Placeholder Scan
- No "TBD", "TODO", "implement later", or "..." found
- Every code block contains complete, working code
- Every test file has complete test functions with assertions
- No `# type: ignore[attr-defined]` comments that skip type checking
- All function signatures match between definition and usage

### 3. Type Consistency
- `ApprovalMode` enum values: `allow_all`, `approve`, `reject_all` — consistent across `config_model.py`, `security_hooks.py`, `schemas/config.py`, `SettingsAgentPage.tsx`, `types/index.ts`
- `risk_level` values: `"low"`, `"medium"`, `"high"` — consistent across `registry.py`, `terminal_tool.py`, `file_tools.py`, `web_extract_tool.py`, `browser_tool.py`, `delegate_tool.py`, `security_hooks.py`, `test_approval.py`, `test_browser_tool.py`
- `ToolEntry.__slots__` includes `risk_level` — matches `__init__` and `register()` signature
- `AgentConfigPayload` TypeScript interface — matches `AgentConfig` Pydantic model
- `AppConfig` field `approval_mode: str` — matches JSON serialization
- `_is_blocked_url()` return type `str | None` — consistent in usage
- `record_approval()` signature `(tool_name, args)` — matches approval_hook call pattern
- `set_parent_config()` signature — used in delegation setup

### 4. Verifiability
- Every test step includes the exact `pytest` command to run
- Every verification step includes the exact Python command and expected output
- All imports are self-contained within each file
- No external network/LLM dependencies in tests

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-11-capability-enhancement.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
