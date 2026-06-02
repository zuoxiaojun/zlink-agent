"""Tests for ``agent.config_manager``.

The M5+ release added the ``disabled_extensions`` key to the config
schema.  These tests lock in the load / save round-trip and the
defensive defaults that prevent old ``config.json`` files from
breaking the agent on load.
"""
from __future__ import annotations

import json

import pytest

from agent import config_manager


def test_load_returns_defaults_when_no_file(tmp_path, monkeypatch):
    """If config.json does not exist, load() returns the full default
    dict — including the M5+ ``disabled_extensions: []`` key."""
    monkeypatch.setattr(config_manager, "CONFIG_FILE", tmp_path / "config.json")
    cfg = config_manager.load()
    assert cfg == dict(config_manager._DEFAULT_CONFIG)
    assert cfg["disabled_extensions"] == []


def test_load_merges_user_data_over_defaults(tmp_path, monkeypatch):
    """If config.json exists, its keys override defaults, but missing
    keys still get the default value (defensive: stale config files
    don't crash the agent)."""
    f = tmp_path / "config.json"
    f.write_text(json.dumps({"llm_model": "claude-sonnet-4-5",
                             "disabled_extensions": ["security-event"]}))
    monkeypatch.setattr(config_manager, "CONFIG_FILE", f)

    cfg = config_manager.load()
    assert cfg["llm_model"] == "claude-sonnet-4-5"
    assert cfg["disabled_extensions"] == ["security-event"]
    # Defaults still present for keys not in the file
    assert cfg["llm_base_url"] == "https://api.openai.com/v1"
    assert cfg["compaction_enabled"] is True


def test_load_returns_defaults_on_corrupt_file(tmp_path, monkeypatch):
    """A broken JSON file should not crash the agent — load() must
    fall back to defaults rather than raising."""
    f = tmp_path / "config.json"
    f.write_text("{not valid json")
    monkeypatch.setattr(config_manager, "CONFIG_FILE", f)
    cfg = config_manager.load()
    assert cfg["llm_model"] == "gpt-4o"  # default
    assert cfg["disabled_extensions"] == []  # default


def test_save_filters_unknown_keys(tmp_path, monkeypatch):
    """save() must strip any keys that aren't in the schema, to
    prevent a typo or stale value from leaking into config.json."""
    f = tmp_path / "config.json"
    monkeypatch.setattr(config_manager, "CONFIG_FILE", f)

    config_manager.save({
        "llm_model": "x",  # known
        "totally_made_up_key": "y",  # unknown — should be dropped
        "disabled_extensions": ["a"],  # known
    })
    saved = json.loads(f.read_text())
    assert "totally_made_up_key" not in saved
    assert saved["llm_model"] == "x"
    assert saved["disabled_extensions"] == ["a"]


def test_round_trip_preserves_disabled_extensions(tmp_path, monkeypatch):
    """M5+ round-trip: load → modify → save → load must return the
    modified ``disabled_extensions`` list unchanged."""
    f = tmp_path / "config.json"
    monkeypatch.setattr(config_manager, "CONFIG_FILE", f)

    cfg = config_manager.load()
    cfg["disabled_extensions"] = ["log-everything"]
    config_manager.save(cfg)

    reloaded = config_manager.load()
    assert reloaded["disabled_extensions"] == ["log-everything"]
