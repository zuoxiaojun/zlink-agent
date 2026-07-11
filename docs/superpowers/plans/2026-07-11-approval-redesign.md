# Approval Redesign — Thread-Blocking Approval System

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-subagent-driven-development (recommended) or superpowers-executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the LLM-driven approval flow (where the LLM calls `confirm_tool_execution` and retries) with an agent-thread-blocking flow where `ApprovalBlockedError` pauses the agent thread, sends an approval request to the frontend, and resumes on user response.

**Architecture:** A custom `ApprovalBlockedError` exception is raised by `approval_hook` instead of returning `__block__` dicts. The agent's `_run_tool_calls` catches it, creates an `ApprovalRequest` with a `threading.Event`, and blocks. The WebSocket layer in `chat.py` forwards the request to the frontend and resolves the event when the user responds. The old `confirm_tool_execution` tool and approval cache system are removed.

**Tech Stack:** Python 3.11+ / FastAPI / React 18+ / TypeScript / threading.Event

---

## File Structure & Responsibility

| File | Action | Responsibility |
|------|--------|---------------|
| `agent/tools/security_hooks.py` | Modify | Add `ApprovalBlockedError`; `approval_hook` raises it instead of returning block dict; remove approval cache |
| `agent/core/agent.py` | Modify | Add `ApprovalRequest` dataclass; `approval_callback` param; catch `ApprovalBlockedError` in `_run_tool_calls` |
| `agent/tools/registry.py` | Modify | `dispatch()` lets `ApprovalBlockedError` propagate instead of catching it |
| `backend/api/chat.py` | Modify | `_pending_approval` management; `approval_callback` bridges agent thread → WebSocket; handle `approval_response` message |
| `agent/tools/confirm_tool.py` | Delete | No longer needed — LLM doesn't participate in approval |
| `agent/core/message_builder.py` | Modify | Remove section 7 (approval guidance for LLM) |
| `tests/test_approval.py` | Modify | Update for exception-based model; add agent-loop integration test; remove cache tests |
| `web/src/types/index.ts` | Modify | Add `approval_request` / `approval_response` WebSocket types |
| `web/src/context/AppContext.tsx` | Modify | Add `pendingApproval` state + reducer actions |
| `web/src/components/ApprovalCard.tsx` | Create | Approval confirmation UI (fixed above input, not in message list) |
| `web/src/hooks/useChat.ts` | Modify | Handle `approval_request` WebSocket message |
| `web/src/pages/ChatPage.tsx` | Modify | Render `ApprovalCard`; send `approval_response` via WebSocket |
| `web/src/styles/global.css` | Modify | Add `.approval-card` styles |
| `web/src/api/ws.ts` | No change | Already handles arbitrary JSON messages |

---

## Task 1: ApprovalBlockedError + approval_hook exception mode

**Files:**
- Modify: `agent/tools/security_hooks.py`
- Test: `tests/test_approval.py`

- [ ] **Step 1.1: Write the failing test for ApprovalBlockedError**

Add this test to `tests/test_approval.py` (after the existing imports):

```python
def test_approval_hook_raises_approval_blocked_error(monkeypatch):
    """In approve mode, high-risk tools cause approval_hook to raise ApprovalBlockedError."""
    from agent.tools.security_hooks import approval_hook, ApprovalBlockedError
    from agent.config_model import AppConfig

    _register_test_tool("test_high", risk_level="high")

    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="approve"),
    )

    with pytest.raises(ApprovalBlockedError) as exc_info:
        approval_hook("test_high", {"path": "/tmp/test"})

    assert exc_info.value.tool_name == "test_high"
    assert exc_info.value.args == {"path": "/tmp/test"}
    assert "需要你的确认" in exc_info.value.reason
```

- [ ] **Step 1.2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_approval.py::test_approval_hook_raises_approval_blocked_error -v
```

Expected: `FAILED` with `ImportError: cannot import name 'ApprovalBlockedError'`

- [ ] **Step 1.3: Add ApprovalBlockedError to security_hooks.py**

Add the exception class right after the logger definition (around line 16):

```python
class ApprovalBlockedError(Exception):
    """Raised by approval_hook when a high-risk tool is blocked in approve mode.

    The agent loop catches this exception and blocks the thread, waiting for
    user approval via the frontend.
    """

    def __init__(self, tool_name: str, args: dict, reason: str):
        self.tool_name = tool_name
        self.args = args
        self.reason = reason
        super().__init__(reason)
```

- [ ] **Step 1.4: Modify approval_hook to raise ApprovalBlockedError in approve mode**

Replace the `if mode == "approve" and risk == "high":` block in `approval_hook()` (lines 116-138). Old code:

```python
    if mode == "approve" and risk == "high":
        with _approval_lock:
            # 优先检查精确匹配（tool_name + args）
            key = f"{tool_name}:{json.dumps(args, ensure_ascii=False, sort_keys=True)}"
            ts = _APPROVED_CALLS.get(key)
            if ts is not None and (time.monotonic() - ts) < _APPROVAL_TTL:
                return args
            # 其次检查通配匹配（仅 tool_name, 由 confirm_tool_execution 写入）
            wild_key = f"{tool_name}:*"
            ts = _APPROVED_CALLS.get(wild_key)
            if ts is not None and (time.monotonic() - ts) < _APPROVAL_TTL:
                # 通配 key 使用后立即消耗，防止同一审批重复执行
                del _APPROVED_CALLS[wild_key]
                return args
        return {
            "__block__": True,
            "__reason__": (
                f"⚠️ 需要你的确认才能执行以下操作：\n"
                f"工具: {tool_name}\n"
                f"参数: {json.dumps(dict(args), ensure_ascii=False)}\n"
                f"请在聊天中回复「批准」或「拒绝」。"
            ),
        }
```

New code:

```python
    if mode == "approve" and risk == "high":
        raise ApprovalBlockedError(
            tool_name=tool_name,
            args=dict(args),
            reason=(
                f"需要你的确认才能执行以下操作：\n"
                f"工具: {tool_name}\n"
                f"参数: {json.dumps(dict(args), ensure_ascii=False)}"
            ),
        )
```

- [ ] **Step 1.5: Remove unused approval cache code**

Delete these lines from `security_hooks.py`:

```python
# Lines 77-79: Cache of approved tool calls
_APPROVED_CALLS: dict[str, float] = {}
_APPROVAL_TTL = 60.0  # seconds before an approval expires
_approval_lock = threading.Lock()
```

Delete the `record_approval` function (lines 143-152) and `clear_approvals` function (lines 155-158).

Also remove unused imports: `threading` and `time` are no longer needed after removing the cache code. Delete the line `import threading` and `import time`. The remaining imports are `json` and `logging`.

- [ ] **Step 1.6: Run the test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_approval.py::test_approval_hook_raises_approval_blocked_error -v
```

Expected: `PASSED`

- [ ] **Step 1.7: Commit**

```bash
git add agent/tools/security_hooks.py tests/test_approval.py
git commit -m "feat(security): add ApprovalBlockedError exception, approval_hook raises instead of returning block dict"
```

---

## Task 2: Update registry.dispatch to propagate ApprovalBlockedError

**Files:**
- Modify: `agent/tools/registry.py`
- Test: `tests/test_approval.py`

- [ ] **Step 2.1: Write failing test for registry propagation**

Add to `tests/test_approval.py`:

```python
def test_registry_dispatch_propagates_approval_blocked_error(monkeypatch):
    """registry.dispatch() must let ApprovalBlockedError propagate to the agent loop."""
    from agent.tools.security_hooks import approval_hook, ApprovalBlockedError
    from agent.config_model import AppConfig

    _register_test_tool("test_high", risk_level="high")

    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="approve"),
    )

    registry.add_before_hook(approval_hook)
    try:
        with pytest.raises(ApprovalBlockedError) as exc_info:
            registry.dispatch("test_high", {"cmd": "rm -rf /"})
        assert exc_info.value.tool_name == "test_high"
        assert exc_info.value.args == {"cmd": "rm -rf /"}
    finally:
        registry.remove_before_hook(approval_hook)
```

- [ ] **Step 2.2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_approval.py::test_registry_dispatch_propagates_approval_blocked_error -v
```

Expected: `FAILED` — currently `registry.dispatch` catches all exceptions and returns `tool_error("Hook blocked execution: ...")`

- [ ] **Step 2.3: Modify registry.dispatch to let ApprovalBlockedError through**

**Important:** Do NOT add a module-level import of `ApprovalBlockedError` in `registry.py` — `security_hooks.py` already imports `registry` from `registry.py`, creating a circular dependency. Instead, use `type(e).__name__` to identify the exception without importing it.

Modify the before-hook loop in `dispatch()` (around lines 207-215). Old code:

```python
        for hook in self._before_hooks:
            try:
                args = hook(name, args)
                if args.get("__block__"):
                    return tool_error(args.get("__reason__", "Blocked by hook"))
            except Exception as e:
                logger.warning("Before-hook failed for tool %s: %s", name, e)
                return tool_error(f"Hook blocked execution: {e}")
```

New code:

```python
        for hook in self._before_hooks:
            try:
                args = hook(name, args)
                if args.get("__block__"):
                    return tool_error(args.get("__reason__", "Blocked by hook"))
            except Exception as e:
                # ApprovalBlockedError must propagate to the agent loop;
                # avoid circular import by checking type name
                if type(e).__name__ == "ApprovalBlockedError":
                    raise
                logger.warning("Before-hook failed for tool %s: %s", name, e)
                return tool_error(f"Hook blocked execution: {e}")
```

- [ ] **Step 2.4: Run test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_approval.py::test_registry_dispatch_propagates_approval_blocked_error -v
```

Expected: `PASSED`

- [ ] **Step 2.5: Commit**

```bash
git add agent/tools/registry.py tests/test_approval.py
git commit -m "feat(registry): propagate ApprovalBlockedError through dispatch() instead of catching it"
```

---

## Task 3: Update all existing approval tests for new exception model

**Files:**
- Modify: `tests/test_approval.py`

- [ ] **Step 3.1: Rewrite test_approve_mode_blocks_high_risk**

Replace the body of `test_approve_mode_blocks_high_risk` (currently checks `__block__` in result) with:

```python
def test_approve_mode_blocks_high_risk(monkeypatch):
    """When approval_mode='approve', high-risk tools raise ApprovalBlockedError."""
    _register_test_tool("test_low", risk_level="low")
    _register_test_tool("test_high", risk_level="high")
    hook, _, _ = _make_approval_hook()

    from agent.config_model import AppConfig

    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="approve"),
    )

    # Low risk still passes
    result = hook("test_low", {})
    assert "__block__" not in result

    # High risk blocked with exception
    with pytest.raises(Exception) as exc_info:
        hook("test_high", {"path": "/tmp/test"})
    # Should be ApprovalBlockedError
    assert "需要你的确认" in str(exc_info.value)
```

- [ ] **Step 3.2: Remove cache-dependent tests**

Delete these tests entirely from `tests/test_approval.py`:

1. `test_approve_mode_passes_pre_approved_calls` — relies on `record_approval()` cache which is removed
2. `test_approval_cache_expires` — relies on `_APPROVED_CALLS` cache which is removed

- [ ] **Step 3.3: Update test_approval_integration_with_dispatch**

Replace the body of `test_approval_integration_with_dispatch` with:

```python
def test_approval_integration_with_dispatch(monkeypatch):
    """End-to-end: approval_hook via registry.dispatch() raises ApprovalBlockedError."""
    _register_test_tool("test_high", risk_level="high")
    hook, _, _ = _make_approval_hook()

    from agent.config_model import AppConfig

    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="approve"),
    )

    registry.add_before_hook(hook)
    try:
        # Without approval → raises
        with pytest.raises(Exception) as exc_info:
            registry.dispatch("test_high", {"x": "y"})
        assert "需要你的确认" in str(exc_info.value)
    finally:
        registry.remove_before_hook(hook)
```

- [ ] **Step 3.4: Update test_approval_hook_raises_approval_blocked_error imports**

Ensure `_make_approval_hook` no longer imports `record_approval` and `clear_approvals` (they were removed). Update `_make_approval_hook`:

```python
def _make_approval_hook():
    """Import and return a fresh approval_hook with clean state."""
    from agent.tools.security_hooks import approval_hook

    return approval_hook, None, None
```

- [ ] **Step 3.5: Remove unused imports from test_approval.py top**

Remove `time` from imports (no longer needed). The final imports should be:

```python
from __future__ import annotations

import json

import pytest

from agent.tools.registry import registry
```

- [ ] **Step 3.6: Run all approval tests to verify**

```bash
.venv/bin/python -m pytest tests/test_approval.py -v
```

Expected: All remaining tests PASS

- [ ] **Step 3.7: Commit**

```bash
git add tests/test_approval.py
git commit -m "test(approval): update tests for exception-based approval model, remove cache-dependent tests"
```

---

## Task 4: Delete confirm_tool.py

**Files:**
- Delete: `agent/tools/confirm_tool.py`

- [ ] **Step 4.1: Remove the file**

```bash
rm /Users/zuoxiaojun/vibecoding/zlink-agent/agent/tools/confirm_tool.py
```

- [ ] **Step 4.2: Verify it no longer registers**

Run the tool discovery check:

```bash
.venv/bin/python -c "
from agent.tools.registry import discover_tools, registry
discover_tools()
assert 'confirm_tool_execution' not in registry.get_all_tool_names(), 'confirm_tool_execution still registered'
print('OK: confirm_tool_execution not in registry')
"
```

Expected: `OK: confirm_tool_execution not in registry`

- [ ] **Step 4.3: Commit**

```bash
git add -A
git commit -m "chore: remove confirm_tool.py — LLM no longer participates in approval flow"
```

---

## Task 5: Remove approval guidance from message_builder.py

**Files:**
- Modify: `agent/core/message_builder.py`

- [ ] **Step 5.1: Remove section 7 from build_system_prompt**

Delete lines 90-111 from `agent/core/message_builder.py` (the entire "7. Approval guidance" section). The code to remove:

```python
    # 7. Approval guidance (if confirm_tool_execution tool is available)
    try:
        from agent.tools.registry import registry

        if "confirm_tool_execution" in registry.get_all_tool_names():
            parts.append(
                "## 高风险操作审批\n"
                "当安全系统因审批模式（approval_mode=approve）拦截了一个高风险工具调用时，"
                "你会收到一条包含「需要你的确认」的阻断消息。\n\n"
                "此时你应该：\n"
                "1. 向用户解释需要执行的操作及其影响\n"
                "2. 如果用户批准，调用 `confirm_tool_execution` 工具来确认执行\n"
                "3. 如果用户拒绝，告知用户操作已取消\n\n"
                "示例：\n"
                "用户：帮我删除 /tmp/test.sql\n"
                "→ 你：调用 file_delete → 被拦截\n"
                "→ 你：系统拦截了 file_delete(/tmp/test.sql)，是否批准执行？\n"
                "用户：批准\n"
                "→ 你：调用 confirm_tool_execution(tool_name=\"file_delete\", args={path: \"/tmp/test.sql\"})"
            )
    except ImportError:
        pass
```

- [ ] **Step 5.2: Update the comment numbering**

Change the comment on line 71 from `# 6. Sub-agent delegation guidance` to `# 6. Sub-agent delegation guidance (no section 7 anymore)`. The remaining sections 1-6 keep their numbering (the list is sequential in code, not by comment number).

- [ ] **Step 5.3: Verify no imports break**

```bash
.venv/bin/python -c "from agent.core.message_builder import build_system_prompt; print('OK')"
```

Expected: `OK`

- [ ] **Step 5.4: Commit**

```bash
git add agent/core/message_builder.py
git commit -m "chore(message_builder): remove approval guidance for LLM — approval is now transparent to the LLM"
```

---

## Task 6: ApprovalRequest + approval_callback in AIAgent

**Files:**
- Modify: `agent/core/agent.py`
- Test: `tests/test_approval.py`

- [ ] **Step 6.1: Write failing test for approval flow through agent loop**

Add to `tests/test_approval.py`:

```python
def test_agent_loop_catches_approval_blocked_error(monkeypatch):
    """When a high-risk tool is called in approve mode, the agent loop blocks
    and calls approval_callback with an ApprovalRequest."""
    import threading
    from agent.core.agent import AIAgent, ApprovalRequest
    from agent.core.llm_client import LLMClient
    from tests.conftest import MockLLMProvider, make_tool_call_response, make_text_response
    from agent.config_model import AppConfig

    # Register a high-risk test tool
    _register_test_tool("test_delete", risk_level="high")

    # Set approval mode to 'approve'
    monkeypatch.setattr(
        "agent.config_manager.load",
        lambda: AppConfig(approval_mode="approve"),
    )

    captured_req: list[ApprovalRequest] = []

    def on_approval(req: ApprovalRequest):
        captured_req.append(req)

    provider = MockLLMProvider(
        responses=[
            make_tool_call_response("test_delete", {"path": "/tmp/test.sql"}),
            make_text_response("done"),
        ]
    )
    agent = AIAgent(
        api_key="sk-fake",
        base_url="x",
        model="gpt-4o",
        max_iterations=3,
        approval_callback=on_approval,
    )
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    # Run agent in a thread so we can resolve the approval from the main thread
    result_holder = []

    def run():
        result_holder.append(agent.run_conversation("delete the file"))

    t = threading.Thread(target=run, daemon=True)
    t.start()

    # Wait for approval request
    t.join(timeout=5)
    assert len(captured_req) >= 1, "approval_callback should have been called"
    req = captured_req[0]
    assert req.tool_name == "test_delete"
    assert req.args == {"path": "/tmp/test.sql"}
    # Resolve with approval
    req.result = "approved"
    req.event.set()
    t.join(timeout=5)

    assert len(result_holder) == 1
    result = result_holder[0]
    # The agent should have executed the tool after approval
    tool_msgs = [m for m in result.get("messages", []) if m.get("role") == "tool"]
    assert len(tool_msgs) >= 1
    payload = json.loads(tool_msgs[-1]["content"])
    assert payload["success"] is True
```

- [ ] **Step 6.2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_approval.py::test_agent_loop_catches_approval_blocked_error -v
```

Expected: `FAILED` with `ImportError: cannot import name 'ApprovalRequest'` (or `TypeError: AIAgent.__init__() got an unexpected keyword argument 'approval_callback'`)

- [ ] **Step 6.3: Add ApprovalRequest dataclass to agent.py**

Add right after the `Envelope` dataclass (after line 124) in `agent/core/agent.py`:

```python
@dataclass
class ApprovalRequest:
    """Thread-safe approval request sent to the frontend.

    When a high-risk tool is blocked in approve mode, the agent creates one
    of these and passes it to ``approval_callback``.  The WebSocket layer
    (``chat.py``) forwards it to the frontend and awaits user response.

    The agent thread calls ``event.wait()`` to block; the WebSocket thread
    calls ``event.set()`` and sets ``result`` to unblock.
    """

    tool_name: str
    args: dict
    reason: str
    event: threading.Event
    result: str | None = None
```

- [ ] **Step 6.4: Add approval_callback parameter to AIAgent.__init__**

Add to the `__init__` signature (line 234), after `progress_callback`:

```python
        approval_callback: Callable[[ApprovalRequest], None] | None = None,
```

Add the attribute assignment after `self.progress_callback = progress_callback` (around line 246):

```python
        self.approval_callback = approval_callback
```

- [ ] **Step 6.5: Modify _run_tool_calls to catch ApprovalBlockedError**

Replace the `dispatch_tool` call block in `_run_tool_calls` (lines 483-489). Old code:

```python
                    args = pre_event.args
                    result, _ = dispatch_tool(
                        tc.name,
                        args,
                        max_result_length=max_result_length,
                    )
```

New code:

```python
                    args = pre_event.args
                    try:
                        result, _ = dispatch_tool(
                            tc.name,
                            args,
                            max_result_length=max_result_length,
                        )
                    except ApprovalBlockedError as e:
                        result = self._handle_approval_block(
                            error=e,
                            tool_name=tc.name,
                            max_result_length=max_result_length,
                        )
```

Add the import at the top of `agent/core/agent.py`:

```python
from agent.tools.security_hooks import ApprovalBlockedError
```

- [ ] **Step 6.6: Add _handle_approval_block method to AIAgent**

Add this method after `_run_tool_calls` (before `run_conversation`):

```python
    def _handle_approval_block(
        self,
        *,
        error: ApprovalBlockedError,
        tool_name: str,
        max_result_length: int,
    ) -> str:
        """Handle an ApprovalBlockedError by blocking and waiting for user approval.

        Returns a JSON result string (success or failure) that is appended
        to the message list as a tool result.
        """
        req = ApprovalRequest(
            tool_name=error.tool_name,
            args=error.args,
            reason=error.reason,
            event=threading.Event(),
        )

        if self.approval_callback:
            self.approval_callback(req)

        # Block until user responds or timeout (120s)
        signaled = req.event.wait(timeout=120)

        if signaled and req.result == "approved":
            # Bypass hooks -- execute handler directly
            entry = registry.get_entry(tool_name)
            if entry is None:
                return json.dumps({"success": False, "error": f"工具已不存在: {tool_name}"})
            try:
                raw = entry.handler(dict(req.args))
                if not isinstance(raw, str):
                    raw = json.dumps(raw, ensure_ascii=False)
                if len(raw) > max_result_length:
                    raw = raw[:max_result_length] + "\n\n..."
                return raw
            except Exception as ex:
                logger.exception("Approved tool %s failed", tool_name)
                return json.dumps({"success": False, "error": f"执行失败: {ex}"})
        else:
            reason = "操作已超时" if not signaled else "操作已被用户拒绝"
            return json.dumps({"success": False, "error": reason})
```

- [ ] **Step 6.7: Run both the old and new tests**

```bash
.venv/bin/python -m pytest tests/test_approval.py -v
```

Expected: all tests PASS (including the new `test_agent_loop_catches_approval_blocked_error`)

- [ ] **Step 6.8: Verify existing agent loop tests still pass**

```bash
.venv/bin/python -m pytest tests/test_agent_loop.py -v
```

Expected: all tests PASS

- [ ] **Step 6.9: Commit**

```bash
git add agent/core/agent.py tests/test_approval.py
git commit -m "feat(agent): add ApprovalRequest, approval_callback, _handle_approval_block to AIAgent"
```

---

## Task 7: Add _pending_approval management to chat.py

**Files:**
- Modify: `backend/api/chat.py`

- [ ] **Step 7.1: Write a test for resolve_pending_approval**

Create `tests/test_approval_chat.py`:

```python
"""Tests for chat.py approval management (resolve_pending_approval, set_pending_approval)."""

from __future__ import annotations

import threading

import pytest

from agent.core.agent import ApprovalRequest


@pytest.fixture
def fresh_approval_state():
    """Reset _pending_approval before and after each test."""
    import backend.api.chat as chat_mod

    with chat_mod._pending_lock:
        chat_mod._pending_approval = None
    yield
    with chat_mod._pending_lock:
        chat_mod._pending_approval = None


def test_set_pending_approval_stores_request(fresh_approval_state):
    """set_pending_approval must store the request globally."""
    import backend.api.chat as chat_mod

    req = ApprovalRequest(
        tool_name="terminal",
        args={"command": "rm file"},
        reason="test",
        event=threading.Event(),
    )
    chat_mod.set_pending_approval(req)

    with chat_mod._pending_lock:
        assert chat_mod._pending_approval is req


def test_resolve_pending_approval_sets_event(fresh_approval_state):
    """resolve_pending_approval must set the event and result."""
    import backend.api.chat as chat_mod

    req = ApprovalRequest(
        tool_name="terminal",
        args={"command": "rm file"},
        reason="test",
        event=threading.Event(),
    )
    chat_mod.set_pending_approval(req)

    result = chat_mod.resolve_pending_approval(True)
    assert result is True
    assert req.result == "approved"
    assert req.event.is_set()


def test_resolve_pending_approval_denied(fresh_approval_state):
    """resolve_pending_approval with False must set result to 'denied'."""
    import backend.api.chat as chat_mod

    req = ApprovalRequest(
        tool_name="terminal",
        args={"command": "rm file"},
        reason="test",
        event=threading.Event(),
    )
    chat_mod.set_pending_approval(req)

    result = chat_mod.resolve_pending_approval(False)
    assert result is True
    assert req.result == "denied"
    assert req.event.is_set()


def test_resolve_pending_approval_noop_when_none(fresh_approval_state):
    """resolve_pending_approval must return False when no pending request."""
    import backend.api.chat as chat_mod

    result = chat_mod.resolve_pending_approval(True)
    assert result is False
```

- [ ] **Step 7.2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_approval_chat.py -v
```

Expected: `FAILED` with `AttributeError: module 'backend.api.chat' has no attribute '_pending_approval'`

- [ ] **Step 7.3: Add _pending_approval management code to chat.py**

Add after the `_session_usage` declaration (around line 34) in `backend/api/chat.py`:

```python
from agent.core.agent import ApprovalRequest

# Pending approval for the current session
_pending_approval: ApprovalRequest | None = None
_pending_lock = threading.Lock()


def set_pending_approval(req: ApprovalRequest) -> None:
    """Store an approval request for the WebSocket handler to resolve."""
    global _pending_approval
    with _pending_lock:
        _pending_approval = req


def resolve_pending_approval(approved: bool) -> bool:
    """Resolve a pending approval request.

    Sets the result and wakes the blocked agent thread.  Returns True if
    a request was actually resolved, False if there was nothing pending.
    """
    global _pending_approval
    with _pending_lock:
        req = _pending_approval
        _pending_approval = None
    if req is None:
        return False
    req.result = "approved" if approved else "denied"
    req.event.set()
    return True
```

- [ ] **Step 7.4: Add approval_callback to agent construction in _run_agent**

In `backend/api/chat.py`, in the `_run_agent` function, add the `approval_callback` before constructing the `AIAgent` (around line 265-274), replacing the old `run_sync` function's agent construction:

```python
    def approval_callback(req: ApprovalRequest):
        """Bridge agent thread's approval request → WebSocket queue."""
        set_pending_approval(req)
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {
                "type": "approval_request",
                "payload": {
                    "tool_name": req.tool_name,
                    "args": req.args,
                    "reason": req.reason,
                },
            }
        )

    def run_sync():
        try:
            agent = AIAgent(
                api_key=api_key,
                base_url=base_url,
                model=model,
                max_iterations=max_iterations,
                progress_callback=progress_callback,
                compaction_settings=compaction_settings,
                approval_callback=approval_callback,
            )
            # ... rest unchanged ...
```

- [ ] **Step 7.5: Handle approval_response in listen_for_stop**

The `listen_for_stop` background task polls for incoming WebSocket messages while the agent runs. Add `approval_response` handling there. Old code (around lines 354-369):

```python
    async def listen_for_stop():
        nonlocal stop_received
        try:
            while not stop_received and not stop_event.is_set():
                try:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.2)
                    data = json.loads(raw)
                    if data.get("type") == "stop":
                        stop_received = True
                        stop_event.set()
                except TimeoutError:
                    pass
                except Exception:
                    break
        except Exception:
            pass
```

New code:

```python
    async def listen_for_stop():
        nonlocal stop_received
        try:
            while not stop_received and not stop_event.is_set():
                try:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.2)
                    data = json.loads(raw)
                    if data.get("type") == "stop":
                        stop_received = True
                        stop_event.set()
                    elif data.get("type") == "approval_response":
                        payload = data.get("payload", {})
                        approved = payload.get("approved", False)
                        resolve_pending_approval(approved)
                except TimeoutError:
                    pass
                except Exception:
                    break
        except Exception:
            pass
```

- [ ] **Step 7.6: Add cleanup on disconnect**

Modify the `except WebSocketDisconnect:` block (lines 229-230):

```python
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", session_id)
        resolve_pending_approval(False)
    except Exception:
        logger.exception("WebSocket error for session %s", session_id)
        resolve_pending_approval(False)
```

- [ ] **Step 7.7: Run the test**

```bash
.venv/bin/python -m pytest tests/test_approval_chat.py -v
```

Expected: all tests PASS

- [ ] **Step 7.8: Commit**

```bash
git add backend/api/chat.py tests/test_approval_chat.py
git commit -m "feat(chat): add _pending_approval management and approval_callback for thread-blocking approval"
```

---

## Task 8: Update frontend types

**Files:**
- Modify: `web/src/types/index.ts`

- [ ] **Step 8.1: Add approval types to WsClientMessage**

Modify the `WsClientMessage` type (line 127-128). Old code:

```typescript
export type WsClientMessage =
  { type: "send_message"; content: string | ContentPart[] } | { type: "stop" };
```

New code:

```typescript
export type WsClientMessage =
  { type: "send_message"; content: string | ContentPart[] }
  | { type: "stop" }
  | { type: "approval_response"; payload: { approved: boolean } };
```

- [ ] **Step 8.2: Add approval types to WsServerMessage**

Add to the `WsServerMessage` union (after `{ type: "error"; message: string; session_id?: string }`):

```typescript
  | { type: "approval_request"; payload: { tool_name: string; args: object; reason: string } };
```

- [ ] **Step 8.3: Add ApprovalInfo interface**

Add before the WebSocket message types section:

```typescript
export interface ApprovalInfo {
  tool_name: string;
  args: object;
  reason: string;
}
```

- [ ] **Step 8.4: Verify TypeScript compiles**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected: exit code 0, no errors

- [ ] **Step 8.5: Commit**

```bash
git add web/src/types/index.ts
git commit -m "feat(web): add approval_request/approval_response WebSocket types"
```

---

## Task 9: Add pendingApproval state to AppContext

**Files:**
- Modify: `web/src/context/AppContext.tsx`

- [ ] **Step 9.1: Add approval imports and state**

Update the import line to include `ApprovalInfo`:

```typescript
import type { Message, ConfigResponse, TokenUsage, ApprovalInfo } from "../types";
```

Add `pendingApproval` to `AppState`:

```typescript
export interface AppState {
  // ... existing fields ...
  pendingApproval: ApprovalInfo | null;
}
```

Add to `initialState`:

```typescript
const initialState: AppState = {
  // ... existing state ...
  config: null,
  pendingApproval: null,
};
```

- [ ] **Step 9.2: Add SET_PENDING_APPROVAL action to AppAction**

Add to the `AppAction` union:

```typescript
  | { type: "SET_PENDING_APPROVAL"; approval: ApprovalInfo | null }
```

- [ ] **Step 9.3: Add reducer case**

Add between `SET_CONFIG` and `default` in the reducer:

```typescript
    case "SET_PENDING_APPROVAL":
      return { ...state, pendingApproval: action.approval };
```

- [ ] **Step 9.4: Verify TypeScript compiles**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected: exit code 0, no errors

- [ ] **Step 9.5: Commit**

```bash
git add web/src/context/AppContext.tsx
git commit -m "feat(web): add pendingApproval state to AppContext"
```

---

## Task 10: Create ApprovalCard component

**Files:**
- Create: `web/src/components/ApprovalCard.tsx`
- Modify: `web/src/styles/global.css`

- [ ] **Step 10.1: Create ApprovalCard component with keyboard handler**

Create `web/src/components/ApprovalCard.tsx`:

```tsx
import { useEffect } from "react";
import type { ApprovalInfo } from "../types";

export default function ApprovalCard({
  approval,
  onApprove,
}: {
  approval: ApprovalInfo;
  onApprove: (approved: boolean) => void;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        onApprove(true);
      } else if (e.key === "Escape") {
        e.preventDefault();
        onApprove(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onApprove]);

  return (
    <div className="approval-card">
      <div className="approval-card-header">
        <span className="approval-card-icon">⚠️</span>
        <span>需要你的确认</span>
      </div>
      <div className="approval-card-body">
        <div className="approval-field">
          <span className="approval-label">工具:</span>
          <code className="approval-value">{approval.tool_name}</code>
        </div>
        <div className="approval-field">
          <span className="approval-label">参数:</span>
          <pre className="approval-args">{JSON.stringify(approval.args, null, 2)}</pre>
        </div>
        {approval.reason && (
          <div className="approval-field">
            <span className="approval-label">说明:</span>
            <span className="approval-value">{approval.reason}</span>
          </div>
        )}
      </div>
      <div className="approval-card-actions">
        <button
          className="btn btn-primary"
          onClick={() => onApprove(true)}
          autoFocus
        >
          ✅ 批准
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => onApprove(false)}
        >
          ❌ 拒绝
        </button>
        <span className="approval-card-hint">
          Enter 批准 · Esc 拒绝
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 10.2: Add CSS for approval card**

Add to `web/src/styles/global.css` (before the `@keyframes fade-in-page` at the end):

```css
/* ═══════════════════════════════════════════════════════════
   Approval Card
   ═══════════════════════════════════════════════════════════ */

.approval-card {
  background: var(--bg-card);
  border: 2px solid var(--warning);
  border-radius: var(--radius-lg);
  padding: 16px 20px;
  margin: 8px 0;
  box-shadow: var(--shadow);
  animation: approval-in 0.25s ease;
}

@keyframes approval-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.approval-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--warning);
  margin-bottom: 12px;
}

.approval-card-icon {
  font-size: 18px;
}

.approval-card-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
}

.approval-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.approval-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-3);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.approval-value {
  font-size: 13px;
  color: var(--text-1);
}

.approval-value code {
  font-family: var(--font-mono);
  font-size: 13px;
  background: var(--bg-hover);
  padding: 2px 6px;
  border-radius: 4px;
}

.approval-args {
  font-family: var(--font-mono);
  font-size: 12px;
  background: var(--bg-hover);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 120px;
  overflow-y: auto;
  line-height: 1.5;
}

.approval-card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.approval-card-hint {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-4);
}
```

- [ ] **Step 10.3: Verify no TypeScript errors**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected: exit code 0, no errors

- [ ] **Step 10.4: Commit**

```bash
git add web/src/components/ApprovalCard.tsx web/src/styles/global.css
git commit -m "feat(web): add ApprovalCard component with keyboard shortcuts and styles"
```

---

## Task 11: Update useChat hook to handle approval_request

**Files:**
- Modify: `web/src/hooks/useChat.ts`

- [ ] **Step 11.1: Add approval_request handler to useChat**

In `useChat.ts`, add a new `case "approval_request"` to the `switch` statement inside `ws.onMessage`. Modify the switch (around line 28) by adding before `case "done"`:

```typescript
          case "approval_request":
            dispatch({ type: "SET_PENDING_APPROVAL", approval: msg.payload });
            break;
```

- [ ] **Step 11.2: Export wsRef for use in ChatPage**

The `useChat` hook needs to expose the `wsRef` so `ChatPage` can send `approval_response` messages through it. Change the return statement from:

```typescript
  return { sendMessage, stopAgent };
```

To:

```typescript
  return { sendMessage, stopAgent, wsRef };
```

- [ ] **Step 11.3: Update ReturnType usage**

The existing callers only use `sendMessage` and `stopAgent`, so adding `wsRef` to the return is backward-compatible.

- [ ] **Step 11.4: Verify TypeScript compiles**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected: exit code 0, no errors

- [ ] **Step 11.5: Commit**

```bash
git add web/src/hooks/useChat.ts
git commit -m "feat(web): handle approval_request in useChat hook, expose wsRef"
```

---

## Task 12: Update ChatPage to render ApprovalCard

**Files:**
- Modify: `web/src/pages/ChatPage.tsx`

- [ ] **Step 12.1: Add imports**

Add to the imports at the top of `ChatPage.tsx`:

```typescript
import ApprovalCard from "../components/ApprovalCard";
import type { ApprovalInfo } from "../types";
```

- [ ] **Step 12.2: Destructure wsRef from useChat**

Change the current destructuring:

```typescript
  const { sendMessage, stopAgent } = useChat();
```

To:

```typescript
  const { sendMessage, stopAgent, wsRef } = useChat();
```

- [ ] **Step 12.3: Remove old onApprove prop from ChatMessage**

In the ChatPage JSX, remove the `onApprove` prop from `<ChatMessage>`. Find:

```tsx
            <ChatMessage
              key={i}
              msgs={g}
              disabled={state.agentRunning}
              onApprove={(approved) => {
                if (!state.agentRunning) sendMessage(approved ? "批准" : "拒绝");
              }}
            />
```

Replace with:

```tsx
            <ChatMessage
              key={i}
              msgs={g}
              disabled={state.agentRunning}
            />
```

- [ ] **Step 12.4: Add ApprovalCard after messages list, before input**

Insert this block between the `{state.tokenUsage && ...}` section and the `<ChatInput>` component:

```tsx
      {state.pendingApproval && (
        <div style={{ padding: "0 0 8px" }}>
          <ApprovalCard
            approval={state.pendingApproval}
            onApprove={(approved) => {
              wsRef.current?.send({
                type: "approval_response",
                payload: { approved },
              });
              dispatch({ type: "SET_PENDING_APPROVAL", approval: null });
            }}
          />
        </div>
      )}
```

- [ ] **Step 12.5: Remove unused `sendMessage` dependency from old approval flow**

Now that `sendMessage` is no longer called from `onApprove`, ensure the `sendMessage` call is still only used for `ChatInput.onSubmit` (it's unchanged).

- [ ] **Step 12.6: Verify TypeScript compiles**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected: exit code 0, no errors

- [ ] **Step 12.7: Commit**

```bash
git add web/src/pages/ChatPage.tsx
git commit -m "feat(web): render ApprovalCard on approval_request, remove old onApprove from ChatMessage"
```

---

## Task 13: Remove old approval UI from ChatMessage

**Files:**
- Modify: `web/src/components/ChatMessage.tsx`

- [ ] **Step 13.1: Remove _isApprovalBlock and ToolResult approval buttons**

In `ChatMessage.tsx`, remove the `_isApprovalBlock` function (lines 7-10), and remove the `isApproval`, `resolved`, and approval buttons from the `ToolResult` component.

Old `ToolResult` component (lines 12-48). Replace with:

```tsx
function ToolResult({ msg }: { msg: Message }) {
  const content = msg.content;

  return (
    <div>
      <details className="tool-result-inline">
        <summary><IconFileText size={12} style={{ marginRight: "4px" }} />工具返回数据</summary>
        <pre>{typeof content === "string" ? content : JSON.stringify(content, null, 2)}</pre>
      </details>
    </div>
  );
}
```

- [ ] **Step 13.2: Remove onApprove and disabled props**

Remove `onApprove` and `disabled` from `AssistantGroupContent` and `ChatMessage` component signatures and their usage. The new signatures:

```typescript
function AssistantGroupContent({ msgs }: { msgs: Message[] }) {
```

```typescript
export default function ChatMessage({ msgs }: { msgs: Message[] }) {
```

- [ ] **Step 13.3: Remove unused IconCircleCheck and IconCircleX imports**

Remove `IconCircleCheck` and `IconCircleX` from the import if they're no longer used elsewhere:

```typescript
import { IconRobot, IconUser, IconTool, IconFileText, IconBolt, IconChartBar } from "@tabler/icons-react";
```

- [ ] **Step 13.4: Update JSX to remove onApprove+disabled props**

Remove the props from `<ToolResult>` and `<AssistantGroupContent>` calls inside.

- [ ] **Step 13.5: Verify TypeScript compiles**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected: exit code 0, no errors

- [ ] **Step 13.6: Commit**

```bash
git add web/src/components/ChatMessage.tsx
git commit -m "feat(web): remove old approval UI from ChatMessage — approval is now handled by ApprovalCard"
```

---

## Task 14: Run full test suite

- [ ] **Step 14.1: Run all Python tests**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: All test suites PASS (65+ tests, ~0.5s)

- [ ] **Step 14.2: Verify no orphaned references to confirm_tool_execution**

```bash
.venv/bin/python -c "
from agent.tools.registry import discover_tools, registry
discover_tools()
names = registry.get_all_tool_names()
assert 'confirm_tool_execution' not in names, 'confirm_tool_execution still registered!'
print('OK: confirm_tool_execution fully removed')
"
```

- [ ] **Step 14.3: Run lint check**

```bash
.venv/bin/python -m ruff check agent/ backend/ tests/ 2>&1 | head -30
```

Expected: No lint errors

- [ ] **Step 14.4: Run frontend type check**

```bash
cd web && npx tsc --noEmit 2>&1
```

Expected: exit code 0, no errors

- [ ] **Step 14.5: Commit**

```bash
git add -A
git commit -m "chore: final approval-redesign cleanup and verification"
```

---

## Validation Summary

| Check | Command | Expected |
|-------|---------|----------|
| Python tests | `.venv/bin/python -m pytest tests/ -v` | All PASS |
| Ruff lint | `.venv/bin/python -m ruff check agent/ backend/ tests/` | No errors |
| Frontend type | `cd web && npx tsc --noEmit` | Exit code 0 |
| No confirm_tool_execution | `python -c "from agent.tools.registry import discover_tools, registry; discover_tools(); assert 'confirm_tool_execution' not in registry.get_all_tool_names()"` | No assertion error |
| No _APPROVED_CALLS | `grep -rE '_APPROVED_CALLS|record_approval|clear_approvals|confirm_tool_execution' agent/ --include='*.py'` | No matches (confirm_tool.py and cache code are gone) |
