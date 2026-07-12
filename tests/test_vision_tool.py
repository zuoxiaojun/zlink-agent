"""Tests for agent/tools/vision_tool.py — image analysis via LLM vision."""

from __future__ import annotations

import json

from agent.tools.vision_tool import (
    _is_data_uri,
    _image_to_base64,
    vision_analyze_tool,
    VISION_ANALYZE_SCHEMA,
)


# ── _is_data_uri ───────────────────────────────────────────────────


class TestIsDataUri:
    def test_data_uri_png(self):
        assert _is_data_uri("data:image/png;base64,abc123") is True

    def test_data_uri_jpeg(self):
        assert _is_data_uri("data:image/jpeg;base64,xyz") is True

    def test_http_url(self):
        assert _is_data_uri("https://example.com/photo.jpg") is False

    def test_empty_string(self):
        assert _is_data_uri("") is False

    def test_data_without_image_prefix(self):
        assert _is_data_uri("data:text/plain;base64,abc") is False


# ── _image_to_base64 ───────────────────────────────────────────────


class FakeClient:
    def __init__(self, content: bytes, content_type: str = "image/png"):
        self._content = content
        self._content_type = content_type

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url, **kw):
        class Resp:
            def raise_for_status(self):
                pass

            @property
            def content(self):
                return self._content_data

            @property
            def headers(self):
                return {"content-type": self._ctype}

            def __init__(self, content, ctype):
                self._content_data = content
                self._ctype = ctype

        return Resp(self._content, self._content_type)


class TestImageToBase64:
    def test_http_success(self, monkeypatch):
        png_data = b"\x89PNG\r\n\x1a\n" + b"x" * 100

        monkeypatch.setattr(
            "agent.tools.vision_tool.httpx.Client",
            lambda **kw: FakeClient(png_data, "image/png"),
        )
        result = _image_to_base64("https://example.com/img.png")
        assert result is not None
        assert result.startswith("data:image/png;base64,")

    def test_http_error_returns_none(self, monkeypatch):
        class ErrClient:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def get(self, url, **kw):
                raise Exception("HTTP error")

        monkeypatch.setattr("agent.tools.vision_tool.httpx.Client", lambda **kw: ErrClient())
        assert _image_to_base64("https://example.com/img.png") is None

    def test_empty_url_returns_none(self):
        assert _image_to_base64("") is None


# ── vision_analyze_tool ────────────────────────────────────────────


class TestVisionAnalyzeTool:
    def test_empty_image_url(self):
        result = json.loads(vision_analyze_tool(""))
        assert "error" in result

    def test_schema_is_valid(self):
        assert VISION_ANALYZE_SCHEMA["name"] == "vision_analyze"
        assert VISION_ANALYZE_SCHEMA["parameters"]["required"] == ["image_url"]