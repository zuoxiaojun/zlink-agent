"""Extension registry.

Bundle ZLink Agent's built-in extensions and auto-discovered plugins,
then expose a single :func:`register_built_in_extensions` entry point.

Discovery
---------
1. Built-in extensions (hard-coded below).
2. Python entry-point plugins (``[project.entry-points."zlink-agent.extensions"]``).
3. Directory plugins from ``data/plugins/*.py``.
"""

from __future__ import annotations

import logging

from agent.events import Extension
from agent.events.extensions import ExtensionRunner, register_extensions
from agent.plugin_system import discover_directory_plugins, discover_entry_point_plugins, get_all_plugin_extensions

logger = logging.getLogger(__name__)


def _built_in_classes() -> list[type[Extension]]:
    from agent.extensions.log_everything import LogEverythingExtension
    from agent.extensions.monitoring import MonitoringExtension
    from agent.extensions.security_event import SecurityEventExtension

    return [LogEverythingExtension, MonitoringExtension, SecurityEventExtension]


_INSTANCES: list[Extension] = []


def _ensure_instances() -> list[Extension]:
    global _INSTANCES
    if not _INSTANCES:
        for cls in _built_in_classes():
            _INSTANCES.append(cls())
        discover_entry_point_plugins()
        try:
            from agent.config_manager import CONFIG_FILE

            plugins_dir = CONFIG_FILE.parent / "plugins"
            discover_directory_plugins(plugins_dir)
        except Exception:
            logger.debug("No directory plugins dir available")
        for cls in get_all_plugin_extensions():
            _INSTANCES.append(cls())
    return _INSTANCES


def register_built_in_extensions() -> list[ExtensionRunner]:
    runners = register_extensions(_ensure_instances())
    logger.info("Extensions registered: %d (%s)", len(runners), [r.extension.name for r in runners])
    return runners


__all__ = ["register_built_in_extensions"]
