"""Core agent loop — split out of the original monolithic agent.py.

Modules
-------
* ``message_builder``  — build the system prompt and turn list sent to the LLM
* ``llm_client``       — LLM call with retry/backoff + streaming consumption
* ``tool_dispatcher``  — run a tool through the registry, applying truncation
* ``agent``            — main loop, ties the three together
"""

from agent.core.iteration_budget import IterationBudget
from agent.core.llm_client import LLMClient, LLMResponse, ToolCallPayload
from agent.core.message_builder import build_system_prompt, build_turn_messages
from agent.core.tool_dispatcher import dispatch_tool

__all__ = [
    "build_system_prompt",
    "build_turn_messages",
    "LLMClient",
    "LLMResponse",
    "ToolCallPayload",
    "dispatch_tool",
    "IterationBudget",
]
