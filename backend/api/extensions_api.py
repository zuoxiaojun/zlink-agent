"""Extension management REST API — M5+.

Surfaces the M2 :mod:`agent.events` extension system to the front-end
so the user can enable / disable each extension without restarting
the server or editing Python source.

Endpoints
---------
* ``GET  /api/extensions``               — list every registered extension
* ``GET  /api/extensions/active``        — list only enabled ones
* ``PUT  /api/extensions/{name}/toggle`` — enable or disable by name
* ``POST /api/extensions/reload``        — re-apply persisted config
                                           (mostly useful after a manual
                                           ``config.json`` edit)

State is persisted in ``config.json`` under ``disabled_extensions``.
On FastAPI startup, ``agent/agent.py`` reads this list and applies it
via :func:`agent.events.extensions.apply_config_overrides`.

Design notes
------------
* The matching is by ``Extension.name`` (a class attribute), not by
  Python class identity.  This means a hot-reload of the agent process
  (which re-instantiates the classes) still finds the right ones.
* The endpoint only ever toggles — it never instantiates new
  extensions.  New extensions are added by editing
  ``agent/extensions/__init__.py`` and restarting.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from agent import config_manager
from agent.events.extensions import (
    apply_config_overrides,
    list_active_extensions,
    list_all_extensions,
)
from backend.schemas.extension import (
    ExtensionInfo,
    ExtensionReloadResult,
    ExtensionToggle,
)

router = APIRouter(prefix="/api/extensions", tags=["extensions"])


# Map extension name → human-readable description + kind for the UI.
# Anything not listed here falls back to "other" and an empty
# description.  Keeping this registry in code (not in the
# extension class) lets us describe third-party / future extensions
# without modifying the extension's own source.
_KIND_BY_NAME: dict[str, tuple[str, str]] = {
    "log-everything": (
        "把所有事件写到 ys-agent.events logger（DEBUG 级别）。用来追踪事件流，调试时打开。",
        "log",
    ),
    "security-event": (
        "在事件层阻断危险操作（写入受保护路径 / 危险 shell 命令）。和 tools/security_hooks 并行工作。",
        "policy",
    ),
}


def _info_for(ext) -> ExtensionInfo:
    name = ext.name
    desc, kind = _KIND_BY_NAME.get(name, ("", "other"))
    return ExtensionInfo(
        name=name,
        enabled=ext.enabled,
        description=desc,
        kind=kind,
    )


@router.get("", response_model=list[ExtensionInfo])
def list_extensions() -> list[ExtensionInfo]:
    """Every registered extension, active or disabled."""
    return [_info_for(e) for e in list_all_extensions()]


@router.get("/active", response_model=list[ExtensionInfo])
def list_active() -> list[ExtensionInfo]:
    """Only the currently subscribed extensions."""
    return [_info_for(e) for e in list_active_extensions()]


@router.put("/{name}/toggle", response_model=ExtensionInfo)
def toggle_extension(name: str, body: ExtensionToggle) -> ExtensionInfo:
    """Enable or disable the extension with the given *name*.

    Persists the new state to ``config.json`` and applies it to the
    live event bus.  Returns the new state so the UI doesn't need
    to re-fetch.
    """
    target = next((e for e in list_all_extensions() if e.name == name), None)
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Extension {name!r} not found. Known: {[e.name for e in list_all_extensions()]}",
        )

    # Read current persisted list, update it, save, then apply.
    cfg = config_manager.load()
    disabled: list[str] = list(cfg.get("disabled_extensions", []))

    if body.enabled:
        # Enable: remove from disabled list
        disabled = [n for n in disabled if n != name]
    else:
        # Disable: add to disabled list (idempotent)
        if name not in disabled:
            disabled.append(name)

    cfg["disabled_extensions"] = disabled
    config_manager.save(cfg)

    apply_config_overrides(disabled)

    # Re-find the (possibly newly-enabled) instance to return.
    after = next(e for e in list_all_extensions() if e.name == name)
    return _info_for(after)


@router.post("/reload", response_model=ExtensionReloadResult)
def reload_extensions() -> ExtensionReloadResult:
    """Re-apply the persisted ``disabled_extensions`` list.

    Useful after a manual ``config.json`` edit, or in tests.
    """
    cfg = config_manager.load()
    disabled: list[str] = list(cfg.get("disabled_extensions", []))
    now_active, now_disabled = apply_config_overrides(disabled)
    return ExtensionReloadResult(
        now_active=[e.name for e in now_active],
        now_disabled=[e.name for e in now_disabled],
    )
