"""Extension registry.

Bundle YS-Agent's built-in extensions and expose a single
:func:`register_built_in_extensions` entry point that
``agent/core/agent.py`` (or ``agent/agent.py``) calls at import time.

M5+ :class:`~backend.api.extensions_api.ExtensionsAPI` reads
``register_built_in_extensions``'s output via
:func:`agent.events.extensions.list_all_extensions` to populate the
"Extensions" settings page.

To add a new built-in extension:

1. Subclass :class:`agent.events.Extension` in a new module under
   ``agent/extensions/``.
2. Append the class to ``BUILT_IN_EXTENSIONS`` below.
3. The M5+ settings page picks it up automatically on next reload.

To disable by code (e.g. for a flaky extension), set ``enabled = False``
in the class definition.  End-users can also toggle from the UI; that
state is persisted to ``config_manager.disabled_extensions`` and applied
on the next call to
:func:`agent.events.extensions.apply_config_overrides`.
"""

from __future__ import annotations

import logging

from agent.events import Extension
from agent.events.extensions import ExtensionRunner, register_extensions

logger = logging.getLogger(__name__)


# Forward-imports of the actual classes.  Done lazily so that
# ``from agent.extensions import register_built_in_extensions`` doesn't
# require every built-in extension's dependencies at import time
# (e.g. log capture without the security extension's regex module).
def _built_in_classes() -> list[type[Extension]]:
    from agent.extensions.log_everything import LogEverythingExtension
    from agent.extensions.security_event import SecurityEventExtension

    return [LogEverythingExtension, SecurityEventExtension]


# Instantiate once at module import.  Each instance is then registered
# via :func:`register_extensions` so its handlers are wired to the bus.
_INSTANCES: list[Extension] = []


def _ensure_instances() -> list[Extension]:
    """Lazily build the singleton instance list."""
    global _INSTANCES
    if not _INSTANCES:
        for cls in _built_in_classes():
            _INSTANCES.append(cls())
    return _INSTANCES


def register_built_in_extensions() -> list[ExtensionRunner]:
    """Register every built-in extension with the global event bus.

    Safe to call multiple times — instances are cached and only
    subscribed to the bus once.
    """
    runners = register_extensions(_ensure_instances())
    logger.info("Built-in extensions registered: %d (%s)", len(runners), [r.extension.name for r in runners])
    return runners


__all__ = ["register_built_in_extensions"]
