"""Tests for the /api/tools REST endpoint lazy tool discovery.

Covers the deferred discover_tools() behavior: tool modules must be
imported lazily (first use) rather than at module import time, so they
stay off the backend startup path.
"""

from __future__ import annotations

import threading


def test_ensure_discovered_idempotent():
    from backend.api import tools_api

    tools_api._ensure_discovered()
    tools_api._ensure_discovered()  # second call must not raise
    assert tools_api._discovered is True


def test_ensure_discovered_thread_safe():
    from backend.api import tools_api

    tools_api._discovered = False
    threads = [threading.Thread(target=tools_api._ensure_discovered) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert tools_api._discovered is True


def test_list_tools_triggers_discovery(isolated_config):
    """The GET /api/tools endpoint returns built-in tools via lazy discovery."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.api.tools_api import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    resp = client.get("/api/tools")
    assert resp.status_code == 200
    names = [t["name"] for t in resp.json()]
    assert len(names) > 0
