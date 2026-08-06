"""Tests for agent/core/agent_adapter.py — AIAgent compatibility layer.

Covers the kernel-mode switch and the legacy kernel path (P1-T4);
the new-kernel path tests are added in P1-T6 and P3.
"""

from __future__ import annotations

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
