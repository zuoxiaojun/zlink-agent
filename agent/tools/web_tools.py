"""Web search and extraction tools for ZLink Agent.

Port of Hermes web_tools.py — simplified using httpx directly.
Supports configurable search backend via env vars.
"""

import html.parser
import logging
import os
import urllib.parse

import httpx

from agent.tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)


def _get_search_url() -> str:
    """Get the search API URL from env, default to DuckDuckGo via a libre approach."""
    return os.getenv("SEARCH_API_URL", "")


def _get_search_api_key() -> str:
    return os.getenv("SEARCH_API_KEY", "")


def _check_web_search() -> bool:
    """Check if web search is available (at minimum, we can use httpx directly)."""
    return True


def web_search_tool(query: str, limit: int = 5) -> str:
    """Perform a web search.

    Supports multiple backends:
    1. If SEARCH_API_URL is configured, sends POST with query to that endpoint
    2. Otherwise, uses a simple DuckDuckGo-based approach
    """
    api_url = _get_search_url()
    api_key = _get_search_api_key()

    if api_url:
        return _search_via_api(query, limit, api_url, api_key)
    else:
        return _search_duckduckgo(query, limit)


def _search_via_api(query: str, limit: int, api_url: str, api_key: str) -> str:
    """Search via a configured API endpoint."""
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {"query": query, "limit": limit}

        with httpx.Client(timeout=15.0) as client:
            resp = client.post(api_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", data.get("organic", []))
        return tool_result(data=_format_results(results, query))
    except Exception as e:
        logger.warning("API search failed: %s", e)
        return tool_error(f"Search failed: {e}")


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
    """Search via DuckDuckGo's HTML interface (no API key needed).

    Uses Python stdlib ``HTMLParser`` instead of regex for robust and
    maintainable HTML parsing.
    """
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()

        parser = _DDGResultParser()
        parser.feed(resp.text)
        parser.close()
        results = parser.results[:limit]
        return tool_result(data=_format_results(results, query))
    except Exception as e:
        logger.warning("DuckDuckGo search failed: %s", e)
        return tool_error(f"Web search failed: {e}")


def _format_results(results: list, query: str) -> dict:
    return {
        "query": query,
        "results": results,
        "result_count": len(results),
    }


WEB_SEARCH_SCHEMA = {
    "name": "web_search",
    "description": "Search the web for information. Returns title, URL, and snippet for each result.",
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
