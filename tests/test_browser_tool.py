"""Tests for the browser automation tool.

These tests verify the URL security filtering, schema definitions,
and tool registration.  They do NOT require Playwright to be
installed — they test the safety layer and tool metadata
in isolation.
"""

from __future__ import annotations

import pytest

from agent.tools.registry import registry


@pytest.fixture(autouse=True)
def ensure_browser_tools_registered():
    """Import browser_tool module to trigger registration."""
    import agent.tools.browser_tool  # noqa: F401

    yield


# ── URL Security ─────────────────────────────────────────────────


def test_blocked_file_protocol():
    """file:// URLs must be blocked."""
    from agent.tools.browser_tool import _is_blocked_url

    assert _is_blocked_url("file:///etc/passwd") is not None


def test_allowed_public_url():
    """Public HTTP/HTTPS URLs must be allowed."""
    from agent.tools.browser_tool import _is_blocked_url

    assert _is_blocked_url("https://www.example.com") is None
    assert _is_blocked_url("http://example.com") is None


def test_blocked_localhost():
    """localhost must be blocked."""
    from agent.tools.browser_tool import _is_blocked_url

    assert _is_blocked_url("http://localhost:8080") is not None
    assert _is_blocked_url("http://127.0.0.1") is not None


def test_blocked_private_ip():
    """Private IP ranges must be blocked."""
    from agent.tools.browser_tool import _is_blocked_url

    assert _is_blocked_url("http://10.0.0.1") is not None
    assert _is_blocked_url("http://192.168.1.1") is not None
    assert _is_blocked_url("http://172.16.0.1") is not None


def test_unsupported_protocol():
    """Only http/https must be allowed."""
    from agent.tools.browser_tool import _is_blocked_url

    assert _is_blocked_url("ftp://files.example.com") is not None
    assert _is_blocked_url("data:text/plain,hello") is not None


# ── Tool Registration ────────────────────────────────────────────


def test_all_browser_tools_registered():
    """All 8 browser tools must be registered."""
    browser_tools = [n for n in registry.get_all_tool_names() if n.startswith("browser_")]
    expected = {
        "browser_navigate",
        "browser_screenshot",
        "browser_click",
        "browser_fill",
        "browser_get_text",
        "browser_get_html",
        "browser_evaluate",
        "browser_close",
    }
    assert set(browser_tools) == expected


def test_browser_tools_have_risk_level():
    """Each browser tool must declare a risk_level."""
    browser_tools = [n for n in registry.get_all_tool_names() if n.startswith("browser_")]
    for name in browser_tools:
        entry = registry.get_entry(name)
        assert entry is not None
        assert entry.risk_level in ("low", "medium"), f"{name} risk_level={entry.risk_level}"


def test_browser_navigate_requires_url():
    """browser_navigate schema must require 'url'."""
    entry = registry.get_entry("browser_navigate")
    assert entry is not None
    params = entry.schema.get("parameters", {})
    assert "url" in params.get("required", [])


def test_browser_fill_requires_selector_and_value():
    """browser_fill schema must require 'selector' and 'value'."""
    entry = registry.get_entry("browser_fill")
    assert entry is not None
    params = entry.schema.get("parameters", {})
    assert "selector" in params.get("required", [])
    assert "value" in params.get("required", [])


def test_browser_click_requires_selector():
    """browser_click schema must require 'selector'."""
    entry = registry.get_entry("browser_click")
    assert entry is not None
    params = entry.schema.get("parameters", {})
    assert "selector" in params.get("required", [])
