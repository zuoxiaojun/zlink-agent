"""OpenAI-compat provider — covers 9 of the 10 providers in
``backend/llm_providers.py``.

OpenAI Chat Completions protocol is a de-facto industry standard; most
Chinese model hosts (DeepSeek, Zhipu, SiliconFlow, DashScope, Moonshot,
OpenRouter) speak it verbatim, with only the ``base_url`` differing.
Baidu Qianfan has its own URL but the rest of the protocol matches.

This module is a 1:1 port of the M1 ``LLMClient`` — same retry logic,
same streaming consumption, same reasoning_content extraction.  The
behaviour is identical; only the class hierarchy changes.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import httpx

from agent.core.llm_providers.base import (
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    ToolCallPayload,
    chat_with_retry,
)

if TYPE_CHECKING:
    import openai

logger = logging.getLogger(__name__)


def _extract_reasoning(msg: Any) -> str | None:
    """Extract ``reasoning_content`` from an OpenAI message
    (DeepSeek reasoning models, etc.)."""
    try:
        return msg.reasoning_content
    except AttributeError:
        pass
    try:
        return msg.model_extra.get("reasoning_content") if msg.model_extra else None
    except AttributeError:
        pass
    return None


class OpenAICompatProvider(LLMProvider):
    """Provider for any OpenAI-Protocol compatible endpoint.

    The constructor is a 1:1 port of the M1 ``LLMClient.__init__``.
    Subclasses / callers should pass the provider's ``base_url`` from
    :data:`backend.llm_providers.LLM_PROVIDERS`.
    """

    name = "openai_compat"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
        max_retries: int = 3,
        max_retry_delay: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_retry_delay = max_retry_delay

    @property
    def client(self) -> openai.OpenAI:
        """Lazy HTTP client.  Exposed for M4 compaction."""
        import openai

        return openai.OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout, max_retries=1)

    def _build_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        *,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | None = "auto",
        stream: bool = False,
        stream_callback: Callable[[str], None] | None = None,
        reasoning_callback: Callable[[str], None] | None = None,
        stop_event: threading.Event | None = None,
        max_retries: int | None = None,
        max_retry_delay: float | None = None,
    ) -> LLMResponse:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice

        retries = self.max_retries if max_retries is None else max_retries
        retry_delay = self.max_retry_delay if max_retry_delay is None else max_retry_delay

        def _invoke() -> LLMResponse:
            try:
                if stream and stream_callback is not None:
                    return self._chat_stream(
                        body=body,
                        stream_callback=stream_callback,
                        reasoning_callback=reasoning_callback,
                        stop_event=stop_event,
                    )
                return self._chat_blocking(body)
            except Exception as e:
                raise LLMProviderError(
                    str(e),
                    transient=False,
                    cause=e,
                ) from e

        return chat_with_retry(
            invoke=_invoke,
            max_retries=retries,
            max_retry_delay=retry_delay,
            stop_event=stop_event,
        )

    def _request(self, body: dict) -> httpx.Response:
        url = self._build_url()
        headers = self._headers()
        resp = httpx.post(
            url,
            headers=headers,
            json=body,
            timeout=httpx.Timeout(self.timeout),
        )
        resp.raise_for_status()
        return resp

    def _request_stream(self, body: dict):
        """Generator yielding raw SSE lines."""
        url = self._build_url()
        headers = self._headers()
        with httpx.Client(timeout=httpx.Timeout(self.timeout)) as client:
            with client.stream("POST", url, headers=headers, json=body) as resp:
                resp.raise_for_status()
                yield from resp.iter_lines()

    def _chat_blocking(self, body: dict) -> LLMResponse:
        resp = self._request(body)
        data = resp.json()
        choice = data["choices"][0]
        msg = choice.get("message", {})

        tool_calls: list[ToolCallPayload] | None = None
        tcs = msg.get("tool_calls")
        if tcs:
            tool_calls = [
                ToolCallPayload(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"] or "{}",
                )
                for tc in tcs
            ]

        usage = None
        if data.get("usage"):
            u = data["usage"]
            usage = {
                "prompt_tokens": u.get("prompt_tokens", 0) or 0,
                "completion_tokens": u.get("completion_tokens", 0) or 0,
                "total_tokens": u.get("total_tokens", 0) or 0,
            }

        return LLMResponse(
            content=msg.get("content", "") or "",
            reasoning=msg.get("reasoning_content"),
            tool_calls=tool_calls,
            usage=usage,
        )

    def _chat_stream(
        self,
        *,
        body: dict,
        stream_callback: Callable[[str], None],
        reasoning_callback: Callable[[str], None] | None = None,
        stop_event: threading.Event | None,
    ) -> LLMResponse:
        body = dict(body)
        body["stream"] = True
        body["stream_options"] = {"include_usage": True}

        content = ""
        reasoning = ""
        tool_calls_map: dict[int, dict] = {}
        usage: dict | None = None

        for line in self._request_stream(body):
            if stop_event and stop_event.is_set():
                break
            if not line:
                continue
            if line.startswith("data:"):
                data_str = line[5:]
                if data_str.startswith(" "):
                    data_str = data_str[1:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                if chunk.get("usage"):
                    u = chunk["usage"]
                    usage = {
                        "prompt_tokens": u.get("prompt_tokens", 0) or 0,
                        "completion_tokens": u.get("completion_tokens", 0) or 0,
                        "total_tokens": u.get("total_tokens", 0) or 0,
                    }
                choices = chunk.get("choices")
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                if delta.get("content"):
                    content += delta["content"]
                    stream_callback(delta["content"])
                rc = delta.get("reasoning_content")
                if rc:
                    reasoning += rc
                    if reasoning_callback:
                        reasoning_callback(rc)
                    else:
                        stream_callback(rc)
                tc_deltas = delta.get("tool_calls")
                if tc_deltas:
                    for tc_delta in tc_deltas:
                        idx = tc_delta.get("index", 0)
                        if idx not in tool_calls_map:
                            tool_calls_map[idx] = {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        entry = tool_calls_map[idx]
                        if tc_delta.get("id"):
                            entry["id"] = tc_delta["id"]
                        fn = tc_delta.get("function")
                        if fn:
                            if fn.get("name"):
                                entry["function"]["name"] += fn["name"]
                            if fn.get("arguments"):
                                entry["function"]["arguments"] += fn["arguments"]

        tool_calls = None
        if tool_calls_map:
            tool_calls = [
                ToolCallPayload(
                    id=v["id"],
                    name=v["function"]["name"],
                    arguments=v["function"]["arguments"] or "{}",
                )
                for v in tool_calls_map.values()
            ]
        return LLMResponse(
            content=content,
            reasoning=reasoning or None,
            tool_calls=tool_calls,
            usage=usage,
        )


__all__ = ["OpenAICompatProvider"]
