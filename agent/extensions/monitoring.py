"""MonitoringExtension — records Prometheus metrics from agent events.

Subscribes to the M2 event bus and pushes counts / durations / gauges
into :mod:`agent.core.metrics`.  This is the thinnest possible layer:
the extension just reads events and calls ``record_*()`` methods on
the collector singleton.
"""

from __future__ import annotations

import logging
import time

from agent.core.metrics import get_metrics
from agent.events import (
    AfterLLMCallEvent,
    AfterToolCallEvent,
    BeforeLLMCallEvent,
    BeforeToolCallEvent,
    Extension,
    SessionBeforeCompactEvent,
    SessionEndEvent,
    SessionStartEvent,
)

logger = logging.getLogger(__name__)


class MonitoringExtension(Extension):
    """Records metrics for every agent event."""

    name = "monitoring"
    enabled = True

    def __init__(self) -> None:
        super().__init__()
        self._metrics = get_metrics()
        self._llm_start: float = 0.0
        self._tool_start: float = 0.0

    def on_session_start(self, event: SessionStartEvent) -> None:
        self._metrics.sessions_total.labels(status="started").inc()
        self._metrics.active_sessions.inc()

    def on_session_end(self, event: SessionEndEvent) -> None:
        if event.error:
            self._metrics.sessions_total.labels(status="error").inc()
            self._metrics.errors_total.labels(type="session_error").inc()
        else:
            self._metrics.sessions_total.labels(status="completed").inc()
        self._metrics.active_sessions.dec()

    def on_before_llm_call(self, event: BeforeLLMCallEvent) -> None:
        self._llm_start = time.monotonic()

    def on_after_llm_call(self, event: AfterLLMCallEvent) -> None:
        model = event.model
        duration = time.monotonic() - self._llm_start
        usage = event.response.usage or {}
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        self._metrics.record_llm_call(
            model=model,
            duration=duration,
            status="success",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def on_before_tool_call(self, event: BeforeToolCallEvent) -> None:
        self._tool_start = time.monotonic()

    def on_after_tool_call(self, event: AfterToolCallEvent) -> None:
        tool = event.tool_name
        duration = time.monotonic() - self._tool_start
        self._metrics.record_tool_call(tool, duration, "success")

    def on_session_before_compact(self, event: SessionBeforeCompactEvent) -> None:
        self._metrics.compactions_total.inc()
