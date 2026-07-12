"""Tests for agent/tools/project_tools.py — named analysis workspaces."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.tools.project_tools import project_list, project_create, project_switch, PROJECTS_FILE


@pytest.fixture(autouse=True)
def isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("agent.tools.project_tools.PROJECTS_FILE", tmp_path / "projects.json")


class TestProjectList:
    def test_empty_list(self):
        result = json.loads(project_list())
        assert result["projects"] == []

    def test_after_create_shows_project(self, isolate):
        project_create("test-project")
        result = json.loads(project_list())
        assert len(result["projects"]) == 1
        assert result["projects"][0]["name"] == "test-project"
        assert result["projects"][0]["active"] is True


class TestProjectCreate:
    def test_create_valid(self, isolate):
        result = json.loads(project_create("my-project"))
        assert result["success"] is True
        assert result["name"] == "my-project"

    def test_create_empty_name_returns_error(self, isolate):
        result = json.loads(project_create(""))
        assert result["success"] is False

    def test_create_duplicate_returns_error(self, isolate):
        project_create("unique")
        result = json.loads(project_create("unique"))
        assert result["success"] is False

    def test_create_duplicate_case_insensitive(self, isolate):
        project_create("ProjectX")
        result = json.loads(project_create("projectx"))
        assert result["success"] is False


class TestProjectSwitch:
    def test_switch_by_id(self, isolate):
        created = json.loads(project_create("switcher"))
        sid = created["id"]
        result = json.loads(project_switch(sid))
        assert result["success"] is True

    def test_switch_by_name(self, isolate):
        project_create("target")
        result = json.loads(project_switch("target"))
        assert result["success"] is True

    def test_switch_nonexistent_returns_error(self, isolate):
        result = json.loads(project_switch("nonexistent"))
        assert result["success"] is False

    def test_switch_empty_name_returns_error(self, isolate):
        result = json.loads(project_switch(""))
        assert result["success"] is False