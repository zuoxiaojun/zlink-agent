"""Tests for agent/core/agent_adapter.py — AIAgent compatibility layer.

Covers the kernel-mode switch and the legacy kernel path (P1-T4);
the new-kernel path tests are added in P1-T6 and P3.
"""

from __future__ import annotations

import json
import os  # noqa: F401 — kept verbatim from the brief; kernel-mode tests use monkeypatch

import agent.core.agent_adapter as adapter_mod
from agent.core.agent_adapter import AIAgent, kernel_mode
from agent.core.llm_client import LLMClient
from tests.conftest import MockLLMProvider, make_text_response


def _force_kernel(monkeypatch, mode: str) -> None:
    """Pin the module-level kernel-mode cache for one test."""
    monkeypatch.setattr(adapter_mod, "_KERNEL_MODE", mode)


class TestKernelMode:
    def test_defaults_to_new(self, monkeypatch):
        monkeypatch.delenv("ZLINK_KERNEL", raising=False)
        monkeypatch.setattr(adapter_mod, "_KERNEL_MODE", None)
        assert kernel_mode() == "new"

    def test_old_via_env(self, monkeypatch):
        monkeypatch.setenv("ZLINK_KERNEL", "old")
        monkeypatch.setattr(adapter_mod, "_KERNEL_MODE", None)
        assert kernel_mode() == "old"

    def test_invalid_value_falls_back_to_new(self, monkeypatch):
        monkeypatch.setenv("ZLINK_KERNEL", "banana")
        monkeypatch.setattr(adapter_mod, "_KERNEL_MODE", None)
        assert kernel_mode() == "new"

    def test_cached_after_first_read(self, monkeypatch):
        monkeypatch.setenv("ZLINK_KERNEL", "new")
        monkeypatch.setattr(adapter_mod, "_KERNEL_MODE", None)
        first = kernel_mode()
        monkeypatch.setenv("ZLINK_KERNEL", "old")  # env changes must NOT matter now
        assert kernel_mode() == first == "new"


class TestLegacyKernelPath:
    """These force ``old`` so they keep passing after P1-T6 flips the default."""

    def test_legacy_plain_text_reply(self, monkeypatch):
        _force_kernel(monkeypatch, "old")
        provider = MockLLMProvider(responses=[make_text_response("hi back")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("hello")
        assert result["final_response"] == "hi back"
        assert result["completed"] is True
        assert result["error"] is None
        assert result["api_calls"] == 1
        assert [m["role"] for m in result["messages"]] == ["user", "assistant"]

    def test_legacy_tool_call_then_text(self, monkeypatch):
        from agent.config_model import AppConfig

        monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))
        _force_kernel(monkeypatch, "old")

        from tests.conftest import make_tool_call_response

        provider = MockLLMProvider(
            responses=[
                make_tool_call_response("terminal", {"command": "echo hi"}),
                make_text_response("echoed"),
            ]
        )
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("run echo")
        assert result["completed"] is True
        assert result["api_calls"] == 2
        assert [m["role"] for m in result["messages"]] == ["user", "assistant", "tool", "assistant"]

    def test_legacy_publishes_event_sequence(self, monkeypatch):
        _force_kernel(monkeypatch, "old")
        from agent.events import Event  # noqa: F401 — kept verbatim from the brief
        from agent.events.bus import event_bus

        seen: list[str] = []
        event_bus.subscribe(lambda e: seen.append(e.type))

        provider = MockLLMProvider(responses=[make_text_response("ok")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        agent.run_conversation("hi", session_id="sess-1")
        for expected in ("session_start", "user_message", "before_llm_call", "after_llm_call", "session_end"):
            assert expected in seen, expected
        assert agent.phase == "idle"


class TestNewKernelPath:
    """These run the default (new) kernel — the mode the full suite exercises."""

    def test_new_plain_text_reply(self, monkeypatch):
        _force_kernel(monkeypatch, "new")
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
        _force_kernel(monkeypatch, "new")
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
        _force_kernel(monkeypatch, "new")
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
        _force_kernel(monkeypatch, "new")
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
        _force_kernel(monkeypatch, "new")
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
        _force_kernel(monkeypatch, "new")
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
        _force_kernel(monkeypatch, "new")
        import pytest

        provider = MockLLMProvider(responses=[make_text_response("hi")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)
        agent._set_phase("turn", "manual")
        with pytest.raises(RuntimeError, match="turn"):
            agent.run_conversation("hello")

    def test_new_snapshot_isolates_config_changes(self, monkeypatch):
        _force_kernel(monkeypatch, "new")
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
        _force_kernel(monkeypatch, "new")
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
        _force_kernel(monkeypatch, "new")
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
        _force_kernel(monkeypatch, "new")
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
        _force_kernel(monkeypatch, "new")
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

    def test_new_dual_run_equivalence(self, monkeypatch):
        """§6.3: the same script through old and new kernels → same outcome."""
        _force_kernel(monkeypatch, "old")  # fallthrough below re-pins per run
        from agent.config_model import AppConfig

        monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))
        from tests.conftest import make_tool_call_response

        def _run_with(mode: str) -> dict:
            _force_kernel(monkeypatch, mode)
            provider = MockLLMProvider(
                responses=[
                    make_tool_call_response("terminal", {"command": "echo hi"}),
                    make_text_response("echoed"),
                ]
            )
            agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
            agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)
            return agent.run_conversation("run echo")

        old_result = _run_with("old")
        new_result = _run_with("new")

        assert new_result["final_response"] == old_result["final_response"] == "echoed"
        assert new_result["completed"] is True and old_result["completed"] is True
        assert new_result["error"] is None and old_result["error"] is None
        assert new_result["api_calls"] == old_result["api_calls"] == 2
        assert [m["role"] for m in new_result["messages"]] == [m["role"] for m in old_result["messages"]]
        old_tool = [m for m in old_result["messages"] if m["role"] == "tool"][0]
        new_tool = [m for m in new_result["messages"] if m["role"] == "tool"][0]
        assert old_tool["tool_call_id"] == new_tool["tool_call_id"] == "c1"
        assert json.loads(old_tool["content"]) == json.loads(new_tool["content"])
