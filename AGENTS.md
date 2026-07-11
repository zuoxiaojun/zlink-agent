# ZLink Agent (智链 Agent)

> **AI Agent Technical Reference + Human Developer Guide**
> This document has two parts. Part 1 is for AI agents making code changes. Part 2 is for human developers setting up, configuring, and extending the project.

---

## Part 1: AI Agent Technical Reference

### 1.1 Project Overview

ZLink Agent (智链 Agent) is an intelligent AI assistant with multi-ERP (YonSuite / NC / extensible) data retrieval, analysis, automation, built-in MCP server management, a skill system, and long-term memory.

**Tech stack:** Python 3.11+ / FastAPI / React + Vite / MCP JSON-RPC / SQLite (FTS5) / pytest / ruff

**Test status:** 65 tests, ~0.5s, zero network/LLM dependencies. Run: `.venv/bin/python -m pytest tests/ -v`

### 1.2 Directory Structure & File Responsibilities

```
zlink-agent/
├── AGENTS.md                   # ⚠️  This file — AI reference + dev guide
├── CONTRIBUTING.md             # ✅  Contributing guidelines (PR flow, code style)
├── README.md                   # ✅  Project README (public-facing)
├── VERSION                     # ✅  Version number (sync w/ pyproject.toml)
├── CHANGELOG.md                # ✅  Release changelog
├── pyproject.toml              # ⚠️  Python project config (version, deps, ruff)
├── start.sh                    # ⚠️  Production/dev server launcher
│
├── backend/                    # FastAPI backend (port 8089)
│   ├── main.py                 # ⚠️  FastAPI app, CORS, lifespan, router mounts
│   ├── config.py               # ✅  CORS origins and other constants
│   ├── llm_providers.py        # ⚠️  9 provider definitions (base_url, models, protocol)
│   ├── api/
│   │   ├── chat.py             # ⚠️  WebSocket /api/chat endpoint (389 lines)
│   │   ├── config_api.py       # ✅  /api/config read/write
│   │   ├── erp_clients_api.py  # ⚠️  ERP client config CRUD (+ MCP toggle)
│   │   ├── mcp_api.py          # ✅  /api/mcp server management
│   │   ├── skills_api.py       # ✅  /api/skills CRUD (with builtin protection)
│   │   ├── tools_api.py        # ✅  /api/tools list
│   │   ├── memory_api.py       # ✅  /api/memory
│   │   ├── metrics_api.py      # ✅  /api/metrics
│   │   ├── sessions.py         # ✅  Session list/delete
│   │   ├── extensions_api.py   # ✅  Extension toggle
│   │   └── system_api.py       # ✅  System info endpoints
│   └── schemas/                # ✅  Pydantic models (config.py, chat.py, mcp.py, ...)
│
├── agent/                      # Core logic (non-FastAPI, reusable)
│   ├── core/
│   │   ├── agent.py            # ⚠️  AIAgent class — M7 agent loop (719 lines)
│   │   ├── llm_client.py       # ⚠️  LLMClient shim → delegates to LLMProvider
│   │   ├── llm_providers/      # ⚠️  Provider abstraction
│   │   │   ├── base.py         #     LLMProvider ABC, LLMResponse, ToolCallPayload
│   │   │   ├── openai_compat.py#     OpenAI-compat via httpx (preserves reasoning_content)
│   │   │   ├── anthropic.py    #     Anthropic adapter
│   │   │   └── factory.py      #     get_provider() factory
│   │   ├── message_builder.py  # ✅  build_system_prompt(), build_turn_messages()
│   │   ├── tool_dispatcher.py  # ✅  dispatch_tool() — registry dispatch + truncation
│   │   ├── iteration_budget.py # ✅  IterationBudget — turn counting
│   │   └── metrics.py          # ✅  Token counting helpers
│   ├── tools/                  # 14 files, 27+ tools
│   │   ├── registry.py         # ❌  ToolRegistry singleton — modify only via register()
│   │   ├── mcp_manager.py      # ⚠️  MCP server connections, circuit breaker, JSON-RPC
│   │   ├── security_hooks.py   # ❌  Three-layer security (system prompt → hook → event)
│   │   ├── terminal_tool.py    # ✅  terminal tool
│   │   ├── file_tools.py       # ✅  read/write/patch/search/ls
│   │   ├── web_tools.py        # ✅  web_search
│   │   ├── web_extract_tool.py # ✅  web_extract
│   │   ├── skills_tool.py      # ⚠️  Skill lifecycle tools (list/view/activate/deactivate/install/export)
│   │   ├── todo_tool.py        # ✅  todo tool
│   │   ├── clarify_tool.py     # ✅  clarify tool
│   │   ├── memory_tool.py      # ✅  memory tool (fact memory read/write)
│   │   ├── session_search_tool.py # ✅  session_search tool
│   │   └── file_mutation_queue.py# ✅  File mutation queue helper
│   ├── events/                 # ⚠️  EventBus + 8 typed event types
│   │   ├── bus.py              #     EventBus (sync, thread-safe), event_bus singleton
│   │   ├── types.py            #     8 event classes (SessionStart, BeforeLLMCall, ...)
│   │   └── extensions.py       #     Extension base class + runner + lifecycle
│   ├── extensions/             # ⚠️  Built-in extensions (modify to add new ones)
│   │   ├── log_everything.py   #     Logging extension
│   │   ├── security_event.py   #     Security event extension
│   │   └── monitoring.py       #     Monitoring/metrics extension
│   ├── config_manager.py       # ⚠️  load()/save()/encrypt_secret()/decrypt_secret()
│   ├── config_model.py         # ⚠️  Pydantic AppConfig, MCPServerEntry, encrypt/decrypt
│   ├── context_compactor.py    # ⚠️  M6 three-level compaction (truncate → LLM summary → drop)
│   ├── skill_manager.py        # ⚠️  Skill CRUD, activation, prompt injection
│   ├── session_manager.py      # ✅  Session persistence (data/sessions/)
│   ├── search_index.py         # ✅  SQLite+FTS5 session search
│   ├── memory_manager.py       # ✅  Conversation summary memory (data/memory/)
│   ├── fact_memory.py          # ✅  Autonomous memory (notes + user profile)
│   ├── slash_commands.py       # ✅  /help /model /compact /clear /login /cost
│   ├── utils.py                # ✅  DATA_DIR, atomic_json_write, _resolve_data_dir
│   └── skills/                 # ❌  Built-in skills (read-only, not editable/deletable)
├── mcp_server/
│   ├── ys_mcp_server.py        # ✅  YonSuite MCP stdio server entry point
│   ├── ys_mcp_server/          # ✅  YonSuite MCP handlers (11 tools)
│   └── nc_mcp/                 # ✅  NC MCP
│       ├── mcp_starter.py      #     sync_nc_mcp() — dynamic registration on config save
│       └── config.py           #     build_nc_mcp_env() — env var conversion
├── web/                        # React + Vite frontend (port 8088)
│   ├── src/
│   │   ├── App.tsx             # ⚠️  React Router (10 routes)
│   │   ├── pages/              # ✅  10 page components
│   │   ├── api/                # ✅  API client layer
│   │   ├── components/         # ✅  Reusable UI components
│   │   ├── styles/             # ✅  CSS
│   │   └── hooks/              # ✅  Custom hooks
│   └── vite.config.ts          # ⚠️  Proxy /api + /ws to backend:8089
├── tests/                      # 12 test files, 65 tests
│   ├── conftest.py             #     clean_extensions, isolated_config, MockLLMProvider
│   ├── test_agent_loop.py      #     5 tests — AIAgent.run_conversation() paths
│   ├── test_tool_registry.py   #     5 tests — ToolRegistry dispatch + hooks
│   ├── test_extensions.py      #     8 tests — Event types + Extension lifecycle
│   ├── test_compactor.py       #     5 tests — Context compaction
│   ├── test_config_manager.py  #     5 tests — Config load/save round-trip
│   └── ...                     #     (6 more files)
├── scripts/
│   ├── build-app.sh            # ⚠️  macOS .app build
│   ├── zlink.sh                # ✅  zlink CLI wrapper
│   └── migrate.py              # ✅  Data migration helper
└── data/                       # Runtime data (~/.zlink-agent/data/)
    ├── config.json             #     LLM/ERP/MCP config (fernet-encrypted secrets)
    ├── active_skills.json      #     Active skill names list
    ├── skills/                 #     User-installed skills
    ├── sessions/               #     Conversation sessions
    ├── memory/                 #     Conversation summaries
    ├── logs/                   #     Runtime logs
    └── backups/                #     Data backups
```

**Legend:** ✅ = safe to modify | ⚠️ = modify with caution (has dependencies) | ❌ = do not modify (builtin protection / external contract)

<!-- NEXT: SECTION_1_3 -->
