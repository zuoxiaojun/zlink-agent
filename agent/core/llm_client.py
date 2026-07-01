"""LLM client — backwards-compatible thin shim.

M3 architecture
---------------
The original ``LLMClient`` (M1) was a 1:1 wrapper around the OpenAI SDK.
M3 introduces a polymorphic :class:`LLMProvider` abstraction in
:mod:`agent.core.llm_providers`.  This module is now a thin shim that
holds a provider and forwards calls to it.

Why keep this class
-------------------
* ``agent/agent.py`` instantiates ``LLMClient(...)`` and uses
  ``.client`` to make the compaction summary call.  Keeping the
  ``.client`` property working means the compaction path is unchanged.
* External code (MCP server, future scripts) that imported
  ``LLMClient`` keeps working.
* M5 cleanup can decide whether to remove this shim.

The shim is intentionally minimal — it does NOT re-implement retry,
streaming, or reasoning extraction.  Those live in
:mod:`agent.core.llm_providers.openai_compat` now.

Usage
-----
The old way (still works)::

    client = LLMClient(api_key="sk-...", base_url="https://api.openai.com/v1")
    response = client.chat(model="gpt-4o", messages=[...])

The new way (recommended for new code)::

    provider = get_provider("OpenAI", api_key="sk-...")
    response = provider.chat(model="gpt-4o", messages=[...])
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from agent.core.llm_providers.base import (
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    ToolCallPayload,
    chat_with_retry_or_error,
)
from agent.core.llm_providers.openai_compat import OpenAICompatProvider

logger = logging.getLogger(__name__)

# Re-export for callers that already imported these from this module.
__all__ = ["LLMClient", "LLMResponse", "ToolCallPayload"]


def _is_transient_error(error: BaseException) -> bool:
    """Heuristic: which exceptions are worth retrying?"""
    from agent.core.llm_providers.base import is_transient_error

    return is_transient_error(error)


def _extract_reasoning(msg: Any) -> str | None:
    """Extract ``reasoning_content`` from an API message (DeepSeek reasoning
    models, etc.).  Kept here for backward compatibility — M3 native
    path uses :func:`agent.core.llm_providers.openai_compat._extract_reasoning`."""
    from agent.core.llm_providers.openai_compat import _extract_reasoning

    return _extract_reasoning(msg)


class LLMClient:
    """Backwards-compatible shim.  Holds an :class:`LLMProvider` and
    forwards calls to it.

    Constructor signature is identical to M1.  Defaults to
    :class:`OpenAICompatProvider` so existing call sites keep working.
    For Anthropic, instantiate the provider directly via
    :func:`agent.core.llm_providers.get_provider`.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
        max_retries: int = 3,
        max_retry_delay: float = 30.0,
        provider: LLMProvider | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_retry_delay = max_retry_delay

        if provider is not None:
            self._provider = provider
        else:
            # Default: OpenAI compat.  This matches M1 behaviour.
            self._provider = OpenAICompatProvider(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
                max_retries=max_retries,
                max_retry_delay=max_retry_delay,
            )

        # Cached reference to the OpenAI client for the ``.client`` property.
        # M3's OpenAICompatProvider already has a ``.client`` that returns
        # an ``openai.OpenAI`` instance.  Anthropic's provider doesn't
        # expose ``.client`` — the property is a no-op in that case.
        self._client: Any = None

    @property
    def client(self) -> Any:
        """Return the raw OpenAI client (for code that needs the SDK
        directly — M4 compaction calls the summary LLM through here).

        For non-OpenAI providers, this raises a clear error.
        """
        if self._client is not None:
            return self._client
        if hasattr(self._provider, "client"):
            self._client = self._provider.client
            return self._client
        raise LLMProviderError(
            f"Provider {self._provider.name!r} does not expose a raw OpenAI "
            f"client.  Compaction should call provider.chat() instead.",
            transient=False,
        )

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
    ) -> LLMResponse:
        """Make a chat completion call.

        Never-throws — errors are returned as ``LLMResponse`` with
        ``error`` set and ``stop_reason="error"``.  The caller checks
        ``response.failed`` instead of catching exceptions.
        """
        return chat_with_retry_or_error(
            invoke=lambda: self._provider.chat(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                stream=stream,
                stream_callback=stream_callback,
                stop_event=stop_event,
            ),
            max_retries=self.max_retries,
            max_retry_delay=self.max_retry_delay,
            stop_event=stop_event,
        )
