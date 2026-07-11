"""Web page content extraction tool.

Fetches URLs and returns page content as formatted text.
"""

import logging
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from agent.tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

TIMEOUT = 30
MAX_PAGE_CHARS = 200_000
MAX_URLS = 5


class _TextExtractor(HTMLParser):
    """Strip HTML tags and extract visible text."""

    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False
        self._tag_stack = []

    def handle_starttag(self, tag, attrs):
        self._tag_stack.append(tag)
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag):
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        if tag in ("script", "style", "noscript"):
            self._skip = False
        if tag in ("p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "th", "td", "div"):
            self._text.append("\n")

    def handle_data(self, data):
        if not self._skip:
            cleaned = re.sub(r"\s+", " ", data).strip()
            if cleaned:
                self._text.append(cleaned + " ")

    def get_text(self) -> str:
        lines = "".join(self._text).split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped:
                cleaned.append(stripped)
        return "\n".join(cleaned)


def _extract_text(html: str) -> str:
    """Extract visible text from HTML."""
    extractor = _TextExtractor()
    try:
        extractor.feed(html)
    except Exception:
        pass
    text = extractor.get_text()
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _fetch_url(url: str) -> str:
    """Fetch a URL and return extracted text content."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return f"[无效 URL: {url}]"

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ZLink-Agent/1.5)",
        "Accept": "text/html,application/xhtml+xml",
    }

    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
    except httpx.TimeoutException:
        return f"[超时: {url}]"
    except httpx.HTTPStatusError as e:
        return f"[HTTP {e.response.status_code}: {url}]"
    except Exception as e:
        return f"[请求失败: {url} — {e}]"

    content_type = resp.headers.get("content-type", "")
    if "text/" not in content_type and "html" not in content_type.lower():
        return f"[不支持的内容类型: {content_type}]"

    text = resp.text[:MAX_PAGE_CHARS]
    extracted = _extract_text(text)
    return extracted or "[无法提取内容]"


def _handle_web_extract(args: dict) -> str:
    """Extract content from web page URLs."""
    urls = args.get("urls", [])
    if not urls or not isinstance(urls, list):
        return tool_error("urls (URL 列表) 是必需的")

    urls = urls[:MAX_URLS]
    results = []
    for url in urls:
        if not isinstance(url, str) or not url.strip():
            continue
        content = _fetch_url(url.strip())
        results.append(f"## {url}\n\n{content[:10000]}")

    if not results:
        return tool_error("没有有效的 URL")

    return tool_result(data="\n\n---\n\n".join(results))


WEB_EXTRACT_SCHEMA = {
    "name": "web_extract",
    "description": (
        "提取指定网页 URL 的内容并返回格式化文本。"
        "与 web_search 配合使用：先搜索找到相关链接，再用此工具提取具体内容。"
        "支持标准 HTML 页面。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要提取内容的 URL 列表（最多 5 个）",
                "maxItems": 5,
            },
        },
        "required": ["urls"],
    },
}

registry.register(
    name="web_extract",
    toolset="web",
    schema=WEB_EXTRACT_SCHEMA,
    handler=_handle_web_extract,
    emoji="📄",
    risk_level="medium",
)
