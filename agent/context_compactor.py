"""Context compaction for long conversations.

When the accumulated conversation history approaches the model's context
window, older messages are summarized via LLM and replaced with a compact
summary, keeping recent messages intact.

M4 changes
----------
* ``compact_messages`` no longer takes a raw OpenAI client.  It now
  accepts a ``summary_caller`` callable (any LLM that takes a prompt
  and returns text).  This decouples compaction from the OpenAI SDK
  and lets Anthropic / future providers run compaction.
* Adds **file tracking** (Pi-style) — before summarising, we scan the
  messages for paths the conversation touched, read a snapshot, and
  attach it to :class:`SessionBeforeCompactEvent` so extensions can
  fold the file contents into the summary.
* Publishes :class:`SessionBeforeCompactEvent` *after* the draft
  summary is generated but *before* the final summary message is
  assembled.  Extensions can read the draft + tracked files and
  append ``event.extra`` strings to the final summary.

Inspired by Pi's Compaction system (CompactionSettings / CompactionPreparation).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from agent.events.bus import EventBus

logger = logging.getLogger(__name__)


# ---- model context window auto-detection ----

# Mapping from model id substrings to context window sizes (tokens).
# Ordered by specificity: longer / more specific patterns first so they
# match before broader family patterns.
_MODEL_CONTEXT_WINDOWS: list[tuple[str, int]] = [
    # OpenAI GPT-4.1 family (1M context)
    ("gpt-4.1-nano", 1_000_000),
    ("gpt-4.1-mini", 1_000_000),
    ("gpt-4.1", 1_000_000),
    # OpenAI o-series
    ("o4-mini", 200_000),
    ("o3", 200_000),
    ("o1", 200_000),
    # OpenAI GPT-4o family
    ("gpt-4o-mini", 128_000),
    ("gpt-4o", 128_000),
    # Anthropic Claude
    ("claude-sonnet-4", 200_000),
    ("claude-opus-4", 200_000),
    ("claude-3-5-sonnet", 200_000),
    ("claude-3-5-haiku", 200_000),
    ("claude-3-opus", 200_000),
    ("claude-3-sonnet", 200_000),
    ("claude-3-haiku", 200_000),
    ("claude-", 200_000),  # catch-all for newer Claude models
    # DeepSeek
    ("deepseek-v4", 1_000_000),
    ("deepseek-reasoner", 128_000),
    ("deepseek-chat", 128_000),
    ("deepseek-v3", 128_000),
    ("deepseek-r1", 128_000),
    ("deepseek-ai/deepseek", 128_000),
    # Kimi
    ("kimi-k2", 128_000),
    ("kimi-latest", 128_000),
    ("kimi-", 128_000),
    # Zhipu GLM
    ("glm-4-plus", 128_000),
    ("glm-4-air", 128_000),
    ("glm-4-flash", 128_000),
    ("glm-4", 128_000),
    ("glm-", 128_000),
    # Qwen
    ("qwen-max", 128_000),
    ("qwen-plus", 128_000),
    ("qwen-turbo", 128_000),
    ("qwen-coder-plus", 128_000),
    ("qwen-coder-turbo", 128_000),
    ("qwen-coder", 128_000),
    ("qwen", 128_000),
    # SiliconFlow / OpenRouter prefixed models
    ("qwen/", 128_000),
    ("openai/gpt-4.1", 1_000_000),
    ("openai/gpt-4o", 128_000),
    ("openai/o3", 200_000),
    ("openai/o4", 200_000),
    ("openai/", 128_000),
    ("anthropic/claude", 200_000),
    ("deepseek/", 128_000),
    ("google/gemini-2.5", 1_000_000),
    ("google/gemini-2.0", 1_000_000),
    ("google/gemini-1.5", 1_000_000),
    ("google/gemini", 128_000),
    # Google
    ("gemini-2.5", 1_000_000),
    ("gemini-2.0", 1_000_000),
    ("gemini-1.5", 1_000_000),
    ("gemini", 128_000),
    # Others
    ("mistral-large", 128_000),
    ("mistral-small", 128_000),
    ("mistral", 128_000),
    ("minimax-m2", 128_000),
    ("minimax-text", 128_000),
    ("minimax", 128_000),
    ("ernie-4", 128_000),
    ("ernie-3", 8_000),
    ("ernie", 128_000),
    ("llama-4", 128_000),
    ("llama-3.3", 128_000),
    ("llama-3.2", 128_000),
    ("llama-3.1", 128_000),
    ("llama-3", 8_000),
    ("llama", 128_000),
    ("qwen2.5-72b", 128_000),
    ("qwen2.5", 128_000),
    ("yi-", 128_000),
    ("moonshot", 128_000),
]

# Safe default for unknown models: assume 128K (the current industry floor
# for frontier models). Users can override via the settings page.
_FALLBACK_CONTEXT_WINDOW = 128_000


def resolve_context_window(model_id: str) -> int:
    """Return the context window size for *model_id*.

    Matches case-insensitively against known model substrings.  Returns
    a conservative fallback when the model is unrecognised.
    """
    if not model_id:
        return _FALLBACK_CONTEXT_WINDOW
    lowered = model_id.lower()
    for pattern, window in _MODEL_CONTEXT_WINDOWS:
        if pattern in lowered:
            return window
    logger.debug("Unknown model %r, using fallback context window %d", model_id, _FALLBACK_CONTEXT_WINDOW)
    return _FALLBACK_CONTEXT_WINDOW


@dataclass
class CompactionSettings:
    enabled: bool = True
    # 0 means "auto-detect from model"; non-zero is a manual override.
    max_context_tokens: int = 0
    reserve_tokens: int = 4_000
    keep_recent_tokens: int = 8_000

    def effective_max_context_tokens(self, model_id: str = "") -> int:
        """Return the resolved context window, auto-detecting when set to 0."""
        if self.max_context_tokens > 0:
            return self.max_context_tokens
        return resolve_context_window(model_id)


# ---- token estimation ----

# Tokens per character for different Unicode ranges (conservative estimate).
# Based on observed behaviour of OpenAI / Anthropic tokenizers.
_CJK_RANGES = [
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0x3400, 0x4DBF),   # CJK Unified Ideographs Extension A
    (0x3000, 0x303F),   # CJK Symbols and Punctuation
    (0xFF00, 0xFFEF),   # Halfwidth and Fullwidth Forms
    (0x3040, 0x309F),   # Hiragana
    (0x30A0, 0x30FF),   # Katakana
    (0xAC00, 0xD7AF),   # Hangul Syllables
]


def _is_cjk(cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)


def estimate_tokens(text: str) -> int:
    """Estimate token count for a string using a character-based heuristic.

    CJK characters compress to ~0.7–1.5 tokens per char in modern
    tokenizers; ASCII / Latin averages ~0.25 tokens per char.  We use a
    blended divisor that slightly over-estimates, so compaction triggers
    conservatively early rather than too late.
    """
    if not text:
        return 0
    cjk = sum(1 for c in text if _is_cjk(ord(c)))
    non_cjk = len(text) - cjk
    return int(cjk / 1.2 + non_cjk / 3.5)


def estimate_message_tokens(messages: list[dict]) -> int:
    """Estimate total tokens for a list of chat messages."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    total += estimate_tokens(block.get("text", ""))
        total += 4  # per-message overhead (role marker, etc.)
    return total


def _total_tokens(messages: list[dict]) -> int:
    """Alias for readability inside this module."""
    return estimate_message_tokens(messages)


# ---- compaction logic ----


def _build_summary_prompt(
    old_messages: list[dict],
    previous_summary: str | None,
    tracked_files: dict[str, str] | None = None,
) -> str:
    lines: list[str] = []
    for msg in old_messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if not isinstance(content, str) or not content.strip():
            continue
        short = content[:800] + "…" if len(content) > 800 else content
        label = {"user": "用户", "assistant": "助手", "tool": "工具"}.get(role, role)
        lines.append(f"[{label}] {short}")

    convo = "\n".join(lines)
    prev = f"\n之前的上下文摘要：\n{previous_summary}\n" if previous_summary else ""

    files_section = ""
    if tracked_files:
        file_lines = []
        for path, contents in tracked_files.items():
            snippet = contents[:600] + "…" if len(contents) > 600 else contents
            file_lines.append(f"### {path}\n```\n{snippet}\n```")
        files_section = (
            "\n## 对话中引用到的文件内容快照：\n"
            + "\n".join(file_lines)
            + "\n请在摘要中保留这些文件的关键信息（路径、当前状态、修改意图）。\n"
        )

    return f"""压缩以下对话历史，生成一段简洁的上下文摘要。保留关键信息：用户需求、技术决策、文件操作、未完成任务。

{prev}
{files_section}
## 需要压缩的对话：
{convo}

## 输出要求：
- 不超过 500 字
- 使用中文
- 直接输出摘要，不要加任何前缀标记"""


# ---- file tracking (M4) ----

# Patterns we treat as file paths.  Conservative on purpose — false
# positives would be visible to the user as "garbage" file content in
# the summary, so we'd rather miss a path than read random strings.
_PATH_PATTERNS = [
    re.compile(r"(?:^|[\s\"'`=,(])(/Users/[^\s\"'`,)]+)"),               # macOS absolute
    re.compile(r"(?:^|[\s\"'`=,(])(/home/[^\s\"'`,)]+)"),                # Linux /home
    re.compile(r"(?:^|[\s\"'`=,(])(/root/[^\s\"'`,)]+)"),                # Linux /root
    re.compile(r"(?:^|[\s\"'`=,(])(/tmp/[^\s\"'`,)]+)"),                 # /tmp
    re.compile(r"(?:^|[\s\"'`=,(])(/var/[^\s\"'`,)]+)"),                 # /var
    re.compile(r"(?:^|[\s\"'`=,(])(?:~/|/Users/zuoxiaojun/Desktop/ClaudeProject/)([A-Za-z0-9_./-]+\.[A-Za-z0-9]{1,8})"),
    re.compile(r"(?:^|[\s\"'`=,(])(?:\./|\.\./)([A-Za-z0-9_./-]+\.[A-Za-z0-9]{1,8})"),
]

# Max total bytes of file content we'll inline in the summary.
_MAX_TRACKED_BYTES = 8_000
# Max number of distinct files we'll read.
_MAX_TRACKED_FILES = 5
# Per-file size cap.
_MAX_FILE_BYTES = 2_000

# Files we will *not* read even if mentioned (defence in depth — tools
# may have sanitised their args, but the compactor doesn't need to
# know what an LLM said about them).
_DENY_PATH_PREFIXES = (
    "/etc", "/sys", "/proc", "/dev", "/boot", "/System",
    "/usr/lib", "/usr/bin", "/usr/sbin",
    "/Library", "/var/run",
)


def _extract_paths_from_text(text: str) -> list[str]:
    """Find candidate file paths in *text*.  Returns absolute paths
    (relative ones get the user's home prepended)."""
    if not text:
        return []
    found: list[str] = []
    for pat in _PATH_PATTERNS:
        for m in pat.finditer(text):
            path = m.group(1)
            # Skip protocol-like strings (http://, file://)
            if "://" in path:
                continue
            # Normalise: expand ~, resolve ..
            try:
                if path.startswith("~"):
                    path = str(Path(path).expanduser())
                elif path.startswith("./") or path.startswith("../"):
                    # Leave relative as-is; the file read will fail
                    # and we just skip it.
                    pass
                found.append(path)
            except (OSError, ValueError):
                continue
    return found


def _extract_paths_from_messages(messages: list[dict]) -> list[str]:
    """Pull file paths out of every tool call's args and every tool
    result.  This is where YS-Agent most often references files:
    ``read_file`` / ``patch`` / ``write_file`` all take a ``path`` arg;
    the assistant often echoes paths in its own text."""
    paths: list[str] = []
    for msg in messages:
        # 1. Tool call args
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {}) if isinstance(tc, dict) else {}
            args_str = fn.get("arguments", "") or ""
            paths.extend(_extract_paths_from_text(args_str))
        # 2. Message content (assistant echoing paths, tool returning file content)
        content = msg.get("content", "")
        if isinstance(content, str):
            paths.extend(_extract_paths_from_text(content))
    return paths


def _read_file_safe(path: str) -> str | None:
    """Read *path* if it exists, is a regular file, is small enough,
    and not in a denied prefix.  Returns the text content, or ``None``
    to skip."""
    try:
        p = Path(path)
        if any(str(p).startswith(prefix) for prefix in _DENY_PATH_PREFIXES):
            return None
        if not p.exists() or not p.is_file():
            return None
        size = p.stat().st_size
        if size > _MAX_FILE_BYTES * 2:  # rough pre-check before opening
            return None
        text = p.read_text(encoding="utf-8", errors="replace")
        if len(text) > _MAX_FILE_BYTES:
            text = text[:_MAX_FILE_BYTES] + "\n… (truncated)"
        return text
    except (OSError, UnicodeError, ValueError):
        return None


def track_files(messages: list[dict]) -> dict[str, str]:
    """Return a ``{path: contents}`` dict of files referenced in
    *messages*, capped at :data:`_MAX_TRACKED_FILES` and
    :data:`_MAX_TRACKED_BYTES` total.  De-duplicates by path; reads
    in first-seen order."""
    seen: set[str] = set()
    out: dict[str, str] = {}
    total_bytes = 0
    for path in _extract_paths_from_messages(messages):
        if path in seen:
            continue
        seen.add(path)
        content = _read_file_safe(path)
        if content is None:
            continue
        if total_bytes + len(content) > _MAX_TRACKED_BYTES:
            break
        out[path] = content
        total_bytes += len(content)
        if len(out) >= _MAX_TRACKED_FILES:
            break
    return out


# ---- compaction logic (M4: provider-agnostic + event hook) ----

# Type of the summary caller.  M3 path: ``agent`` passes a closure that
# calls ``provider.chat(...)``.  Tests can pass any ``(str) -> str``.
SummaryCaller = Callable[[str], str]


def compact_messages(
    messages: list[dict],
    settings: CompactionSettings,
    summary_caller: SummaryCaller,
    model: str,
    previous_summary: str | None = None,
    event_bus: "EventBus | None" = None,
) -> tuple[list[dict], str | None, int]:
    """Compact old messages into a summary, keeping recent messages intact.

    M4 signature change: ``summary_caller`` replaces the old
    ``openai_client`` argument.  Pass any callable ``(prompt) -> str``.
    The M3 path constructs this from ``LLMProvider.chat()`` so
    Anthropic / OpenAI / etc. all work.

    Returns ``(new_messages, new_summary, tokens_saved)``.  If
    compaction isn't needed, returns the input unchanged.
    """
    if not settings.enabled:
        return messages, previous_summary, 0

    total = _total_tokens(messages)
    max_ctx = settings.effective_max_context_tokens(model)
    threshold = max_ctx - settings.reserve_tokens

    if total <= threshold:
        return messages, previous_summary, 0

    # Walk backwards to find the keep / summarise boundary.
    kept: list[dict] = []
    kept_tokens = 0
    for msg in reversed(messages):
        t = _total_tokens([msg])
        if kept_tokens + t <= settings.keep_recent_tokens:
            kept.insert(0, msg)
            kept_tokens += t
        else:
            break

    old_messages = messages[: len(messages) - len(kept)]
    if not old_messages:
        return messages, previous_summary, 0

    old_tokens = _total_tokens(old_messages)
    logger.info(
        "Compaction triggered: total=%d threshold=%d old=%d keep=%d",
        total, threshold, old_tokens, kept_tokens,
    )

    # M4: read files the conversation touched, before the LLM call.
    # This way the snapshot reflects the state at compaction time, not
    # at the moment the LLM first read the file.
    tracked_files = track_files(old_messages)
    if tracked_files:
        logger.info(
            "Compaction: tracked %d file(s): %s",
            len(tracked_files), list(tracked_files.keys()),
        )

    prompt = _build_summary_prompt(old_messages, previous_summary, tracked_files)

    # Call summary_caller.  Wrapped in try/except so a transient LLM
    # error falls back to the same "key user requests" salvage the
    # original code used — preserves M1 behaviour.
    try:
        new_summary = summary_caller(prompt).strip()
        if not new_summary:
            raise ValueError("empty summary")
    except Exception as e:
        logger.warning("Compaction LLM call failed (%s), using fallback summary", e)
        parts = []
        for m in old_messages:
            c = m.get("content", "")
            if isinstance(c, str) and c.strip() and m.get("role") == "user":
                parts.append(c[:120])
        new_summary = "历史需求摘要：" + "；".join(parts[-8:]) if parts else "（无法生成摘要）"

    # M4: publish SessionBeforeCompactEvent so extensions can read the
    # draft summary + tracked files and append their own notes via
    # ``event.extra``.
    if event_bus is not None:
        # Local import to avoid a cycle (events.types → no cycle today,
        # but keeping the dependency one-way: compactor depends on
        # events, not the other way around).
        from agent.events.types import SessionBeforeCompactEvent
        ev = SessionBeforeCompactEvent(
            old_messages=old_messages,
            summary=new_summary,
            tracked_files=tracked_files,
            extra=[],
        )
        event_bus.publish(ev)
        # Append any extension contributions to the summary, in order.
        if ev.extra:
            extra_text = "\n\n".join(ev.extra)
            new_summary = f"{new_summary}\n\n{extra_text}".strip()

    summary_msg = {
        "role": "user",
        "content": (
            "[上下文压缩摘要]\n"
            "以下是对之前对话内容的自动摘要。请结合这些背景信息继续对话：\n\n"
            + new_summary
        ),
    }

    compacted = [summary_msg] + kept
    after = _total_tokens(compacted)
    saved = total - after

    logger.info("Compaction: %d → %d tokens (%d saved)", total, after, saved)
    return compacted, new_summary, saved
