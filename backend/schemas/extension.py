from pydantic import BaseModel


class ExtensionInfo(BaseModel):
    """One extension as the M5+ settings page sees it."""

    name: str
    enabled: bool
    # What kind of work it does.  Surfaced in the UI for the user to
    # understand what toggling does.
    description: str = ""
    # ``"log"`` for observation-only; ``"policy"`` for cancel/blocking;
    # ``"transform"`` for mutating events; ``"other"`` if unknown.
    kind: str = "other"


class ExtensionToggle(BaseModel):
    enabled: bool


class ExtensionReloadResult(BaseModel):
    """Returned by ``POST /api/extensions/reload``."""

    now_active: list[str] = []
    now_disabled: list[str] = []
