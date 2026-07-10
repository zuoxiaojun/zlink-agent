# ZLink Agent Test Suite

pytest tests, ~0.5s total runtime. **No LLM, no network, no YonSuite
API.**  Every test runs against the real code with a `MockLLMProvider`
or a `FastAPI TestClient` plus a tmp-dir-isolated config.

## Run

```bash
.venv/bin/python -m pytest tests/ -v
```

Or just the file you touched:

```bash
.venv/bin/python -m pytest tests/test_extensions.py -v
```

## What's covered

| File | Cases | What it locks down |
|---|---|---|
| `conftest.py` | — | `clean_extensions` autouse fixture (event-bus isolation); `isolated_config` fixture (config redirected to tmp_path); `MockLLMProvider` factory |
| `test_extensions.py` | 8 | 8 event types' field contract; Extension register/disable; `apply_config_overrides` toggle on/off both directions; idempotency; `BeforeToolCallEvent.cancel` contract |
| `test_agent_loop.py` | 5 | `AIAgent.run_conversation`: no-API-key early return, plain text reply, one-tool-call flow, full event sequence, event-layer security block |
| `test_tool_registry.py` | 5 | ToolRegistry dispatch + `__block__` protocol; before-hook arg rewriting; after-hook result rewriting; unknown-tool error path |
| `test_config_manager.py` | 5 | load/save round-trip; `disabled_extensions` (M5+) persistence; default-on-missing; corrupt-file fallback; unknown-key filtering |
| `test_compactor.py` | 5 | token estimation; CJK-aware message tokens; Pi-style file tracking; `SessionBeforeCompactEvent` publish; extension appends to `extra` and final summary folds it in |
| `test_api_extensions.py` | 7 | GET list / active; PUT toggle (disable + re-enable); unknown → 404; POST reload; `/api/health` smoke |

## Design constraints

* **No new dependencies.**  pytest 9.0.3 was already installed; we
  did not add `pytest-asyncio` / `pytest-cov` / `httpx` (httpx is a
  FastAPI transitive dep, not a test dep).
* **No real LLM calls.**  `MockLLMProvider` returns scripted
  `LLMResponse` objects.  Tests run offline.
* **No real YonSuite / MCP server.**  The `client` fixture spins up
  the FastAPI app in-process; the MCP-on-startup hook may attempt
  to connect to a non-existent stdio server and log a warning —
  this is harmless and the test still passes.
* **Real `data/config.json` is never written.**  The
  `isolated_config` fixture redirects `agent.config_manager`'s
  `load`/`save` to a per-test tmp file.
* **Test isolation.**  The `clean_extensions` autouse fixture calls
  `shutdown_all_extensions()` after every test, wiping the global
  `_all_extensions` / `_active_runners` lists.  The `client` fixture
  re-registers the 2 built-in extensions after the wipe.

## Why this set

The 36 cases concentrate on the M1–M5+ refactor surface: any
regression in the event bus, the hook chain, the agent loop, or
the M5+ toggle path will be caught immediately.  Coverage is
intentionally low (probably ~15% of LOC) — the goal is "fail fast
on the parts most likely to break when adding new features", not
"hit 80%".  Extend as the codebase grows.
