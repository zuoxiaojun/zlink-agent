"""Todo list tool for session task management.

Lets the LLM create, update, and track multi-step tasks during a session.
Persistence to DATA_DIR / "todos.json".
"""

import json
import logging

from agent.tools.registry import registry, tool_error, tool_result
from agent.utils import DATA_DIR, atomic_json_write

logger = logging.getLogger(__name__)

TODO_FILE = DATA_DIR / "todos.json"


def _read() -> list[dict]:
    if not TODO_FILE.exists():
        return []
    try:
        data = json.loads(TODO_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write(todos: list[dict]):
    TODO_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_json_write(TODO_FILE, todos)


def _handle_todo(args: dict) -> str:
    """Manage the task list."""
    todos_param = args.get("todos")
    merge = args.get("merge", False)

    if todos_param is None:
        # Read mode
        current = _read()
        if not current:
            return tool_result(data="当前没有待办任务。", todos=[])
        return tool_result(
            data=f"当前有 {len(current)} 个待办任务：",
            todos=current,
        )

    if not isinstance(todos_param, list):
        return tool_error("todos 必须是数组")

    if merge:
        current = _read()
        new_by_id = {t.get("id"): t for t in todos_param if t.get("id")}
        merged = list(current)
        for i, item in enumerate(merged):
            if item.get("id") in new_by_id:
                merged[i] = new_by_id.pop(item["id"])
        merged.extend(new_by_id.values())
        _write(merged)
    else:
        _write(todos_param)

    return tool_result(
        data=f"已{'合并' if merge else '更新'}待办列表，共 {len(_read())} 项。",
        todos=_read(),
    )


TODO_SCHEMA = {
    "name": "todo",
    "description": (
        "管理当前会话的任务列表。适用于需要 3 步以上的复杂任务或多任务场景。\n\n"
        "无参数调用时返回当前列表。\n\n"
        "写入时：\n"
        "- 提供 todos 数组创建/更新任务\n"
        "- merge=false（默认）：完整替换整个列表\n"
        "- merge=true：按 id 更新已有项，添加新项\n\n"
        "每项格式：{id: string, content: string, "
        "status: pending|in_progress|completed|cancelled}\n"
        "列表顺序即优先级。同一时间只允许一个 in_progress。\n"
        "任务完成后立即标记为 completed。失败则标记为 cancelled 并新增修正项。\n"
        "始终返回完整的当前列表。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "要写入的任务项。省略则读取当前列表。",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "唯一标识"},
                        "content": {"type": "string", "description": "任务描述"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed", "cancelled"],
                            "description": "当前状态",
                        },
                    },
                    "required": ["id", "content", "status"],
                },
            },
            "merge": {
                "type": "boolean",
                "description": "true=按 id 合并更新，false=完整替换（默认 false）",
                "default": False,
            },
        },
    },
}

registry.register(
    name="todo",
    toolset="todo",
    schema=TODO_SCHEMA,
    handler=_handle_todo,
    emoji="📋",
)
