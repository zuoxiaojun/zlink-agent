"""Plugin discovery and loading system.

YS-Agent's plugin system discovers extensions via two mechanisms:
1. **Entry points** — packages installed with ``[project.entry-points."ys-agent.extensions"]``
2. **Directory scan** — ``.py`` files in ``data/plugins/`` (for local development)

Every plugin must expose an ``extension_classes()`` function that returns
a list of :class:`~agent.events.extensions.Extension` subclasses.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_ENTRY_POINT_GROUP = "ys-agent.extensions"
_loaded_plugins: dict[str, list[type]] = {}


def discover_entry_point_plugins() -> dict[str, list[type]]:
    """Discover plugins registered via package entry points.

    Reads ``[project.entry-points."ys-agent.extensions"]`` from every
    installed package and calls ``extension_classes()`` on each entry.
    """
    plugins: dict[str, list[type]] = {}
    try:
        eps = importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP)
        for ep in eps:
            try:
                module = ep.load()
                classes = module.extension_classes() if hasattr(module, "extension_classes") else []
                if classes:
                    plugins[ep.name] = classes
                    logger.info("Plugin loaded via entry point: %s (%d extensions)", ep.name, len(classes))
            except Exception:
                logger.exception("Failed to load entry-point plugin: %s", ep.name)
    except Exception:
        logger.debug("No entry-point plugins discovered")
    _loaded_plugins.update(plugins)
    return plugins


def discover_directory_plugins(plugins_dir: str | Path) -> dict[str, list[type]]:
    """Scan a directory for ``.py`` files and import each as a plugin.

    Each file should define an ``extension_classes()`` function returning
    a list of :class:`~agent.events.extensions.Extension` subclasses.
    """
    plugins: dict[str, list[type]] = {}
    p = Path(plugins_dir)
    if not p.is_dir():
        return plugins

    for file in sorted(p.glob("*.py")):
        if file.name.startswith("_"):
            continue
        mod_name = f"_plugin_{file.stem}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, file)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            # Ensure the plugin can import from the project root
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
            classes = module.extension_classes() if hasattr(module, "extension_classes") else []
            if classes:
                plugins[file.stem] = classes
                logger.info("Plugin loaded from directory: %s (%d extensions)", file.name, len(classes))
        except Exception:
            logger.exception("Failed to load plugin from file: %s", file.name)
    _loaded_plugins.update(plugins)
    return plugins


def get_all_plugin_extensions() -> list[type]:
    """Return every :class:`Extension` subclass from every loaded plugin."""
    result: list[type] = []
    for classes in _loaded_plugins.values():
        result.extend(classes)
    return result


__all__ = [
    "discover_entry_point_plugins",
    "discover_directory_plugins",
    "get_all_plugin_extensions",
]
