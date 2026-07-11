"""Tool execution confirmation — user approval for high-risk operations.

When the ``approval_hook`` in ``security_hooks.py`` blocks a high-risk
tool (approval_mode="approve"), the LLM receives a block message.  It
should ask the user for permission, and if approved, call this tool to
record the approval and re-execute the original operation.

Flow
----
1. Agent calls a high-risk tool (e.g. ``terminal``, ``file_delete``)
2. ``approval_hook`` blocks it → returns block message
3. Agent explains to user: "XX 操作需要你的批准"
4. User replies: "批准"
5. Agent calls ``confirm_tool_execution(tool_name, args)``
6. This tool records approval in the cache (60s TTL)
7. Then re-dispatches the original tool
8. ``approval_hook`` sees cached approval → lets it through
"""

from __future__ import annotations

import json
import logging

from agent.tools.registry import registry

logger = logging.getLogger(__name__)

SCHEMA = {
    "name": "confirm_tool_execution",
    "description": (
        "确认执行一个被安全系统拦截的高风险操作。\n\n"
        "当你的工具调用被 approval_hook 拦截并返回「需要你的确认」消息时，"
        "你应该先向用户解释需要执行的操作，请用户批准。\n"
        "如果用户批准，调用此工具来确认执行。\n"
        "如果用户拒绝，回复用户操作已取消。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "description": "需要确认执行的工具名称（从阻断消息中获取）",
            },
            "args": {
                "type": "object",
                "description": "需要确认执行的工具参数（从阻断消息中获取）",
            },
        },
        "required": ["tool_name", "args"],
    },
}


def handle_confirm_tool_execution(args: dict) -> str:
    """Handle a ``confirm_tool_execution`` tool call.

    1. Record approval in the security cache (60s TTL).
    2. Re-dispatch the original tool.
    """
    tool_name = args.get("tool_name", "")
    tool_args = args.get("args", {})

    if not tool_name:
        return json.dumps({"success": False, "error": "tool_name 参数是必需的"})

    # Record approval in the cache
    try:
        from agent.tools.security_hooks import record_approval

        record_approval(tool_name, tool_args)
        logger.info("Approval recorded: %s %s", tool_name, tool_args)
    except Exception as e:
        logger.exception("Failed to record approval")
        return json.dumps({"success": False, "error": f"记录审批失败: {e}"})

    # Re-dispatch the original tool
    try:
        result = registry.dispatch(tool_name, tool_args)
        if not isinstance(result, str):
            result = json.dumps(result, ensure_ascii=False)
        return result
    except Exception as e:
        logger.exception("Re-dispatch failed after approval")
        return json.dumps({"success": False, "error": f"重新执行 {tool_name} 失败: {e}"})


# Auto-register at import time
registry.register(
    name="confirm_tool_execution",
    toolset="agent",
    schema=SCHEMA,
    handler=handle_confirm_tool_execution,
    description="确认执行被安全系统拦截的高风险操作",
    emoji="✅",
    risk_level="low",
)
