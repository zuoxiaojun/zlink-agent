"""Backwards-compatible re-export.

M1 refactor moved :class:`AIAgent` to :mod:`agent.core.agent`.  This
module keeps the old import path working so ``backend/api/chat.py`` and
any external scripts do not need to change.

M5+ addition: importing this module also triggers registration of
ZLink Agent's built-in :mod:`agent.events` extensions (log + security).
Doing it here means any entry point that imports ``AIAgent`` from
``agent.agent`` will end up with the extensions wired up — whether
the entry point is ``backend/api/chat.py`` or a stand-alone script.
"""

from agent.core.agent import AIAgent
from agent.extensions import register_built_in_extensions

# M5+: wire built-in extensions at import time.  ``register_built_in_extensions``
# is idempotent and tracks instances globally, so this is safe to call
# from any process that imports ``agent.agent``.
try:
    register_built_in_extensions()
except Exception:  # pragma: no cover
    # If extensions can't be loaded (e.g. an import error in a
    # built-in), don't break the entire agent import.  Logged
    # inside ``register_built_in_extensions`` already.
    pass

# Re-apply the persisted disabled-extensions list so the M5+ settings
# page's choices take effect on startup.  Done after registration so
# the registry knows about every built-in.
try:
    from agent import config_manager
    from agent.events.extensions import apply_config_overrides

    cfg = config_manager.load()
    if cfg.disabled_extensions:
        apply_config_overrides(cfg.disabled_extensions)
except Exception:  # pragma: no cover
    pass

__all__ = ["AIAgent"]
