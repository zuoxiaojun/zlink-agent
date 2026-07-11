"""Browser automation tool set using Playwright.

Provides a set of tools for the LLM to control a headless Chromium
browser: navigate, screenshot, click, fill, get_text, get_html,
evaluate, and close.

Architecture
------------
A ``_BrowserSession`` manages the Playwright browser lifecycle:
- Lazy initialisation (first tool call launches Chromium)
- Session reuse (multiple calls in the same conversation share the
  same browser context, preserving cookies)
- Idle detection via ``heartbeat()`` — an external caller (e.g. a
  periodic timer or the agent loop at end of turn) should invoke
  ``heartbeat()`` to close an idle session after 5 minutes.
- Thread-safe (lock-protected access)

Security
--------
- Blocks access to private/internal IPs (127.0.0.1, 10.*, 172.16-31.*,
  192.168.*) and file:// protocol.
- Navigation timeout: 30 seconds.
- Auto-dismisses JavaScript dialogs (alert, confirm, prompt).
"""

from __future__ import annotations

import base64
import json
import logging
import re
import threading
import time
from urllib.parse import urlparse

from agent.tools.registry import registry

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────

_IDLE_TIMEOUT = 300.0  # 5 minutes
_NAVIGATION_TIMEOUT = 30_000  # 30 seconds (ms)

# Regex patterns for blocked IP ranges
_PRIVATE_IP_PATTERNS = [
    re.compile(r"^127\.\d{1,3}\.\d{1,3}\.\d{1,3}"),
    re.compile(r"^10\.\d{1,3}\.\d{1,3}\.\d{1,3}"),
    re.compile(r"^172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"),
    re.compile(r"^192\.168\.\d{1,3}\.\d{1,3}"),
    re.compile(r"^0\.0\.0\.0$"),
    re.compile(r"^localhost$", re.IGNORECASE),
]


# ── URL Security ─────────────────────────────────────────────────


def _is_blocked_url(url: str) -> str | None:
    """Check if *url* should be blocked.  Returns an error message or None."""
    parsed = urlparse(url)

    if parsed.scheme == "file":
        return "不允许访问 file:// 协议"

    if parsed.scheme not in ("http", "https"):
        return f"不支持的协议: {parsed.scheme}"

    hostname = parsed.hostname or ""
    for pattern in _PRIVATE_IP_PATTERNS:
        if pattern.search(hostname):
            return f"不允许访问内网地址: {hostname}"

    # Block common internal hostnames
    internal_hosts = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
    if hostname.lower() in internal_hosts:
        return f"不允许访问内网地址: {hostname}"

    return None


# ── Browser Session Manager ─────────────────────────────────────


class _BrowserSession:
    """Class-level state managing a Playwright Chromium instance.

    Thread-safe.  Lazily starts the browser on first use.
    An external caller should invoke ``heartbeat()`` periodically
    to close idle sessions.
    """

    _lock = threading.Lock()
    _playwright = None
    _browser = None
    _context = None
    _page = None
    _last_used = 0.0
    _closed = False

    @classmethod
    def get_page(cls):
        """Return the current page, lazy-starting the browser if needed."""
        with cls._lock:
            if cls._page is None or cls._closed:
                cls._start_browser()
            cls._last_used = time.monotonic()
            return cls._page

    @classmethod
    def _start_browser(cls):
        """Launch Playwright Chromium in headless mode."""
        try:
            import playwright.sync_api
        except ImportError:
            raise RuntimeError(
                "Playwright is not installed. Run: pip install 'zlink-agent[browser]' && playwright install chromium"
            )

        try:
            cls._playwright = playwright.sync_api.sync_playwright().start()
            cls._browser = cls._playwright.chromium.launch(headless=True)
            cls._context = cls._browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            cls._page = cls._context.new_page()

            # Auto-dismiss JavaScript dialogs
            cls._page.on("dialog", lambda dialog: dialog.dismiss())

            # Set default navigation timeout
            cls._page.set_default_navigation_timeout(_NAVIGATION_TIMEOUT)

            cls._closed = False
            logger.info("Browser session started")
        except Exception as e:
            cls._cleanup()
            raise RuntimeError(f"Failed to start browser: {e}")

    @classmethod
    def close(cls):
        """Close the browser and release all resources."""
        with cls._lock:
            cls._cleanup()
            cls._closed = True
            logger.info("Browser session closed")

    @classmethod
    def _cleanup(cls):
        """Internal cleanup without lock (caller must hold lock)."""
        try:
            if cls._page:
                cls._page.close()
        except Exception:
            pass
        cls._page = None
        try:
            if cls._context:
                cls._context.close()
        except Exception:
            pass
        cls._context = None
        try:
            if cls._browser:
                cls._browser.close()
        except Exception:
            pass
        cls._browser = None
        try:
            if cls._playwright:
                cls._playwright.stop()
        except Exception:
            pass
        cls._playwright = None

    @classmethod
    def is_idle(cls) -> bool:
        """Check if the browser has been idle longer than the timeout."""
        if cls._page is None or cls._closed:
            return False
        return (time.monotonic() - cls._last_used) > _IDLE_TIMEOUT

    @classmethod
    def heartbeat(cls):
        """Call periodically to auto-close idle sessions.  Idempotent."""
        if cls.is_idle():
            cls.close()


# ── Tool Handlers ────────────────────────────────────────────────


def handle_browser_navigate(args: dict) -> str:
    """Navigate to a URL."""
    url = args.get("url", "").strip()
    if not url:
        return json.dumps({"success": False, "error": "url 参数是必需的"})

    blocked = _is_blocked_url(url)
    if blocked:
        return json.dumps({"success": False, "error": blocked})

    try:
        page = _BrowserSession.get_page()
        page.goto(url, wait_until="domcontentloaded")
        return json.dumps(
            {"success": True, "data": f"已导航到 {url}，当前页面标题: {page.title()}"}, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": f"导航失败: {e}"})


def handle_browser_screenshot(args: dict) -> str:
    """Take a full-page screenshot and return it as base64."""
    try:
        page = _BrowserSession.get_page()
        screenshot_bytes = page.screenshot(full_page=True)
        b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        return json.dumps(
            {"success": True, "data": "截图已生成", "screenshot_base64": b64, "mime_type": "image/png"},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": f"截图失败: {e}"})


def handle_browser_click(args: dict) -> str:
    """Click an element on the page."""
    selector = args.get("selector", "").strip()
    if not selector:
        return json.dumps({"success": False, "error": "selector 参数是必需的"})

    try:
        page = _BrowserSession.get_page()
        page.click(selector)
        wait_after = int(args.get("wait_after", 500))
        if wait_after > 0:
            page.wait_for_timeout(wait_after)
        return json.dumps({"success": True, "data": f"已点击元素: {selector}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": f"点击失败: {e}"})


def handle_browser_fill(args: dict) -> str:
    """Fill a text input with a value."""
    selector = args.get("selector", "").strip()
    value = args.get("value", "")

    if not selector:
        return json.dumps({"success": False, "error": "selector 参数是必需的"})

    try:
        page = _BrowserSession.get_page()
        page.fill(selector, value)
        return json.dumps({"success": True, "data": f"已填写元素 {selector}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": f"填写失败: {e}"})


def handle_browser_get_text(args: dict) -> str:
    """Get the text content of an element on the page."""
    selector = args.get("selector", "").strip()
    if not selector:
        return json.dumps({"success": False, "error": "selector 参数是必需的"})

    try:
        page = _BrowserSession.get_page()
        element = page.query_selector(selector)
        if element is None:
            return json.dumps({"success": False, "error": f"未找到元素: {selector}"})
        text = element.text_content() or ""
        return json.dumps({"success": True, "data": text}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": f"获取文本失败: {e}"})


def handle_browser_get_html(args: dict) -> str:
    """Get the full HTML content of the current page."""
    try:
        page = _BrowserSession.get_page()
        html = page.content()
        return json.dumps({"success": True, "data": html}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": f"获取 HTML 失败: {e}"})


def handle_browser_evaluate(args: dict) -> str:
    """Execute JavaScript in the browser context."""
    code = args.get("code", "").strip()
    if not code:
        return json.dumps({"success": False, "error": "code 参数是必需的"})

    try:
        page = _BrowserSession.get_page()
        result = page.evaluate(code)
        return json.dumps({"success": True, "data": str(result)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": f"JavaScript 执行失败: {e}"})


def handle_browser_close(args: dict) -> str:
    """Close the browser instance."""
    try:
        _BrowserSession.close()
        return json.dumps({"success": True, "data": "浏览器已关闭"})
    except Exception as e:
        return json.dumps({"success": False, "error": f"关闭浏览器失败: {e}"})


# ── Tool Schema Definitions ──────────────────────────────────────


def _make_schema(name: str, description: str, properties: dict, required: list | None = None) -> dict:
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required or [],
        },
    }


_NAVIGATE_SCHEMA = _make_schema(
    "browser_navigate",
    "导航到指定 URL",
    {"url": {"type": "string", "description": "目标 URL"}},
    ["url"],
)

_SCREENSHOT_SCHEMA = _make_schema(
    "browser_screenshot",
    "截取当前页面的全页截图（返回 base64 图片）",
    {},
)

_CLICK_SCHEMA = _make_schema(
    "browser_click",
    "点击页面上的元素",
    {
        "selector": {"type": "string", "description": "CSS 选择器"},
        "wait_after": {"type": "number", "description": "点击后等待时间（毫秒，默认 500）"},
    },
    ["selector"],
)

_FILL_SCHEMA = _make_schema(
    "browser_fill",
    "在输入框中填写文本",
    {
        "selector": {"type": "string", "description": "CSS 选择器"},
        "value": {"type": "string", "description": "要填写的文本"},
    },
    ["selector", "value"],
)

_GET_TEXT_SCHEMA = _make_schema(
    "browser_get_text",
    "获取页面元素的文本内容",
    {"selector": {"type": "string", "description": "CSS 选择器"}},
    ["selector"],
)

_GET_HTML_SCHEMA = _make_schema(
    "browser_get_html",
    "获取当前页面的完整 HTML 内容",
    {},
)

_EVALUATE_SCHEMA = _make_schema(
    "browser_evaluate",
    "在浏览器中执行 JavaScript 并返回结果",
    {"code": {"type": "string", "description": "要执行的 JavaScript 代码"}},
    ["code"],
)

_CLOSE_SCHEMA = _make_schema(
    "browser_close",
    "关闭浏览器实例，释放资源",
    {},
)


# ── Auto-registration ────────────────────────────────────────────

registry.register(
    name="browser_navigate",
    toolset="browser",
    schema=_NAVIGATE_SCHEMA,
    handler=handle_browser_navigate,
    description="导航到指定 URL",
    emoji="🌐",
    risk_level="medium",
)
registry.register(
    name="browser_screenshot",
    toolset="browser",
    schema=_SCREENSHOT_SCHEMA,
    handler=handle_browser_screenshot,
    description="截取当前页面截图",
    emoji="📸",
    risk_level="low",
)
registry.register(
    name="browser_click",
    toolset="browser",
    schema=_CLICK_SCHEMA,
    handler=handle_browser_click,
    description="点击页面元素",
    emoji="👆",
    risk_level="medium",
)
registry.register(
    name="browser_fill",
    toolset="browser",
    schema=_FILL_SCHEMA,
    handler=handle_browser_fill,
    description="填写表单输入框",
    emoji="✏️",
    risk_level="medium",
)
registry.register(
    name="browser_get_text",
    toolset="browser",
    schema=_GET_TEXT_SCHEMA,
    handler=handle_browser_get_text,
    description="获取页面元素文本",
    emoji="📝",
    risk_level="low",
)
registry.register(
    name="browser_get_html",
    toolset="browser",
    schema=_GET_HTML_SCHEMA,
    handler=handle_browser_get_html,
    description="获取当前页面完整 HTML",
    emoji="📄",
    risk_level="low",
)
registry.register(
    name="browser_evaluate",
    toolset="browser",
    schema=_EVALUATE_SCHEMA,
    handler=handle_browser_evaluate,
    description="执行 JavaScript 代码",
    emoji="⚡",
    risk_level="medium",
)
registry.register(
    name="browser_close",
    toolset="browser",
    schema=_CLOSE_SCHEMA,
    handler=handle_browser_close,
    description="关闭浏览器释放资源",
    emoji="🚫",
    risk_level="low",
)
