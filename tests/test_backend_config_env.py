"""Tests for backend/config.py — _load_env_files candidate loading (B)."""

from __future__ import annotations

import os


def test_loads_user_level_env_before_root(monkeypatch, tmp_path):
    import backend.config as cfg

    env_dir = tmp_path / "data"
    env_dir.mkdir()
    (env_dir.parent / ".env").write_text("TAVILY_TEST_KEY=from-user-file\n", encoding="utf-8")
    monkeypatch.setattr(cfg, "DATA_DIR", env_dir)
    monkeypatch.delenv("TAVILY_TEST_KEY", raising=False)

    cfg._load_env_files()

    assert os.environ.get("TAVILY_TEST_KEY") == "from-user-file"


def test_existing_environment_variable_wins(monkeypatch, tmp_path):
    import backend.config as cfg

    env_dir = tmp_path / "data"
    env_dir.mkdir()
    (env_dir.parent / ".env").write_text("TAVILY_TEST_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setattr(cfg, "DATA_DIR", env_dir)
    monkeypatch.setenv("TAVILY_TEST_KEY", "from-env")

    cfg._load_env_files()

    assert os.environ.get("TAVILY_TEST_KEY") == "from-env"
