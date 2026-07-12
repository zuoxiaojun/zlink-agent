"""Tests for agent/tools/memory_tool.py — fact memory read/write."""

from __future__ import annotations

import json
from pathlib import Path

from agent.tools.memory_tool import (
    MEMORY_SCHEMA,
    _handle_memory,
)


class TestMemoryTool:
    def test_empty_action_returns_error(self):
        result = json.loads(_handle_memory({}))
        assert result["success"] is False

    def test_invalid_action_returns_error(self):
        result = json.loads(_handle_memory({"action": "unknown", "target": "memory"}))
        assert result["success"] is False

    def test_invalid_target_returns_error(self):
        result = json.loads(_handle_memory({"action": "list", "target": "unknown"}))
        assert result["success"] is False

    def test_add_without_content_returns_error(self):
        result = json.loads(_handle_memory({"action": "add", "target": "memory"}))
        assert result["success"] is False

    def test_replace_without_content_returns_error(self):
        result = json.loads(_handle_memory({"action": "replace", "target": "memory"}))
        assert result["success"] is False

    def test_remove_without_old_text_returns_error(self):
        result = json.loads(_handle_memory({"action": "remove", "target": "memory"}))
        assert result["success"] is False

    def test_schema_is_valid(self):
        assert MEMORY_SCHEMA["name"] == "memory"
        assert "parameters" in MEMORY_SCHEMA