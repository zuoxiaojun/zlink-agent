"""Tests for backend/api/chat.py — helper functions (non-WebSocket)."""

from __future__ import annotations

from agent.core.agent import ApprovalRequest


class TestGenerateSummary:
    def test_no_api_key_returns_none(self):
        from backend.api.chat import _generate_summary

        result = _generate_summary([{"role": "user", "content": "hello"}], "", "", "gpt-4o")
        assert result is None

    def test_no_messages_returns_none(self):
        from backend.api.chat import _generate_summary

        result = _generate_summary([], "sk-test", "http://example.com", "gpt-4o")
        assert result is None

    def test_empty_sample_returns_none(self):
        from backend.api.chat import _generate_summary

        result = _generate_summary(
            [{"role": "tool", "content": "result"}],
            "sk-test",
            "http://example.com",
            "gpt-4o",
        )
        assert result is None


class TestApprovalHelpers:
    def test_set_and_resolve_approval(self):
        from backend.api.chat import _resolve_pending_approval, _set_pending_approval

        req = ApprovalRequest(tool_name="test_tool", reason="safety check")
        _set_pending_approval("session_1", req)
        resolved = _resolve_pending_approval("session_1", True)
        assert resolved is True
        assert req.result == "approved"

    def test_resolve_nonexistent_returns_false(self):
        from backend.api.chat import _resolve_pending_approval

        resolved = _resolve_pending_approval("nonexistent", True)
        assert resolved is False

    def test_clear_pending(self):
        from backend.api.chat import _resolve_pending_approval, _set_pending_approval

        req = ApprovalRequest(tool_name="test", reason="test")
        _set_pending_approval("sid", req)
        _set_pending_approval("sid", None)
        resolved = _resolve_pending_approval("sid", True)
        assert resolved is False

    def test_deny_approval(self):
        from backend.api.chat import _resolve_pending_approval, _set_pending_approval

        req = ApprovalRequest(tool_name="test", reason="test")
        _set_pending_approval("sid", req)
        _resolve_pending_approval("sid", False)
        assert req.result == "denied"
