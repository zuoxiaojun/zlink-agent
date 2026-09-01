"""Message construction — system prompt + turn list sent to the LLM.

Extracted from the original ``AIAgent._truncate``/``run_conversation``
inline logic.  The system prompt is the result of concatenating:

  1. Base system prompt (with security rules etc.)
  2. Fact memory blocks (frozen snapshot from session start)
  3. Current time stamp
  4. Memory manager context
  5. Active skills index
   6. Skill detail (if user query matches a skill)
   7. Sub-agent delegation guidance (if delegate_task tool is available)
   8. ERP data-source context (dynamic, from active ERP clients)

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
    erp_context: str = "",
    artifact_dir: str = "",
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

    # 6. ERP 数据源上下文（动态注入）
    if erp_context:
        parts.append("## 可用数据源\n" + erp_context)

    # 7. 会话产物目录（每轮动态注入；无会话时为空，不注入）
    if artifact_dir:
        parts.append("## 会话产物\n" + artifact_dir)

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


def strip_images_from_messages(messages: list[dict]) -> list[dict]:
    """Remove ``image_url`` content blocks from messages.

    Used when the current model does not support vision (image input).
    Keeps text-only content blocks intact; replaces image-only messages
    with a placeholder text.
    """
    out: list[dict] = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            # Multimodal content blocks: keep only text, drop image_url
            text_parts = [b for b in content if isinstance(b, dict) and b.get("type") == "text"]
            image_count = sum(1 for b in content if isinstance(b, dict) and b.get("type") == "image_url")
            if image_count > 0 and not text_parts:
                # Image-only message — replace with placeholder
                msg = dict(msg)
                msg["content"] = f"[用户发送了 {image_count} 张图片，但当前模型不支持图片输入，已自动过滤]"
            elif text_parts:
                msg = dict(msg)
                msg["content"] = [{"type": "text", "text": b.get("text", "")} for b in text_parts]
        out.append(msg)
    return out


__all__ = ["build_system_prompt", "build_turn_messages"]
