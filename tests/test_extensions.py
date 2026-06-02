"""Tests for the M2 event system + M5+ extension registry.

Priority: highest.  These tests guard the runtime-toggle path that
M5+ shipped, plus the 8 typed event classes that the agent loop
publishes at every interesting point.
"""
from __future__ import annotations

import json

import pytest

from agent.events import (
    Extension,
    Event,
    SessionStartEvent,
    SessionEndEvent,
    UserMessageEvent,
    BeforeLLMCallEvent,
    AfterLLMCallEvent,
    BeforeToolCallEvent,
    AfterToolCallEvent,
    SessionBeforeCompactEvent,
)
from agent.events.bus import event_bus
from agent.events.extensions import (
    ExtensionRunner,
    apply_config_overrides,
    list_active_extensions,
    list_all_extensions,
    register_extensions,
    shutdown_all_extensions,
)


# ────────────────────────────────────────────────────────────────────
# 1) 8 事件类型字段签名（守住 M2 的事件契约）
# ────────────────────────────────────────────────────────────────────

def test_eight_event_classes_exist_with_documented_fields():
    """The 8 typed event classes must be importable and constructible.

    Locks the M2 event contract: any future rename of these fields is
    a breaking change for every Extension that subscribes to them.
    """
    # SessionStartEvent — session_id + history
    e = SessionStartEvent(session_id="s1", history=[{"role": "user", "content": "hi"}])
    assert e.type == "session_start"
    assert e.session_id == "s1"
    assert len(e.history) == 1

    # SessionEndEvent — no extra fields
    e = SessionEndEvent()
    assert e.type == "session_end"

    # UserMessageEvent — content (str or list)
    e = UserMessageEvent(content="hello")
    assert e.type == "user_message"
    assert e.content == "hello"

    # BeforeLLMCallEvent — messages (mutable for prompt-rewriting)
    e = BeforeLLMCallEvent(messages=[])
    assert e.type == "before_llm_call"
    assert e.messages == []

    # AfterLLMCallEvent — model + response (read-only contract)
    from agent.core.llm_providers import LLMResponse
    resp = LLMResponse(content="x", usage={"total_tokens": 1})
    e = AfterLLMCallEvent(model="gpt-4o", response=resp)
    assert e.type == "after_llm_call"
    assert e.model == "gpt-4o"
    assert e.response is resp

    # BeforeToolCallEvent — tool_name + args (cancellable)
    e = BeforeToolCallEvent(tool_name="terminal", args={"command": "ls"})
    assert e.type == "before_tool_call"
    assert e.tool_name == "terminal"
    assert e.cancelled is False

    # AfterToolCallEvent — tool_name + args + result
    e = AfterToolCallEvent(tool_name="terminal", args={"command": "ls"}, result="ok")
    assert e.type == "after_tool_call"
    assert e.result == "ok"

    # SessionBeforeCompactEvent — extra (mutable for extension-supplied context)
    e = SessionBeforeCompactEvent(summary="...", extra={})
    assert e.type == "session_before_compact"
    assert e.summary == "..."


# ────────────────────────────────────────────────────────────────────
# 2) Extension 类 + ExtensionRunner 基础路径
# ────────────────────────────────────────────────────────────────────

class _CountExtension(Extension):
    """Test extension that counts how many of each event it sees."""
    name = "counter"
    enabled = True

    def __init__(self):
        super().__init__()
        self.session_start_count = 0
        self.before_tool_call_count = 0
        self.captured_tool_args: list[dict] = []

    def on_session_start(self, event: SessionStartEvent) -> None:
        self.session_start_count += 1

    def on_before_tool_call(self, event: BeforeToolCallEvent) -> None:
        self.before_tool_call_count += 1
        self.captured_tool_args.append(dict(event.args))

    def on_event(self, event: Event) -> None:
        # catch-all
        pass


def test_register_extensions_subscribes_handlers():
    """A registered extension receives every published event of its type."""
    counter = _CountExtension()
    runners = register_extensions([counter])
    assert len(runners) == 1

    # Publish 2 session_start + 1 before_tool_call
    event_bus.publish(SessionStartEvent(session_id="s1", history=[]))
    event_bus.publish(SessionStartEvent(session_id="s2", history=[]))
    event_bus.publish(BeforeToolCallEvent(tool_name="t", args={"k": "v"}))

    assert counter.session_start_count == 2
    assert counter.before_tool_call_count == 1
    assert counter.captured_tool_args == [{"k": "v"}]


def test_disabled_extension_is_not_subscribed():
    """An extension with enabled=False must NOT receive any events."""
    counter = _CountExtension()
    counter.enabled = False
    runners = register_extensions([counter])
    assert runners == [], "disabled extension should not get a runner"

    event_bus.publish(SessionStartEvent(session_id="s1", history=[]))
    assert counter.session_start_count == 0, "disabled ext must stay silent"


# ────────────────────────────────────────────────────────────────────
# 3) M5+ 运行时 toggle（核心新功能）
# ────────────────────────────────────────────────────────────────────

def test_apply_config_overrides_disables_active_extension():
    """A running extension can be toggled off at runtime."""
    counter = _CountExtension()
    register_extensions([counter])
    assert counter.enabled is True
    assert counter.name in {e.name for e in list_active_extensions()}

    # 触发一次 — 应能收到
    event_bus.publish(SessionStartEvent(session_id="s1", history=[]))
    assert counter.session_start_count == 1

    # 关掉
    now_active, now_disabled = apply_config_overrides(disabled_names={"counter"})
    assert {e.name for e in now_disabled} == {"counter"}
    assert counter.enabled is False
    assert counter.name not in {e.name for e in list_active_extensions()}

    # 触发第二次 — 不应收到
    event_bus.publish(SessionStartEvent(session_id="s2", history=[]))
    assert counter.session_start_count == 1, "toggled-off ext must not receive events"


def test_apply_config_overrides_re_enables_disabled_extension():
    """A previously-disabled extension can be re-enabled at runtime."""
    counter = _CountExtension()
    counter.enabled = False
    register_extensions([counter])  # 注册但 disabled
    assert list_active_extensions() == []

    # Re-enable via the override
    now_active, now_disabled = apply_config_overrides(disabled_names=set())
    assert {e.name for e in now_active} == {"counter"}
    assert counter.enabled is True
    assert counter.name in {e.name for e in list_active_extensions()}

    event_bus.publish(SessionStartEvent(session_id="s1", history=[]))
    assert counter.session_start_count == 1


def test_list_all_extensions_includes_disabled():
    """list_all_extensions must include both active AND disabled."""
    a = _CountExtension()
    a.name = "a"
    a.enabled = True
    b = _CountExtension()
    b.name = "b"
    b.enabled = False
    register_extensions([a, b])

    all_names = {e.name for e in list_all_extensions()}
    active_names = {e.name for e in list_active_extensions()}
    assert all_names == {"a", "b"}
    assert active_names == {"a"}


def test_apply_config_overrides_is_idempotent():
    """Calling apply_config_overrides twice with the same set is safe."""
    counter = _CountExtension()
    register_extensions([counter])
    apply_config_overrides(disabled_names={"counter"})
    # 第二次调用应不抛、不重复关
    apply_config_overrides(disabled_names={"counter"})
    assert counter.enabled is False
    assert counter.name not in {e.name for e in list_active_extensions()}


# ────────────────────────────────────────────────────────────────────
# 4) 取消契约（BeforeToolCallEvent.cancel）
# ────────────────────────────────────────────────────────────────────

class _CancelExt(Extension):
    name = "canceller"
    enabled = True

    def on_before_tool_call(self, event: BeforeToolCallEvent) -> None:
        if event.args.get("dangerous"):
            event.cancel(reason="blocked by test")


def test_before_tool_call_can_be_cancelled():
    """An extension can cancel a tool call before it runs."""
    register_extensions([_CancelExt()])

    evt = BeforeToolCallEvent(tool_name="terminal", args={"dangerous": True})
    event_bus.publish(evt)
    assert evt.cancelled is True
    assert evt.cancel_reason == "blocked by test"

    # Non-dangerous call should pass through
    evt2 = BeforeToolCallEvent(tool_name="terminal", args={"dangerous": False})
    event_bus.publish(evt2)
    assert evt2.cancelled is False
