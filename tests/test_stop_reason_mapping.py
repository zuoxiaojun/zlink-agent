"""Tests for finish_reason → stop_reason mapping (spec §8 R3).

Zero-network: providers' HTTP layer is monkeypatched, exactly like
tests/test_openai_compat.py.
"""

from __future__ import annotations

import threading

from agent.core.llm_providers.anthropic import (
    _anthropic_response_to_llm,
    _map_anthropic_stop_reason,
)
from agent.core.llm_providers.openai_compat import (
    OpenAICompatProvider,
    _map_finish_reason,
)


class TestMapFinishReason:
    def test_stop_maps_to_end_turn(self):
        assert _map_finish_reason("stop") == "end_turn"

    def test_length_passes_through(self):
        assert _map_finish_reason("length") == "length"

    def test_tool_calls_maps(self):
        assert _map_finish_reason("tool_calls") == "tool_calls"

    def test_none_and_unknown(self):
        assert _map_finish_reason(None) is None
        assert _map_finish_reason("weird") == "weird"


class TestOpenAIBlocking:
    def _provider(self):
        return OpenAICompatProvider(api_key="sk-x", base_url="http://localhost:9/v1")

    def test_blocking_length_finish_reason(self, monkeypatch):
        provider = self._provider()

        def mock_request(body):
            return _FakeResponse(
                json={
                    "choices": [
                        {
                            "message": {"content": "partial", "role": "assistant"},
                            "finish_reason": "length",
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                }
            )

        monkeypatch.setattr(provider, "_request", mock_request)
        resp = provider._chat_blocking({"model": "gpt-4o", "messages": []})
        assert resp.stop_reason == "length"
        assert resp.content == "partial"

    def test_blocking_stop_finish_reason(self, monkeypatch):
        provider = self._provider()

        def mock_request(body):
            return _FakeResponse(
                json={
                    "choices": [{"message": {"content": "ok", "role": "assistant"}, "finish_reason": "stop"}],
                    "usage": {},
                }
            )

        monkeypatch.setattr(provider, "_request", mock_request)
        resp = provider._chat_blocking({"model": "gpt-4o", "messages": []})
        assert resp.stop_reason == "end_turn"


class _FakeResponse:
    def __init__(self, json):
        self._json = json

    def json(self):
        return self._json


class TestOpenAIStreaming:
    def test_stream_captures_length_finish_reason(self, monkeypatch):
        provider = OpenAICompatProvider(api_key="sk-x", base_url="http://localhost:9/v1")
        lines = [
            'data: {"choices":[{"delta":{"content":"Hello"},"index":0}]}',
            'data: {"choices":[{"delta":{},"index":0,"finish_reason":"length"}],"usage":{"prompt_tokens":1,"completion_tokens":2,"total_tokens":3}}',
            "data: [DONE]",
        ]
        monkeypatch.setattr(provider, "_request_stream", lambda body: iter(lines))
        resp = provider._chat_stream(
            body={"model": "gpt-4o"},
            stream_callback=lambda t: None,
            stop_event=threading.Event(),
        )
        assert resp.stop_reason == "length"
        assert resp.content == "Hello"

    def test_stream_no_finish_reason_is_none(self, monkeypatch):
        provider = OpenAICompatProvider(api_key="sk-x", base_url="http://localhost:9/v1")
        lines = [
            'data: {"choices":[{"delta":{"content":"Hello"},"index":0}]}',
            "data: [DONE]",
        ]
        monkeypatch.setattr(provider, "_request_stream", lambda body: iter(lines))
        resp = provider._chat_stream(
            body={"model": "gpt-4o"},
            stream_callback=lambda t: None,
            stop_event=threading.Event(),
        )
        assert resp.stop_reason is None


class TestMapAnthropicStopReason:
    def test_max_tokens_maps_to_length(self):
        assert _map_anthropic_stop_reason("max_tokens") == "length"

    def test_end_turn_and_tool_use(self):
        assert _map_anthropic_stop_reason("end_turn") == "end_turn"
        assert _map_anthropic_stop_reason("tool_use") == "tool_calls"

    def test_none_and_unknown(self):
        assert _map_anthropic_stop_reason(None) is None
        assert _map_anthropic_stop_reason("stop_sequence") == "stop_sequence"


class _FakeBlock:
    def __init__(self, btype, **kw):
        self.type = btype
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeUsage:
    input_tokens = 1
    output_tokens = 2


class _FakeAnthResponse:
    def __init__(self, stop_reason=None, content=None, usage=None):
        self.stop_reason = stop_reason
        self.content = content or []
        self.usage = usage


class TestAnthropicBlocking:
    def test_max_tokens_stop_reason_maps_to_length(self):
        resp = _FakeAnthResponse(
            stop_reason="max_tokens",
            content=[_FakeBlock("text", text="partial answer")],
            usage=_FakeUsage(),
        )
        llm = _anthropic_response_to_llm(resp)
        assert llm.stop_reason == "length"
        assert llm.content == "partial answer"

    def test_tool_use_stop_reason(self):
        resp = _FakeAnthResponse(
            stop_reason="tool_use",
            content=[_FakeBlock("tool_use", id="t1", name="ls", input={})],
            usage=_FakeUsage(),
        )
        llm = _anthropic_response_to_llm(resp)
        assert llm.stop_reason == "tool_calls"
        assert llm.tool_calls is not None and llm.tool_calls[0].name == "ls"

    def test_no_stop_reason_is_none(self):
        resp = _FakeAnthResponse(content=[_FakeBlock("text", text="ok")], usage=_FakeUsage())
        llm = _anthropic_response_to_llm(resp)
        assert llm.stop_reason is None
