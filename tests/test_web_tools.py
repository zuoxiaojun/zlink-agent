"""Tests for agent/tools/web_tools.py — web search with DDG html.parser."""

from __future__ import annotations

import json

from agent.tools.web_tools import (
    _check_web_search,
    _DDGResultParser,
    _format_results,
    _search_duckduckgo,
    _search_via_api,
    web_search_tool,
)

# ── _DDGResultParser ───────────────────────────────────────────────


class TestDDGResultParser:
    def _parse(self, html: str) -> _DDGResultParser:
        parser = _DDGResultParser()
        parser.feed(html)
        parser.close()
        return parser

    def test_parse_empty_html(self):
        parser = self._parse("")
        assert parser.results == []

    def test_parse_no_results(self):
        parser = self._parse("<html><body><p>No results found</p></body></html>")
        assert parser.results == []

    def test_parse_single_result(self):
        html = (
            '<html><a rel="nofollow" class="result__a" href="https://example.com">'
            "Example Title</a>"
            '<a class="result__snippet">Example snippet text</a>'
        )
        parser = self._parse(html)
        assert len(parser.results) == 1
        assert parser.results[0]["title"] == "Example Title"
        assert parser.results[0]["url"] == "https://example.com"
        assert parser.results[0]["snippet"] == "Example snippet text"

    def test_parse_multiple_results(self):
        html = (
            '<a rel="nofollow" class="result__a" href="http://a.com">Title A</a>'
            '<a class="result__snippet">Snippet A</a>'
            '<a rel="nofollow" class="result__a" href="http://b.com">Title B</a>'
            '<a class="result__snippet">Snippet B</a>'
        )
        parser = self._parse(html)
        assert len(parser.results) == 2
        assert parser.results[0]["title"] == "Title A"

    def test_parse_handles_missing_url(self):
        """Result link without href should be skipped."""
        html = '<a rel="nofollow" class="result__a">No href</a>'
        parser = self._parse(html)
        assert parser.results == []

    def test_parse_handles_nested_tags(self):
        """Title with nested tags should still be captured."""
        html = '<a rel="nofollow" class="result__a" href="http://x.com"><b>Bold</b> Title</a>'
        parser = self._parse(html)
        assert len(parser.results) == 1
        assert "Title" in parser.results[0]["title"]


# ── _format_results ────────────────────────────────────────────────


class TestFormatResults:
    def test_formats_empty_list(self):
        result = _format_results([], "test query")
        assert result["query"] == "test query"
        assert result["results"] == []
        assert result["result_count"] == 0

    def test_formats_with_results(self):
        results = [{"title": "A", "url": "http://a", "snippet": "snip"}]
        result = _format_results(results, "q")
        assert result["result_count"] == 1


# ── _search_duckduckgo (mocked) ────────────────────────────────────


class FakeResponse:
    def __init__(self, text: str, status: int = 200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, resp: FakeResponse):
        self._resp = resp

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url, **kwargs):
        return self._resp


class TestSearchDuckduckgo:
    def test_success(self, monkeypatch):
        html = (
            '<a rel="nofollow" class="result__a" href="http://ex.com">Example</a><a class="result__snippet">Snippet</a>'
        )

        def fake_client(*args, **kwargs):
            return FakeClient(FakeResponse(html))

        monkeypatch.setattr("agent.tools.web_tools.httpx.Client", fake_client)
        result = _search_duckduckgo("test", 5)
        data = json.loads(result)
        assert data["success"] is True
        assert len(data["data"]["results"]) == 1

    def test_limit_respects_max_results(self, monkeypatch):
        html = (
            '<a rel="nofollow" class="result__a" href="http://a.com">A</a>'
            '<a class="result__snippet">Sa</a>'
            '<a rel="nofollow" class="result__a" href="http://b.com">B</a>'
            '<a class="result__snippet">Sb</a>'
            '<a rel="nofollow" class="result__a" href="http://c.com">C</a>'
            '<a class="result__snippet">Sc</a>'
        )

        def fake_client(*args, **kwargs):
            return FakeClient(FakeResponse(html))

        monkeypatch.setattr("agent.tools.web_tools.httpx.Client", fake_client)
        result = _search_duckduckgo("test", 2)
        data = json.loads(result)
        assert data["data"]["result_count"] == 2

    def test_http_error_returns_error(self, monkeypatch):
        def fake_client(*args, **kwargs):
            return FakeClient(FakeResponse("", 500))

        monkeypatch.setattr("agent.tools.web_tools.httpx.Client", fake_client)
        result = _search_duckduckgo("test", 5)
        data = json.loads(result)
        assert data["success"] is False


# ── _search_via_api (mocked) ───────────────────────────────────────


class FakePostClient:
    def __init__(self, resp_data: dict, status: int = 200):
        self._data = resp_data
        self._status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def post(self, url, **kw):
        class Resp:
            def __init__(self, data, status):
                self._data = data
                self._status = status

            def raise_for_status(self):
                if self._status >= 400:
                    raise Exception(f"HTTP {self._status}")

            def json(self):
                return self._data

        return Resp(self._data, self._status)


class TestSearchViaApi:
    def test_success(self, monkeypatch):
        fake = FakePostClient({"results": [{"title": "A", "url": "http://a"}]})

        monkeypatch.setattr("agent.tools.web_tools.httpx.Client", lambda **kw: fake)
        result = _search_via_api("test", 5, "http://api/search", "key-123")
        data = json.loads(result)
        assert data["success"] is True

    def test_failure_returns_error(self, monkeypatch):
        fake = FakePostClient({}, 500)

        monkeypatch.setattr("agent.tools.web_tools.httpx.Client", lambda **kw: fake)
        result = _search_via_api("test", 5, "http://api/search", "key-123")
        data = json.loads(result)
        assert data["success"] is False


# ── web_search_tool (integration) ──────────────────────────────────


class TestWebSearchTool:
    def test_uses_duckduckgo_by_default(self, monkeypatch):
        called = False

        def fake_ddg(q, limit):
            nonlocal called
            called = True
            return json.dumps({"success": True, "data": {"results": [], "result_count": 0}})

        monkeypatch.setattr("agent.tools.web_tools._search_duckduckgo", fake_ddg)
        monkeypatch.setattr("agent.tools.web_tools._get_search_url", lambda: "")
        web_search_tool("test")
        assert called is True

    def test_uses_api_when_url_is_set(self, monkeypatch):
        called = False

        def fake_api(q, limit, url, key):
            nonlocal called
            called = True
            return json.dumps({"success": True, "data": {"results": [], "result_count": 0}})

        monkeypatch.setattr("agent.tools.web_tools._search_via_api", fake_api)
        monkeypatch.setattr("agent.tools.web_tools._get_search_url", lambda: "http://api/search")
        web_search_tool("test")
        assert called is True

    def test_check_fn_returns_true(self):
        assert _check_web_search() is True
