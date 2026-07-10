"""Metrics collector — agent-level counters, histograms, and gauges.

Uses ``prometheus_client`` when available; degrades gracefully to a
no-op stub when the package is not installed (so the agent core never
hard-depends on it).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Gauge, Histogram

    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False

    class _Stub:
        """prometheus_client 不可用时的 no-op 占位。"""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            # 真实 prometheus_client.Counter/Gauge/Histogram 的 __init__ 需要参数,
            # 降级 stub 必须吞掉所有参数,否则 MetricsCollector() 会抛 TypeError。
            pass

        def labels(self, **_labels: Any) -> _Stub:
            return self

        def inc(self, _amount: float = 1) -> None:
            pass

        def observe(self, _amount: float) -> None:
            pass

        def set(self, _value: float) -> None:
            pass

    Counter = _Stub  # type: ignore
    Gauge = _Stub  # type: ignore
    Histogram = _Stub  # type: ignore


class MetricsCollector:
    """Singleton that owns all Prometheus metric objects.

    Access via :func:`get_metrics`.
    """

    def __init__(self) -> None:
        if not _HAS_PROMETHEUS:
            logger.info("prometheus_client not installed — metrics are no-ops")

        # -- Sessions --
        self.sessions_total = Counter(
            "ys_agent_sessions_total",
            "Total sessions processed",
            ["status"],
        )
        self.active_sessions = Gauge(
            "ys_agent_active_sessions",
            "Currently active sessions",
        )

        # -- LLM calls --
        self.llm_calls_total = Counter(
            "ys_agent_llm_calls_total",
            "Total LLM calls",
            ["model", "status"],
        )
        self.llm_call_duration = Histogram(
            "ys_agent_llm_call_duration_seconds",
            "LLM call latency",
            ["model"],
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, float("inf")),
        )
        self.llm_tokens_total = Counter(
            "ys_agent_llm_tokens_total",
            "Tokens consumed by LLM calls",
            ["type"],
        )
        self.llm_retries_total = Counter(
            "ys_agent_llm_retries_total",
            "Retried LLM calls",
            ["model"],
        )

        # -- Tool calls --
        self.tool_calls_total = Counter(
            "ys_agent_tool_calls_total",
            "Total tool calls",
            ["tool", "status"],
        )
        self.tool_call_duration = Histogram(
            "ys_agent_tool_call_duration_seconds",
            "Tool call latency",
            ["tool"],
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, float("inf")),
        )

        # -- Errors --
        self.errors_total = Counter(
            "ys_agent_errors_total",
            "Total errors by category",
            ["type"],
        )

        # -- MCP --
        self.mcp_connected_servers = Gauge(
            "ys_agent_mcp_connected_servers",
            "Number of connected MCP servers",
        )

        # -- Memory --
        self.memory_operations_total = Counter(
            "ys_agent_memory_operations_total",
            "Memory read/write operations",
            ["operation"],
        )

        # -- Compaction --
        self.compactions_total = Counter(
            "ys_agent_compactions_total",
            "Context compaction runs",
        )
        self.compaction_tokens_saved = Counter(
            "ys_agent_compaction_tokens_saved",
            "Total tokens saved by compaction",
        )

    # -- Convenience helpers --

    def record_llm_call(
        self,
        model: str,
        duration: float,
        status: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        self.llm_calls_total.labels(model=model, status=status).inc()
        self.llm_call_duration.labels(model=model).observe(duration)
        if prompt_tokens:
            self.llm_tokens_total.labels(type="prompt").inc(prompt_tokens)
        if completion_tokens:
            self.llm_tokens_total.labels(type="completion").inc(completion_tokens)

    def record_tool_call(self, tool: str, duration: float, status: str) -> None:
        self.tool_calls_total.labels(tool=tool, status=status).inc()
        self.tool_call_duration.labels(tool=tool).observe(duration)


# Module-level singleton
_METRICS: MetricsCollector | None = None


def get_metrics() -> MetricsCollector:
    global _METRICS
    if _METRICS is None:
        _METRICS = MetricsCollector()
    return _METRICS
