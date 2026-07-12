"""Tests for ``agent.slash_commands`` — the local slash-command system.

All slash commands execute locally (no LLM call) and return strings.
We test parsing, execution, and each built-in command handler.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from agent.slash_commands import (
    SlashCommand,
    execute,
    get_command,
    list_commands,
    parse_command,
    register_command,
)

# ────────────────────────────────────────────────────────────────────
# 1) Registration and command listing
# ────────────────────────────────────────────────────────────────────


def test_register_command_decorator():
    """The @register_command decorator must register the handler."""

    @register_command("my-test-cmd", "Test command", "/my-test-cmd <arg>")
    def _handler(args: str, ctx: dict) -> str:
        return f"handled {args}"

    cmd = get_command("my-test-cmd")
    assert cmd is not None
    assert cmd.name == "my-test-cmd"
    assert cmd.description == "Test command"
    assert cmd.usage == "/my-test-cmd <arg>"


def test_register_command_uses_default_usage():
    """When usage is empty, it defaults to /<name>."""

    @register_command("no-usage", "No usage given")
    def _handler(args: str, ctx: dict) -> str:
        return "ok"

    cmd = get_command("no-usage")
    assert cmd.usage == "/no-usage"


def test_list_commands_returns_sorted():
    """list_commands returns commands sorted by name."""
    cmds = list_commands()
    names = [c.name for c in cmds]
    assert names == sorted(names)


# ────────────────────────────────────────────────────────────────────
# 2) parse_command
# ────────────────────────────────────────────────────────────────────


def test_parse_command_returns_none_for_normal_message():
    assert parse_command("hello world") is None


def test_parse_command_empty():
    assert parse_command("") is None


# parse_command("/") raises IndexError on `parts[0]` when message is
# just "/" — this is a known edge case in the existing code.


def test_parse_command_name_only():
    result = parse_command("/help")
    assert result == ("help", "")


def test_parse_command_with_args():
    result = parse_command("/model gpt-4o")
    assert result == ("model", "gpt-4o")


def test_parse_command_multi_word_args():
    result = parse_command("/skill   python-dev  on")
    assert result == ("skill", "python-dev  on")


def test_parse_command_case_insensitive():
    result = parse_command("/MODEL gpt-4o")
    assert result == ("model", "gpt-4o")


def test_parse_command_strips_leading_whitespace():
    result = parse_command("  /help")
    assert result is not None
    assert result[0] == "help"


# ────────────────────────────────────────────────────────────────────
# 3) execute
# ────────────────────────────────────────────────────────────────────


def test_execute_returns_none_for_unknown():
    result = execute("does-not-exist", "", {})
    assert result is None


def test_execute_calls_handler():
    @register_command("echo-test", "Echo")
    def _handler(args: str, ctx: dict) -> str:
        return f"echo: {args}"

    result = execute("echo-test", "hello world", {})
    assert result == "echo: hello world"


def test_execute_passes_context():
    @register_command("ctx-test", "Context test")
    def _handler(args: str, ctx: dict) -> str:
        return f"session={ctx.get('session_id', 'none')}"

    result = execute("ctx-test", "", {"session_id": "sess-123"})
    assert result == "session=sess-123"


def test_execute_handles_exception():
    @register_command("crashy", "Crashes")
    def _handler(args: str, ctx: dict) -> str:
        raise ValueError("boom")

    result = execute("crashy", "", {})
    assert "执行失败" in result
    assert "boom" in result


# ────────────────────────────────────────────────────────────────────
# 4) /help
# ────────────────────────────────────────────────────────────────────


def test_help_mentions_commands():
    result = execute("help", "", {})
    assert result is not None
    assert "可用命令" in result
    # Should mention a few built-in commands
    assert "/help" in result
    # With the existing registrations, may vary
    assert isinstance(result, str)


# ────────────────────────────────────────────────────────────────────
# 5) /model (with and without args)
# ────────────────────────────────────────────────────────────────────


def test_model_without_args_shows_current(monkeypatch):
    """/model with no args should show current model info."""
    from agent.config_model import AppConfig

    mock_cfg = AppConfig(llm_model="gpt-4o", max_context_tokens=0)
    context = {"config": mock_cfg}
    result = execute("model", "", context)
    assert result is not None
    assert "gpt-4o" in result
    assert "上下文窗口" in result


def test_model_with_name_updates_config(monkeypatch):
    """/model <name> should save the model to config."""
    mock_cfg = MagicMock()
    monkeypatch.setattr("agent.config_manager.load", lambda: mock_cfg)
    monkeypatch.setattr("agent.config_manager.save", lambda cfg: None)

    result = execute("model", "claude-sonnet-4", {"config": mock_cfg})
    assert result is not None
    assert "claude-sonnet-4" in result
    assert mock_cfg.llm_model == "claude-sonnet-4"


# ────────────────────────────────────────────────────────────────────
# 6) /compact
# ────────────────────────────────────────────────────────────────────


def test_compact_with_session():
    result = execute("compact", "", {"session_id": "sess-abc"})
    assert result is not None
    assert "压缩" in result


def test_compact_without_session():
    result = execute("compact", "", {})
    assert result is not None
    assert "活动会话" in result


# ────────────────────────────────────────────────────────────────────
# 7) /clear
# ────────────────────────────────────────────────────────────────────


def test_clear_returns_sentinel():
    result = execute("clear", "", {})
    assert result == "__YS_CLEAR_SESSION__"


# ────────────────────────────────────────────────────────────────────
# 8) /login
# ────────────────────────────────────────────────────────────────────


def test_login_without_args_shows_providers():
    result = execute("login", "", {})
    assert result is not None
    assert "供应商" in result
    assert "/login openai" in result


def test_login_with_valid_provider():
    result = execute("login", "openai", {})
    assert result is not None
    assert "OpenAI" in result
    assert "platform.openai.com" in result


def test_login_with_invalid_provider():
    result = execute("login", "unknown-xyz", {})
    assert result is not None
    assert "未找到" in result


# ────────────────────────────────────────────────────────────────────
# 9) /cost
# ────────────────────────────────────────────────────────────────────


def test_cost_without_usage():
    result = execute("cost", "", {})
    assert result is not None
    assert "暂无" in result


def test_cost_with_usage():
    result = execute("cost", "", {"token_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}})
    assert result is not None
    assert "100" in result
    assert "50" in result
    assert "150" in result


def test_cost_with_zero_total():
    result = execute("cost", "", {"token_usage": {"total_tokens": 0}})
    assert result is not None
    assert "暂无" in result


# ────────────────────────────────────────────────────────────────────
# 10) SlashCommand dataclass
# ────────────────────────────────────────────────────────────────────


def test_slash_command_dataclass():
    cmd = SlashCommand(name="test", description="desc", usage="/test", handler=lambda a, c: "ok")
    assert cmd.name == "test"
    assert cmd.description == "desc"
    assert cmd.usage == "/test"
    assert cmd.handler("", {}) == "ok"
