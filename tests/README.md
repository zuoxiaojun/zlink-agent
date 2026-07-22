# ZLink Agent Test Suite

pytest tests, ~5s total runtime. **No LLM, no network, no YonSuite API.** Every test runs against the real code with a `MockLLMProvider` or a `FastAPI TestClient` plus a tmp-dir-isolated config.

## Run

```bash
.venv/bin/python -m pytest tests/ -v
```

Or just the file you touched:

```bash
.venv/bin/python -m pytest tests/test_extensions.py -v
```

## What's covered

387 tests across 31 files, concentrated on the M1–M7 refactor surface:

| Area | Files | What it locks down |
|---|---|---|
| Agent loop & phase machine | `test_agent_loop.py` | `AIAgent.run_conversation`, phase transitions, event sequence, reentrancy, config isolation |
| Tools & registry | `test_tool_registry.py`, `test_approval.py`, `test_file_tools.py`, `test_process_tool.py`, `test_project_tools.py`, `test_vision_tool.py`, `test_web_tools.py`, `test_web_extract_tool.py`, `test_session_search_tool.py` | Tool dispatch, hooks, risk-level approval, file safety, delegation, process/project/vision/web tools |
| Config & ERP | `test_config_manager.py`, `test_config_api.py`, `test_config_manager_erp.py`, `test_erp_clients_base.py`, `test_erp_clients_api.py` | Config load/save, ERP client registry, API endpoints, permission handling |
| Extensions & events | `test_extensions.py`, `test_api_extensions.py` | Event types, Extension register/disable, `apply_config_overrides`, toggle API |
| Context & memory | `test_compactor.py`, `test_memory_tool.py`, `test_message_builder.py` | Token estimation, file tracking, compaction events, memory tool, message building |
| MCP | `test_mcp_manager.py`, `test_mcp_management_tool.py`, `test_mcp_api.py` | MCP server lifecycle, agent-facing management tools, REST API |
| Skills | `test_skill_manager.py`, `test_skills_api.py` | Skill discovery, activation, install/export, REST API |
| Slash commands | `test_slash_commands.py` | Command parsing and dispatch |
| LLM providers | `test_openai_compat.py`, `test_deepseek_provider.py` | Provider adapters and response parsing |
| Chat / sessions | `test_chat.py`, `test_utils_data_dir.py` | WebSocket chat flow, data dir resolution |

## Design constraints

* **No new dependencies.** pytest 9.1.1 and pytest-cov are already in the dev extra; we did not add `pytest-asyncio` or `httpx` (httpx is a FastAPI transitive dep, not a test dep).
* **No real LLM calls.** `MockLLMProvider` returns scripted `LLMResponse` objects. Tests run offline.
* **No real YonSuite / MCP server.** The `client` fixture spins up the FastAPI app in-process; the MCP-on-startup hook may attempt to connect to a non-existent stdio server and log a warning — this is harmless and the test still passes.
* **Real `data/config.json` is never written.** The `isolated_config` fixture redirects `agent.config_manager`'s `load`/`save` to a per-test tmp file.
* **Test isolation.** The `clean_extensions` autouse fixture calls `shutdown_all_extensions()` after every test, wiping the global `_all_extensions` / `_active_runners` lists. The `client` fixture re-registers the built-in extensions after the wipe.
* **Cross-platform paths.** Path-safety tests use `tmp_path` fixtures and normalized path comparisons so they pass on Windows, macOS, and Linux.

## Why this set

The 387 cases concentrate on the refactor surface: any regression in the event bus, the hook chain, the agent loop, tool dispatch, config persistence, or the M5+ toggle path will be caught immediately. Coverage is intentionally focused on "fail fast on the parts most likely to break when adding new features", not on hitting a percentage. Extend as the codebase grows.
