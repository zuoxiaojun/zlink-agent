"""Sub-agent delegation tool.

Lets the main LLM agent spawn child ``AIAgent`` instances in a
``ThreadPoolExecutor`` to handle independent subtasks in parallel.
The child agent shares the same LLM configuration, tool registry,
and security hooks as the parent, but runs in its own conversation
context with a limited iteration budget.

Usage triggered by the LLM when a complex query involves multiple
independent data sources (e.g. "compare sales from YonSuite and NC").
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from agent.tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────

_MAX_WORKERS = 3
_SUB_AGENT_TIMEOUT = 120.0  # seconds
_SUB_AGENT_MAX_ITERATIONS = 15
_MAX_RESULT_CHARS = 10_000

# Thread-local storage for the parent agent's config so sub-agents
# can inherit credentials without passing them through tool args.
# NOTE: Values are captured on the calling thread and passed explicitly
# to executor.submit() — threading.local() values don't cross
# thread boundaries.
_parent_config = threading.local()


def _run_sub_agent(task: str, context: str, parent_cfg: dict) -> str:
    """Execute *task* in a child AIAgent and return its final response.

    The child agent is created with the same LLM credentials,
    tool registry, and model as the parent but starts with an
    empty conversation history and a limited iteration budget.

    Args:
        task: The subtask description for the child agent.
        context: Optional context information.
        parent_cfg: Dictionary with ``api_key``, ``base_url``,
            ``model``, ``temperature`` captured on the calling thread.
    """
    from agent.core.agent import AIAgent
    from agent.tools.registry import discover_tools

    # Guard redundant discover_tools: parent already discovered tools,
    # but ensure we don't miss any if tools were loaded after parent init.
    if not registry.get_all_tool_names():
        discover_tools()

    api_key = parent_cfg.get("api_key", "")
    base_url = parent_cfg.get("base_url", "https://api.openai.com/v1")
    model = parent_cfg.get("model", "gpt-4o")
    temperature = parent_cfg.get("temperature", 0.7)

    # Build the prompt: context + task
    system_message = f"你是 ZLink Agent 的子代理，负责完成主代理委托给你的特定子任务。\n\n## 任务\n{task}\n\n"
    if context:
        system_message += f"## 上下文信息\n{context}\n"

    sub_agent = AIAgent(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
        max_iterations=_SUB_AGENT_MAX_ITERATIONS,
        max_tool_result_length=_MAX_RESULT_CHARS,
        # Forward the parent's approval_callback so the child can
        # surface high-risk tool blocks (approval_mode=approve) to the
        # same UI.  When the parent's callback is None (default), the
        # child falls back to its existing 120 s silent timeout.
        approval_callback=parent_cfg.get("approval_callback"),
    )

    result = sub_agent.run_conversation(
        user_message=f"请完成以下任务：\n\n{task}\n\n{'上下文：' + context if context else ''}",
        system_message=system_message,
    )

    response = result.get("final_response", "") or ""
    if not response and not result.get("completed", True):
        response = f"[子代理任务未完成：{result.get('error', '未知错误')}]"

    if len(response) > _MAX_RESULT_CHARS:
        response = response[:_MAX_RESULT_CHARS] + "\n\n[结果已截断]"

    return response


def handle_delegate_task(args: dict) -> str:
    """Handle a ``delegate_task`` tool call.

    Spawns a child AIAgent via ThreadPoolExecutor and returns the
    child's final response.  The child shares the parent's LLM
    credentials but has its own conversation context.

    Important: Parent config is captured on the calling thread
    *before* submitting to the executor, because ``threading.local()``
    values are per-thread and do not propagate to worker threads.
    """
    task = args.get("task", "")
    context = args.get("context", "")

    if not task:
        return tool_error("task 参数是必需的")

    # Capture parent config on the calling thread before submitting
    # to the executor — threading.local() does NOT cross thread boundaries.
    parent_cfg = {
        "api_key": getattr(_parent_config, "api_key", ""),
        "base_url": getattr(_parent_config, "base_url", "https://api.openai.com/v1"),
        "model": getattr(_parent_config, "model", "gpt-4o"),
        "temperature": getattr(_parent_config, "temperature", 0.7),
        # Forwarded so child agents can prompt the same WS client when
        # they trigger a high-risk tool under approval_mode=approve.
        # Without this, the child would silently wait 120 s and then
        # return "user denied" — leaving the user confused.
        "approval_callback": getattr(_parent_config, "approval_callback", None),
    }

    try:
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            future = executor.submit(_run_sub_agent, task, context, parent_cfg)
            sub_result = future.result(timeout=_SUB_AGENT_TIMEOUT)
    except TimeoutError:
        return tool_error(f"子代理执行超时（{_SUB_AGENT_TIMEOUT} 秒）")
    except Exception as e:
        logger.exception("Sub-agent failed")
        return tool_error(f"子代理执行失败: {e}")

    return tool_result(data=sub_result)


_DELEGATE_TASK_SCHEMA = {
    "name": "delegate_task",
    "description": (
        "将子任务委托给一个子 AI Agent 并行执行。\n\n"
        "当你遇到可以独立并行的子任务时使用。例如：\n"
        "- 同时查 YonSuite 和 NC 两个系统的数据\n"
        "- 同时搜索多个不同领域的信息\n"
        "- 将一个复杂任务拆成多个独立步骤并行处理\n\n"
        "每个子代理有独立的对话上下文和 15 轮迭代上限。\n"
        "主代理在收到所有子代理结果后合并呈现给用户。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "子代理需要完成的任务描述。应当清晰、具体，包含所有必要信息。",
            },
            "context": {
                "type": "string",
                "description": "子代理需要的上下文信息（相关对话历史、数据、配置等）。可选但推荐提供。",
            },
        },
        "required": ["task"],
    },
}


def set_parent_config(
    api_key: str = "",
    base_url: str = "",
    model: str = "",
    temperature: float = 0.7,
    approval_callback=None,
):
    """Set the parent agent's LLM config for child agents to inherit.

    Called from the agent loop (``agent.py``) before delegate_task
    may be invoked.  Uses thread-local storage so multiple concurrent
    conversations don't interfere.

    ``approval_callback`` is forwarded to child AIAgents so high-risk
    tool blocks raised under ``approval_mode=approve`` can be surfaced
    to the same UI as the parent's requests.
    """
    _parent_config.api_key = api_key
    _parent_config.base_url = base_url
    _parent_config.model = model
    _parent_config.temperature = temperature
    _parent_config.approval_callback = approval_callback
