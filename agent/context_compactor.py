"""Context compaction for long conversations.

When the accumulated conversation history approaches the model's context
window, older messages are summarized via LLM and replaced with a compact
summary, keeping recent messages intact.

Inspired by Pi's Compaction system (CompactionSettings / CompactionPreparation).
"""

import logging
import re
from dataclasses import dataclass

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

    return f"""压缩以下对话历史，生成一段简洁的上下文摘要。保留关键信息：用户需求、技术决策、文件操作、未完成任务。

{prev}
## 需要压缩的对话：
{convo}

## 输出要求：
- 不超过 500 字
- 使用中文
- 直接输出摘要，不要加任何前缀标记"""


def compact_messages(
    messages: list[dict],
    settings: CompactionSettings,
    openai_client,
    model: str,
    previous_summary: str | None = None,
) -> tuple[list[dict], str | None, int]:
    """Compact old messages into a summary, keeping recent messages intact.

    Returns (new_messages, new_summary, tokens_saved).
    If compaction is not needed, returns the original messages unchanged.
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

    prompt = _build_summary_prompt(old_messages, previous_summary)

    try:
        resp = openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.3,
        )
        new_summary = resp.choices[0].message.content.strip()
    except Exception:
        logger.warning("Compaction LLM call failed, using fallback summary")
        parts = []
        for m in old_messages:
            c = m.get("content", "")
            if isinstance(c, str) and c.strip() and m.get("role") == "user":
                parts.append(c[:120])
        new_summary = "历史需求摘要：" + "；".join(parts[-8:]) if parts else "（无法生成摘要）"

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
