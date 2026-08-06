"""Tests for backend/api/chat.py — the new-kernel async WS path (_run_agent_new)."""

from __future__ import annotations

import asyncio

from agent.core.kernel_types import (
    AgentEnd,
    MessageEnd,
    MessageStart,
    MessageUpdate,
    ToolExecutionEnd,
    ToolExecutionStart,
    ToolResult,
    TurnEnd,
)


class _FakeAgent:
    """Stand-in for backend.api.chat.AIAgent — drives scripted events."""

    system_prompt = "test system prompt"

    def __init__(self, events, result=None, delay: float = 0.0):
        self._events = list(events)
        self._result = result or {
            "final_response": "final",
            "messages": [],
            "api_calls": 1,
            "token_usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "completed": True,
            "error": None,
        }
        self._delay = delay
        self.cancelled = False
        self.steered: list[dict] = []
        self.run_kwargs: dict = {}

        class _Inner:
            def __init__(self, owner):
                self._owner = owner
                self._listeners = []

            def subscribe(self, listener):
                self._listeners.append(listener)
                return lambda: None

            def emit(self, event):
                for ln in list(self._listeners):
                    ln(event)

        self.agent = _Inner(self)

    async def run_conversation_async(self, **kwargs):
        self.run_kwargs = kwargs
        for ev in self._events:
            self.agent.emit(ev)
        if self._delay:
            await asyncio.sleep(self._delay)
        return dict(self._result)

    def cancel(self):
        self.cancelled = True

    def steer(self, message: dict):
        self.steered.append(message)


def _make_events():
    return [
        MessageStart(message={"role": "user", "content": "hi"}),
        MessageEnd(message={"role": "user", "content": "hi"}),
        MessageStart(message={"role": "assistant", "content": ""}),
        MessageUpdate(message={"role": "assistant", "content": "你"}, delta="你"),
        MessageUpdate(message={"role": "assistant", "content": "你好"}, delta="好"),
        MessageEnd(message={"role": "assistant", "content": "你好"}),
        ToolExecutionStart(tool_call_id="c1", tool_name="ls", args={}),
        ToolExecutionEnd(tool_call_id="c1", tool_name="ls", result='{"success": true, "data": "[]"}'),
        TurnEnd(
            message={"role": "assistant", "content": "你好"},
            tool_results=[ToolResult(tool_call_id="c1", tool_name="ls", result='{"success": true}')],
        ),
        AgentEnd(messages=[]),
    ]


def _monkeypatch_ws_env(monkeypatch):
    from agent import config_manager

    cfg = config_manager.load().model_copy(deep=True)
    cfg.llm_api_key = "sk-test"
    cfg.llm_base_url = "http://localhost:9/v1"
    cfg.llm_model = "gpt-4o"
    cfg.max_iterations = 3
    monkeypatch.setattr(config_manager, "load", lambda: cfg)
    monkeypatch.setattr("backend.api.chat._generate_summary", lambda *a, **k: None)
    monkeypatch.setattr("agent.session_manager.load_session", lambda sid: [])
    monkeypatch.setattr("agent.session_manager.save_session", lambda *a, **k: None)
    monkeypatch.setattr("agent.session_manager.auto_title", lambda msgs: "title")
    monkeypatch.setattr("agent.skill_manager.get_active_instructions", lambda: "")
    monkeypatch.setattr("agent.skill_manager.get_instructions_for_query", lambda q: None)
    monkeypatch.setattr("agent.memory_manager.get_context", lambda: "")


def test_ws_streams_flat_messages_in_order(monkeypatch):
    _monkeypatch_ws_env(monkeypatch)
    fake = _FakeAgent(_make_events())
    monkeypatch.setattr("backend.api.chat.AIAgent", lambda **kw: fake)

    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    with client.websocket_connect("/ws/chat/sess-stream") as ws:
        ws.send_json({"type": "send_message", "content": "hi"})
        types: list[str] = []
        while True:
            msg = ws.receive_json()
            types.append(msg["type"])
            if msg["type"] == "done":
                assert msg["final_response"] == "final"
                assert msg["session_id"] == "sess-stream"
                assert msg["session_title"] == "title"
                break

    assert "progress" in types
    assert "token" in types
    assert "tool_call" in types
    assert "tool_result" in types
    assert types[-1] == "done"
    # token deltas arrive in stream order
    token_contents = [
        msg["content"] for msg in _collect_ws_messages(client, fake, "sess-tokens") if msg["type"] == "token"
    ]
    assert token_contents == ["你", "好"]


def _collect_ws_messages(client, fake, session_id: str):
    """Send a message and collect every WS frame until done."""
    out: list[dict] = []
    with client.websocket_connect(f"/ws/chat/{session_id}") as ws:
        ws.send_json({"type": "send_message", "content": "hi"})
        while True:
            msg = ws.receive_json()
            out.append(msg)
            if msg["type"] == "done":
                break
    return out


def test_ws_stop_cancels_agent(monkeypatch):
    _monkeypatch_ws_env(monkeypatch)
    fake = _FakeAgent(_make_events(), delay=1.0)
    monkeypatch.setattr("backend.api.chat.AIAgent", lambda **kw: fake)

    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    with client.websocket_connect("/ws/chat/sess-stop") as ws:
        ws.send_json({"type": "send_message", "content": "hi"})
        ws.send_json({"type": "stop"})
        while True:
            msg = ws.receive_json()
            if msg["type"] == "done":
                break

    assert fake.cancelled is True


def test_ws_error_frame_on_run_exception(monkeypatch):
    _monkeypatch_ws_env(monkeypatch)

    class _ExplodingAgent(_FakeAgent):
        async def run_conversation_async(self, **kwargs):
            self.run_kwargs = kwargs
            raise RuntimeError("agent exploded")

    fake = _ExplodingAgent([])
    monkeypatch.setattr("backend.api.chat.AIAgent", lambda **kw: fake)

    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    with client.websocket_connect("/ws/chat/sess-err") as ws:
        ws.send_json({"type": "send_message", "content": "hi"})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "agent exploded" in msg["message"]
        assert msg["session_id"] == "sess-err"
