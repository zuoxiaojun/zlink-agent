"""Message construction — system prompt + turn list sent to the LLM.

Extracted from the original ``AIAgent._truncate``/``run_conversation``
inline logic.  The system prompt is the result of concatenating:

  1. Base system prompt (with security rules etc.)
  2. Fact memory blocks (frozen snapshot from session start)
  3. Current time stamp
  4. Memory manager context
  5. Active skills index
  6. Skill detail (if user query matches a skill)

This module is intentionally side-effect-free — given a list of
``(label, content)`` fragments, it concatenates them.  The agent loop
in ``core/agent.py`` decides what fragments to add; ``message_builder``
just glues them together.

Why split this out
------------------
* Testable: ``build_system_prompt(fragments)`` is pure.
* Reusable: M4 (compaction) will need to build its own system prompt
  prefix when summarising old messages.
* Readable: the original 481-line ``agent.py`` had this logic in the
  middle of the loop, making it hard to follow.
"""

from __future__ import annotations

from datetime import datetime


def build_system_prompt(
    base: str,
    memory_store: object | None = None,
    memory_context: str = "",
    skill_index: str = "",
    skill_detail: str = "",
) -> str | None:
    """Concatenate system prompt fragments.

    Returns ``None`` if only the base prompt is present (saves us wrapping
    a single string in a list when there's no extra context).
    """
    parts: list[str] = [base]

    # 1. Fact memory blocks (frozen snapshot)
    if memory_store is not None:
        for target in ("memory", "user"):
            block = memory_store.format_for_system_prompt(target)  # type: ignore[attr-defined]
            if block:
                parts.append(block)

    # 2. Current time
    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    parts.append(f"## 当前信息\n当前时间：{now.strftime('%Y年%m月%d日 %H:%M')} {weekdays[now.weekday()]}")

    # 3. Memory manager context (long-term cross-session facts)
    if memory_context:
        parts.append("## 记忆信息\n" + memory_context)

    # 4. Active skills index
    if skill_index:
        parts.append(skill_index)

    # 5. Skill detail (specific instructions for a matched skill)
    if skill_detail:
        parts.append(skill_detail)

    if len(parts) == 1:
        return None
    return "\n\n".join(parts)


def build_turn_messages(
    history: list[dict] | None,
    user_message: str | list,
) -> list[dict]:
    """Build the message list for one agent turn.

    ``history`` is the conversation before the current user turn.  We
    intentionally do not strip ``tool`` messages here — the agent loop
    only passes pre-filtered history (see ``backend/api/chat.py``).

    ``user_message`` mirrors the original ``run_conversation`` signature,
    which accepted either a plain string or a list of content parts
    (the OpenAI multimodal content shape).
    """
    messages: list[dict] = []
    if history:
        messages.extend(list(history))
    messages.append({"role": "user", "content": user_message})
    return messages


__all__ = ["build_system_prompt", "build_turn_messages"]
