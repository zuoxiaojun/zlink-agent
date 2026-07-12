"""Tests for ``agent.context_compactor`` — the M4 refactor surface.

We test the three most likely things to break in a future refactor:
* token estimation (CJK-aware)
* file path tracking (the Pi-style "what files did the agent
  touch?" extraction)
* the new ``event_bus`` parameter on ``compact_messages`` — making
  sure ``SessionBeforeCompactEvent`` is published and extensions can
  augment the summary
"""

from __future__ import annotations

import json
from pathlib import Path

from agent.context_compactor import (
    CompactionSettings,
    _extract_paths_from_text,
    compact_messages,
    estimate_message_tokens,
    estimate_tokens,
    track_files,
)
from agent.events import Extension, SessionBeforeCompactEvent
from agent.events.bus import event_bus


def test_estimate_tokens_english_rough():
    """English ~ 1 token per 4 chars (rule of thumb used in the impl)."""
    # We don't pin the exact ratio (it could change), but we do
    # assert the function is monotonic, non-negative, and returns
    # something reasonable for empty input.
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello world") >= 3
    assert estimate_tokens("a" * 400) > estimate_tokens("a" * 100)


def test_estimate_message_tokens_handles_strings_and_lists():
    """``estimate_message_tokens`` should accept both string and
    list content shapes — ChatPage sends list, AIAgent sends str."""
    msgs_str = [{"role": "user", "content": "hello there"}]
    msgs_list = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "hello there"},
            ],
        }
    ]
    # Both should be > 0 and within an order of magnitude of each other
    s = estimate_message_tokens(msgs_str)
    lst = estimate_message_tokens(msgs_list)
    assert s > 0
    assert lst > 0
    # ratio should be reasonable — same text just wrapped differently
    assert 0.5 < s / lst < 2.0


def test_track_files_extracts_paths_from_tool_calls(tmp_path):
    """Pi-style file tracking: tool_calls with a ``path`` arg and
    message text containing file paths both get picked up.

    ``track_files`` actually reads the file (capped at a small
    number of bytes) — so we need a real existing file.  We write
    one into ``/tmp/`` and reference it from the messages.
    """
    f1 = "/tmp/test_track_alpha.py"
    f2 = "/tmp/test_track_beta.py"
    Path(f1).write_text("# alpha")
    Path(f2).write_text("# beta")
    try:
        msgs = [
            {"role": "user", "content": f"read {f1} and {f2}"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": json.dumps({"path": f1})},
                    }
                ],
            },
            {"role": "tool", "content": "# alpha\n# beta"},
        ]
        tracked = track_files(msgs)
        assert f1 in tracked
        assert f2 in tracked
        # Content is inlined — should contain the marker
        assert "alpha" in tracked[f1]
        assert "beta" in tracked[f2]
    finally:
        for p in (f1, f2):
            try:
                Path(p).unlink()
            except FileNotFoundError:
                pass


def test_extract_paths_from_text_ignores_urls():
    """``http://...`` and ``file://...`` must not be treated as paths."""
    paths = _extract_paths_from_text("see https://example.com/foo and file:///etc/passwd")
    # Neither URL should appear in the result
    assert not any("://" in p for p in paths)


def test_compact_messages_publishes_session_before_compact_event():
    """compact_messages(messages, settings, summary_caller, model,
    event_bus=...) must publish ``SessionBeforeCompactEvent`` when
    compaction is actually triggered.

    We force compaction by setting ``max_context_tokens`` very low.
    """
    # Settings: max_ctx=100, reserve=0, keep=0 → any non-empty message
    # list triggers compaction.
    settings = CompactionSettings(
        max_context_tokens=100,
        reserve_tokens=0,
        keep_recent_tokens=0,
    )
    msgs = [
        {"role": "user", "content": "old message " * 50},
        {"role": "assistant", "content": "old reply " * 50},
    ]

    captured: list[SessionBeforeCompactEvent] = []

    def _spy(evt):
        if isinstance(evt, SessionBeforeCompactEvent):
            captured.append(evt)

    event_bus.subscribe(_spy)

    def fake_summary(prompt: str) -> str:
        return "MOCK SUMMARY"

    new_msgs, new_summary, _tokens = compact_messages(
        messages=msgs,
        settings=settings,
        summary_caller=fake_summary,
        model="gpt-4o",
        event_bus=event_bus,
    )
    assert len(captured) == 1, (
        f"compact_messages should publish exactly 1 event when forced; got {len(captured)}. new_summary={new_summary!r}"
    )
    evt = captured[0]
    # SessionBeforeCompactEvent has these fields per M4:
    #   old_messages, summary, tracked_files, extra (list[str])
    assert evt.summary == "MOCK SUMMARY"
    assert isinstance(evt.extra, list)
    # Extensions can append to evt.extra; verify it's a list
    evt.extra.append("from-test")
    assert evt.extra == ["from-test"]


def test_compact_messages_extension_can_augment_summary():
    """An extension subscribed to SessionBeforeCompactEvent can append
    strings to evt.extra, and compact_messages must fold those into
    the final summary."""
    settings = CompactionSettings(
        max_context_tokens=100,
        reserve_tokens=0,
        keep_recent_tokens=0,
    )
    msgs = [
        {"role": "user", "content": "old message " * 50},
        {"role": "assistant", "content": "old reply " * 50},
    ]

    class AugmentExt(Extension):
        name = "augmenter"
        enabled = True

        def on_session_before_compact(self, evt: SessionBeforeCompactEvent) -> None:
            # extra is list[str] in M4 — append, don't assign
            evt.extra.append("[AUGMENTED by extension]")

    from agent.events.extensions import register_extensions

    register_extensions([AugmentExt()])

    def fake_summary(prompt: str) -> str:
        return "BASE"

    _, new_summary, _ = compact_messages(
        messages=msgs,
        settings=settings,
        summary_caller=fake_summary,
        model="gpt-4o",
        event_bus=event_bus,
    )
    assert new_summary is not None
    assert "BASE" in new_summary
    assert "AUGMENTED by extension" in new_summary, f"extension append not folded in: {new_summary!r}"


# ────────────────────────────────────────────────────────────────────
# resolve_context_window
# ────────────────────────────────────────────────────────────────────


def test_resolve_context_window_known_model():
    """Known models should return their mapped context window."""
    from agent.context_compactor import resolve_context_window

    assert resolve_context_window("gpt-4o") == 128_000
    assert resolve_context_window("gpt-4.1") == 1_000_000
    assert resolve_context_window("claude-sonnet-4-20250514") == 200_000
    assert resolve_context_window("deepseek-chat") == 128_000
    assert resolve_context_window("qwen-plus") == 128_000
    assert resolve_context_window("gemini-2.5-pro") == 1_000_000
    assert resolve_context_window("o3") == 200_000
    assert resolve_context_window("kimi-k2.5") == 128_000
    assert resolve_context_window("glm-4-plus") == 128_000


def test_resolve_context_window_unknown_model():
    """Unknown models should return the fallback."""
    from agent.context_compactor import resolve_context_window

    assert resolve_context_window("completely-unknown-model-v99") == 128_000


def test_resolve_context_window_empty():
    """Empty string should return fallback."""
    from agent.context_compactor import resolve_context_window

    assert resolve_context_window("") == 128_000


def test_resolve_context_window_case_insensitive():
    """Model matching should be case-insensitive."""
    from agent.context_compactor import resolve_context_window

    assert resolve_context_window("GPT-4O") == 128_000
    assert resolve_context_window("Claude-Sonnet-4") == 200_000
    assert resolve_context_window("DEEPSEEK-CHAT") == 128_000


def test_resolve_context_window_prefers_specific():
    """More specific (longer) patterns should match before broader ones."""
    from agent.context_compactor import resolve_context_window

    assert resolve_context_window("minimax-m3") == 1_000_000  # specific, not generic 128K
    assert resolve_context_window("minimax-m2.5") == 128_000  # falls to m2.5 row
    assert resolve_context_window("gpt-4.1-mini") == 1_000_000  # 4.1 family, not generic 4o


# ────────────────────────────────────────────────────────────────────
# CompactionSettings.effective_max_context_tokens
# ────────────────────────────────────────────────────────────────────


def test_effective_max_context_tokens_manual_override():
    """When max_context_tokens > 0, the manual value is used."""
    settings = CompactionSettings(max_context_tokens=32000)
    assert settings.effective_max_context_tokens("gpt-4o") == 32000


def test_effective_max_context_tokens_auto():
    """When max_context_tokens == 0, the model's value is used."""
    settings = CompactionSettings(max_context_tokens=0)
    assert settings.effective_max_context_tokens("gpt-4o") == 128_000


def test_effective_max_context_tokens_unknown_model():
    """When model is unknown and max_context_tokens==0, fallback applies."""
    settings = CompactionSettings(max_context_tokens=0)
    assert settings.effective_max_context_tokens("unknown-model") == 128_000


def test_effective_max_context_tokens_defaults():
    """Default CompactionSettings with no model should return fallback."""
    settings = CompactionSettings()
    assert settings.effective_max_context_tokens() == 128_000


# ────────────────────────────────────────────────────────────────────
# Additional edge cases for estimate_tokens
# ────────────────────────────────────────────────────────────────────


def test_estimate_tokens_cjk():
    """CJK characters are heavier than ASCII per char."""
    from agent.context_compactor import estimate_tokens

    cjk = estimate_tokens("你好世界")
    ascii = estimate_tokens("hello world")
    # CJK should estimate more tokens than equivalent-length ASCII
    assert cjk >= ascii


def test_estimate_tokens_mixed():
    """Mixed CJK + ASCII should still produce a positive count."""
    from agent.context_compactor import estimate_tokens

    t = estimate_tokens("你好 world hello 世界")
    assert t > 0


def test_estimate_tokens_newlines():
    """Newlines alone produce zero tokens (the estimator counts
    non-whitespace chars)."""
    from agent.context_compactor import estimate_tokens

    assert estimate_tokens("\n\n\n") == 0
