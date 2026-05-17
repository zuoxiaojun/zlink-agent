"""Clarify tool — ask the user a question when instructions are ambiguous.

The tool returns a structured question. The agent loop finishes the turn,
the user sees the question, and their next message serves as the answer.
"""

import logging

from agent.tools.registry import registry, tool_result, tool_error

logger = logging.getLogger(__name__)

MAX_CHOICES = 4


def _handle_clarify(args: dict) -> str:
    """Present a question to the user."""
    question = args.get("question", "")
    choices = args.get("choices")

    if not question:
        return tool_error("question（问题）是必需的")

    if choices is not None:
        if not isinstance(choices, list):
            return tool_error("choices 必须是数组")
        if len(choices) > MAX_CHOICES:
            choices = choices[:MAX_CHOICES]

    return tool_result(
        data=question,
        question=question,
        choices=choices,
    )


CLARIFY_SCHEMA = {
    "name": "clarify",
    "description": (
        "当指令不明确、需要用户确认或决策时，向用户提出澄清问题。"
        "支持两种模式：\n\n"
        "1. 多项选择 — 提供最多 4 个选项供用户选择\n"
        "2. 开放式 — 省略 choices，用户自由输入\n\n"
        "在以下情况使用：\n"
        "- 任务有歧义，需要用户选择方案\n"
        "- 决策有重要权衡，需要用户参与\n"
        "- 任务完成后征求反馈\n\n"
        "不要对低风险决策使用此工具——自行做出合理选择即可。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "要向用户提出的问题。",
            },
            "choices": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": MAX_CHOICES,
                "description": (
                    "最多 4 个选项。省略此参数则为开放式问题。"
                ),
            },
        },
        "required": ["question"],
    },
}

registry.register(
    name="clarify",
    toolset="clarify",
    schema=CLARIFY_SCHEMA,
    handler=_handle_clarify,
    emoji="❓",
)
