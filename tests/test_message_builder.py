"""Tests for agent/core/message_builder.py — system prompt and turn message assembly."""

from __future__ import annotations

from agent.core.message_builder import (
    build_system_prompt,
    build_turn_messages,
    strip_images_from_messages,
)


class TestBuildSystemPrompt:
    def test_returns_string_when_base_provided(self):
        result = build_system_prompt(base="你是助手")
        assert result is not None
        assert "你是助手" in result

    def test_returns_string_with_time_when_no_base(self):
        result = build_system_prompt(base="")
        # Even without base, time info is always included
        assert result is not None

    def test_erp_context_appended_when_provided(self):
        result = build_system_prompt(base="你是助手", erp_context="YonSuite ✅")
        assert result is not None
        assert "可用数据源" in result
        assert "YonSuite" in result

    def test_erp_context_empty_when_not_provided(self):
        result = build_system_prompt(base="你是助手")
        # Should not contain the section when no erp_context given
        assert "可用数据源" not in result


class TestBuildTurnMessages:
    def test_empty_history_creates_single_user_message(self):
        msgs = build_turn_messages(None, "hello")
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "hello"

    def test_with_history_appends_user_message(self):
        history = [{"role": "user", "content": "prev"}, {"role": "assistant", "content": "resp"}]
        msgs = build_turn_messages(history, "next")
        assert len(msgs) == 3
        assert msgs[-1]["role"] == "user"
        assert msgs[-1]["content"] == "next"

    def test_none_history_is_handled(self):
        msgs = build_turn_messages(None, "test")
        assert len(msgs) == 1

    def test_empty_list_history_is_handled(self):
        msgs = build_turn_messages([], "test")
        assert len(msgs) == 1


class TestStripImagesFromMessages:
    def test_removes_image_blocks(self):
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hello"},
                    {"type": "image_url", "image_url": {"url": "data:image/..."}},
                ],
            }
        ]
        stripped = strip_images_from_messages(msgs)
        assert len(stripped) == 1
        content = stripped[0]["content"]
        if isinstance(content, list):
            assert all(b.get("type") != "image_url" for b in content)

    def test_preserves_text_only_messages(self):
        msgs = [{"role": "user", "content": "hello"}]
        stripped = strip_images_from_messages(msgs)
        assert stripped == msgs
