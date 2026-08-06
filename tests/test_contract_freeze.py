"""Frozen-contract regression tests (C1–C4) — run at every phase gate.

C2 (WS message types) is covered by tests/test_chat_async.py: the flat
message types observed there are exactly {token, reasoning_token,
progress, tool_call, tool_result, approval_request, done, error}.
"""

from __future__ import annotations

import inspect

from agent.core.agent import AIAgent
from agent.core.llm_client import LLMClient
from tests.conftest import MockLLMProvider, make_text_response


class TestC1RunConversationContract:
    def test_constructor_signature_frozen(self):
        sig = inspect.signature(AIAgent.__init__)
        params = list(sig.parameters)
        for expected in (
            "api_key", "base_url", "model", "max_iterations", "max_tokens",
            "max_tool_result_length", "system_prompt", "enabled_tools",
            "disabled_tools", "temperature", "progress_callback",
            "tool_call_callback", "tool_result_callback", "compaction_settings",
            "max_retries", "max_retry_delay", "approval_callback",
        ):
            assert expected in params, expected

    def test_run_conversation_signature_frozen(self):
        sig = inspect.signature(AIAgent.run_conversation)
        params = list(sig.parameters)
        for expected in (
            "user_message", "system_message", "conversation_history",
            "stream_callback", "reasoning_callback", "stop_event", "session_id",
        ):
            assert expected in params, expected

    def test_return_keys_frozen(self):
        provider = MockLLMProvider(responses=[make_text_response("hi")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)
        result = agent.run_conversation("hello")
        assert set(result.keys()) == {
            "final_response", "messages", "api_calls", "token_usage", "completed", "error",
        }


class TestC3EventBusContract:
    def test_eight_event_classes_still_importable(self):
        from agent.events.types import (
            AfterLLMCallEvent,
            AfterToolCallEvent,
            BeforeLLMCallEvent,
            BeforeToolCallEvent,
            PhaseChangeEvent,
            SessionEndEvent,
            SessionStartEvent,
            UserMessageEvent,
        )
        assert SessionStartEvent.type == "session_start"
        assert SessionEndEvent.type == "session_end"
        assert UserMessageEvent.type == "user_message"
        assert BeforeLLMCallEvent.type == "before_llm_call"
        assert AfterLLMCallEvent.type == "after_llm_call"
        assert BeforeToolCallEvent.type == "before_tool_call"
        assert AfterToolCallEvent.type == "after_tool_call"
        assert PhaseChangeEvent.type == "phase_change"

    def test_cancel_semantics_unchanged(self):
        from agent.events.types import BeforeToolCallEvent

        ev = BeforeToolCallEvent(tool_name="ls", args={})
        ev.cancel("blocked by test")
        assert ev.cancelled is True
        assert ev.cancel_reason == "blocked by test"


class TestC4RegistryContract:
    def test_public_api_present(self):
        from agent.tools.registry import registry

        assert callable(registry.register)
        assert callable(registry.deregister)
        assert callable(registry.dispatch)
        assert callable(registry.get_definitions)
        assert callable(registry.get_all_tool_names)
        assert callable(registry.add_before_hook)
        assert callable(registry.remove_before_hook)
        assert callable(registry.add_after_hook)
        assert callable(registry.remove_after_hook)

    def test_block_protocol_unchanged(self):
        from agent.tools.registry import registry

        def block_hook(tool_name, args):
            return {**args, "__block__": True, "__reason__": "frozen protocol"}

        registry.add_before_hook(block_hook)
        try:
            result = registry.dispatch("definitely_missing_tool_xyz", {})
            import json

            payload = json.loads(result)
            assert payload["success"] is False
            assert "Unknown tool" in payload["error"]
        finally:
            registry.remove_before_hook(block_hook)
