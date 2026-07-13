"""Tests for ``agent.config_manager``.

The M5+ release added the ``disabled_extensions`` key to the config
schema.  These tests lock in the load / save round-trip and the
defensive defaults that prevent old ``config.json`` files from
breaking the agent on load.
"""

from __future__ import annotations

import json

from agent import config_manager
from agent.config_model import AppConfig


def test_load_returns_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager, "CONFIG_FILE", tmp_path / "config.json")
    cfg = config_manager.load()
    assert isinstance(cfg, AppConfig)
    assert cfg.disabled_extensions == []


def test_load_merges_user_data_over_defaults(tmp_path, monkeypatch):
    f = tmp_path / "config.json"
    f.write_text(json.dumps({"llm_model": "claude-sonnet-4-5", "disabled_extensions": ["security-event"]}))
    monkeypatch.setattr(config_manager, "CONFIG_FILE", f)

    cfg = config_manager.load()
    assert cfg.llm_model == "claude-sonnet-4-5"
    assert cfg.disabled_extensions == ["security-event"]
    assert cfg.llm_base_url == "https://api.openai.com/v1"
    assert cfg.compaction_enabled is True


def test_load_returns_defaults_on_corrupt_file(tmp_path, monkeypatch):
    f = tmp_path / "config.json"
    f.write_text("{not valid json")
    monkeypatch.setattr(config_manager, "CONFIG_FILE", f)
    cfg = config_manager.load()
    assert cfg.llm_model == "gpt-4o"
    assert cfg.disabled_extensions == []


def test_save_filters_unknown_keys(tmp_path, monkeypatch):
    f = tmp_path / "config.json"
    monkeypatch.setattr(config_manager, "CONFIG_FILE", f)

    cfg = AppConfig(llm_model="x", disabled_extensions=["a"])
    config_manager.save(cfg)
    saved = json.loads(f.read_text())
    assert "totally_made_up_key" not in saved
    assert saved["llm_model"] == "x"
    assert saved["disabled_extensions"] == ["a"]


def test_round_trip_preserves_disabled_extensions(tmp_path, monkeypatch):
    f = tmp_path / "config.json"
    monkeypatch.setattr(config_manager, "CONFIG_FILE", f)

    cfg = config_manager.load()
    cfg.disabled_extensions = ["log-everything"]
    config_manager.save(cfg)

    reloaded = config_manager.load()
    assert reloaded.disabled_extensions == ["log-everything"]


def test_save_sets_owner_only_permissions_on_config_file(tmp_path, monkeypatch):
    """``save()`` must chmod ``config.json`` to 0600 so plain-JSON secrets
    are not readable by other local users.

    Skipped on Windows because os.chmod on Windows only honours the
    read-only bit and cannot grant/revoke owner-only semantics.
    """
    import sys

    if sys.platform == "win32":
        return

    f = tmp_path / "config.json"
    monkeypatch.setattr(config_manager, "CONFIG_FILE", f)

    cfg = AppConfig(llm_api_key="sk-test", ys_app_secret="secret")
    config_manager.save(cfg)

    mode = f.stat().st_mode & 0o777
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


def test_save_overwrite_resets_permissions(tmp_path, monkeypatch):
    """A second ``save()`` re-tightens perms even if a previous write
    left them looser (defence-in-depth against external edits)."""
    import os
    import sys

    if sys.platform == "win32":
        return

    f = tmp_path / "config.json"
    monkeypatch.setattr(config_manager, "CONFIG_FILE", f)

    cfg = AppConfig(llm_api_key="sk-test")
    config_manager.save(cfg)

    # Simulate a user manually widening perms
    os.chmod(f, 0o644)

    config_manager.save(cfg)
    mode = f.stat().st_mode & 0o777
    assert mode == 0o600, f"expected 0o600 after re-save, got {oct(mode)}"
