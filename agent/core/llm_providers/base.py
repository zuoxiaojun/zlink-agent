"""Provider abstraction — base classes and shared types.

The unified response shape is the same one ``LLMClient`` already used
in M1/M2, so the agent loop doesn't need to change.  Provider
implementations adapt their native response into :class:`LLMResponse`.

Why dataclasses
---------------
* Easy to construct from any provider's native type via ``__init__``.
* Type-checked in IDE / pyright.
* Immutable-ish — providers don't need to mutate after returning.

Why not Pydantic
----------------
* LLMResponse is internal — never serialised to a user-facing API.
* Avoid pulling in a heavy dependency for one dataclass.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from agent.context_compactor import estimate_tokens

logger = logging.getLogger(__name__)


@dataclass
class ToolCallPayload:
    """Parsed tool call in OpenAI shape, regardless of provider."""

    id: str
    name: str
    arguments: str  # raw JSON string (kept as string for stream fidelity)


@dataclass
class LLMResponse:
    """Unified response shape returned by every :class:`LLMProvider`.

    Fields
    ------
    * ``content``     — assistant text, may be empty when the model only
      returned tool calls (matches OpenAI semantics).
    * ``reasoning``   — extended thinking / chain-of-thought from
      providers that expose it (DeepSeek R1, Claude extended thinking).
      ``None`` for providers that don't.
    * ``tool_calls``  — list of tool calls, or ``None`` for a final text
      response.
    * ``usage``       — ``{prompt_tokens, completion_tokens, total_tokens}``
      or ``None`` if the provider didn't report usage.
    * ``error``       — non-empty when the call failed (never-throw
      contract).  The agent loop checks this instead of catching
      exceptions.  See :func:`chat_with_retry_or_error`.
    * ``stop_reason`` — ``"error"`` when ``error`` is set, ``"end_turn"``
      for normal completion, or ``None``.
    """

    content: str = ""
    reasoning: str | None = None
    tool_calls: list[ToolCallPayload] | None = None
    usage: dict | None = field(default_factory=dict)
    error: str = ""
    stop_reason: str | None = None

    @property
    def failed(self) -> bool:
        """Convenience: was this response an error?"""
        return bool(self.error)


class LLMProviderError(RuntimeError):
    """Wraps any provider-specific error so callers can catch one type.

    Subclass of ``RuntimeError`` so it doesn't shadow built-in
    ``Exception`` patterns.  Provider classes raise this; the retry
    layer (``_chat_with_retry``) inspects ``.transient`` to decide
    whether to retry.
    """

    def __init__(self, message: str, *, transient: bool = False, cause: Exception | None = None):
        super().__init__(message)
        self.transient = transient
        self.__cause__ = cause


def is_transient_error(error: BaseException) -> bool:
    """Heuristic: which errors are worth retrying?

    Used by every provider's retry loop.  Conservative — we'd rather
    retry a permanent error once than fail on a transient one.
    """
    msg = str(error).lower()
    transient_markers = [
        "rate limit",
        "rate_limit",
        "429",
        "server error",
        "500",
        "502",
        "503",
        "504",
        "timeout",
        "timed out",
        "connection",
        "too many requests",
        "overloaded",
        "internal server error",
        "service unavailable",
    ]
    return any(m in msg for m in transient_markers)


def chat_with_retry(
    *,
    invoke: Callable[[], LLMResponse],
    max_retries: int,
    max_retry_delay: float,
    stop_event: threading.Event | None,
    on_retry: Callable[[int, float, BaseException], None] | None = None,
) -> LLMResponse:
    """Run *invoke* with exponential-backoff retry on transient errors.

    *invoke* should raise :class:`LLMProviderError` (with ``transient=True``
    for retryable failures) or any other exception (treated as transient
    if :func:`is_transient_error` matches).
    """
    last_error: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            return invoke()
        except LLMProviderError as e:
            last_error = e
            transient = e.transient or is_transient_error(e)
            if not transient or attempt >= max_retries:
                raise
            delay = min(2**attempt + random.uniform(0, 1), max_retry_delay)
            logger.warning(
                "LLM call failed (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1,
                max_retries,
                delay,
                e,
            )
            if on_retry:
                on_retry(attempt + 1, delay, e)
            if stop_event:
                stop_event.wait(delay)
            else:
                time.sleep(delay)
        except Exception as e:
            last_error = e
            if not is_transient_error(e) or attempt >= max_retries:
                raise
            delay = min(2**attempt + random.uniform(0, 1), max_retry_delay)
            logger.warning(
                "LLM call failed (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1,
                max_retries,
                delay,
                e,
            )
            if on_retry:
                on_retry(attempt + 1, delay, e)
            if stop_event:
                stop_event.wait(delay)
            else:
                time.sleep(delay)
    # Should never reach here — the loop either returns or raises.
    assert last_error is not None
    raise last_error


def chat_with_retry_or_error(
    *,
    invoke: Callable[[], LLMResponse],
    max_retries: int,
    max_retry_delay: float,
    stop_event: threading.Event | None = None,
    on_retry: Callable[[int, float, BaseException], None] | None = None,
) -> LLMResponse:
    """Never-throw variant of :func:`chat_with_retry`.

    Catches *all* exceptions and returns an ``LLMResponse`` with
    ``error`` set and ``stop_reason="error"``.  The caller never
    needs a try/except — it inspects ``response.failed`` instead.

    This is the **recommended** entry point for LLM calls in production.
    """
    try:
        return chat_with_retry(
            invoke=invoke,
            max_retries=max_retries,
            max_retry_delay=max_retry_delay,
            stop_event=stop_event,
            on_retry=on_retry,
        )
    except Exception as e:
        logger.error("LLM call failed after %d retries: %s", max_retries, e)
        return LLMResponse(
            error=str(e),
            stop_reason="error",
        )


class LLMProvider(ABC):
    """Abstract base class for all LLM providers.

    Subclasses implement :meth:`chat` to call their native SDK and
    adapt the response into :class:`LLMResponse`.  The base class
    provides the retry loop and the ``estimate_tokens`` hook (M4 will
    replace the heuristic with provider-specific tokenisers).

    Public methods
    --------------
    * :meth:`chat`         — make one chat completion call.
    * :meth:`estimate_tokens` — heuristic token estimate (M3 default).
    """

    name: str = "base"

    @property
    def client(self) -> Any:
        """Optional raw SDK client.

        :class:`OpenAICompatProvider` exposes an ``openai.OpenAI``
        instance here for code that needs to call the SDK directly
        (e.g. M4 compaction's summary call).  Providers that don't
        have a raw client (Anthropic) can leave this as ``None`` —
        callers should fall back to :meth:`chat` in that case.
        """
        return None

    @abstractmethod
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
        max_retries: int = 3,
        max_retry_delay: float = 30.0,
    ) -> LLMResponse:
        """Make a chat completion call.

        Implementations should wrap their native SDK call in
        :func:`chat_with_retry` so retries work uniformly.
        """

    def estimate_tokens(self, text: str) -> int:
        """Conservative heuristic.  Providers may override with their
        own tokeniser (M4 will use tiktoken for OpenAI providers when
        available)."""
        return estimate_tokens(text)


__all__ = [
    "LLMProvider",
    "LLMResponse",
    "ToolCallPayload",
    "LLMProviderError",
    "is_transient_error",
    "chat_with_retry",
]
