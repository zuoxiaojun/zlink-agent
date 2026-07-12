"""Tests for agent/tools/process_tool.py — process management."""

from __future__ import annotations

import json

from agent.tools.process_tool import process_tool, PROCESS_SCHEMA


class TestProcessTool:
    def test_list_contains_processes(self):
        result = json.loads(process_tool("list"))
        assert result["success"] is True
        assert "data" in result

    def test_invalid_action_returns_error(self):
        result = json.loads(process_tool("unknown"))
        assert result["success"] is False

    def test_empty_action_defaults_to_list(self):
        result = json.loads(process_tool(""))
        assert result["success"] is True
        assert "data" in result

    def test_kill_without_pid_still_executes(self):
        result = json.loads(process_tool("kill"))
        # Should try to kill but gracefully handle missing pid
        assert "success" in result

    def test_schema_is_valid(self):
        assert PROCESS_SCHEMA["name"] == "process"