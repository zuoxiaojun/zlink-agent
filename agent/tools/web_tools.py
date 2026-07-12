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

    Uses Python's stdlib HTMLParser — much more robust than regex for
    parsing HTML DOM structure. Degrades gracefully if DDG changes
    their page structure (empty results instead of crash).
    """

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._in_result = False
        self._in_title = False
        self._in_snippet = False
        self._current_url = ""
        self._current_title = ""
        self._current_snippet = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "a" and attrs_dict.get("class") == "result__a":
            self._in_result = True
            self._in_title = True
            self._current_url = attrs_dict.get("href", "")
            self._current_title = ""
            self._current_snippet = ""
        elif tag == "a" and attrs_dict.get("class") == "result__snippet":
            self._in_snippet = True
            self._current_snippet = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_result:
            self._in_result = False
            self._in_title = False
            self._in_snippet = False
            if self._current_url and self._current_title:
                self.results.append(
                    {
                        "title": self._current_title.strip(),
                        "url": self._current_url,
                        "snippet": self._current_snippet.strip(),
                    }
                )

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._current_title += data
        elif self._in_snippet:
            self._current_snippet += data


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
