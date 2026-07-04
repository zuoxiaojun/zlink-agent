"""Factory: pick the right provider class from a config dict.

Called by :mod:`agent.core.llm_client` (M3 migration shim) and by
``backend/api/chat.py`` (M5 will move config loading here).

Design
------
The factory takes a provider *display name* (``"OpenAI"``,
``"Anthropic"``, etc.) — the human-readable label that comes back from
the ``/api/providers`` endpoint — and returns an instance of the right
:class:`LLMProvider` subclass.

It also exposes :func:`get_provider_for_config` which takes the full
config dict (with ``llm_provider`` / ``llm_api_key`` / ``llm_base_url``
/ ``llm_model`` fields) and returns a ready-to-use provider.  This is
the entry point used by ``chat.py`` once M5 migration is done.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agent.core.llm_providers.base import LLMProvider, LLMProviderError
from agent.core.llm_providers.openai_compat import OpenAICompatProvider

if TYPE_CHECKING:
    from backend.llm_providers import LLM_PROVIDERS  # noqa: F401

logger = logging.getLogger(__name__)


def _load_providers_dict() -> dict:
    """Import the provider registry.  Done lazily so unit tests can run
    without ``backend`` on the path (e.g. CI environment that only
    imports the agent core)."""
    try:
        from backend.llm_providers import LLM_PROVIDERS
    except ImportError as e:
        raise LLMProviderError(
            "Could not import backend.llm_providers — is the backend package installed?",
            transient=False,
        ) from e
    return LLM_PROVIDERS


def list_protocols() -> dict[str, str]:
    """Return ``{display_name: protocol}`` for every provider in the
    registry.  Useful for debugging / status pages."""
    return {name: info.get("protocol", "openai_compat") for name, info in _load_providers_dict().items()}


def get_provider(
    display_name: str,
    *,
    api_key: str,
    base_url: str | None = None,
    timeout: float = 30.0,
    max_retries: int = 3,
    max_retry_delay: float = 30.0,
) -> LLMProvider:
    """Return an :class:`LLMProvider` instance for the given display name.

    If *base_url* is not provided, the registry's default is used.
    """
    if display_name == "自定义":
        if not base_url:
            raise LLMProviderError(
                "Custom provider requires a base_url",
                transient=False,
            )
        return OpenAICompatProvider(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            max_retry_delay=max_retry_delay,
        )

    providers = _load_providers_dict()
    if display_name not in providers:
        raise LLMProviderError(
            f"Unknown LLM provider: {display_name!r}. Available: {sorted(providers.keys())}",
            transient=False,
        )

    info = providers[display_name]
    protocol = info.get("protocol", "openai_compat")
    url = base_url or info["base_url"]

    if protocol == "openai_compat":
        return OpenAICompatProvider(
            api_key=api_key,
            base_url=url,
            timeout=timeout,
            max_retries=max_retries,
            max_retry_delay=max_retry_delay,
        )

    if protocol == "anthropic":
        # Lazy import: anthropic is an optional dependency.
        from agent.core.llm_providers.anthropic import AnthropicProvider

        return AnthropicProvider(
            api_key=api_key,
            base_url=url,
            timeout=timeout,
            max_retries=max_retries,
            max_retry_delay=max_retry_delay,
        )

    raise LLMProviderError(
        f"Unknown protocol {protocol!r} for provider {display_name!r}",
        transient=False,
    )


def get_provider_for_config(cfg: dict) -> LLMProvider:
    """Build a provider from a config dict (as stored by config_manager).

    Expected keys (with their existing defaults)::

        cfg["llm_provider"]    = "OpenAI"
        cfg["llm_api_key"]     = ""
        cfg["llm_base_url"]    = ""  # optional override
        cfg["llm_model"]       = "gpt-4o"
    """
    display_name = cfg.get("llm_provider", "OpenAI")
    api_key = cfg.get("llm_api_key", "")
    base_url = cfg.get("llm_base_url") or None
    return get_provider(
        display_name=display_name,
        api_key=api_key,
        base_url=base_url,
    )


__all__ = [
    "get_provider",
    "get_provider_for_config",
    "list_protocols",
]
