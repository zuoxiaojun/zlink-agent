"""Tests for agent/core/llm_providers/openai_compat.py — OpenAI-compat LLM provider."""

from __future__ import annotations

import threading

import httpx

from agent.core.llm_providers.base import LLMResponse
from agent.core.llm_providers.openai_compat import (
    OpenAICompatProvider,
    _extract_inline_thinking,
    _extract_reasoning,
)

# ── _extract_reasoning ────────────────────────────────────────────


class MockMsg:
    def __init__(self, reasoning_content=None, model_extra=None):
        self.reasoning_content = reasoning_content
        self.model_extra = model_extra or {}


class TestExtractReasoning:
    def test_extracts_from_direct_attribute(self):
        msg = MockMsg(reasoning_content="step by step thinking")
        assert _extract_reasoning(msg) == "step by step thinking"

    def test_extracts_from_model_extra(self):
        """model_extra is only checked when reasoning_content attr is absent."""

        class _Msg:
            model_extra = {"reasoning_content": "deep thinking"}

        assert _extract_reasoning(_Msg()) == "deep thinking"

    def test_returns_none_when_missing(self):
        msg = MockMsg(reasoning_content=None, model_extra={})
        assert _extract_reasoning(msg) is None

    def test_handles_non_dict_model_extra(self):
        class _Msg:
            model_extra = None

        assert _extract_reasoning(_Msg()) is None

    def test_handles_non_openai_object(self):
        assert _extract_reasoning("string") is None
        assert _extract_reasoning(42) is None


# ── _extract_inline_thinking (<think>...</think> / thinking...response) ──


class TestExtractInlineThinking:
    """Inline-thinking extraction for models that don't return reasoning_content.

    Handles two marker conventions:
      • ``<think>...</think>`` (Qwen-style)
      • ``thinking\\n...\\nresponse\\n...`` (DeepSeek-paw-style)
    """

    def test_qwen_style_strips_markers_and_splits(self):
        content = "<think>用户简单打了个招呼。</think>你好！我是 ZLink Agent。"
        cleaned, reasoning = _extract_inline_thinking(content)
        assert cleaned == "你好！我是 ZLink Agent。"
        assert reasoning == "用户简单打了个招呼。"

    def test_qwen_style_with_leading_whitespace(self):
        content = "\n<think>\n用户问好\n</think>\n你好呀"
        cleaned, reasoning = _extract_inline_thinking(content)
        assert cleaned == "你好呀"
        assert reasoning == "用户问好"

    def test_deepseek_style_still_works(self):
        """Existing thinking/response marker style preserved."""
        content = "thinking\nstep by step\nresponse\nfinal answer"
        cleaned, reasoning = _extract_inline_thinking(content)
        assert cleaned == "final answer"
        assert reasoning == "step by step"

    def test_plain_content_unchanged(self):
        content = "Just a normal answer with no markers."
        cleaned, reasoning = _extract_inline_thinking(content)
        assert cleaned == content
        assert reasoning is None

    def test_empty_content(self):
        cleaned, reasoning = _extract_inline_thinking("")
        assert cleaned == ""
        assert reasoning is None

    def test_unclosed_think_treated_as_thinking(self):
        """Stream cut off mid-thinking → all content is reasoning."""
        content = "<think>the model was still thinking when stream ended"
        cleaned, reasoning = _extract_inline_thinking(content)
        assert cleaned == ""
        assert reasoning == "the model was still thinking when stream ended"


# ── Helpers ───────────────────────────────────────────────────────


class FakeResponse:
    def __init__(self, json_data: dict, status: int = 200):
        self._json_data = json_data
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json_data


# ── OpenAICompatProvider tests ────────────────────────────────────


class TestOpenAICompatProvider:
    def setup_method(self):
        self.provider = OpenAICompatProvider(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            timeout=10.0,
        )

    # ── _build_url / _headers ──

    def test_build_url_appends_chat_completions(self):
        assert self.provider._build_url() == "https://api.openai.com/v1/chat/completions"

    def test_build_url_with_trailing_slash(self):
        provider = OpenAICompatProvider(api_key="sk-test", base_url="https://api.example.com/")
        assert provider._build_url() == "https://api.example.com/chat/completions"

    def test_headers_contain_bearer_token(self):
        headers = self.provider._headers()
        assert headers["Authorization"] == "Bearer sk-test"
        assert headers["Content-Type"] == "application/json"

    # ── _chat_blocking ──

    def test_chat_blocking_text_response(self, monkeypatch):
        def mock_request(body):
            return FakeResponse(
                {
                    "choices": [
                        {
                            "index": 0,
                            "message": {"content": "Hello world", "role": "assistant"},
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                }
            )

        monkeypatch.setattr(self.provider, "_request", mock_request)
        resp = self.provider._chat_blocking({"model": "gpt-4o", "messages": []})
        assert resp.content == "Hello world"
        assert resp.usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        assert resp.tool_calls is None

    def test_chat_blocking_with_tool_calls(self, monkeypatch):
        def mock_request(body):
            return FakeResponse(
                {
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "content": "",
                                "role": "assistant",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {"name": "web_search", "arguments": '{"query":"test"}'},
                                    }
                                ],
                            },
                        }
                    ],
                }
            )

        monkeypatch.setattr(self.provider, "_request", mock_request)
        resp = self.provider._chat_blocking({"model": "gpt-4o", "messages": []})
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "web_search"

    def test_chat_blocking_with_reasoning(self, monkeypatch):
        def mock_request(body):
            return FakeResponse(
                {
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "content": "Final answer",
                                "role": "assistant",
                                "reasoning_content": "Step by step",
                            },
                        }
                    ],
                }
            )

        monkeypatch.setattr(self.provider, "_request", mock_request)
        resp = self.provider._chat_blocking({"model": "deepseek-r1", "messages": []})
        assert resp.reasoning == "Step by step"

    # ── _chat_stream ──

    def test_chat_stream_text(self, monkeypatch):
        lines = [
            'data: {"choices":[{"delta":{"content":"Hello","role":"assistant"},"index":0}]}',
            'data: {"choices":[{"delta":{"content":" world"},"index":0}]}',
            'data: {"choices":[{"delta":{},"index":0}],"usage":{"prompt_tokens":5,"completion_tokens":2,"total_tokens":7}}',
            "data: [DONE]",
        ]
        received = []

        monkeypatch.setattr(self.provider, "_request_stream", lambda body: iter(lines))
        resp = self.provider._chat_stream(
            body={"model": "gpt-4o"},
            stream_callback=received.append,
            stop_event=threading.Event(),
        )
        assert resp.content == "Hello world"
        assert received == ["Hello", " world"]
        assert resp.usage == {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}

    def test_chat_stream_with_reasoning(self, monkeypatch):
        lines = [
            'data: {"choices":[{"delta":{"reasoning_content":"thinking"},"index":0}]}',
            'data: {"choices":[{"delta":{"content":"answer"},"index":0}]}',
            "data: [DONE]",
        ]
        content_parts = []
        reasoning_parts = []

        monkeypatch.setattr(self.provider, "_request_stream", lambda body: iter(lines))
        resp = self.provider._chat_stream(
            body={"model": "deepseek-r1"},
            stream_callback=content_parts.append,
            reasoning_callback=reasoning_parts.append,
            stop_event=threading.Event(),
        )
        assert resp.content == "answer"
        assert resp.reasoning == "thinking"

    def test_chat_stream_inline_qwen_think_extracts_reasoning(self, monkeypatch):
        """Streaming <think>...</think> → reasoning_callback gets text,
        stream_callback gets only cleaned content."""
        # Build markers from ASCII fragments — the source editor strips
        # `` as if it were an HTML tag otherwise.
        _open = "<" + "think" + ">"
        _close = "<" + "/" + "think" + ">"
        _delta_open = 'data: {"choices":[{"delta":{"content":"' + _open + '"},"index":0}]}'
        _delta_close = 'data: {"choices":[{"delta":{"content":"' + _close + '"},"index":0}]}'
        lines = [
            _delta_open,
            'data: {"choices":[{"delta":{"content":"用户问好"},"index":0}]}',
            'data: {"choices":[{"delta":{"content":"，简单回应"},"index":0}]}',
            _delta_close,
            'data: {"choices":[{"delta":{"content":"你好！我是 ZLink Agent。"},"index":0}]}',
            "data: [DONE]",
        ]
        content_parts = []
        reasoning_parts = []

        monkeypatch.setattr(self.provider, "_request_stream", lambda body: iter(lines))
        resp = self.provider._chat_stream(
            body={"model": "qwen"},
            stream_callback=content_parts.append,
            reasoning_callback=reasoning_parts.append,
            stop_event=threading.Event(),
        )
        # Cleaned content has no markers
        assert resp.content == "你好！我是 ZLink Agent。"
        # Reasoning text joined from chunks
        assert "用户问好" in resp.reasoning
        assert "简单回应" in resp.reasoning
        # stream_callback never sees raw open/close markers
        joined_content = "".join(content_parts)
        assert _open not in joined_content
        assert _close not in joined_content

    def test_chat_stream_inline_deepseek_markers_extracts_reasoning(self, monkeypatch):
        """Streaming thinking\\n...\\nresponse\\n... → reasoning separated."""
        lines = [
            'data: {"choices":[{"delta":{"content":"thinking\\n"},"index":0}]}',
            'data: {"choices":[{"delta":{"content":"step 1, step 2"},"index":0}]}',
            'data: {"choices":[{"delta":{"content":"\\nresponse\\n"},"index":0}]}',
            'data: {"choices":[{"delta":{"content":"final answer"},"index":0}]}',
            "data: [DONE]",
        ]
        content_parts = []
        reasoning_parts = []

        monkeypatch.setattr(self.provider, "_request_stream", lambda body: iter(lines))
        resp = self.provider._chat_stream(
            body={"model": "deepseek"},
            stream_callback=content_parts.append,
            reasoning_callback=reasoning_parts.append,
            stop_event=threading.Event(),
        )
        assert resp.content == "final answer"
        assert "step 1, step 2" in resp.reasoning

    def test_chat_stream_tool_calls(self, monkeypatch):
        """SSE delta with tool_calls accumulates correctly."""
        lines = [
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","function":{"name":"search","arguments":""}}]},"index":0}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"q"}}]},"index":0}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"uery\\":\\"test\\"}"}}]},"index":0}]}',
            "data: [DONE]",
        ]

        monkeypatch.setattr(self.provider, "_request_stream", lambda body: iter(lines))
        resp = self.provider._chat_stream(
            body={"model": "gpt-4o"},
            stream_callback=lambda t: None,
            stop_event=threading.Event(),
        )
        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "search"

    def test_chat_stream_stops_on_stop_event(self, monkeypatch):
        stop = threading.Event()

        def gen():
            yield 'data: {"choices":[{"delta":{"content":"before"},"index":0}]}'
            stop.set()
            yield 'data: {"choices":[{"delta":{"content":"after"},"index":0}]}'

        monkeypatch.setattr(self.provider, "_request_stream", lambda body: gen())
        resp = self.provider._chat_stream(
            body={"model": "gpt-4o"},
            stream_callback=lambda t: None,
            stop_event=stop,
        )
        assert resp.content == "before"
        assert "after" not in resp.content

    # ── chat() integration ──

    def test_chat_blocking_path(self, monkeypatch):
        called = False

        def mock_blocking(body):
            nonlocal called
            called = True
            return LLMResponse(content="ok")

        monkeypatch.setattr(self.provider, "_chat_blocking", mock_blocking)
        resp = self.provider.chat(model="gpt-4o", messages=[], stream=False)
        assert called is True
        assert resp.content == "ok"

    def test_chat_stream_path(self, monkeypatch):
        called = False

        def mock_stream(**kw):
            nonlocal called
            called = True
            return LLMResponse(content="streamed")

        monkeypatch.setattr(self.provider, "_chat_stream", mock_stream)
        resp = self.provider.chat(model="gpt-4o", messages=[], stream=True, stream_callback=lambda t: None)
        assert called is True
        assert resp.content == "streamed"

    def test_chat_passes_tools(self, monkeypatch):
        tools = [{"type": "function", "function": {"name": "test"}}]
        captured = {}

        def mock_blocking(body):
            captured["body"] = body
            return LLMResponse(content="")

        monkeypatch.setattr(self.provider, "_chat_blocking", mock_blocking)
        self.provider.chat(model="gpt-4o", messages=[], tools=tools, tool_choice="auto")
        assert captured["body"]["tools"] == tools
        assert captured["body"]["tool_choice"] == "auto"

    def test_chat_passes_max_tokens(self, monkeypatch):
        captured = {}

        def mock_blocking(body):
            captured["body"] = body
            return LLMResponse(content="")

        monkeypatch.setattr(self.provider, "_chat_blocking", mock_blocking)
        self.provider.chat(model="gpt-4o", messages=[], max_tokens=500)
        assert captured["body"]["max_tokens"] == 500
