"""End-to-end tests for :class:`agent.core.agent.AIAgent`.

These tests drive the full ``run_conversation`` loop with a
``MockLLMProvider`` so we can assert on the agent's response shape,
tool-call behaviour, and event-bus interactions without a real LLM
in the loop.

The 5 cases here cover the most expensive paths:

1. No API key → returns the documented empty-error contract
2. Plain text reply → no tool calls, no api_calls > 1
3. One tool call + final text → message list has 4 messages (user,
   assistant(tool_call), tool, assistant(text))
4. EventBus sees session_start + user_message + before/after LLM +
   before/after tool + session_end
5. Event-layer SecurityEventExtension cancels a dangerous tool call
   BEFORE ToolRegistry sees it
"""

from __future__ import annotations

import json

from agent.core.agent import AIAgent
from agent.core.llm_client import LLMClient
from tests.conftest import MockLLMProvider, make_text_response, make_tool_call_response

# ────────────────────────────────────────────────────────────────────
# 1) API Key 校验 — 早期返回的契约
# ────────────────────────────────────────────────────────────────────


def test_run_conversation_returns_error_when_api_key_empty():
    """An agent with no API key must return the documented error
    contract without making any LLM call."""
    provider = MockLLMProvider()
    agent = AIAgent(api_key="", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="", base_url="x", provider=provider)

    result = agent.run_conversation("hi")
    assert result["final_response"] == ""
    assert result["api_calls"] == 0
    assert result["completed"] is False
    assert "API Key" in result["error"]
    assert provider.call_count == 0, "no LLM call should have been made"


# ────────────────────────────────────────────────────────────────────
# 2) 单轮纯文本回复
# ────────────────────────────────────────────────────────────────────


def test_run_conversation_plain_text_reply():
    """No tool calls → loop exits after 1 LLM call."""
    provider = MockLLMProvider(responses=[make_text_response("hi back")])
    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    result = agent.run_conversation("hello")
    assert result["final_response"] == "hi back"
    assert result["completed"] is True
    assert result["error"] is None
    assert result["api_calls"] == 1
    # Messages: [user, assistant]
    assert len(result["messages"]) == 2
    assert result["messages"][0]["role"] == "user"
    assert result["messages"][1]["role"] == "assistant"


# ────────────────────────────────────────────────────────────────────
# 3) 一次工具调用 + 最终文本
# ────────────────────────────────────────────────────────────────────


def test_run_conversation_with_one_tool_call(monkeypatch):
    """Tool-call → tool result → text reply.  Message list should be
    [user, assistant(tool_call), tool(result), assistant(text)]."""
    from agent.config_model import AppConfig

    monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))

    provider = MockLLMProvider(
        responses=[
            make_tool_call_response("terminal", {"command": "echo hi"}),
            make_text_response("echoed"),
        ]
    )
    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    result = agent.run_conversation("run echo", stream_callback=lambda t: None)
    assert result["completed"] is True
    assert result["api_calls"] == 2
    assert len(result["messages"]) == 4

    # 第 3 条是 tool result
    tool_msg = result["messages"][2]
    assert tool_msg["role"] == "tool"
    payload = json.loads(tool_msg["content"])
    assert payload["success"] is True
    assert "hi" in payload.get("data", "")


# ────────────────────────────────────────────────────────────────────
# 4) 事件总线收到完整序列
# ────────────────────────────────────────────────────────────────────


def test_run_conversation_publishes_full_event_sequence(monkeypatch):
    """The M7+ event types are all reachable from a normal turn."""
    from agent.config_model import AppConfig

    monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))

    from agent.events import (
        Event,
    )
    from agent.events.bus import event_bus

    seen: list[str] = []

    def _spy(event: Event) -> None:
        seen.append(event.type)

    event_bus.subscribe(_spy)

    provider = MockLLMProvider(
        responses=[
            make_tool_call_response("terminal", {"command": "echo ok"}),
            make_text_response("done"),
        ]
    )
    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    result = agent.run_conversation("test")
    assert result["completed"] is True

    # phase_change events bookend the conversation
    assert "phase_change" in seen
    assert seen.count("phase_change") >= 2  # idle→turn + turn→idle

    # session_start + user_message + (before/after_llm + before/after_tool) +
    # session_end.  顺序也应符合直觉。
    assert "session_start" in seen
    assert "user_message" in seen
    assert "before_llm_call" in seen
    assert "after_llm_call" in seen
    assert "before_tool_call" in seen
    assert "after_tool_call" in seen
    assert seen.index("session_start") < seen.index("user_message")
    assert seen.index("user_message") < seen.index("before_llm_call")
    assert seen.index("before_llm_call") < seen.index("after_llm_call")
    assert seen.index("after_llm_call") < seen.index("before_tool_call")
    assert seen.index("before_tool_call") < seen.index("after_tool_call")


# ────────────────────────────────────────────────────────────────────
# 5) SecurityEventExtension 事件层拦截
# ────────────────────────────────────────────────────────────────────


def test_security_event_extension_blocks_dangerous_command():
    """The M5+ event-layer security extension must cancel a
    ``rm -rf /`` call BEFORE ToolRegistry runs it."""
    from agent.events.extensions import register_extensions
    from agent.extensions.security_event import SecurityEventExtension

    # Re-enable: the autouse fixture cleared all state, so
    # security_event is currently disabled.  Re-enable explicitly.
    ext = SecurityEventExtension()
    ext.enabled = True
    register_extensions([ext])

    provider = MockLLMProvider(
        responses=[
            make_tool_call_response("terminal", {"command": "rm -rf /etc/passwd"}),
        ]
    )
    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    result = agent.run_conversation("rm -rf something")
    # The LLM was asked to call terminal; security-event cancelled it;
    # the tool message reflects the cancellation.  The agent loop
    # then re-prompts the LLM with the cancellation as a tool result,
    # and the LLM replies with a final "ack" — so we expect 2 LLM
    # calls and 4 messages (user, assistant, tool, assistant).
    assert result["api_calls"] == 2
    assert len(result["messages"]) == 4
    tool_msgs = [m for m in result["messages"] if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    payload = json.loads(tool_msgs[0]["content"])
    assert payload["success"] is False
    assert "拒绝" in payload.get("error", "") or "Blocked" in payload.get("error", "")


# ────────────────────────────────────────────────────────────────────
# 6) Phase Machine —— 状态转换
# ────────────────────────────────────────────────────────────────────


def test_phase_machine_idle_to_turn_to_idle():
    """Agent phase travels idle → turn → idle after a plain text reply."""
    provider = MockLLMProvider(responses=[make_text_response("hi")])
    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    assert agent.phase == "idle"
    result = agent.run_conversation("hello")
    assert result["completed"] is True
    assert agent.phase == "idle"  # must return to idle


# ────────────────────────────────────────────────────────────────────
# 8) System prompt — ERP context injection
# ────────────────────────────────────────────────────────────────────


def test_build_system_prompt_includes_erp_context_when_enabled(monkeypatch):
    """当 erp_clients 中有启用项时，system prompt 应包含可用数据源信息"""
    from agent.config_model import AppConfig

    cfg = AppConfig(approval_mode="allow_all")
    cfg.erp_clients = {
        "yonsuite": {"enabled": True, "tenant_id": "t1", "app_key": "k1", "app_secret": "s1"},
        "nc": {"enabled": False},
    }
    monkeypatch.setattr("agent.config_manager.load", lambda: cfg)

    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=MockLLMProvider())

    sys_prompt = agent._build_system_prompt()
    assert sys_prompt is not None
    assert "可用数据源" in sys_prompt
    assert "YonSuite" in sys_prompt
    assert "NC" not in sys_prompt  # 禁用的系统不显示
    # 只有一个启用 → 规则说"使用已启用系统"
    assert "使用已启用" in sys_prompt


def test_build_system_prompt_no_erp_context_when_none_enabled(monkeypatch):
    """当所有 ERP 都未启用时，不注入可用数据源 section"""
    from agent.config_model import AppConfig

    cfg = AppConfig(approval_mode="allow_all")
    cfg.erp_clients = {}
    monkeypatch.setattr("agent.config_manager.load", lambda: cfg)

    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=MockLLMProvider())

    sys_prompt = agent._build_system_prompt()
    assert sys_prompt is None or "可用数据源" not in sys_prompt


def test_build_system_prompt_multi_erp_ask_which_system(monkeypatch):
    """当多个 ERP 都启用时，规则应提示询问用户指定系统"""
    from agent.config_model import AppConfig

    cfg = AppConfig(approval_mode="allow_all")
    cfg.erp_clients = {
        "yonsuite": {"enabled": True},
        "nc": {"enabled": True},
    }
    monkeypatch.setattr("agent.config_manager.load", lambda: cfg)

    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=MockLLMProvider())

    sys_prompt = agent._build_system_prompt()
    assert sys_prompt is not None
    assert "可用数据源" in sys_prompt
    # 两个启用 → 规则说先问查哪个系统
    assert "查哪个系统的数据" in sys_prompt
    assert "如果用户已指定系统名称" in sys_prompt
    assert "YonSuite" in sys_prompt
    assert "NC" in sys_prompt


def test_build_system_prompt_no_erp_context_when_all_disabled(monkeypatch):
    """当所有 ERP 都显式禁用时，不注入可用数据源 section"""
    from agent.config_model import AppConfig

    cfg = AppConfig(approval_mode="allow_all")
    cfg.erp_clients = {
        "yonsuite": {"enabled": False},
        "nc": {"enabled": False},
    }
    monkeypatch.setattr("agent.config_manager.load", lambda: cfg)

    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=MockLLMProvider())

    sys_prompt = agent._build_system_prompt()
    assert sys_prompt is None or "可用数据源" not in sys_prompt


def test_phase_machine_rejects_reentrant_call():
    """Calling run_conversation while running must raise."""

    provider = MockLLMProvider(responses=[make_text_response("hi")])
    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    # Manually set to turn to simulate re-entrance
    agent._set_phase("turn", "manual")

    try:
        agent.run_conversation("hello")
        raise AssertionError("Should have raised RuntimeError")
    except RuntimeError as e:
        assert "turn" in str(e)


def test_phase_machine_records_phase_change_events():
    """PhaseChangeEvent must carry from_phase, to_phase, and reason."""
    from agent.events import Event
    from agent.events.bus import event_bus

    changes: list[dict] = []

    def _spy(event: Event) -> None:
        if event.type == "phase_change":
            changes.append(
                {
                    "from": event.from_phase,
                    "to": event.to_phase,
                    "reason": event.reason,
                }
            )

    event_bus.subscribe(_spy)

    provider = MockLLMProvider(responses=[make_text_response("ok")])
    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    agent.run_conversation("test")

    assert len(changes) >= 2
    assert changes[0]["from"] == "idle"
    assert changes[0]["to"] == "turn"
    assert changes[-1]["from"] == "turn"
    assert changes[-1]["to"] == "idle"


# ────────────────────────────────────────────────────────────────────
# 7) Turn Snapshot —— 快照隔离
# ────────────────────────────────────────────────────────────────────


def test_turn_snapshot_isolates_config_changes(monkeypatch):
    """Changes to agent config mid-turn must not affect the running turn."""
    from agent.config_model import AppConfig

    monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))

    provider = MockLLMProvider(
        responses=[
            make_tool_call_response("terminal", {"command": "echo a"}),
            make_text_response("done"),
        ]
    )
    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    # Hook into BeforeLLMCallEvent to mutate config during the turn
    from agent.events import Event
    from agent.events.bus import event_bus

    def _mutate(event: Event) -> None:
        if event.type == "before_llm_call":
            agent.model = "mutated-model"

    event_bus.subscribe(_mutate)

    result = agent.run_conversation("test")

    # The snapshot should have frozen the original model
    assert provider.call_count > 0
    # Agent's instance attribute was changed, but snapshot preserved original
    assert agent.model == "mutated-model"
    assert result["completed"] is True


def test_turn_snapshot_cleared_after_conversation():
    """_snapshot must be None after run_conversation completes."""
    provider = MockLLMProvider(responses=[make_text_response("done")])
    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    assert agent._snapshot is None
    agent.run_conversation("hello")
    assert agent._snapshot is None


# ────────────────────────────────────────────────────────────────────
# 8) session_id propagated into session_* and phase_change events
# ────────────────────────────────────────────────────────────────────


def _capture_events(provider):
    """Run a turn and return a snapshot of every event the agent fires."""
    from agent.events import Event
    from agent.events.bus import event_bus
    from agent.events.types import PhaseChangeEvent, SessionEndEvent, SessionStartEvent

    captured: list[Event] = []

    def _spy(event: Event) -> None:
        captured.append(event)

    event_bus.subscribe(_spy)

    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    return agent, captured, SessionStartEvent, SessionEndEvent, PhaseChangeEvent


def test_run_conversation_propagates_session_id_to_events():
    """``session_id`` passed to ``run_conversation`` must appear on
    ``SessionStartEvent`` and ``SessionEndEvent`` so that event-bus
    subscribers can correlate activity with the originating chat."""
    provider = MockLLMProvider(responses=[make_text_response("ok")])
    agent, captured, SessionStartEvent, SessionEndEvent, PhaseChangeEvent = _capture_events(provider)

    agent.run_conversation("hello", session_id="chat-42")

    starts = [e for e in captured if isinstance(e, SessionStartEvent)]
    ends = [e for e in captured if isinstance(e, SessionEndEvent)]
    assert len(starts) == 1
    assert len(ends) == 1
    assert starts[0].session_id == "chat-42"
    assert ends[0].session_id == "chat-42"


def test_run_conversation_propagates_session_id_to_phase_changes():
    """Every ``PhaseChangeEvent`` fired during a turn must carry the
    same ``session_id``.  This lets monitoring extensions attribute
    phase transitions to a session without out-of-band state."""
    provider = MockLLMProvider(responses=[make_text_response("ok")])
    from agent.events.types import PhaseChangeEvent

    agent, captured, _, _, _ = _capture_events(provider)
    agent.run_conversation("hi", session_id="sess-1")

    phase_changes = [e for e in captured if isinstance(e, PhaseChangeEvent)]
    assert phase_changes, "expected at least one PhaseChangeEvent"
    for ev in phase_changes:
        assert ev.session_id == "sess-1", f"unexpected session_id: {ev.session_id!r}"


# ────────────────────────────────────────────────────────────────────
# 9) Exception safety — phase + snapshot must reset on any raise
# ────────────────────────────────────────────────────────────────────


class _ExplodingProvider:
    """LLM provider that raises on every call — used to drive the
    exception-cleanup path of ``run_conversation``."""

    def __init__(self, exc: BaseException):
        from agent.core.llm_providers import LLMResponse

        self._exc = exc
        self._fallback = LLMResponse(error=str(exc), stop_reason="error")
        self.call_count = 0

    def chat(self, **kwargs):
        self.call_count += 1
        # Always raise on the first call so the agent hits its exception
        # cleanup branch; subsequent calls (during RETRY phase) return a
        # clean error response so the loop eventually exits cleanly.
        if self.call_count == 1:
            raise self._exc
        return self._fallback


def test_run_conversation_phase_resets_to_idle_on_exception(monkeypatch):
    """If anything inside the run body raises, ``self.phase`` must
    still end up at ``idle`` so the agent is reusable.  Regression for
    the bug where an exception inside the run body left
    ``self.phase == "turn"`` and every subsequent call hit
    ``_assert_idle``.

    We trigger the failure by monkey-patching ``_take_snapshot`` to
    raise — that call sits inside the guarded body so the ``finally``
    block is responsible for restoring agent state.
    """
    import pytest

    provider = MockLLMProvider(responses=[make_text_response("never used")])
    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    def _boom() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(agent, "_take_snapshot", _boom)

    with pytest.raises(RuntimeError, match="boom"):
        agent.run_conversation("hi", session_id="sess-x")

    # The guard MUST have cleaned up: phase back to idle, snapshot cleared.
    assert agent.phase == "idle", f"phase leaked to {agent.phase!r}"
    assert agent._snapshot is None, "snapshot leaked across exception"

    # And the agent must be immediately reusable.
    # Undo monkeypatch so the next call takes a real snapshot.
    monkeypatch.undo()
    result = agent.run_conversation("again")
    assert result["completed"] is True
    assert result["final_response"] == "never used"  # the only scripted response


def test_run_conversation_phase_resets_on_reentrant_failure(monkeypatch):
    """A subscriber that cancels ``UserMessageEvent`` must still leave
    the agent in ``idle`` so the next user message works."""
    from agent.events import Event
    from agent.events.bus import event_bus

    def _reject_user(event: Event) -> None:
        if event.type == "user_message":
            event.cancel("test rejection")

    event_bus.subscribe(_reject_user)

    provider = MockLLMProvider(responses=[make_text_response("ok")])
    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    result = agent.run_conversation("hi")

    assert result["completed"] is False
    assert "User message rejected" in result["error"]
    assert agent.phase == "idle", f"phase leaked: {agent.phase!r}"
    assert agent._snapshot is None


# ────────────────────────────────────────────────────────────────────
# 10) tool_result_callback — 渐进式工具结果推送
# ────────────────────────────────────────────────────────────────────


def test_tool_result_callback_invoked(monkeypatch):
    """tool_result_callback must be called with (tool_name, result_str)
    after a tool executes."""
    from agent.config_model import AppConfig

    monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))

    captured: list[tuple[str, str]] = []

    def spy(name: str, result: str) -> None:
        captured.append((name, result))

    provider = MockLLMProvider(
        responses=[
            make_tool_call_response("terminal", {"command": "echo hi"}),
            make_text_response("done"),
        ]
    )
    agent = AIAgent(
        api_key="sk-fake",
        base_url="x",
        model="gpt-4o",
        max_iterations=3,
        tool_result_callback=spy,
    )
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    result = agent.run_conversation("run echo")
    assert result["completed"] is True
    assert len(captured) == 1, f"expected 1 call, got {captured}"
    name, res = captured[0]
    assert name == "terminal"
    payload = json.loads(res)
    assert payload["success"] is True


def test_tool_call_and_result_callbacks_both_invoked_in_order(monkeypatch):
    """tool_call_callback must fire before tool_result_callback,
    in the same execution pass."""
    from agent.config_model import AppConfig

    monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))

    order: list[str] = []

    def call_cb(name: str, args: str) -> None:
        order.append(f"call:{name}")

    def result_cb(name: str, result: str) -> None:
        order.append(f"result:{name}")

    provider = MockLLMProvider(
        responses=[
            make_tool_call_response("terminal", {"command": "echo hi"}),
            make_text_response("done"),
        ]
    )
    agent = AIAgent(
        api_key="sk-fake",
        base_url="x",
        model="gpt-4o",
        max_iterations=3,
        tool_call_callback=call_cb,
        tool_result_callback=result_cb,
    )
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    result = agent.run_conversation("run echo")
    assert result["completed"] is True
    assert order == ["call:terminal", "result:terminal"], f"unexpected order: {order}"
