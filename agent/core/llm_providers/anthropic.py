"""Anthropic native provider.

The Anthropic Messages API differs from OpenAI in three material ways:

1. **No system role in messages** — system content is a separate
   top-level field.
2. **Tool calls come back as ``content`` blocks** of type ``tool_use``,
   not as a separate ``tool_calls`` array.
3. **Tools are declared as ``tools: [{name, description, input_schema}]``,
   not as ``functions: {...}`` schemas.

This module translates between the two shapes.  Translation lives
entirely here — the agent loop sees only :class:`LLMResponse`.

Optional dependency
-------------------
The ``anthropic`` package is NOT a hard dependency.  Importing this
module works even when the package isn't installed; only calling
:meth:`AnthropicProvider.chat` raises a clear error.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from typing import Any

from agent.core.llm_providers.base import (
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    ToolCallPayload,
    chat_with_retry,
)

logger = logging.getLogger(__name__)


def _anthropic_tools_to_openai(tools: list[dict]) -> list[dict]:
    """Convert OpenAI tool schemas to Anthropic's shape.

    OpenAI: ``{"type":"function","function":{"name":...,"description":...,"parameters":{...}}}``
    Anthropic: ``{"name":...,"description":...,"input_schema":{...}}``
    """
    out = []
    for t in tools:
        fn = t.get("function", {})
        out.append(
            {
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            }
        )
    return out


def _anthropic_response_to_llm(response: Any) -> LLMResponse:
    """Convert an Anthropic Message response to LLMResponse.

    ``response.content`` is a list of typed blocks:
    * ``type=text``  → text content
    * ``type=tool_use`` → tool call
    * ``type=thinking`` → reasoning (extended thinking)
    """
    text_parts: list[str] = []
    tool_calls: list[ToolCallPayload] = []
    reasoning_parts: list[str] = []
    for block in response.content:
        btype = getattr(block, "type", None)
        if btype == "text":
            text_parts.append(block.text)
        elif btype == "tool_use":
            tool_calls.append(
                ToolCallPayload(
                    id=block.id,
                    name=block.name,
                    arguments=json.dumps(block.input or {}, ensure_ascii=False),
                )
            )
        elif btype == "thinking":
            # Extended thinking block (Claude 4)
            thinking_text = getattr(block, "thinking", None) or getattr(block, "text", None)
            if thinking_text:
                reasoning_parts.append(thinking_text)

    usage = None
    try:
        u = response.usage
        if u:
            usage = {
                "prompt_tokens": u.input_tokens or 0,
                "completion_tokens": u.output_tokens or 0,
                "total_tokens": (u.input_tokens or 0) + (u.output_tokens or 0),
            }
    except Exception:
        pass

    return LLMResponse(
        content="".join(text_parts),
        reasoning="\n".join(reasoning_parts) if reasoning_parts else None,
        tool_calls=tool_calls or None,
        usage=usage,
    )


def _split_system_from_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    """Anthropic wants system as a top-level field.  Extract the
    first system message and return the rest."""
    system_text = ""
    rest: list[dict] = []
    for m in messages:
        if m.get("role") == "system" and not system_text:
            content = m.get("content", "")
            if isinstance(content, str):
                system_text = content
            continue
        rest.append(m)
    return system_text, rest


def _messages_to_anthropic(messages: list[dict]) -> list[dict]:
    """Convert OpenAI-style messages to Anthropic's format.

    Differences:
    * OpenAI ``tool`` role → Anthropic ``user`` role with a
      ``tool_result`` content block.
    * OpenAI ``assistant`` with ``tool_calls`` → Anthropic ``assistant``
      with ``tool_use`` content blocks.
    """
    out: list[dict] = []
    pending_tool_results: list[dict] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "tool":
            # Batch consecutive tool results into one user message
            pending_tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": m.get("tool_call_id", ""),
                    "content": content if isinstance(content, str) else str(content),
                }
            )
            continue
        if pending_tool_results:
            out.append({"role": "user", "content": pending_tool_results})
            pending_tool_results = []
        if role == "assistant":
            blocks: list[dict] = []
            if content:
                blocks.append({"type": "text", "text": content})
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function", {})
                try:
                    inp = json.loads(fn.get("arguments") or "{}")
                except (json.JSONDecodeError, TypeError):
                    inp = {}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": fn.get("name", ""),
                        "input": inp,
                    }
                )
            if blocks:
                out.append({"role": "assistant", "content": blocks})
        elif role == "user":
            out.append({"role": "user", "content": content if isinstance(content, str) else str(content)})
    if pending_tool_results:
        out.append({"role": "user", "content": pending_tool_results})
    return out


class AnthropicProvider(LLMProvider):
    """Anthropic Messages API provider.

    Optional dependency: requires ``pip install anthropic``.  Importing
    this module is safe without the package; only :meth:`chat` raises
    a clear error pointing the user at the install command.
    """

    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.anthropic.com",
        timeout: float = 30.0,
        max_retries: int = 3,
        max_retry_delay: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_retry_delay = max_retry_delay
        self._client = None  # lazy

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic  # type: ignore[import-not-found]
            except ImportError as e:
                raise LLMProviderError(
                    "Anthropic provider requires the 'anthropic' package. Install it with: pip install anthropic",
                    transient=False,
                ) from e
            self._client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=0,  # we handle retries ourselves
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
        reasoning_callback: Callable[[str], None] | None = None,
        stop_event: threading.Event | None = None,
        max_retries: int | None = None,
        max_retry_delay: float | None = None,
    ) -> LLMResponse:
        # Stream path delegates to the same handler but with stream=True
        # on the SDK.  We keep the streaming consumer in a private method.
        system_text, rest = _split_system_from_messages(messages)
        anth_messages = _messages_to_anthropic(rest)

        anth_tools = _anthropic_tools_to_openai(tools) if tools else None

        # Anthropic requires max_tokens.  Default to 4096 if caller didn't set.
        anth_max = max_tokens if max_tokens is not None else 4096

        retries = self.max_retries if max_retries is None else max_retries
        retry_delay = self.max_retry_delay if max_retry_delay is None else max_retry_delay

        def _invoke() -> LLMResponse:
            try:
                client = self._get_client()
                if stream and stream_callback is not None:
                    return self._chat_stream(
                        client=client,
                        model=model,
                        system=system_text,
                        messages=anth_messages,
                        temperature=temperature,
                        max_tokens=anth_max,
                        tools=anth_tools,
                        stream_callback=stream_callback,
                        stop_event=stop_event,
                    )
                resp = client.messages.create(
                    model=model,
                    system=system_text or "",
                    messages=anth_messages,
                    temperature=temperature,
                    max_tokens=anth_max,
                    tools=anth_tools,
                )
                return _anthropic_response_to_llm(resp)
            except Exception as e:
                # Anthropic SDK has its own exception types; let the
                # retry helper's transient heuristic decide.
                raise LLMProviderError(str(e), transient=False, cause=e) from e

        return chat_with_retry(
            invoke=_invoke,
            max_retries=retries,
            max_retry_delay=retry_delay,
            stop_event=stop_event,
        )

    def _chat_stream(
        self,
        *,
        client: Any,
        model: str,
        system: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        tools: list[dict] | None,
        stream_callback: Callable[[str], None],
        stop_event: threading.Event | None,
    ) -> LLMResponse:
        """Streamed Anthropic call.

        Anthropic's event stream is richer than OpenAI's.  We collect:
        * ``text`` events → content
        * ``content_block_start`` with type=tool_use → start a tool call
        * ``content_block_delta`` with type=input_json_delta → append to
          the tool call's arguments
        * ``content_block_stop`` → close the tool call
        * ``message_delta`` with stop_reason → end of message
        """
        text = ""
        tool_calls_map: dict[int, dict] = {}  # block index → {id, name, args}
        thinking_parts: list[str] = []
        usage: dict | None = None

        with client.messages.stream(
            model=model,
            system=system or None,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
        ) as stream:
            current_block_idx: int = -1
            for event in stream:
                if stop_event and stop_event.is_set():
                    break
                etype = getattr(event, "type", None)
                if etype == "content_block_start":
                    block = event.content_block
                    btype = getattr(block, "type", None)
                    if btype == "tool_use":
                        current_block_idx = event.index
                        tool_calls_map[event.index] = {
                            "id": block.id,
                            "name": block.name,
                            "arguments": "",
                        }
                    elif btype == "thinking":
                        # No-op; we'll get the text via deltas
                        pass
                elif etype == "content_block_delta":
                    delta = event.delta
                    dtype = getattr(delta, "type", None)
                    if dtype == "text_delta":
                        chunk = delta.text
                        text += chunk
                        if stream_callback is not None:
                            stream_callback(chunk)
                    elif dtype == "input_json_delta":
                        partial = delta.partial_json
                        idx = event.index
                        if idx in tool_calls_map:
                            tool_calls_map[idx]["arguments"] += partial
                    elif dtype == "thinking_delta":
                        chunk = getattr(delta, "thinking", "") or ""
                        thinking_parts.append(chunk)
                elif etype == "message_delta":
                    usage_obj = getattr(event, "usage", None)
                    if usage_obj:
                        in_t = getattr(usage_obj, "input_tokens", 0) or 0
                        out_t = getattr(usage_obj, "output_tokens", 0) or 0
                        usage = {
                            "prompt_tokens": in_t,
                            "completion_tokens": out_t,
                            "total_tokens": in_t + out_t,
                        }

        tool_calls = None
        if tool_calls_map:
            tool_calls = [
                ToolCallPayload(
                    id=v["id"],
                    name=v["name"],
                    arguments=v["arguments"] or "{}",
                )
                for _, v in sorted(tool_calls_map.items())
            ]

        return LLMResponse(
            content=text,
            reasoning="\n".join(thinking_parts) if thinking_parts else None,
            tool_calls=tool_calls,
            usage=usage,
        )


__all__ = ["AnthropicProvider"]
