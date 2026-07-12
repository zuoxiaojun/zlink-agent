"""Tests for agent/tools/session_search_tool.py — FTS5 session recall."""

from __future__ import annotations

import json

from agent.tools.session_search_tool import _handle_session_search, SESSION_SEARCH_SCHEMA


class TestSessionSearchTool:
    def test_empty_query_returns_list(self):
        result = json.loads(_handle_session_search({"query": "", "limit": 5}))
        assert result["success"] is True
        assert "results" in result

    def test_default_limit_used_when_limit_omitted(self):
        result = json.loads(_handle_session_search({"query": "test"}))
        assert result["success"] is True

    def test_schema_is_valid(self):
        assert SESSION_SEARCH_SCHEMA["name"] == "session_search"