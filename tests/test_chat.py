"""Tests for backend/api/chat.py — helper functions + WebSocket."""

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


class TestWebSocketIntegration:
    """WS round-trip using FastAPI ``TestClient``.

    The previously-uncovered surface of ``chat.py`` (real ``ws_chat``
    entry + no-api-key error path) is exercised here.  Skip the
    session-creation happy path because it spawns a real AIAgent that
    touches ``loop.run_in_executor`` and is harder to drive from sync
    test code without rewriting the agent surface.
    """

    def test_no_api_key_returns_error_frame(self, monkeypatch):
        """When ``llm_api_key`` is empty the WS endpoint must publish
        a single ``error`` frame and close — never hang or crash."""
        from agent import config_manager

        cfg = config_manager.load().model_copy(deep=True)
        cfg.llm_api_key = ""

        def fail_on_config_save(*_args, **_kwargs):
            raise AssertionError("WebSocket tests must not write config.json")

        monkeypatch.setattr(config_manager, "load", lambda: cfg)
        monkeypatch.setattr(config_manager, "save", fail_on_config_save)

        from fastapi.testclient import TestClient

        from backend.main import app

        client = TestClient(app)
        with client.websocket_connect("/ws/chat/sess-no-key") as ws:
            first = ws.receive_json()
            assert first["type"] == "error"
            assert "API Key" in first["message"]
            # Server should close the WS after the error frame —
            # a second receive raises an exception on the client side.
            # Server-side close may surface as ``WebSocketDisconnect``
            # or a runtime error ("Cannot call receive once the connection
            # is closed").  Both are valid signals that the WS was closed
            # after the error frame, which is all the test needs to verify.
            with __import__("pytest").raises(Exception):  # noqa: B017
                ws.receive_json()

    def test_approval_callback_round_trip(self):
        """The same registry-based approval flow used by chat.py's
        ``_on_approval_request`` must round-trip a request through
        set / resolve correctly."""
        from agent.core.agent import ApprovalRequest
        from backend.api.chat import (
            _resolve_pending_approval,
            _set_pending_approval,
        )

        req = ApprovalRequest(tool_name="terminal", reason="dangerous")
        _set_pending_approval("sess-approval-cb", req)

        assert _resolve_pending_approval("sess-approval-cb", True) is True
        assert req.result == "approved"

        # Setting None clears the registry entry
        req2 = ApprovalRequest(tool_name="delete_file", reason="rm")
        _set_pending_approval("sess-approval-cb", req2)
        _set_pending_approval("sess-approval-cb", None)
        assert _resolve_pending_approval("sess-approval-cb", True) is False
