"""Memory tool — durable fact-level memory that persists across sessions.

Uses the MemoryStore singleton from fact_memory for storage and
frozen-snapshot injection via the agent loop.
"""

import logging

from agent import fact_memory
from agent.tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)


def _handle_memory(args: dict) -> str:
    """Manage persistent fact memory."""
    action = args.get("action", "")
    target = args.get("target", "memory")
    content = args.get("content")
    old_text = args.get("old_text")

    if action not in ("add", "replace", "remove", "list"):
        return tool_error("action 必须是 add、replace、remove 或 list")

    if target not in ("memory", "user"):
        return tool_error("target 必须是 'memory' 或 'user'")

    store = fact_memory.get_store()
    if store is None:
        return tool_error("Memory 不可用。")

    if action == "list":
        raw = store.list_entries(target)
        if not raw:
            return tool_result(data=f"「{target}」中没有记忆。")
        return tool_result(data=f"「{target}」中的记忆:\n" + "\n".join(f"- {e}" for e in raw))

    if action == "add":
        if not content:
            return tool_error("add 操作需要 content")
        result = store.add(target, content)
    elif action == "replace":
        if not content or not old_text:
            return tool_error("replace 操作需要 content 和 old_text")
        result = store.replace(target, old_text, content)
    else:
        if not old_text:
            return tool_error("remove 操作需要 old_text")
        result = store.remove(target, old_text)

    if result["success"]:
        return tool_result(
            data=f"已{ {'add': '添加', 'replace': '替换', 'remove': '移除'}[action] }"
            f"到「{target}」（{result.get('usage', '')}）。",
        )
    return tool_error(result["error"])


MEMORY_SCHEMA = {
    "name": "memory",
    "description": (
        "将持久化信息保存到跨会话的记忆中。记忆会在后续会话中注入到系统提示，"
        "所以请保持简洁，只保存以后还会有用的事实。\n\n"
        "何时保存（自动执行，不要等用户要求）：\n"
        "- 用户纠正你或说「记住这个」/「别再这么做了」\n"
        "- 用户分享了偏好、习惯或个人细节（名字、角色、时区、编码风格）\n"
        "- 你发现了环境信息（操作系统、已安装工具、项目结构）\n"
        "- 你学到了某个约定、API 特性或工作流\n\n"
        "两个存储目标：\n"
        "- 'user'：用户是谁——名字、角色、偏好、沟通风格\n"
        "- 'memory'：你的笔记——环境事实、项目约定、工具特性、经验教训\n\n"
        "操作：add（新增），replace（替换——old_text 标识），"
        "remove（删除——old_text 标识），list（列出当前条目）\n\n"
        "不要保存：临时任务状态、会话结果、明显信息。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "replace", "remove", "list"],
                "description": "要执行的操作。list 列出当前条目，不要求 content 和 old_text。",
            },
            "target": {
                "type": "string",
                "enum": ["memory", "user"],
                "description": "目标存储：'memory' 为个人笔记，'user' 为用户画像。",
            },
            "content": {
                "type": "string",
                "description": "条目内容。add 和 replace 操作必需。",
            },
            "old_text": {
                "type": "string",
                "description": "标识要替换或删除的条目的短文本。replace 和 remove 操作必需。",
            },
        },
        "required": ["action", "target"],
    },
}

registry.register(
    name="memory",
    execution_mode="sequential",
    toolset="memory",
    schema=MEMORY_SCHEMA,
    handler=_handle_memory,
    emoji="🧠",
)
