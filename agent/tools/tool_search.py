"""Progressive tool disclosure ("tool search") for ZLink Agent.

When enabled, deferrable tools (ERP, MCP, cron, skills, project, etc.) are
replaced by three bridge tools — ``tool_search``, ``tool_describe``,
``tool_call`` — and surfaced on demand. Core tools (file, terminal, web,
memory, etc.) are never deferred.

Design
------
* Core toolsets are always loaded. Deferrable toolsets are hidden when
  schemas exceed a threshold percentage of the model's context window.
* BM25 retrieval over tool descriptions for search.
* Bridge tools route through the same registry dispatch as direct calls.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field

from agent.tools.registry import registry

logger = logging.getLogger(__name__)

# ── Bridge tool names ────────────────────────────────────────────────

TOOL_SEARCH_NAME = "tool_search"
TOOL_DESCRIBE_NAME = "tool_describe"
TOOL_CALL_NAME = "tool_call"
BRIDGE_TOOL_NAMES = frozenset({TOOL_SEARCH_NAME, TOOL_DESCRIBE_NAME, TOOL_CALL_NAME})

# ── Core toolsets (never deferred) ───────────────────────────────────

CORE_TOOLSETS = frozenset({
    "file", "terminal", "web", "clarify", "memory",
    "session_search", "todo", "code", "system", "vision", "agent",
})

# ── Token estimation ─────────────────────────────────────────────────

CHARS_PER_TOKEN = 4.0


def estimate_tokens_from_schemas(tool_defs: list[dict]) -> int:
    total_chars = 0
    for td in tool_defs:
        try:
            total_chars += len(json.dumps(td, ensure_ascii=False, separators=(",", ":")))
        except (TypeError, ValueError):
            total_chars += len(str(td))
    return int(math.ceil(total_chars / CHARS_PER_TOKEN))


# ── Classification ───────────────────────────────────────────────────

def is_deferrable_name(name: str) -> bool:
    """Return True if a tool is eligible for deferral."""
    if name in BRIDGE_TOOL_NAMES:
        return False
    return True  # all non-bridge tools are potentially deferrable


def classify_tools(tool_defs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split tool-defs into (visible, deferrable)."""
    visible: list[dict] = []
    deferrable: list[dict] = []
    for td in tool_defs:
        fn = td.get("function") or {}
        name = fn.get("name", "")
        if name in BRIDGE_TOOL_NAMES:
            continue
        if is_deferrable_name(name):
            deferrable.append(td)
        else:
            visible.append(td)
    return visible, deferrable


def classify_tool_defs_by_toolset(tool_defs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split tool-defs into (visible, deferrable) based on toolset membership.

    Uses the registry to look up each tool's toolset. Core toolsets are
    always visible; everything else is deferrable.
    """
    visible: list[dict] = []
    deferrable: list[dict] = []
    for td in tool_defs:
        fn = td.get("function") or {}
        name = fn.get("name", "")
        if name in BRIDGE_TOOL_NAMES:
            continue
        entry = registry.get_entry(name)
        toolset = entry.toolset if entry else ""
        if toolset in CORE_TOOLSETS:
            visible.append(td)
        else:
            deferrable.append(td)
    return visible, deferrable


# ── BM25 Catalog ─────────────────────────────────────────────────────

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass
class CatalogEntry:
    name: str
    description: str
    schema: dict
    _tokens: list[str] = field(default_factory=list)


def build_catalog(tool_defs: list[dict]) -> list[CatalogEntry]:
    catalog: list[CatalogEntry] = []
    for td in tool_defs:
        fn = td.get("function") or {}
        name = fn.get("name", "")
        if not name:
            continue
        desc = fn.get("description", "") or ""
        _search_text = f"{name.replace('_', ' ')} {desc}"
        entry = CatalogEntry(
            name=name,
            description=desc,
            schema=td,
            _tokens=_tokenize(_search_text),
        )
        catalog.append(entry)
    return catalog


def search_catalog(catalog: list[CatalogEntry], query: str, limit: int = 5) -> list[CatalogEntry]:
    if not catalog or limit <= 0:
        return []
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    doc_lengths = [len(e._tokens) for e in catalog]
    avg_dl = sum(doc_lengths) / max(len(doc_lengths), 1)
    doc_freq: dict[str, int] = {}
    for e in catalog:
        for t in set(e._tokens):
            doc_freq[t] = doc_freq.get(t, 0) + 1
    n_docs = len(catalog)

    scored: list[tuple[float, CatalogEntry]] = []
    for entry in catalog:
        s = _bm25_score(query_tokens, entry._tokens, doc_lengths, avg_dl, doc_freq, n_docs)
        if s > 0:
            scored.append((s, entry))

    if not scored:
        ql = query.lower()
        for entry in catalog:
            if ql in entry.name.lower():
                scored.append((0.1, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:limit]]


def _bm25_score(
    query_tokens: list[str], doc_tokens: list[str],
    doc_lengths: list[int], avg_dl: float,
    doc_freq: dict[str, int], n_docs: int,
    k1: float = 1.5, b: float = 0.75,
) -> float:
    if not doc_tokens:
        return 0.0
    score = 0.0
    dl = len(doc_tokens)
    doc_tf: dict[str, int] = {}
    for t in doc_tokens:
        doc_tf[t] = doc_tf.get(t, 0) + 1
    for q in query_tokens:
        df = doc_freq.get(q, 0)
        if df == 0:
            continue
        idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
        tf = doc_tf.get(q, 0)
        if tf == 0:
            continue
        norm = tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / max(avg_dl, 1.0)))
        score += idf * norm
    return score


# ── Bridge tool schemas ──────────────────────────────────────────────

def bridge_tool_schemas(deferred_count: int) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": TOOL_SEARCH_NAME,
                "description": (
                    f"Search {deferred_count} additional tools that are loaded on demand. "
                    "Returns up to ``limit`` matches with name and description. Follow "
                    f"with `{TOOL_DESCRIBE_NAME}` to load a tool's full schema, then "
                    f"`{TOOL_CALL_NAME}` to invoke it."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Keywords describing the capability you need (e.g. 'query orders').",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results. Default 5, max 20.",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": TOOL_DESCRIBE_NAME,
                "description": (
                    f"Load the full JSON schema for one tool returned by `{TOOL_SEARCH_NAME}`. "
                    f"Required before `{TOOL_CALL_NAME}` if parameters are unknown."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Exact tool name (as returned by tool_search).",
                        },
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": TOOL_CALL_NAME,
                "description": (
                    "Invoke a deferred tool by name with the given arguments. "
                    "Argument shape matches the tool's schema (see tool_describe)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Exact tool name to invoke.",
                        },
                        "arguments": {
                            "type": "object",
                            "description": "Arguments for the tool, matching its schema.",
                        },
                    },
                    "required": ["name", "arguments"],
                },
            },
        },
    ]


# ── Assembly ─────────────────────────────────────────────────────────

@dataclass
class AssemblyResult:
    tool_defs: list[dict]
    activated: bool
    deferred_count: int = 0
    deferred_tokens: int = 0
    threshold_tokens: int = 0


def assemble_tool_defs(
    tool_defs: list[dict],
    *,
    context_length: int | None = None,
    threshold_pct: float = 10.0,
    force_off: bool = False,
) -> AssemblyResult:
    """Apply progressive tool disclosure.

    When the deferrable tool schemas would consume more than
    ``threshold_pct`` of the context window, they are replaced by
    the three bridge tools. Set ``force_off=True`` to skip.
    """
    if force_off:
        return AssemblyResult(tool_defs=tool_defs, activated=False)

    incoming = [td for td in tool_defs
                if (td.get("function") or {}).get("name") not in BRIDGE_TOOL_NAMES]

    visible, deferrable = classify_tool_defs_by_toolset(incoming)
    if not deferrable:
        return AssemblyResult(tool_defs=incoming, activated=False)

    deferrable_tokens = estimate_tokens_from_schemas(deferrable)

    if not context_length or context_length <= 0:
        should_activate = deferrable_tokens >= 20_000
    else:
        threshold_tokens = int(context_length * (threshold_pct / 100.0))
        should_activate = deferrable_tokens >= threshold_tokens

    if not should_activate:
        threshold_tokens = int((context_length or 0) * (threshold_pct / 100.0))
        return AssemblyResult(
            tool_defs=incoming, activated=False,
            deferred_count=len(deferrable), deferred_tokens=deferrable_tokens,
            threshold_tokens=threshold_tokens,
        )

    bridge = bridge_tool_schemas(len(deferrable))
    result = visible + bridge
    threshold_tokens = int((context_length or 0) * (threshold_pct / 100.0))

    logger.info(
        "tool_search activated: %d core tools kept, %d deferred (~%d tokens, threshold ~%d)",
        len(visible), len(deferrable), deferrable_tokens, threshold_tokens,
    )

    return AssemblyResult(
        tool_defs=result, activated=True,
        deferred_count=len(deferrable), deferred_tokens=deferrable_tokens,
        threshold_tokens=threshold_tokens,
    )


# ── Bridge tool dispatch ─────────────────────────────────────────────

def dispatch_tool_search(args: dict, *, current_tool_defs: list[dict]) -> str:
    query = str(args.get("query") or "").strip()
    if not query:
        return json.dumps({"error": "query is required"}, ensure_ascii=False)

    limit = max(1, min(20, int(args.get("limit", 5))))

    _, deferrable = classify_tool_defs_by_toolset(current_tool_defs)
    catalog = build_catalog(deferrable)
    hits = search_catalog(catalog, query, limit=limit)
    return json.dumps({
        "query": query,
        "total_available": len(catalog),
        "matches": [{"name": h.name, "description": (h.description or "")[:400]} for h in hits],
    }, ensure_ascii=False)


def dispatch_tool_describe(args: dict, *, current_tool_defs: list[dict]) -> str:
    name = str(args.get("name") or "").strip()
    if not name:
        return json.dumps({"error": "name is required"}, ensure_ascii=False)

    _, deferrable = classify_tool_defs_by_toolset(current_tool_defs)
    for td in deferrable:
        fn = td.get("function") or {}
        if fn.get("name") == name:
            return json.dumps({
                "name": name,
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {}),
            }, ensure_ascii=False)
    return json.dumps({
        "error": f"'{name}' is not currently available. Re-run tool_search to refresh.",
    }, ensure_ascii=False)


def dispatch_tool_call(args: dict) -> str:
    """Execute a deferred tool by name. Dispatches through the registry."""
    name = str(args.get("name") or "").strip()
    if not name:
        return json.dumps({"error": "tool_call requires a 'name' argument"}, ensure_ascii=False)
    if name in BRIDGE_TOOL_NAMES:
        return json.dumps({"error": f"tool_call cannot invoke '{name}' (bridge tool)"}, ensure_ascii=False)

    raw_args = args.get("arguments", {})
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"arguments is not valid JSON: {e}"}, ensure_ascii=False)
    if not isinstance(raw_args, dict):
        return json.dumps({"error": "arguments must be an object"}, ensure_ascii=False)

    return registry.dispatch(name, raw_args)


__all__ = [
    "TOOL_SEARCH_NAME", "TOOL_DESCRIBE_NAME", "TOOL_CALL_NAME",
    "BRIDGE_TOOL_NAMES",
    "assemble_tool_defs", "classify_tool_defs_by_toolset",
    "dispatch_tool_search", "dispatch_tool_describe", "dispatch_tool_call",
    "build_catalog", "search_catalog",
]
