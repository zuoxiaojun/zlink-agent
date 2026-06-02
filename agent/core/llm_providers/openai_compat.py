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

import logging
import threading
from typing import Any, Callable

from openai import OpenAI

from agent.core.llm_providers.base import (
    LLMProvider,
    LLMResponse,
    ToolCallPayload,
    LLMProviderError,
    chat_with_retry,
)

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
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        """Lazy OpenAI client.  Exposed for M4 compaction which uses
        it to call the summary LLM directly."""
        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=1,
            )
        return self._client

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
        stop_event: threading.Event | None = None,
        max_retries: int | None = None,
        max_retry_delay: float | None = None,
    ) -> LLMResponse:
        api_kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            api_kwargs["max_tokens"] = max_tokens
        if tools:
            api_kwargs["tools"] = tools
            api_kwargs["tool_choice"] = tool_choice

        retries = self.max_retries if max_retries is None else max_retries
        retry_delay = self.max_retry_delay if max_retry_delay is None else max_retry_delay

        def _invoke() -> LLMResponse:
            try:
                if stream and stream_callback is not None:
                    return self._chat_stream(
                        api_kwargs=api_kwargs,
                        stream_callback=stream_callback,
                        stop_event=stop_event,
                    )
                return self._chat_blocking(api_kwargs)
            except Exception as e:
                # Wrap so the retry loop can inspect.
                raise LLMProviderError(
                    str(e), transient=False, cause=e,
                ) from e

        return chat_with_retry(
            invoke=_invoke,
            max_retries=retries,
            max_retry_delay=retry_delay,
            stop_event=stop_event,
        )

    # -- internals --

    def _chat_blocking(self, api_kwargs: dict) -> LLMResponse:
        resp = self.client.chat.completions.create(**api_kwargs)
        choice = resp.choices[0]
        msg = choice.message
        tool_calls: list[ToolCallPayload] | None = None
        if msg.tool_calls:
            tool_calls = [
                ToolCallPayload(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments or "{}",
                )
                for tc in msg.tool_calls
            ]
        usage = None
        try:
            if resp.usage:
                usage = {
                    "prompt_tokens": resp.usage.prompt_tokens or 0,
                    "completion_tokens": resp.usage.completion_tokens or 0,
                    "total_tokens": resp.usage.total_tokens or 0,
                }
        except Exception:
            pass
        return LLMResponse(
            content=msg.content or "",
            reasoning=_extract_reasoning(msg),
            tool_calls=tool_calls,
            usage=usage,
        )

    def _chat_stream(
        self,
        *,
        api_kwargs: dict,
        stream_callback: Callable[[str], None],
        stop_event: threading.Event | None,
    ) -> LLMResponse:
        response = self.client.chat.completions.create(
            **api_kwargs, stream=True,
            stream_options={"include_usage": True},
        )
        content = ""
        reasoning = ""
        tool_calls_map: dict[int, dict] = {}
        usage: dict | None = None

        for chunk in response:
            if stop_event and stop_event.is_set():
                break
            try:
                if chunk.usage:
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens or 0,
                        "completion_tokens": chunk.usage.completion_tokens or 0,
                        "total_tokens": chunk.usage.total_tokens or 0,
                    }
            except Exception:
                pass
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                content += delta.content
                # Caller passed stream_callback in the `if stream and stream_callback is not None`
                # branch above, so it's non-None here.
                assert stream_callback is not None
                stream_callback(delta.content)
            rc = getattr(delta, "reasoning_content", None)
            if rc:
                reasoning += rc
                if stream_callback is not None:
                    stream_callback(rc)
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_map:
                        tool_calls_map[idx] = {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    entry = tool_calls_map[idx]
                    if tc_delta.id:
                        entry["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            entry["function"]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            entry["function"]["arguments"] += tc_delta.function.arguments

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
