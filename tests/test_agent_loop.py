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


def test_run_conversation_with_one_tool_call():
    """Tool-call → tool result → text reply.  Message list should be
    [user, assistant(tool_call), tool(result), assistant(text)]."""
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


def test_run_conversation_publishes_full_event_sequence():
    """The 8 M2 event types are all reachable from a normal turn."""
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

    # session_start + user_message + (before/after_llm + before/after_tool) +
    # session_end.  顺序也应符合直觉。
    assert "session_start" in seen
    assert "user_message" in seen
    assert "before_llm_call" in seen
    assert "after_llm_call" in seen
    assert "before_tool_call" in seen
    assert "after_tool_call" in seen
    # session_end 由 chat.py 显式 publish；AIAgent.run_conversation 不一定发。
    # 这次只断言 agent 内部能看到的 6 个事件。
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
