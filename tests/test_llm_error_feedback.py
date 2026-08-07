"""Tests for LLM error visibility: friendly messages + live retry feedback.

Covers:
* ``_friendly_http_error`` — provider response body surfaced in the message.
* ``LLMClient.chat(on_retry=...)`` — retry callback passthrough.
* Adapter: failed LLM turn propagates the real error into ``result["error"]``
  (instead of the generic "Max iterations reached" fallback).
* Adapter: provider retries emit ``llm_retry`` events on the Agent stream.
"""

from __future__ import annotations

import httpx

from agent.core.agent_adapter import AIAgent
from agent.core.llm_client import LLMClient
from agent.core.llm_providers.base import LLMProviderError
from agent.core.llm_providers.openai_compat import _friendly_http_error
from tests.conftest import MockLLMProvider, make_text_response


def _status_error(status: int, body: str) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    response = httpx.Response(status, text=body, request=request)
    return httpx.HTTPStatusError(f"error {status}", request=request, response=response)


class TestFriendlyHttpError:
    def test_extracts_provider_message_from_json_body(self):
        body = '{"type":"error","error":{"type":"rate_limit_error","message":"已达到 Token Plan 使用上限"}}'
        msg = _friendly_http_error(_status_error(429, body))
        assert "HTTP 429" in msg
        assert "额度" in msg  # hint for 429
        assert "已达到 Token Plan 使用上限" in msg

    def test_401_hint_without_json_body(self):
        msg = _friendly_http_error(_status_error(401, "unauthorized"))
        assert "HTTP 401" in msg
        assert "API Key" in msg
        assert "unauthorized" in msg

    def test_unreadable_body_falls_back_gracefully(self):
        request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
        response = httpx.Response(500, request=request)  # no body read
        err = httpx.HTTPStatusError("boom", request=request, response=response)
        msg = _friendly_http_error(err)
        assert "HTTP 500" in msg


class _FlakyProvider:
    """Fails with a transient error on the first call, succeeds after."""

    def __init__(self):
        self.call_count = 0

    def chat(self, **kwargs):
        self.call_count += 1
        if self.call_count == 1:
            raise LLMProviderError("HTTP 429 too many requests", transient=True)
        return make_text_response("ok")


class TestOnRetryPassthrough:
    def test_llm_client_invokes_on_retry(self):
        seen: list[tuple[int, float, str]] = []
        client = LLMClient(
            api_key="sk-fake",
            base_url="x",
            max_retries=2,
            max_retry_delay=0.01,
            provider=_FlakyProvider(),
        )
        resp = client.chat(model="m", messages=[], on_retry=lambda a, d, e: seen.append((a, d, str(e))))
        assert not resp.failed
        assert resp.content == "ok"
        assert len(seen) == 1
        assert seen[0][0] == 1  # attempt number
        assert "429" in seen[0][2]

    def test_llm_client_without_on_retry_still_works(self):
        client = LLMClient(
            api_key="sk-fake",
            base_url="x",
            max_retries=2,
            max_retry_delay=0.01,
            provider=_FlakyProvider(),
        )
        resp = client.chat(model="m", messages=[])
        assert resp.content == "ok"

    def test_quota_error_fails_fast_without_retry(self):
        """no_retry=True (quota exhausted) must bypass the retry loop."""

        class _QuotaProvider:
            def __init__(self):
                self.call_count = 0

            def chat(self, **kwargs):
                self.call_count += 1
                raise LLMProviderError(
                    "HTTP 429 Too Many Requests；服务商返回：已达到 Token Plan 使用上限",
                    transient=False,
                    no_retry=True,
                )

        retries: list = []
        provider = _QuotaProvider()
        client = LLMClient(
            api_key="sk-fake",
            base_url="x",
            max_retries=3,
            max_retry_delay=0.01,
            provider=provider,
        )
        resp = client.chat(model="m", messages=[], on_retry=lambda *a: retries.append(a))
        assert resp.failed
        assert provider.call_count == 1  # 不重试
        assert retries == []
        assert "Token Plan" in resp.error


class TestRetryLabel:
    def test_llm_retry_event_shows_http_status(self):
        """The short reason comes from the __cause__ chain (httpx error),
        not the wrapper's class name."""

        class _HttpFlakyProvider:
            def __init__(self):
                self.call_count = 0

            def chat(self, **kwargs):
                self.call_count += 1
                if self.call_count == 1:
                    raise LLMProviderError(
                        "HTTP 429 Too Many Requests",
                        transient=True,
                        cause=_status_error(429, "slow down"),
                    )
                return make_text_response("ok")

        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(
            api_key="sk-fake",
            base_url="x",
            max_retry_delay=0.01,
            provider=_HttpFlakyProvider(),
        )
        retry_events: list[str] = []
        agent.agent.subscribe(lambda e: retry_events.append(e.error) if e.type == "llm_retry" else None)

        result = agent.run_conversation("hello")
        assert result["final_response"] == "ok"
        assert retry_events == ["HTTP 429"]


class TestAdapterErrorSurface:
    def test_llm_failure_propagates_real_error(self):
        err_resp = make_text_response("")
        err_resp.content = ""
        err_resp.error = "HTTP 429 Too Many Requests；请求过于频繁或账户额度已用完"
        err_resp.stop_reason = "error"
        # adapter retries the whole call max_retries(3) times → 4 total calls
        provider = MockLLMProvider(responses=[err_resp, err_resp, err_resp, err_resp])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("hello")
        assert result["completed"] is False
        assert result["error"] is not None
        assert "HTTP 429" in result["error"]
        assert "Max iterations" not in result["error"]

    def test_retry_emits_llm_retry_event(self):
        provider = _FlakyProvider()
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(
            api_key="sk-fake",
            base_url="x",
            max_retry_delay=0.01,
            provider=provider,
        )
        events: list[str] = []
        agent.agent.subscribe(lambda e: events.append(e.type))

        result = agent.run_conversation("hello")
        assert result["final_response"] == "ok"
        assert "llm_retry" in events
