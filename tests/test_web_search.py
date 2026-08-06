"""Tests for the web_search provider fallback chain (agent/tools/web_tools.py).

Zero-network policy: every httpx call is replaced by a scriptable fake
client, so nothing in this file touches the real internet.
"""

from __future__ import annotations

import json

import httpx
import pytest

from agent.tools.web_tools import (
    _call_provider,
    _search_brave,
    _search_ddg_instant_answer,
    _search_duckduckgo,
    _search_tavily,
    web_search_tool,
)

CUSTOM_URL = "https://custom.example/search"
TAVILY_URL = "https://api.tavily.com/search"
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
DDG_IA_URL = "https://api.duckduckgo.com/"
DDG_HTML_URL = "https://html.duckduckgo.com/html/"

HTML_RESULTS = (
    '<a rel="nofollow" class="result__a" href="http://ex.com">Example</a><a class="result__snippet">Snippet text</a>'
)

# A DDG Instant Answer response with no abstract and no related topics.
DEFAULT_EMPTY = {"AbstractText": "", "AbstractURL": "", "Heading": "", "RelatedTopics": []}


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_data: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "http://fake.invalid/")
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=request,
                response=httpx.Response(self.status_code, request=request),
            )

    def json(self) -> dict:
        if self._json_data is None:
            raise ValueError("no JSON body in fake response")
        return self._json_data


class _FakeClient:
    """Scriptable httpx.Client stand-in. Routes are keyed by base URL."""

    def __init__(self, routes: dict | None = None, raise_exc=None, **kwargs):
        self._routes = routes or {}
        self._raise_exc = raise_exc  # callable(url) -> Exception | None
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def _resolve(self, url: str, **kwargs):
        self.calls.append(url)
        if self._raise_exc is not None:
            exc = self._raise_exc(url)
            if exc is not None:
                raise exc
        # Unregistered URLs fail loudly (404) so a wrong-order call is visible.
        return self._routes.get(url, _FakeResponse(status_code=404))

    def get(self, url: str, **kwargs):
        return self._resolve(url, **kwargs)

    def post(self, url: str, **kwargs):
        return self._resolve(url, **kwargs)


def _patch_client(monkeypatch, routes=None, raise_exc=None) -> _FakeClient:
    fake = _FakeClient(routes=routes, raise_exc=raise_exc)
    monkeypatch.setattr("agent.tools.web_tools.httpx.Client", lambda **kw: fake)
    return fake


@pytest.fixture(autouse=True)
def _clean_search_env(monkeypatch):
    for key in ("SEARCH_API_URL", "SEARCH_API_KEY", "TAVILY_API_KEY", "BRAVE_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def _search(query: str, limit: int = 5) -> dict:
    return json.loads(web_search_tool(query, limit))


# ── Chain order & first-success-wins ────────────────────────────────


class TestFallbackChainOrder:
    def test_first_tier_custom_api_success_does_not_degrade(self, monkeypatch):
        monkeypatch.setenv("SEARCH_API_URL", CUSTOM_URL)
        monkeypatch.setenv("TAVILY_API_KEY", "t-key")
        monkeypatch.setenv("BRAVE_API_KEY", "b-key")
        fake = _patch_client(
            monkeypatch,
            routes={
                CUSTOM_URL: _FakeResponse(
                    json_data={"results": [{"title": "Custom", "url": "http://c", "snippet": "s"}]}
                )
            },
        )
        out = _search("q")
        assert out["success"] is True
        assert out["data"]["result_count"] == 1
        assert fake.calls == [CUSTOM_URL]

    def test_custom_api_failure_falls_through_to_tavily(self, monkeypatch):
        monkeypatch.setenv("SEARCH_API_URL", CUSTOM_URL)
        monkeypatch.setenv("TAVILY_API_KEY", "t-key")
        monkeypatch.setenv("BRAVE_API_KEY", "b-key")
        fake = _patch_client(
            monkeypatch,
            routes={
                CUSTOM_URL: _FakeResponse(status_code=500),
                TAVILY_URL: _FakeResponse(
                    json_data={"results": [{"title": "Tavily", "url": "http://t", "content": "tc"}]}
                ),
            },
        )
        out = _search("q")
        assert out["success"] is True
        assert out["data"]["results"][0]["title"] == "Tavily"
        assert fake.calls == [CUSTOM_URL, TAVILY_URL]

    def test_401_degrades_to_next_provider(self, monkeypatch):
        monkeypatch.setenv("SEARCH_API_URL", CUSTOM_URL)
        monkeypatch.setenv("TAVILY_API_KEY", "t-key")
        monkeypatch.setenv("BRAVE_API_KEY", "b-key")
        fake = _patch_client(
            monkeypatch,
            routes={
                CUSTOM_URL: _FakeResponse(status_code=500),
                TAVILY_URL: _FakeResponse(status_code=401),
                BRAVE_URL: _FakeResponse(
                    json_data={"web": {"results": [{"title": "Brave", "url": "http://b", "description": "bd"}]}}
                ),
            },
        )
        out = _search("q")
        assert out["success"] is True
        assert out["data"]["results"][0]["title"] == "Brave"
        assert fake.calls == [CUSTOM_URL, TAVILY_URL, BRAVE_URL]

    def test_zero_config_uses_duckduckgo_instant_answer(self, monkeypatch):
        fake = _patch_client(
            monkeypatch,
            routes={
                DDG_IA_URL: _FakeResponse(
                    json_data={
                        "Heading": "Python",
                        "AbstractText": "Python is a language.",
                        "AbstractURL": "http://py",
                        "RelatedTopics": [],
                    }
                )
            },
        )
        out = _search("q")
        assert out["success"] is True
        assert out["data"]["results"][0]["snippet"] == "Python is a language."
        assert fake.calls == [DDG_IA_URL]

    def test_zero_config_html_crawler_fallback(self, monkeypatch):
        fake = _patch_client(
            monkeypatch,
            routes={DDG_IA_URL: _FakeResponse(json_data=DEFAULT_EMPTY), DDG_HTML_URL: _FakeResponse(text=HTML_RESULTS)},
        )
        out = _search("q")
        assert out["success"] is True
        assert out["data"]["result_count"] == 1
        assert fake.calls == [DDG_IA_URL, DDG_HTML_URL]


# ── Error classification: config (401/403) vs transient ─────────────


class TestErrorClassification:
    def test_tavily_401_is_config(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "t-key")
        _patch_client(monkeypatch, routes={TAVILY_URL: _FakeResponse(status_code=401)})
        ok, reason, kind = _call_provider(_search_tavily, "q", 5)
        assert ok is False
        assert kind == "config"
        assert reason == "key 无效(401)"

    def test_tavily_403_is_config(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "t-key")
        _patch_client(monkeypatch, routes={TAVILY_URL: _FakeResponse(status_code=403)})
        ok, reason, kind = _call_provider(_search_tavily, "q", 5)
        assert ok is False
        assert kind == "config"

    def test_tavily_5xx_is_transient(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "t-key")
        _patch_client(monkeypatch, routes={TAVILY_URL: _FakeResponse(status_code=502)})
        ok, reason, kind = _call_provider(_search_tavily, "q", 5)
        assert ok is False
        assert kind == "transient"
        assert reason == "HTTP 502"

    def test_brave_timeout_is_transient(self, monkeypatch):
        monkeypatch.setenv("BRAVE_API_KEY", "b-key")

        def fail(url):
            if url == BRAVE_URL:
                return httpx.ConnectTimeout("timed out")
            return None

        _patch_client(monkeypatch, raise_exc=fail)
        ok, reason, kind = _call_provider(_search_brave, "q", 5)
        assert ok is False
        assert kind == "transient"
        assert reason == "超时"

    def test_network_error_is_transient(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "t-key")

        def fail(url):
            if url == TAVILY_URL:
                return httpx.ConnectError("connection refused")
            return None

        _patch_client(monkeypatch, raise_exc=fail)
        ok, reason, kind = _call_provider(_search_tavily, "q", 5)
        assert ok is False
        assert kind == "transient"
        assert reason == "网络错误"


# ── All tiers fail → aggregated Chinese error ───────────────────────


class TestAllFailAggregation:
    def test_error_lists_every_provider_failure_and_hint(self, monkeypatch):
        monkeypatch.setenv("SEARCH_API_URL", CUSTOM_URL)
        monkeypatch.setenv("TAVILY_API_KEY", "t-key")
        monkeypatch.setenv("BRAVE_API_KEY", "b-key")
        _patch_client(
            monkeypatch,
            routes={
                CUSTOM_URL: _FakeResponse(status_code=500),
                TAVILY_URL: _FakeResponse(status_code=401),
                BRAVE_URL: _FakeResponse(status_code=500),
                DDG_IA_URL: _FakeResponse(json_data=DEFAULT_EMPTY),
                DDG_HTML_URL: _FakeResponse(status_code=500),
            },
        )
        out = _search("q")
        assert out["success"] is False
        error = out["error"]
        assert "custom-api: HTTP 500" in error
        assert "tavily: key 无效(401)" in error
        assert "brave: HTTP 500" in error
        assert "duckduckgo: HTTP 500" in error
        assert "搜索暂不可用，请勿重复重试；可在 .env 配置 TAVILY_API_KEY 等搜索 key" in error

    def test_zero_config_all_fail_reports_duckduckgo_only(self, monkeypatch):
        _patch_client(
            monkeypatch,
            routes={DDG_IA_URL: _FakeResponse(status_code=500), DDG_HTML_URL: _FakeResponse(status_code=500)},
        )
        out = _search("q")
        assert out["success"] is False
        assert "duckduckgo: HTTP 500" in out["error"]
        assert "tavily:" not in out["error"]


# ── DDG Instant Answer parsing ──────────────────────────────────────


class TestDdgInstantAnswer:
    def test_parses_abstract_and_related_topics(self, monkeypatch):
        data = {
            "Heading": "Python",
            "AbstractText": "Python is a programming language.",
            "AbstractURL": "https://en.wikipedia.org/wiki/Python",
            "RelatedTopics": [
                {"Text": "Python 3.12 release notes", "FirstURL": "https://docs.python.org/3/whatsnew/3.12.html"},
                {"Text": "Python for beginners", "FirstURL": "https://www.python.org/about/gettingstarted/"},
            ],
        }
        _patch_client(monkeypatch, routes={DDG_IA_URL: _FakeResponse(json_data=data)})
        out = json.loads(_search_ddg_instant_answer("python", 5))
        assert out["success"] is True
        results = out["data"]["results"]
        assert len(results) == 3
        assert results[0]["title"] == "Python"
        assert results[0]["url"] == "https://en.wikipedia.org/wiki/Python"
        assert results[0]["snippet"] == "Python is a programming language."
        assert results[1]["title"] == "Python 3.12 release notes"
        assert results[1]["url"] == "https://docs.python.org/3/whatsnew/3.12.html"

    def test_respects_limit(self, monkeypatch):
        data = {
            "AbstractText": "abs",
            "AbstractURL": "http://abs",
            "RelatedTopics": [{"Text": f"topic {i}", "FirstURL": f"http://t{i}"} for i in range(5)],
        }
        _patch_client(monkeypatch, routes={DDG_IA_URL: _FakeResponse(json_data=data)})
        out = json.loads(_search_ddg_instant_answer("q", 2))
        assert out["data"]["result_count"] == 2

    def test_skips_non_dict_related_topics(self, monkeypatch):
        data = {
            "AbstractText": "abs",
            "AbstractURL": "http://abs",
            "RelatedTopics": [
                ["nested", {"Text": "inner", "FirstURL": "http://inner"}],
                {"Text": "flat topic", "FirstURL": "http://flat"},
            ],
        }
        _patch_client(monkeypatch, routes={DDG_IA_URL: _FakeResponse(json_data=data)})
        out = json.loads(_search_ddg_instant_answer("q", 5))
        assert len(out["data"]["results"]) == 2  # abstract + flat topic

    def test_duckduckgo_skips_html_when_instant_answer_has_results(self, monkeypatch):
        fake = _patch_client(
            monkeypatch,
            routes={
                DDG_IA_URL: _FakeResponse(
                    json_data={"AbstractText": "abs", "AbstractURL": "http://abs", "RelatedTopics": []}
                ),
                DDG_HTML_URL: _FakeResponse(text=HTML_RESULTS),
            },
        )
        out = json.loads(_search_duckduckgo("q", 5))
        assert out["success"] is True
        assert out["data"]["result_count"] == 1
        assert fake.calls == [DDG_IA_URL]
