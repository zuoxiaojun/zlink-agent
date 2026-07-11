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

### 1.3 Module Dependency Diagram

The diagram below shows the calling chain. **Bold** names are hub nodes (changing them affects many consumers). *(italic)* names are leaf nodes (safer to modify independently).

```
                                 ┌──────────────────────────┐
                                 │    frontend (React/Vite)  │
                                 │    port 8088             │
                                 └──────┬───────────────────┘
                                        │ WebSocket /api/chat
                                        ▼
                              ┌──────────────────────┐
                              │  backend/api/chat.py  │
                              │  (WebSocket endpoint) │
                              └──────┬───────────────┘
                                     │ run_in_executor
                                     ▼
╔══════════════════════════════════════════════════════════════╗
║                    *AIAgent.run_conversation()*              ║
║  agent/core/agent.py — Phase Machine (idle/turn/compact/   ║
║  retry), TurnSnapshot, EventBus publishing                  ║
╚═══════╤════════════════════════════════════════════╤════════╝
        │   1st call (pre-turn)                      │ tool calls
        ▼                                            ▼
┌─────────────────────────┐             ┌──────────────────────┐
│  *message_builder.py*   │             │ *tool_dispatcher.py* │
│  build_system_prompt()  │             │ dispatch_tool()      │
│  build_turn_messages()  │             └─────────┬────────────┘
└────────────┬────────────┘                       │
             │  reads                             ▼
             ▼                         ┌──────────────────────┐
┌─────────────────────────┐            │  *ToolRegistry*      │
│  *LLMClient.chat()*     │            │  registry.py         │
│  agent/core/llm_client  │            │  dispatch()          │
└────────────┬────────────┘            └─────────┬────────────┘
             │  delegates to                      │  routes to
             ▼                                    ▼
┌─────────────────────────┐            ┌──────────────────────┐
│ *LLMProvider.chat()*    │            │ Tool handler (e.g.   │
│ base.py / openai_compat │            │ terminal_tool.py)   │
│ / anthropic.py          │            │ OR                   │
└─────────────────────────┘            │ *mcp_manager.py*     │
                                       │ → MCP server process │
                                       └──────────────────────┘

        ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
        EventBus (agent/events/bus.py) — published events:
        SessionStart → UserMessage → BeforeLLMCall →
        AfterLLMCall → BeforeToolCall → AfterToolCall →
        SessionEnd  (+ PhaseChange, SessionBeforeCompact)
        ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
                              │
                              ▼
                    ┌─────────────────────────┐
                    │  *skill_manager.py*     │
                    │  get_active_instructions│
                    │  get_instructions_for_  │
                    │    _query()→ n-gram     │
                    │  match→ Level 1 inject  │
                    └─────────────────────────┘
                              │
                              ▼
                    ┌─────────────────────────┐
                    │  *config_manager.py*    │
                    │  load() → AppConfig     │
                    │  save()                 │
                    │  encrypt/decrypt_secret │
                    └─────────────────────────┘
```

**Hub nodes (change with care):**
- `agent/core/agent.py` — AIAgent, called by chat.py, depends on every other core module
- `agent/tools/registry.py` — all tool modules register here; dispatch central
- `agent/tools/mcp_manager.py` — MCP server lifecycle; config_manager reads server list
- `backend/api/chat.py` — WebSocket entry point; bridges sync agent into async FastAPI
- `agent/config_model.py` — AppConfig schema changes affect config_manager + all consumers

**Leaf nodes (safer to modify independently):**
- `agent/core/iteration_budget.py` — standalone counter
- `agent/tools/todo_tool.py` / `clarify_tool.py` — single-purpose tools
- `agent/search_index.py` — SQLite FTS5, no runtime deps on other modules
- `backend/schemas/*.py` — Pydantic models, pure data definitions
- `mcp_server/nc_mcp/config.py` — env var conversion, pure function

### 1.4 Core Data Flows

#### Flow A: Chat (WebSocket → AIAgent → LLM → response)

```
frontend WS ──► chat.py (receive JSON)
                  │
                  ├──► parse slash command? → execute() → response
                  │
                  └──► AIAgent.run_conversation(message, stream_cb)
                          │
                          ├──► build_turn_messages()  [message_builder.py]
                          ├──► _take_snapshot()        [freezes model/temp/tools]
                          ├──► SessionStartEvent       [event_bus.publish]
                          ├──► _maybe_compact()         [context_compactor.py]
                          │
                          ├──► _call_llm()
                          │       └──► LLMClient.chat()
                          │               └──► LLMProvider.chat() [openai_compat / anthropic]
                          │
                          ├──► [if tool_calls] _run_tool_calls()
                          │       ├──► dispatch_tool() → registry.dispatch()
                          │       │       └──► tool handler OR mcp_manager.call_tool()
                          │       └──► append tool results to messages
                          │       └──► loop back to _call_llm()
                          │
                          └──► SessionEndEvent → return {final_response, messages, ...}
```

Key files: `backend/api/chat.py`, `agent/core/agent.py`, `agent/core/llm_client.py`, `agent/core/llm_providers/`, `agent/core/message_builder.py`, `agent/core/tool_dispatcher.py`, `agent/tools/registry.py`

#### Flow B: MCP Tool Execution

```
AIAgent._run_tool_calls()
  └──► dispatch_tool(name, args)
        └──► registry.dispatch(name, args)
              └──► [if MCP tool] mcp_manager.call_tool(server_name, tool_name, args)
                    ├──► JSON-RPC request {jsonrpc:"2.0", id, method:"tools/call", params}
                    ├──► stdio: write to subprocess stdin → read stdout
                    │         (asyncio.create_subprocess_exec)
                    └──► HTTP: POST to server URL → parse JSON-RPC response
                          (httpx, timeout from MCPServerEntry.timeout)
```

Key files: `agent/tools/mcp_manager.py`, `agent/tools/registry.py`, `agent/config_model.py` (MCPServerEntry)

**Circuit breaker:** 3 consecutive failures → 60s cooldown.

#### Flow C: ERP Configuration Save → MCP Server Sync

```
SettingsERPPage (React) ──PUT /api/config/erp-clients/{name}──► erp_clients_api.py
  │
  ├──► decrypt incoming secret fields, merge config
  ├──► write raw dict to config.json (agent.config_manager.CONFIG_FILE)
  │
  └──► [if name=="nc"] mcp_starter.sync_nc_mcp()
        ├──► reads nc config from config_manager
        ├──► build_nc_mcp_env() → env dict
        └──► connect_server("mcp-nc", command, args, env)
              └──► mcp_manager.connect_server() → list tools → register to registry
```

Key files: `backend/api/erp_clients_api.py`, `agent/config_manager.py`, `mcp_server/nc_mcp/mcp_starter.py`, `mcp_server/nc_mcp/config.py`

#### Flow D: Skill Injection into System Prompt

```
User input arrives
  │
  ├──► skill_manager.get_active_instructions()
  │     → reads active_skills.json
  │     → returns name+description list (Level 0 — injected into system prompt)
  │
  └──► skill_manager.get_instructions_for_query(user_message)
        → n-gram matches skill name/description/tags
        → returns full SKILL.md content for matched skills (Level 1 — loaded on-demand)
              │
              ▼
        build_system_prompt(base, skill_index=..., skill_detail=...)
              │
              ▼
        system prompt → LLM sees active skills + matched skill instructions
```

Key files: `agent/skill_manager.py`, `agent/core/message_builder.py`, `agent/tools/skills_tool.py`

<!-- NEXT: SECTION_1_5 -->
