"""pytest shared fixtures for ZLink Agent test suite.

These tests do NOT touch the network, do NOT use the real LLM, and do
NOT call the real YonSuite API.  Every test gets a clean
``MockLLMProvider`` so we can drive the agent loop deterministically.

Design notes
------------
* The :func:`clean_extensions` autouse fixture is the most important
  one — it wipes the global ``_all_extensions`` /
  ``_active_runners`` lists and unsubscribes everything from the
  event bus between tests.  Without it, tests that register an
  extension would leak into every other test.

* The :func:`isolated_config` fixture redirects config reads/writes
  to a temp directory so M5+ config tests don't pollute the real
  ``data/config.json`` on the developer's machine.

* The :func:`mock_llm_provider` factory returns a tiny stand-in for
  the OpenAI chat API.  Use it via the ``agent._llm`` private
  attribute (the AIAgent accepts any LLMClient; we replace it after
  construction).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

# Ensure the project root is on sys.path so ``agent.*`` and ``backend.*``
# imports work — same trick used in ``backend/main.py``.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ────────────────────────────────────────────────────────────────────
# Event-bus isolation
# ────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clean_extensions():
    """Wipe global extension state and event bus subscriptions.

    Runs after each test (yield-then-cleanup pattern).  Without this,
    any ``register_extensions`` call inside a test would leak into
    every subsequent test.
    """
    yield  # run the test first
    try:
        from agent.events.bus import event_bus
        from agent.events.extensions import (
            shutdown_all_extensions,
        )

        # shutdown_all_extensions unsubscribes its own runners and
        # forgets instances.  We then explicitly clear any stragglers
        # that may have been subscribed via ``event_bus.subscribe``
        # directly (not common but defensive).
        shutdown_all_extensions()
        # event_bus._subscribers is a list managed inside the bus;
        # ``clear()`` exists for this exact case.
        if hasattr(event_bus, "_subscribers"):
            event_bus._subscribers.clear()
    except Exception:
        # Best-effort cleanup — never let a cleanup failure mask
        # a real test failure.
        pass


@pytest.fixture(autouse=True)
def clean_search_db():
    """Close all tracked SQLite connections after each test to avoid ResourceWarning."""
    yield
    try:
        from agent.search_index import close_all_connections

        close_all_connections()
    except Exception:
        pass


# ────────────────────────────────────────────────────────────────────
# Config isolation
# ────────────────────────────────────────────────────────────────────


@pytest.fixture
def isolated_config(monkeypatch, tmp_path: Path):
    """Redirect ``agent.config_manager`` to a temp file.

    Used by tests that exercise the M5+ ``disabled_extensions`` save/
    load round-trip.  Returns the temp Path so the test can inspect
    the persisted JSON directly.
    """
    from agent import config_manager
    from agent.config_model import AppConfig

    fake_file = tmp_path / "config.json"
    fake_file.write_text(json.dumps(AppConfig().model_dump(mode="json")))

    monkeypatch.setattr(config_manager, "CONFIG_FILE", fake_file)
    return fake_file


# ────────────────────────────────────────────────────────────────────
# Mock LLM provider
# ────────────────────────────────────────────────────────────────────


class MockLLMProvider:
    """Drop-in stand-in for LLMProvider that returns scripted responses.

    The real :class:`LLMProvider` is an ABC; we don't inherit it
    (tests want zero ceremony), so we expose the same ``chat(**kwargs)``
    method that ``LLMClient`` calls.  ``LLMClient`` uses duck typing —
    the ``provider: LLMProvider | None`` annotation on its constructor
    is a hint, not a runtime check.
    """

    def __init__(self, responses: list | None = None):
        from agent.core.llm_providers import LLMResponse

        self._script = list(responses or [])
        self._fallback = LLMResponse(
            content="done",
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )
        self.call_count = 0

    def chat(self, **kwargs: Any):
        self.call_count += 1
        if self._script:
            return self._script.pop(0)
        return self._fallback


def make_tool_call_response(tool_name: str, args: dict, call_id: str = "c1"):
    """Build a LLMResponse with a single tool call.  Test helper."""
    from agent.core.llm_providers import LLMResponse, ToolCallPayload

    return LLMResponse(
        content="",
        tool_calls=[
            ToolCallPayload(
                id=call_id,
                name=tool_name,
                arguments=json.dumps(args),
            )
        ],
        usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    )


def make_text_response(text: str = "done"):
    from agent.core.llm_providers import LLMResponse

    return LLMResponse(
        content=text,
        usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    )
