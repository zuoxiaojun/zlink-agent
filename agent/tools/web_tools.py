"""Web search and extraction tools for ZLink Agent.

Port of Hermes web_tools.py — simplified using httpx directly.
``web_search`` uses a provider fallback chain: custom API
(SEARCH_API_URL) → Tavily (TAVILY_API_KEY) → Brave (BRAVE_API_KEY) →
DuckDuckGo (zero-config, Instant Answer + HTML crawler). The first tier
that succeeds wins; if every tier fails, the error lists each tier's
failure reason.
"""

import html.parser
import json
import logging
import os

import httpx

from agent.tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

# Per-tier timeouts (seconds). The DuckDuckGo tier is the least reliable
# zero-config fallback, so it gets a shorter budget.
_TIMEOUT_API = 15.0
_TIMEOUT_DDG = 8.0


def _get_search_url() -> str:
    """Get the search API URL from env, default to DuckDuckGo via a libre approach."""
    return os.getenv("SEARCH_API_URL", "")


def _get_search_api_key() -> str:
    return os.getenv("SEARCH_API_KEY", "")


def _check_web_search() -> bool:
    """Check if web search is available (at minimum, we can use httpx directly)."""
    return True


def _call_provider(fn, *args) -> tuple[bool, str, str]:
    """Run one search provider.

    Returns ``(success, payload, kind)``:

    - success=True  → payload is the ``tool_result`` JSON to return.
    - success=False → payload is the failure reason (user-visible Chinese)
      and kind is ``"transient"`` (network error / timeout / 5xx) or
      ``"config"`` (401/403 — bad key; retrying will not help).
    """
    try:
        payload = fn(*args)
    except Exception as e:
        logger.warning("Search provider raised: %s", e)
        return False, "provider 内部异常", "transient"
    try:
        data = json.loads(payload)
    except Exception:
        return False, "provider 返回数据无法解析", "transient"
    if data.get("success"):
        return True, payload, ""
    return False, data.get("error", "未知错误"), data.get("error_kind", "transient")


def _has_results(payload: str) -> bool:
    """True if a provider JSON envelope carries at least one result."""
    try:
        return bool(json.loads(payload).get("data", {}).get("results"))
    except Exception:
        return False


def _classify_http_status(e: httpx.HTTPStatusError, *, config_statuses: bool = False) -> tuple[str, str]:
    """Map an HTTP error to ``(user-visible reason, error kind)``.

    With ``config_statuses=True`` a 401/403 is treated as a bad-key
    config error; keyless providers (DuckDuckGo) treat it as a plain
    HTTP error instead.
    """
    status = e.response.status_code
    if config_statuses and status in (401, 403):
        return f"key 无效({status})", "config"
    return f"HTTP {status}", "transient"


def web_search_tool(query: str, limit: int = 5) -> str:
    """Perform a web search using a provider fallback chain.

    Order: custom API (SEARCH_API_URL) → Tavily (TAVILY_API_KEY) → Brave
    (BRAVE_API_KEY) → DuckDuckGo (zero-config). The first tier that
    succeeds wins; if every tier fails, the returned error lists each
    tier's failure reason plus a hint about configuring a search key.
    """
    failures: list[str] = []

    api_url = _get_search_url()
    if api_url:
        ok, payload, _ = _call_provider(_search_via_api, query, limit, api_url, _get_search_api_key())
        if ok:
            return payload
        failures.append(f"custom-api: {payload}")

    if os.getenv("TAVILY_API_KEY", "").strip():
        ok, payload, _ = _call_provider(_search_tavily, query, limit)
        if ok:
            return payload
        failures.append(f"tavily: {payload}")

    if os.getenv("BRAVE_API_KEY", "").strip():
        ok, payload, _ = _call_provider(_search_brave, query, limit)
        if ok:
            return payload
        failures.append(f"brave: {payload}")

    # Last tier: DuckDuckGo — zero-config, no API key needed.
    ok, payload, _ = _call_provider(_search_duckduckgo, query, limit)
    if ok:
        return payload
    failures.append(f"duckduckgo: {payload}")

    joined = "；".join(failures)
    hint = "搜索暂不可用，请勿重复重试；可在 .env 配置 TAVILY_API_KEY 等搜索 key"
    logger.warning("All web search providers failed: %s", joined)
    return tool_error(f"所有搜索后端均失败：{joined}。{hint}")


def _search_via_api(query: str, limit: int, api_url: str, api_key: str) -> str:
    """Tier 1: search via a configured custom API endpoint (SEARCH_API_URL)."""
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {"query": query, "limit": limit}

        with httpx.Client(timeout=_TIMEOUT_API) as client:
            resp = client.post(api_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", data.get("organic", []))
        return tool_result(data=_format_results(results, query))
    except httpx.HTTPStatusError as e:
        reason, kind = _classify_http_status(e, config_statuses=True)
        return tool_error(reason, error_kind=kind)
    except httpx.TimeoutException:
        return tool_error("超时")
    except httpx.HTTPError:
        return tool_error("网络错误")
    except Exception as e:
        logger.warning("Custom API search failed: %s", e)
        return tool_error(f"异常: {e}")


def _search_tavily(query: str, limit: int) -> str:
    """Tier 2: Tavily Search API (requires TAVILY_API_KEY)."""
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return tool_error("未配置 TAVILY_API_KEY")
    try:
        payload = {"api_key": api_key, "query": query, "max_results": limit}
        with httpx.Client(timeout=_TIMEOUT_API) as client:
            resp = client.post("https://api.tavily.com/search", json=payload)
            resp.raise_for_status()
            data = resp.json()

        results = [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")}
            for r in data.get("results", [])
        ][:limit]
        return tool_result(data=_format_results(results, query))
    except httpx.HTTPStatusError as e:
        reason, kind = _classify_http_status(e, config_statuses=True)
        return tool_error(reason, error_kind=kind)
    except httpx.TimeoutException:
        return tool_error("超时")
    except httpx.HTTPError:
        return tool_error("网络错误")
    except Exception as e:
        logger.warning("Tavily search failed: %s", e)
        return tool_error(f"异常: {e}")


def _search_brave(query: str, limit: int) -> str:
    """Tier 3: Brave Search API (requires BRAVE_API_KEY)."""
    api_key = os.getenv("BRAVE_API_KEY", "").strip()
    if not api_key:
        return tool_error("未配置 BRAVE_API_KEY")
    try:
        params = {"q": query, "count": limit}
        headers = {"X-Subscription-Token": api_key}
        with httpx.Client(timeout=_TIMEOUT_API) as client:
            resp = client.get("https://api.search.brave.com/res/v1/web/search", params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("description", "")}
            for r in data.get("web", {}).get("results", [])
        ][:limit]
        return tool_result(data=_format_results(results, query))
    except httpx.HTTPStatusError as e:
        reason, kind = _classify_http_status(e, config_statuses=True)
        return tool_error(reason, error_kind=kind)
    except httpx.TimeoutException:
        return tool_error("超时")
    except httpx.HTTPError:
        return tool_error("网络错误")
    except Exception as e:
        logger.warning("Brave search failed: %s", e)
        return tool_error(f"异常: {e}")


def _search_ddg_instant_answer(query: str, limit: int) -> str:
    """DuckDuckGo Instant Answer API — zero-config, no API key.

    Parses AbstractText/AbstractURL plus the first ``limit``
    RelatedTopics entries. Often returns 200 with empty results (no
    instant answer for the query), which is a valid success.
    """
    try:
        params = {"q": query, "format": "json", "no_html": 1}
        with httpx.Client(timeout=_TIMEOUT_DDG) as client:
            resp = client.get("https://api.duckduckgo.com/", params=params)
            resp.raise_for_status()
            data = resp.json()

        results: list[dict[str, str]] = []
        if data.get("AbstractText"):
            results.append(
                {
                    "title": data.get("Heading", ""),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data.get("AbstractText", ""),
                }
            )
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(
                    {
                        "title": topic.get("Text", "")[:80],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", ""),
                    }
                )
            if len(results) >= limit:
                break
        results = results[:limit]
        return tool_result(data=_format_results(results, query))
    except httpx.HTTPStatusError as e:
        reason, _ = _classify_http_status(e)
        return tool_error(reason)
    except httpx.TimeoutException:
        return tool_error("超时")
    except httpx.HTTPError:
        return tool_error("网络错误")
    except Exception as e:
        logger.warning("DuckDuckGo Instant Answer search failed: %s", e)
        return tool_error(f"异常: {e}")


class _DDGResultParser(html.parser.HTMLParser):
    """HTML parser for DuckDuckGo search results.

    Expected HTML structure (two separate <a> tags per result)::

        <a rel="nofollow" class="result__a" href="URL">TITLE TEXT</a>
        <a class="result__snippet">SNIPPET TEXT</a>
    """

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str | None]] = []
        self._pending: dict[str, str | None] | None = None
        self._collecting: str | None = None  # "title" or "snippet"
        self._depth = 0  # track nested <a> tag depth

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "a":
            cls = attrs_dict.get("class", "")
            if cls == "result__a":
                if self._pending and self._pending["url"] and self._pending["title"]:
                    self.results.append(self._pending)
                self._pending = {"url": attrs_dict.get("href", ""), "title": "", "snippet": ""}
                self._collecting = "title"
                self._depth = 1
            elif cls == "result__snippet":
                self._collecting = "snippet"
                self._depth = 1

    def _save_pending(self):
        if self._pending and self._pending["url"] and self._pending["title"]:
            self.results.append(self._pending)
        self._pending = None
        self._collecting = None

    def close(self):
        self._save_pending()
        super().close()

    def handle_endtag(self, tag: str) -> None:
        if tag != "a":
            return
        if self._depth <= 0:
            return
        self._depth -= 1
        if self._depth > 0:
            return  # still inside nested <a>
        # outermost </a> closes the block
        if self._collecting == "snippet":
            self._save_pending()
        elif self._collecting == "title":
            # title <a> closed; snippet <a> may follow
            self._collecting = None

    def handle_data(self, data: str) -> None:
        if self._collecting == "title" and self._pending is not None:
            self._pending["title"] = (self._pending["title"] or "") + data
        elif self._collecting == "snippet" and self._pending is not None:
            self._pending["snippet"] = (self._pending["snippet"] or "") + data


def _search_duckduckgo(query: str, limit: int) -> str:
    """Last-resort tier (zero-config): DDG Instant Answer, then HTML crawler.

    Each sub-provider is tried at most once — no retries. The HTML
    crawler only runs when the Instant Answer API yields no results.
    """
    instant = _search_ddg_instant_answer(query, limit)
    if _has_results(instant):
        return instant
    return _search_ddg_html(query, limit)


def _search_ddg_html(query: str, limit: int) -> str:
    """DuckDuckGo HTML crawler — zero-config, single attempt, no retries.

    Uses Python stdlib ``HTMLParser`` (see ``_DDGResultParser``) instead
    of regex for robust and maintainable HTML parsing.
    """
    try:
        params = {"q": query}
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        with httpx.Client(timeout=_TIMEOUT_DDG, follow_redirects=True) as client:
            resp = client.get("https://html.duckduckgo.com/html/", params=params, headers=headers)
            resp.raise_for_status()

        parser = _DDGResultParser()
        parser.feed(resp.text)
        parser.close()
        results = parser.results[:limit]
        return tool_result(data=_format_results(results, query))
    except httpx.HTTPStatusError as e:
        reason, _ = _classify_http_status(e)
        return tool_error(reason)
    except httpx.TimeoutException:
        return tool_error("超时")
    except httpx.HTTPError:
        return tool_error("网络错误")
    except Exception as e:
        logger.warning("DuckDuckGo HTML search failed: %s", e)
        return tool_error(f"异常: {e}")


def _format_results(results: list, query: str) -> dict:
    return {
        "query": query,
        "results": results,
        "result_count": len(results),
    }


WEB_SEARCH_SCHEMA = {
    "name": "web_search",
    "description": (
        "搜索互联网获取信息，返回每条结果的标题、URL 和摘要。"
        "自动按顺序降级尝试：自定义 API（SEARCH_API_URL）、Tavily（TAVILY_API_KEY）、"
        "Brave（BRAVE_API_KEY）、DuckDuckGo（零配置），无需指定后端。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "description": "Max results", "default": 5},
        },
        "required": ["query"],
    },
}

registry.register(
    name="web_search",
    toolset="web",
    schema=WEB_SEARCH_SCHEMA,
    handler=lambda args: web_search_tool(
        query=args.get("query", ""),
        limit=int(args.get("limit", 5)),
    ),
    check_fn=_check_web_search,
    emoji="🌐",
)
