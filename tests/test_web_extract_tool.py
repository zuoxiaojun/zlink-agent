"""Tests for agent/tools/web_extract_tool.py — web page content extraction."""

from __future__ import annotations

import json

from agent.tools.web_extract_tool import _handle_web_extract, WEB_EXTRACT_SCHEMA


class TestWebExtractTool:
    def test_empty_url_returns_error(self):
        result = json.loads(_handle_web_extract({"url": ""}))
        assert result["success"] is False

    def test_invalid_url_returns_error(self):
        result = json.loads(_handle_web_extract({"url": "not-a-url"}))
        assert result["success"] is False

    def test_schema_is_valid(self):
        assert WEB_EXTRACT_SCHEMA["name"] == "web_extract"
        assert "urls" in WEB_EXTRACT_SCHEMA["parameters"]["required"]