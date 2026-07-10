"""Metrics REST API — Prometheus /metrics endpoint + enriched health check.

Endpoints
---------
* ``GET /api/metrics``       — Prometheus text exposition format
* ``GET /api/health``        — replaces the inline health check with detail
"""

import logging
import time

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from backend.api.system_api import _get_version

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])

# Track server start time for uptime
_SERVER_START = time.time()


def _prometheus_metrics() -> str:
    """Return Prometheus metrics as text (inline generation)."""
    from prometheus_client import REGISTRY, generate_latest

    return generate_latest(REGISTRY).decode("utf-8")


@router.get("/api/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    """Prometheus metrics endpoint (text exposition format)."""
    return _prometheus_metrics()


@router.get("/api/health")
def health() -> dict:
    """Rich health check with uptime and dependency status."""
    from agent.tools.mcp_manager import _connections

    return {
        "status": "ok",
        "uptime_seconds": time.time() - _SERVER_START,
        "version": _get_version(),
        "mcp_servers_connected": len(_connections),
    }
