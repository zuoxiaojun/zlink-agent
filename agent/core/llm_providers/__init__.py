"""LLM provider abstraction.

M3 architecture
---------------
The original ``agent.core.llm_client.LLMClient`` was a 1:1 wrapper around
the OpenAI SDK.  M3 introduces a polymorphic ``LLMProvider`` so that
switching between OpenAI / Anthropic / etc. is a one-line change.

Provider implementations
------------------------
* :class:`OpenAICompatProvider` — covers OpenAI, DeepSeek, Zhipu,
  SiliconFlow, DashScope (Qwen), Moonshot (Kimi), OpenRouter, MiniMax,
  Baidu Qianfan.  They all speak the OpenAI Chat Completions protocol.
* :class:`AnthropicProvider`     — uses the official ``anthropic`` SDK
  and translates the tool-call shape to OpenAI's.

The ``protocol`` field in :data:`backend.llm_providers.LLM_PROVIDERS`
picks which class to use.  Add a new provider by adding one entry there
— no Python code changes needed.

The unified response shape is :class:`LLMResponse`, identical to what
``LLMClient`` already returned.  Provider implementations adapt their
native response into this shape.
"""
from __future__ import annotations

from agent.core.llm_providers.base import (
    LLMProvider,
    LLMResponse,
    ToolCallPayload,
    LLMProviderError,
)
from agent.core.llm_providers.openai_compat import OpenAICompatProvider
from agent.core.llm_providers.factory import (
    get_provider,
    get_provider_for_config,
    list_protocols,
)

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "ToolCallPayload",
    "LLMProviderError",
    "OpenAICompatProvider",
    "get_provider",
    "get_provider_for_config",
    "list_protocols",
]
