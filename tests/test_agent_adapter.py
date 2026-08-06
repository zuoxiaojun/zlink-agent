"""Tests for agent/core/agent_adapter.py — AIAgent compatibility layer.

Covers the new-kernel path (P1-T6, extended in P2/P3) and, after P4,
the frozen contract with the legacy kernel and ZLINK_KERNEL removed.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from agent.core.agent_adapter import AIAgent
from agent.core.llm_client import LLMClient
from agent.core.llm_providers.base import ToolCallPayload
from agent.tools.registry import registry
from tests.conftest import MockLLMProvider, make_text_response, make_tool_call_response


@pytest.fixture(autouse=True)
def _clean_registry():
    """Register built-ins first, then snapshot — teardown only removes
    tools the test added (never wipes the 57 built-in tools)."""
    from agent.tools.registry import discover_tools

    discover_tools()
    saved_before = set(registry.get_all_tool_names())
    yield
    for name in set(registry.get_all_tool_names()) - saved_before:
        try:
            registry.deregister(name)
        except Exception:
            pass


class TestNewKernelPath:
    """These run the default (new) kernel — the mode the full suite exercises."""

    def test_new_plain_text_reply(self, monkeypatch):
        provider = MockLLMProvider(responses=[make_text_response("hi back")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("hello")
        assert result["final_response"] == "hi back"
        assert result["completed"] is True
        assert result["error"] is None
        assert result["api_calls"] == 1
        assert [m["role"] for m in result["messages"]] == ["user", "assistant"]
        assert agent.phase == "idle"

    def test_new_tool_call_then_text(self, monkeypatch):
        from agent.config_model import AppConfig

        monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))
        from tests.conftest import make_tool_call_response

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
        roles = [m["role"] for m in result["messages"]]
        assert roles == ["user", "assistant", "tool", "assistant"]
        tool_msg = result["messages"][2]
        assert tool_msg["tool_call_id"] == "c1"
        assert json.loads(tool_msg["content"])["success"] is True

    def test_new_publishes_full_event_sequence(self, monkeypatch):
        from agent.config_model import AppConfig

        monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))
        from agent.events import Event  # noqa: F401 — kept verbatim from the brief
        from agent.events.bus import event_bus
        from tests.conftest import make_tool_call_response

        seen: list[str] = []
        event_bus.subscribe(lambda e: seen.append(e.type))

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
        assert seen.count("phase_change") >= 2
        for expected in (
            "session_start",
            "user_message",
            "before_llm_call",
            "after_llm_call",
            "before_tool_call",
            "after_tool_call",
            "session_end",
        ):
            assert expected in seen, expected
        assert seen.index("session_start") < seen.index("user_message")
        assert seen.index("user_message") < seen.index("before_llm_call")
        assert seen.index("before_llm_call") < seen.index("after_llm_call")
        assert seen.index("after_llm_call") < seen.index("before_tool_call")
        assert seen.index("before_tool_call") < seen.index("after_tool_call")

    def test_new_session_id_propagates_to_events(self, monkeypatch):
        from agent.events import Event
        from agent.events.bus import event_bus
        from agent.events.types import PhaseChangeEvent, SessionEndEvent, SessionStartEvent

        captured: list[Event] = []
        event_bus.subscribe(lambda e: captured.append(e))

        provider = MockLLMProvider(responses=[make_text_response("ok")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        agent.run_conversation("hi", session_id="chat-42")

        starts = [e for e in captured if isinstance(e, SessionStartEvent)]
        ends = [e for e in captured if isinstance(e, SessionEndEvent)]
        assert len(starts) == 1 and starts[0].session_id == "chat-42"
        assert len(ends) == 1 and ends[0].session_id == "chat-42"
        for ev in [e for e in captured if isinstance(e, PhaseChangeEvent)]:
            assert ev.session_id == "chat-42"

    def test_new_security_event_blocks_dangerous_command(self, monkeypatch):
        from agent.events.extensions import register_extensions
        from agent.extensions.security_event import SecurityEventExtension

        ext = SecurityEventExtension()
        ext.enabled = True
        register_extensions([ext])
        from tests.conftest import make_tool_call_response

        provider = MockLLMProvider(
            responses=[
                make_tool_call_response("terminal", {"command": "rm -rf /etc/passwd"}),
            ]
        )
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("rm -rf something")
        assert result["api_calls"] == 2  # blocked tool → model retries → fallback text
        assert len(result["messages"]) == 4
        tool_msgs = [m for m in result["messages"] if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        payload = json.loads(tool_msgs[0]["content"])
        assert payload["success"] is False
        assert "拒绝" in payload.get("error", "") or "Blocked" in payload.get("error", "")

    def test_new_phase_machine_idle_turn_idle_and_snapshot_cleared(self, monkeypatch):
        provider = MockLLMProvider(responses=[make_text_response("hi")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        assert agent.phase == "idle"
        assert agent._snapshot is None
        result = agent.run_conversation("hello")
        assert result["completed"] is True
        assert agent.phase == "idle"
        assert agent._snapshot is None

    def test_new_rejects_reentrant_call(self, monkeypatch):
        import pytest

        provider = MockLLMProvider(responses=[make_text_response("hi")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)
        agent._set_phase("turn", "manual")
        with pytest.raises(RuntimeError, match="turn"):
            agent.run_conversation("hello")

    def test_new_snapshot_isolates_config_changes(self, monkeypatch):
        from agent.config_model import AppConfig

        monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))
        from agent.events import Event
        from agent.events.bus import event_bus
        from tests.conftest import make_tool_call_response

        provider = MockLLMProvider(
            responses=[
                make_tool_call_response("terminal", {"command": "echo a"}),
                make_text_response("done"),
            ]
        )
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        def _mutate(event: Event) -> None:
            if event.type == "before_llm_call":
                agent.model = "mutated-model"

        event_bus.subscribe(_mutate)
        result = agent.run_conversation("test")
        assert agent.model == "mutated-model"
        assert result["completed"] is True

    def test_new_user_message_rejected(self, monkeypatch):
        from agent.events import Event
        from agent.events.bus import event_bus

        def _reject(event: Event) -> None:
            if event.type == "user_message":
                event.cancel("test rejection")

        event_bus.subscribe(_reject)
        provider = MockLLMProvider(responses=[make_text_response("ok")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("hi")
        assert result["completed"] is False
        assert "User message rejected" in result["error"]
        assert result["api_calls"] == 0
        assert agent.phase == "idle"
        assert agent._snapshot is None

    def test_new_stop_event_stops_run(self, monkeypatch):
        import threading

        provider = MockLLMProvider(responses=[make_text_response("never")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)
        stop_event = threading.Event()
        stop_event.set()  # already stopped before the run starts

        result = agent.run_conversation("hi", stop_event=stop_event)
        assert result["completed"] is False
        assert result["error"] == "用户已手动停止"
        assert agent.phase == "idle"

    def test_new_budget_exhaustion_error(self, monkeypatch):
        from tests.conftest import make_tool_call_response

        provider = MockLLMProvider(
            responses=[
                make_tool_call_response("terminal", {"command": "echo 1"}),
                make_tool_call_response("terminal", {"command": "echo 2"}),
                make_tool_call_response("terminal", {"command": "echo 3"}),
                make_tool_call_response("terminal", {"command": "echo 4"}),
                make_text_response("done"),
            ]
        )
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("go")
        assert result["completed"] is False
        assert result["error"] == "Max iterations reached without final response"
        assert agent.phase == "idle"

    def test_new_compaction_hook_fires(self, monkeypatch):
        from agent.context_compactor import CompactionSettings
        from agent.events import Event  # noqa: F401 — kept verbatim from the brief
        from agent.events.bus import event_bus

        long_user = "长" * 400  # ~333 tokens under the character heuristic

        class _SpyProvider:
            def __init__(self, inner):
                self.inner = inner
                self.messages: list[list[dict]] = []

            def chat(self, **kwargs):
                self.messages.append(list(kwargs.get("messages", [])))
                return self.inner.chat(**kwargs)

        inner = MockLLMProvider(responses=[make_text_response("summary"), make_text_response("ok")])
        spy = _SpyProvider(inner)
        agent = AIAgent(
            api_key="sk-fake",
            base_url="x",
            model="gpt-4o",
            max_iterations=3,
            compaction_settings=CompactionSettings(
                enabled=True, max_context_tokens=120, reserve_tokens=20, keep_recent_tokens=50
            ),
        )
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=spy)

        phases: list[str] = []
        event_bus.subscribe(lambda e: phases.append(e.to_phase) if e.type == "phase_change" else None)

        result = agent.run_conversation(long_user)
        assert result["completed"] is True
        assert result["final_response"] == "ok"
        assert "compaction" in phases
        # the second LLM call (main turn) sees the compaction summary message
        assert len(spy.messages) == 2
        assert any(m.get("content", "").startswith("[上下文压缩摘要]") for m in spy.messages[1])

    def test_new_length_stop_reason_skips_tool_execution(self, monkeypatch):
        from agent.config_model import AppConfig

        monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))
        from agent.core.llm_providers import LLMResponse

        ran: list[str] = []

        def _spy_handler(args: dict) -> str:
            ran.append("ran")
            return json.dumps({"success": True})

        registry.register(name="spy_tool", toolset="test", schema={"type": "object"}, handler=_spy_handler)

        provider = MockLLMProvider(
            responses=[
                LLMResponse(
                    content="",
                    tool_calls=[ToolCallPayload(id="c1", name="spy_tool", arguments="{}")],
                    stop_reason="length",
                ),
                make_text_response("please re-issue"),
            ]
        )
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("go")
        assert ran == [], "truncated tool calls must never execute"
        tool_msgs = [m for m in result["messages"] if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert "参数可能被截断，请重新完整发出" in tool_msgs[0]["content"]
        assert result["final_response"] == "please re-issue"
        assert result["completed"] is True

    def test_cancel_during_run_ends_with_agent_end(self, monkeypatch):
        import time

        from agent.core.kernel_types import AgentEnd
        from agent.core.llm_providers import LLMResponse

        ended: list[AgentEnd] = []

        def _sleepy(args: dict) -> str:
            time.sleep(0.5)
            return json.dumps({"success": True})

        registry.register(name="sleepy_tool", toolset="test", schema={"type": "object"}, handler=_sleepy)
        provider = MockLLMProvider(
            responses=[
                LLMResponse(content="", tool_calls=[ToolCallPayload(id="c1", name="sleepy_tool", arguments="{}")]),
                make_text_response("never"),
            ]
        )
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)
        agent.agent.subscribe(lambda e: ended.append(e) if isinstance(e, AgentEnd) else None)

        async def _scenario() -> dict:
            task = asyncio.create_task(
                agent.run_conversation_async(user_message="go", conversation_history=[], session_id="s1")
            )
            await asyncio.sleep(0.1)
            agent.cancel()
            result = await task
            await agent.agent.wait_idle()
            return result

        result = asyncio.run(_scenario())
        assert result["error"] == "用户已手动停止"
        assert result["completed"] is False
        assert len(ended) == 1, "AgentEnd must close the event stream on cancel"
        assert agent.agent.state.running is False
        assert agent.agent.state.pendingToolCalls == 0
        assert agent.phase == "idle"

    def test_cancel_keeps_partial_streamed_content(self, monkeypatch):
        import time

        def _sleepy(args: dict) -> str:
            time.sleep(0.5)
            return json.dumps({"success": True})

        registry.register(name="partial_sleepy", toolset="test", schema={"type": "object"}, handler=_sleepy)

        class _StreamingProvider:
            """First call streams chunks through stream_callback then returns a
            tool-call response (content ""); the sleepy tool then blocks the run
            so the test can cancel mid-run while _partial_response is populated."""

            def __init__(self, inner):
                self.inner = inner
                self.first = True

            def chat(self, **kwargs):
                stream_cb = kwargs.get("stream_callback")
                if self.first:
                    self.first = False
                    if stream_cb:
                        stream_cb("streamed-")
                        stream_cb("partial")
                    return make_tool_call_response("partial_sleepy", {})
                return self.inner.chat(**kwargs)

        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(
            api_key="sk-fake",
            base_url="x",
            provider=_StreamingProvider(MockLLMProvider()),
        )

        async def _scenario() -> dict:
            task = asyncio.create_task(
                agent.run_conversation_async(
                    user_message="go",
                    conversation_history=[],
                    session_id="s1",
                    stream_callback=lambda t: None,
                )
            )
            await asyncio.sleep(0.1)
            agent.cancel()
            result = await task
            await agent.agent.wait_idle()
            return result

        result = asyncio.run(_scenario())
        assert result["final_response"] == ""
        assert result["completed"] is False
        assert result["error"] == "用户已手动停止"
        contents = [m.get("content") for m in result["messages"]]
        assert contents.count("streamed-partial") == 1

    def test_steer_injected_next_turn(self, monkeypatch):
        import threading

        entered = threading.Event()
        release = threading.Event()

        class _GatedProvider:
            """Blocks the first LLM call until the test injects its steer.

            The mocked run completes in a single event-loop slice (the
            instant ``to_thread`` LLM call never suspends), so a fixed
            sleep races the run.  Gating the LLM call makes mid-run
            injection deterministic: the steer lands while turn 1 is
            in-flight and is consumed at the next turn boundary.
            """

            def __init__(self, inner):
                self.inner = inner
                self.first = True

            def chat(self, **kwargs):
                if self.first:
                    self.first = False
                    entered.set()
                    release.wait(timeout=5)
                return self.inner.chat(**kwargs)

        provider = _GatedProvider(
            MockLLMProvider(responses=[make_text_response("first"), make_text_response("second")])
        )
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        async def _scenario() -> dict:
            task = asyncio.create_task(
                agent.run_conversation_async(user_message="go", conversation_history=[], session_id="s1")
            )
            await asyncio.to_thread(entered.wait, 5)
            agent.steer({"role": "user", "content": "interrupt"})
            release.set()
            return await task

        result = asyncio.run(_scenario())
        contents = [m.get("content") for m in result["messages"]]
        assert "interrupt" in contents
        idx_steer = contents.index("interrupt")
        idx_second = contents.index("second")
        assert idx_steer < idx_second
        assert result["final_response"] == "second"

    def test_steer_one_at_a_time_oldest_first(self, monkeypatch):
        import threading

        entered = threading.Event()
        release = threading.Event()

        class _GatedProvider:
            def __init__(self, inner):
                self.inner = inner
                self.first = True

            def chat(self, **kwargs):
                if self.first:
                    self.first = False
                    entered.set()
                    release.wait(timeout=5)
                return self.inner.chat(**kwargs)

        provider = _GatedProvider(
            MockLLMProvider(
                responses=[make_text_response("a"), make_text_response("b"), make_text_response("c")]
            )
        )
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=5)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        async def _scenario() -> dict:
            task = asyncio.create_task(
                agent.run_conversation_async(user_message="go", conversation_history=[], session_id="s1")
            )
            await asyncio.to_thread(entered.wait, 5)
            agent.steer({"role": "user", "content": "steer-1"})
            agent.steer({"role": "user", "content": "steer-2"})
            release.set()
            return await task

        result = asyncio.run(_scenario())
        contents = [m.get("content") for m in result["messages"]]
        assert contents.index("steer-1") < contents.index("steer-2") < contents.index("c")


class TestPostKernelCleanup:
    def test_no_kernel_mode_symbols(self):
        import agent.core.agent_adapter as mod

        assert not hasattr(mod, "kernel_mode")
        assert not hasattr(mod, "_KERNEL_MODE")

    def test_run_conversation_still_returns_frozen_dict(self, monkeypatch):
        provider = MockLLMProvider(responses=[make_text_response("hi")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)
        result = agent.run_conversation("hello")
        assert set(result.keys()) == {"final_response", "messages", "api_calls", "token_usage", "completed", "error"}
        assert result["final_response"] == "hi"
