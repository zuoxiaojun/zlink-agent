"""Browser automation tools using Playwright.

Provides browser_navigate, browser_snapshot, browser_click, browser_type,
browser_scroll, browser_back, browser_press, browser_get_images, browser_console.
Uses local headless Chromium via Playwright's synchronous API.

Inspired by Hermes Agent's browser tool but simplified:
- Pure Playwright (no agent-browser CLI dependency)
- Local Chromium only (no cloud providers)
- Single global browser/page session
- Playwright accessibility tree for page text representation
"""

import atexit
import logging

from playwright.sync_api import TimeoutError as PwTimeout
from playwright.sync_api import sync_playwright

from agent.tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────

_INTERACTIVE_SELECTOR = (
    'button, a[href], input:not([type="hidden"]), textarea, select, '
    '[role="button"], [role="link"], [role="checkbox"], [role="radio"], '
    '[role="tab"], [role="menuitem"], [tabindex]:not([tabindex="-1"]), '
    'details summary, [contenteditable="true"]'
)

NAV_TIMEOUT = 30000
ACTION_TIMEOUT = 10000

# ── Global browser singleton ───────────────────────────────────────

_pw = None
_browser = None
_page = None


def _get_browser():
    """Lazy-init headless Chromium, return the Browser instance."""
    global _pw, _browser
    if _browser is None:
        try:
            _pw = sync_playwright().start()
            _pw.selectors.set_test_id_attribute("data-testid")
            _browser = _pw.chromium.launch(headless=True)
        except Exception:
            logger.exception("Failed to launch Playwright browser")
            raise
    return _browser


def _get_page():
    """Lazy-init browser + page, return the Page singleton."""
    global _page
    if _page is None:
        browser = _get_browser()
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        _page = context.new_page()
    return _page


@atexit.register
def _cleanup():
    global _pw, _browser, _page
    _page = None
    if _browser:
        try:
            _browser.close()
        except Exception:
            pass
        _browser = None
    if _pw:
        try:
            _pw.stop()
        except Exception:
            pass
        _pw = None


# ── Page snapshot helpers ──────────────────────────────────────────


def _collect_interactive_elements():
    """Return a list of (ref, desc) for all interactive elements."""
    page = _get_page()
    elements = []
    try:
        locator = page.locator(_INTERACTIVE_SELECTOR)
        count = locator.count()
        for i in range(count):
            el = locator.nth(i)
            try:
                tag = el.evaluate("el => el.tagName.toLowerCase()")
                visible = el.is_visible()
                if not visible:
                    continue
                role = (el.get_attribute("role") or "").strip()
                text = (el.inner_text() or "").strip()[:60]
                label = (el.get_attribute("aria-label") or "").strip()[:60]
                href = (el.get_attribute("href") or "").strip()

                ref = f"@e{len(elements) + 1}"
                elements.append((ref, tag, role, text, label, href, i))
            except Exception:
                continue
    except Exception as e:
        logger.debug("Failed to enumerate interactive elements: %s", e)
    return elements


def _build_snapshot_text(elements):
    """Build a human-readable snapshot with @ref annotations."""
    page = _get_page()
    lines = [f"标题: {page.title()}", f"URL: {page.url}", ""]

    # Page text from accessibility tree
    try:
        snap = page.accessibility.snapshot()
        tree_lines = _flatten_accessibility_tree(snap)
        if tree_lines:
            lines.append("--- 页面内容 (无障碍树) ---")
            lines.extend(tree_lines[:200])
            lines.append("")
    except Exception as e:
        logger.debug("Accessibility snapshot failed: %s", e)
        # Fallback: visible body text
        try:
            body = page.inner_text("body")[:3000]
            if body.strip():
                lines.append("--- 页面内容 ---")
                lines.append(body)
                lines.append("")
        except Exception:
            pass

    # Interactive elements
    if elements:
        lines.append("--- 可交互元素 ---")
        for ref, tag, role, text, label, href, _ in elements:
            desc = role or tag
            if text:
                desc += f' "{text}"'
            elif label:
                desc += f' "{label}"'
            elif href and href not in ("#", "javascript:void(0)"):
                desc += f" → {href[:50]}"
            lines.append(f"  [{ref}] {desc}")

    return "\n".join(lines)


def _flatten_accessibility_tree(node, depth=0):
    """Recursively flatten the Playwright accessibility tree into text lines."""
    if not node:
        return []
    role = node.get("role", "")
    name = (node.get("name") or "").strip()
    if not name and role in ("text", "InlineTextBox", "paragraph"):
        name = (node.get("value") or "").strip()
    if not name and role in ("text", "InlineTextBox"):
        return []

    lines = []
    indent = "  " * depth

    if role == "heading" and node.get("level"):
        prefix = "#" * node["level"]
        lines.append(f"{indent}{prefix} {name}")
    elif role == "link":
        value = node.get("valueString") or ""
        if value:
            lines.append(f"{indent}[链接] {name} ({value})")
        else:
            lines.append(f"{indent}[链接] {name}")
    elif role == "button":
        lines.append(f"{indent}[按钮] {name}")
    elif role in ("checkbox", "radio"):
        checked = "✓" if node.get("checked") else "○"
        lines.append(f"{indent}[{checked} {role}] {name}")
    elif role == "textbox":
        value = (node.get("valueString") or node.get("value") or "").strip()
        if value:
            lines.append(f'{indent}[输入框] {name} = "{value[:50]}"')
        else:
            lines.append(f"{indent}[输入框] {name}")
    elif role == "combobox":
        value = (node.get("valueString") or "").strip()
        if value:
            lines.append(f'{indent}[下拉框] {name} = "{value[:50]}"')
        else:
            lines.append(f"{indent}[下拉框] {name}")
    elif role == "list":
        lines.extend(_process_children(node, depth))
        return lines  # children already indented
    elif role in ("listitem", "generic", "unknown", "document", "WebArea"):
        lines.extend(_process_children(node, depth))
        return lines
    elif name:
        lines.append(f"{indent}{name}")
    else:
        lines.extend(_process_children(node, depth))
        return lines

    # Children
    lines.extend(_process_children(node, depth + 1))
    return lines


def _process_children(node, depth):
    result = []
    for child in node.get("children", []):
        result.extend(_flatten_accessibility_tree(child, depth))
    return result


def _click_ref(ref: str) -> str:
    """Click an element by @ref ID."""
    page = _get_page()
    if not ref.startswith("@"):
        ref = f"@{ref}"

    try:
        idx = int(ref[2:]) - 1
    except ValueError:
        return f"无效的 ref: {ref}（格式应为 @e1, @e2 ...）"

    if idx < 0:
        return f"无效的 ref: {ref}"

    locator = page.locator(_INTERACTIVE_SELECTOR)
    count = locator.count()
    if idx >= count:
        return f"ref {ref} 超出范围（共 {count} 个可交互元素）"

    try:
        target = locator.nth(idx)
        target.wait_for(state="visible", timeout=ACTION_TIMEOUT)
        target.click(timeout=ACTION_TIMEOUT)
        return f"已点击 {ref}"
    except PwTimeout:
        return f"点击 {ref} 超时（元素不可见或未加载）"
    except Exception as e:
        return f"点击 {ref} 失败: {e}"


def _type_ref(ref: str, text: str) -> str:
    """Type text into an element by @ref ID."""
    page = _get_page()
    if not ref.startswith("@"):
        ref = f"@{ref}"

    try:
        idx = int(ref[2:]) - 1
    except ValueError:
        return f"无效的 ref: {ref}"

    if idx < 0:
        return f"无效的 ref: {ref}"

    locator = page.locator(_INTERACTIVE_SELECTOR)
    count = locator.count()
    if idx >= count:
        return f"ref {ref} 超出范围（共 {count} 个可交互元素）"

    try:
        target = locator.nth(idx)
        target.wait_for(state="visible", timeout=ACTION_TIMEOUT)
        target.fill("", timeout=ACTION_TIMEOUT)
        target.fill(text, timeout=ACTION_TIMEOUT)
        return f"已在 {ref} 输入: {text[:100]}"
    except PwTimeout:
        return f"在 {ref} 输入超时"
    except Exception as e:
        return f"在 {ref} 输入失败: {e}"


# ── Tool handlers ──────────────────────────────────────────────────


def _handle_browser_navigate(args: dict) -> str:
    url = args.get("url", "").strip()
    if not url:
        return tool_error("url 不能为空")

    page = _get_page()
    try:
        page.goto(url, timeout=NAV_TIMEOUT, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=10000)
    except PwTimeout:
        pass  # Page may still be partially loaded
    except Exception as e:
        return tool_error(f"导航失败: {e}")

    elements = _collect_interactive_elements()
    snapshot = _build_snapshot_text(elements)

    return tool_result(
        data=snapshot,
        url=page.url,
        title=page.title(),
        element_count=len(elements),
    )


def _handle_browser_snapshot(args: dict) -> str:
    elements = _collect_interactive_elements()
    snapshot = _build_snapshot_text(elements)
    return tool_result(
        data=snapshot,
        element_count=len(elements),
    )


def _handle_browser_click(args: dict) -> str:
    ref = args.get("ref", "").strip()
    if not ref:
        return tool_error("ref 不能为空")
    msg = _click_ref(ref)
    if msg.startswith("已点击"):
        # Return updated snapshot after click
        elements = _collect_interactive_elements()
        snapshot = _build_snapshot_text(elements)
        return tool_result(data=f"{msg}\n\n{snapshot}")
    return tool_error(msg)


def _handle_browser_type(args: dict) -> str:
    ref = args.get("ref", "").strip()
    text = args.get("text", "")
    if not ref:
        return tool_error("ref 不能为空")
    msg = _type_ref(ref, text)
    if msg.startswith("已在"):
        return tool_result(data=msg)
    return tool_error(msg)


def _handle_browser_scroll(args: dict) -> str:
    direction = args.get("direction", "down").strip()
    if direction not in ("up", "down"):
        return tool_error("direction 必须是 'up' 或 'down'")

    page = _get_page()
    delta = -500 if direction == "up" else 500
    try:
        page.evaluate(f"window.scrollBy(0, {delta})")
    except Exception as e:
        return tool_error(f"滚动失败: {e}")
    return tool_result(data=f"已向{direction}滚动")


def _handle_browser_back(args: dict) -> str:
    page = _get_page()
    try:
        page.go_back(timeout=NAV_TIMEOUT)
    except Exception as e:
        return tool_error(f"后退失败: {e}")

    elements = _collect_interactive_elements()
    snapshot = _build_snapshot_text(elements)
    return tool_result(data=snapshot)


def _handle_browser_press(args: dict) -> str:
    key = args.get("key", "").strip()
    if not key:
        return tool_error("key 不能为空")

    page = _get_page()
    try:
        page.keyboard.press(key)
    except Exception as e:
        return tool_error(f"按键失败: {e}")

    # After pressing, take a snapshot to show what changed
    elements = _collect_interactive_elements()
    snapshot = _build_snapshot_text(elements)
    return tool_result(data=f"已按键: {key}\n\n{snapshot}")


def _handle_browser_get_images(args: dict) -> str:
    page = _get_page()
    try:
        images = page.evaluate("""() => {
            const imgs = document.querySelectorAll('img[src]');
            return Array.from(imgs).map((img, i) => ({
                index: i + 1,
                src: img.src,
                alt: img.alt || '',
                width: img.naturalWidth,
                height: img.naturalHeight,
            }));
        }""")
    except Exception as e:
        return tool_error(f"获取图片失败: {e}")

    if not images:
        return tool_result(data="页面中没有图片")

    lines = [f"共 {len(images)} 张图片：", ""]
    for img in images:
        alt = f' alt="{img["alt"]}"' if img["alt"] else ""
        size = f" ({img['width']}x{img['height']})" if img["width"] else ""
        lines.append(f"  #{img['index']}{alt}: {img['src'][:100]}{size}")

    return tool_result(data="\n".join(lines))


def _handle_browser_console(args: dict) -> str:
    page = _get_page()
    # Evaluate a JS expression in page context
    # We can't directly read console messages retroactively with Playwright sync API
    # Instead, evaluate the provided expression or return page info
    expression = args.get("expression", "").strip()

    if expression:
        try:
            result = page.evaluate(expression)
            try:
                import json as _json

                output = _json.dumps(result, ensure_ascii=False, default=str)
            except Exception:
                output = str(result)
            return tool_result(data=f"JS 执行结果:\n{output[:5000]}")
        except Exception as e:
            return tool_error(f"JS 执行失败: {e}")

    # Just return page info if no expression
    info = {
        "url": page.url,
        "title": page.title(),
        "viewport": {"width": page.viewport_size["width"], "height": page.viewport_size["height"]},
    }
    try:
        info["scroll_y"] = page.evaluate("window.scrollY")
        info["scroll_height"] = page.evaluate("document.documentElement.scrollHeight")
    except Exception:
        pass

    lines = [
        f"URL: {info['url']}",
        f"标题: {info['title']}",
        f"视口: {info['viewport']['width']}x{info['viewport']['height']}",
    ]
    if "scroll_y" in info:
        lines.append(f"滚动位置: {info['scroll_y']}/{info['scroll_height']}")

    return tool_result(data="\n".join(lines))


# ── Tool schemas ───────────────────────────────────────────────────

BROWSER_NAVIGATE_SCHEMA = {
    "name": "browser_navigate",
    "description": "打开浏览器并导航到指定 URL。初始化浏览器（如未启动），加载页面后返回可交互元素列表。首次使用浏览器工具时必须先调用此工具。对于纯文本内容（.md, .txt, .json 等），优先使用 web_extract（更快更省）。",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要打开的 URL"},
        },
        "required": ["url"],
    },
}

BROWSER_SNAPSHOT_SCHEMA = {
    "name": "browser_snapshot",
    "description": "获取当前页面的文本快照，包含页面内容和可交互元素列表（带 @e1, @e2 等引用 ID）。页面变化后调用此工具刷新状态。",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

BROWSER_CLICK_SCHEMA = {
    "name": "browser_click",
    "description": "点击页面上指定 ref 的元素（如 @e5）。点击后自动返回更新后的页面快照。需要先调用 browser_navigate 和 browser_snapshot。",
    "parameters": {
        "type": "object",
        "properties": {
            "ref": {"type": "string", "description": "元素的引用 ID（如 @e5）"},
        },
        "required": ["ref"],
    },
}

BROWSER_TYPE_SCHEMA = {
    "name": "browser_type",
    "description": "在输入框中填入文本。会先清空已有内容再输入。需要先调用 browser_navigate 和 browser_snapshot。",
    "parameters": {
        "type": "object",
        "properties": {
            "ref": {"type": "string", "description": "输入框的引用 ID（如 @e3）"},
            "text": {"type": "string", "description": "要输入的文本"},
        },
        "required": ["ref", "text"],
    },
}

BROWSER_SCROLL_SCHEMA = {
    "name": "browser_scroll",
    "description": "滚动页面，向上或向下。",
    "parameters": {
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "enum": ["up", "down"],
                "description": "滚动方向",
            },
        },
        "required": ["direction"],
    },
}

BROWSER_BACK_SCHEMA = {
    "name": "browser_back",
    "description": "浏览器后退到上一页。",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

BROWSER_PRESS_SCHEMA = {
    "name": "browser_press",
    "description": "按下键盘按键。用于提交表单（Enter）、切换焦点（Tab）等。",
    "parameters": {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "按键名称（如 'Enter', 'Tab', 'Escape', 'ArrowDown'）",
            },
        },
        "required": ["key"],
    },
}

BROWSER_GET_IMAGES_SCHEMA = {
    "name": "browser_get_images",
    "description": "获取当前页面所有图片的 URL 和描述信息。",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

BROWSER_CONSOLE_SCHEMA = {
    "name": "browser_console",
    "description": "执行 JavaScript 表达式并返回结果，或获取页面基本信息。用于读取页面状态、DOM 信息或执行数据提取。",
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "在页面上下文执行的 JavaScript 表达式（如 'document.title'），非必填",
            },
            "clear": {"type": "boolean", "description": "是否清除控制台"},
        },
    },
}


# ── Registry ───────────────────────────────────────────────────────

registry.register(
    name="browser_navigate",
    toolset="browser",
    schema=BROWSER_NAVIGATE_SCHEMA,
    handler=_handle_browser_navigate,
    emoji="🌐",
)

registry.register(
    name="browser_snapshot",
    toolset="browser",
    schema=BROWSER_SNAPSHOT_SCHEMA,
    handler=_handle_browser_snapshot,
    emoji="📸",
)

registry.register(
    name="browser_click",
    toolset="browser",
    schema=BROWSER_CLICK_SCHEMA,
    handler=_handle_browser_click,
    emoji="👆",
)

registry.register(
    name="browser_type",
    toolset="browser",
    schema=BROWSER_TYPE_SCHEMA,
    handler=_handle_browser_type,
    emoji="⌨️",
)

registry.register(
    name="browser_scroll",
    toolset="browser",
    schema=BROWSER_SCROLL_SCHEMA,
    handler=_handle_browser_scroll,
    emoji="📜",
)

registry.register(
    name="browser_back",
    toolset="browser",
    schema=BROWSER_BACK_SCHEMA,
    handler=_handle_browser_back,
    emoji="◀️",
)

registry.register(
    name="browser_press",
    toolset="browser",
    schema=BROWSER_PRESS_SCHEMA,
    handler=_handle_browser_press,
    emoji="⌨️",
)

registry.register(
    name="browser_get_images",
    toolset="browser",
    schema=BROWSER_GET_IMAGES_SCHEMA,
    handler=_handle_browser_get_images,
    emoji="🖼️",
)

registry.register(
    name="browser_console",
    toolset="browser",
    schema=BROWSER_CONSOLE_SCHEMA,
    handler=_handle_browser_console,
    emoji="🖥️",
)
