"""ContextVar 会话上下文：产物目录解析 + 未设会话时返回 None。"""

from pathlib import Path

import pytest

from agent import session_context as ctx
from agent import session_manager as sm


@pytest.fixture
def sessions_root(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    root.mkdir()
    monkeypatch.setattr(sm, "SESSIONS_DIR", root)
    monkeypatch.setattr(sm, "INDEX_FILE", root / "index.json")
    yield root
    ctx.set_current_session(None)


def test_none_by_default():
    assert ctx.get_current_session() is None
    assert ctx.current_artifacts_dir() is None
    assert ctx.ensure_current_artifacts_dir() is None


def test_resolves_to_session_artifacts(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    assert ctx.get_current_session() == sid
    assert ctx.current_artifacts_dir() == sessions_root / sid / "artifacts"
    made = ctx.ensure_current_artifacts_dir()
    assert isinstance(made, Path) and made.is_dir()


def test_empty_string_session_means_no_session(sessions_root):
    ctx.set_current_session("")
    assert ctx.get_current_session() is None


def test_system_prompt_contains_artifact_dir(sessions_root):
    from agent.core.message_builder import build_system_prompt

    sid = sm.create_session()
    ctx.set_current_session(sid)
    text = build_system_prompt(base="B", artifact_dir=f"本次会话的产物目录：`{sm.artifacts_dir(sid)}`") or ""
    assert "## 会话产物" in text
    assert sid in text


def test_system_prompt_unchanged_without_artifact_dir():
    from agent.core.message_builder import build_system_prompt

    text = build_system_prompt(base="B") or ""
    assert "## 会话产物" not in text
    assert text.startswith("B")


def test_run_conversation_signature_frozen():
    """只允许**传**已有的 session_id 参数，不得增删形参。"""

    import inspect

    from agent.core.agent_adapter import AIAgent

    params = list(inspect.signature(AIAgent.run_conversation).parameters)
    assert params == [
        "self",
        "user_message",
        "system_message",
        "conversation_history",
        "stream_callback",
        "reasoning_callback",
        "stop_event",
        "session_id",
    ]
