# ZLink Agent (智链 Agent)

> **AI Agent Technical Reference + Human Developer Guide**
> This document has two parts. Part 1 is for AI agents making code changes. Part 2 is for human developers setting up, configuring, and extending the project.

---

## Part 1: AI Agent Technical Reference

### 1.1 Project Overview

ZLink Agent (智链 Agent) is an intelligent AI assistant with multi-ERP (YonSuite / NC / extensible) data retrieval, analysis, automation, built-in MCP server management, a skill system, and long-term memory.

**Tech stack:** Python 3.11+ / FastAPI / React + Vite / MCP JSON-RPC / SQLite (FTS5) / pytest / ruff

**Test status:** 99 tests, ~0.7s, zero network/LLM dependencies. Run: `.venv/bin/python -m pytest tests/ -v`

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
│   │   ├── chat.py             # ⚠️  WebSocket /api/chat endpoint (460 lines)
│   │   ├── config_api.py       # ✅  /api/config read/write
│   │   ├── erp_clients_api.py  # ⚠️  ERP client config CRUD (+ MCP toggle)
│   │   ├── mcp_api.py          # ✅  /api/mcp server management
│   │   ├── skills_api.py       # ✅  /api/skills CRUD (with builtin protection)
│   │   ├── tools_api.py        # ✅  /api/tools list
│   │   ├── slash_commands_api.py # ✅  /api/slash-commands list
│   │   ├── cronjob_api.py      # ✅  /api/cronjobs CRUD + run
│   │   ├── memory_api.py       # ✅  /api/memory
│   │   ├── metrics_api.py      # ✅  /api/metrics
│   │   ├── sessions.py         # ✅  Session list/delete
│   │   ├── extensions_api.py   # ✅  Extension toggle
│   │   └── system_api.py       # ✅  System info endpoints
│   └── schemas/                # ✅  Pydantic models (config.py, chat.py, mcp.py, slash_command.py)
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
│   │   └── iteration_budget.py # ✅  IterationBudget — turn counting
│   ├── tools/                  # 18 files, 41+ tools
│   │   ├── registry.py         # ❌  ToolRegistry singleton — modify only via register()
│   │   ├── mcp_manager.py      # ⚠️  MCP server connections, circuit breaker, JSON-RPC
│   │   ├── security_hooks.py   # ❌  Three-layer security (system prompt → hook → event)
│   │   ├── terminal_tool.py    # ✅  terminal + read_terminal + close_terminal
│   │   ├── file_tools.py       # ✅  read/write/patch/search/ls
│   │   ├── web_tools.py        # ✅  web_search
│   │   ├── web_extract_tool.py # ✅  web_extract
│   │   ├── browser_tool.py     # ✅  browser_navigate/click/fill/screenshot etc
│   │   ├── skills_tool.py      # ⚠️  Skill lifecycle tools (list/view/activate/deactivate/install/export)
│   │   ├── todo_tool.py        # ✅  todo tool
│   │   ├── clarify_tool.py     # ✅  clarify tool
│   │   ├── memory_tool.py      # ✅  memory tool (fact memory read/write)
│   │   ├── session_search_tool.py # ✅  session_search tool
│   │   ├── cronjob_tools.py    # ✅  Cron job management (list/create/delete/toggle/run/update)
│   │   ├── code_execution_tool.py # ✅  Sandboxed Python execution
│   │   ├── project_tools.py    # ✅  Project management (list/create/switch)
│   │   ├── vision_tool.py      # ✅  Image analysis via LLM vision
│   │   ├── process_tool.py     # ✅  Process management (list/kill)
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

### 1.5 Key Class / Method Signature Reference

#### AIAgent (`agent/core/agent.py:196`)

```python
class AIAgent:
    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        max_iterations: int = 30,
        max_tokens: int | None = None,
        max_tool_result_length: int = sys.maxsize,
        system_prompt: str | None = None,
        enabled_tools: list[str] | None = None,
        disabled_tools: set[str] | None = None,
        temperature: float = 0.7,
        progress_callback: Callable | None = None,
        compaction_settings: CompactionSettings | None = None,
        max_retries: int = 3,
        max_retry_delay: float = 30.0,
    )

    def run_conversation(
        self,
        user_message: str | list,
        system_message: str | None = None,
        conversation_history: list[dict] | None = None,
        stream_callback: Callable[[str], None] | None = None,
        reasoning_callback: Callable[[str], None] | None = None,
        stop_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        """Returns {final_response, messages, api_calls, token_usage, completed, error}."""

    def _take_snapshot(self) -> TurnSnapshot:
        """Freeze (model, temperature, max_tokens, system_prompt, tool_defs, compaction_settings)."""

    # Phase machine: self.phase ∈ {"idle", "turn", "compaction", "retry"}
    # Published events: SessionStart, UserMessage, BeforeLLMCall, AfterLLMCall,
    #                   BeforeToolCall, AfterToolCall, SessionEnd, PhaseChange
```

M7 contract: `run_conversation()` rejects if `self.phase != "idle"`. Call `run_conversation` once per turn; the phase resets to `"idle"` on completion.

#### LLMClient (`agent/core/llm_client.py:74`)

```python
class LLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
        max_retries: int = 3,
        max_retry_delay: float = 30.0,
        provider: LLMProvider | None = None,  # default: OpenAICompatProvider
    )

    def chat(
        self,
        *,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | None = "auto",
        stream: bool = False,
        stream_callback: Callable[[str], None] | None = None,
        reasoning_callback: Callable[[str], None] | None = None,
        stop_event: threading.Event | None = None,
    ) -> LLMResponse:
        """Never-throws — errors returned as LLMResponse with .error set and .failed==True."""
```

#### LLMResponse & ToolCallPayload (`agent/core/llm_providers/base.py:33`)

```python
@dataclass
class ToolCallPayload:
    id: str
    name: str
    arguments: str  # raw JSON string

@dataclass
class LLMResponse:
    content: str = ""
    reasoning: str | None = None
    tool_calls: list[ToolCallPayload] | None = None
    usage: dict | None = field(default_factory=dict)  # {prompt_tokens, completion_tokens, total_tokens}
    error: str = ""
    stop_reason: str | None = None

    @property
    def failed(self) -> bool: ...
```

#### ToolRegistry (`agent/tools/registry.py:66`)

```python
class ToolEntry:
    __slots__ = ("name", "toolset", "schema", "handler", "check_fn", "description", "emoji")

class ToolRegistry:
    def register(self, name: str, toolset: str, schema: dict, handler: Callable, ...) -> None
    def deregister(self, name: str) -> None
    def dispatch(self, name: str, args: dict) -> str  # returns JSON string
    def get_definitions(
        self,
        tool_names: list[str] | None = None,
        disabled_tools: set[str] | None = None,
    ) -> list[dict]  # OpenAI-format tools
    def get_all_tool_names(self) -> list[str]
    # Hooks:
    def add_before_hook(self, hook: BeforeHook) -> None  # BeforeHook = Callable[[str, dict], dict]
    def add_after_hook(self, hook: AfterHook) -> None    # AfterHook = Callable[[str, dict, str], str]
    def remove_before_hook(self, hook: BeforeHook) -> None
    def remove_after_hook(self, hook: AfterHook) -> None

# Singleton (module-level):
registry = ToolRegistry()
discover_tools()  # imports all tool modules → each calls registry.register()
```

**Before-hook protocol:** To block execution, return `{"__block__": True, "__reason__": "..."}`. Modified args are passed to the handler.

#### MCPServerConnection (`agent/tools/mcp_manager.py`)

```python
class MCPServerConnection:
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def call_tool(self, tool_name: str, arguments: dict) -> dict: ...

    # Properties:
    #   connected -> bool
    #   status -> str          # "connected", "error", or "disconnected"
    #   tool_count -> int

# Module-level helpers (called by main.py lifespan):
async def connect_all_servers(servers_config: dict) -> dict[str, str]: ...
async def connect_server(name: str, config: dict) -> None: ...
async def disconnect_server(name: str) -> None: ...
def get_server_statuses() -> list[dict]: ...
async def reload_all_servers() -> dict: ...
async def test_server_connection(name: str, config: dict) -> dict: ...
```

**Circuit breaker constants:** `_CIRCUIT_BREAKER_THRESHOLD = 3`, `_CIRCUIT_BREAKER_COOLDOWN_SEC = 60.0`

#### config_manager (`agent/config_manager.py`)

```python
def load() -> AppConfig: ...                            # Load from data/config.json
def save(cfg: AppConfig) -> None: ...                    # Persist (encrypts secrets)
def encrypt_secret(plain: str) -> str: ...                # → "encrypted:<fernet_token>"
def decrypt_secret(value: str) -> str: ...                # → plaintext
def get_erp_config(name: str) -> dict: ...                # ERP-specific config dict

# Known ERP secret fields (for encrypt/decrypt routing):
ERP_SECRET_FIELDS = {"yonsuite": ("app_key", "app_secret"), "nc": ("password",)}
```

#### AppConfig (`agent/config_model.py:56`)

```python
class AppConfig(BaseModel):
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o"
    llm_provider: str = "OpenAI"
    ys_app_key: str = ""
    ys_app_secret: str = ""
    ys_tenant_id: str = ""
    ys_gateway_url: str = "https://c2.yonyoucloud.com/iuap-api-gateway"
    max_iterations: int = Field(default=30, ge=5, le=50)
    compaction_enabled: bool = True
    max_context_tokens: int = Field(default=0, ge=0)       # 0 = auto-detect
    reserve_tokens: int = Field(default=4000, ge=1000)
    keep_recent_tokens: int = Field(default=8000, ge=2000)
    mcp_servers: dict[str, MCPServerEntry] = {}
    erp_clients: dict[str, dict[str, Any]] = {}
    disabled_extensions: list[str] = []

    def model_dump_encrypted(self) -> dict: ...             # Encrypts secrets before serialization
    @classmethod
    def model_validate_decrypted(cls, data: dict) -> AppConfig: ...  # Decrypts on load
```

#### build_system_prompt (`agent/core/message_builder.py:32`)

```python
def build_system_prompt(
    base: str,
    memory_store: object | None = None,
    memory_context: str = "",
    skill_index: str = "",
    skill_detail: str = "",
) -> str | None:
    """Concatenate fragments: base + memory + time + skill_index + skill_detail."""
```

#### MCPServerEntry (`agent/config_model.py:44`)

```python
class MCPServerEntry(BaseModel):
    transport: str = "stdio"           # "stdio" or "http"
    enabled: bool = True
    timeout: int = 120
    command: str | None = None
    args: list[str] = []
    url: str | None = None             # for http transport
    headers: dict[str, str] = {}
    env: dict[str, str] = {}
    builtin: bool = False              # builtin servers cannot be deleted via API
```

### 1.6 Development Constraints

#### Do-Not-Modify Zones (❌)

| Path | Reason |
|------|--------|
| `agent/skills/<name>/SKILL.md` | Built-in skills — frontend API rejects DELETE/EDIT on builtin=True |
| `mcp_server/ys_mcp_server/` | YonSuite MCP handler contract; changing response shape breaks LLM tool parsing |
| `agent/tools/registry.py` | Tool dispatch central hub — extend via `register()`, never edit internals |
| `agent/tools/security_hooks.py` | Three-layer security enforcement — modifying weakens the protection model |
| `backend/schemas/*.py` | Pydantic models consumed by frontend API responses — rename fields = breaking change |

#### ⚠️ Modify-With-Caution Zones

| Path | Risk |
|------|------|
| `agent/core/agent.py` | AIAgent constructor signature is frozen for M1; changing `run_conversation()` return dict keys breaks `chat.py` |
| `agent/core/llm_providers/base.py` | LLMResponse field names are consumed by `agent.py` and extensions |
| `agent/events/types.py` | Event class field names are contracts — extensions read them by name |
| `backend/api/erp_clients_api.py` | ERP secret field list must match `config_manager.ERP_SECRET_FIELDS` |
| `mcp_server/nc_mcp/mcp_starter.py` | `sync_nc_mcp()` is called from `erp_clients_api.py` — changing signature breaks ERP toggle |

#### Naming Conventions

- **MCP tool names** in config.json / tool registry: `mcp_<server_name>_<tool_name>` (e.g. `mcp_yonsuite_ys_api`)
- **API routes**: all under `/api/*` prefix, defined in `backend/api/` routers
- **REST endpoints**: follow RESTful pattern (`GET /api/resources`, `POST /api/resources`, etc.)
- **Test files**: `test_<module_name>.py` in `tests/`
- **Tool modules**: one file per toolset in `agent/tools/`
- **ERP client modules**: named after ERP system (yonsuite, nc)

#### Security Three-Layer Protection

```
Layer 1: System prompt         — Instructions telling the LLM to avoid dangerous actions
Layer 2: Before-hook chain     — security_hooks.py intercepts tool calls, blocks rm -rf etc.
Layer 3: SecurityEventExtension — events/security_event.py subscribes to BeforeToolCallEvent,
                                 cancels blocked operations
```

To add a new blocked pattern: edit `agent/tools/security_hooks.py` or `agent/extensions/security_event.py`. Never disable all three layers simultaneously.

#### Configuration Encryption Convention

- Secrets stored in config.json with `encrypted:` prefix
- Encryption: Fernet (symmetric), key derived from `sha256(hostname + "::zlink-agent::salt_v1")`
- See `agent/config_model.py:_encrypt()` / `_decrypt()` / `_derive_key()`
- ERP secret fields auto-encrypted on PUT via `erp_clients_api.py`:SECRET_FIELDS
- When adding a new ERP with secrets: add field names to both `ERP_SECRET_FIELDS` (config_manager.py) and `SECRET_FIELDS` (erp_clients_api.py)

### 1.7 Test System

**Run all tests:** `.venv/bin/python -m pytest tests/ -v`

**Coverage target:** 70%+ (measured by `--cov=agent --cov=backend --cov-report=term-missing`)

**Zero-network policy:** All tests use `MockLLMProvider`, `FastAPI TestClient`, and temp-file config isolation. No real LLM, YonSuite, or MCP server calls.

#### Test File ↔ Module Mapping

| Test file | Module under test | Mock/Isolation strategy |
|-----------|------------------|------------------------|
| `tests/conftest.py` | Shared fixtures | `clean_extensions` (autouse, wipes event bus between tests), `isolated_config` (redirects config to tmp_path), `MockLLMProvider` (scripted LLMResponse) |
| `tests/test_agent_loop.py` | `agent/core/agent.py` (AIAgent) | `MockLLMProvider` replaces `_llm` |
| `tests/test_extensions.py` | `agent/events/*` + `agent/extensions/*` | `clean_extensions` autouse |
| `tests/test_tool_registry.py` | `agent/tools/registry.py` | Clean tool registry per test (snapshot/restore) |
| `tests/test_compactor.py` | `agent/context_compactor.py` | Pure functions, no mocks needed |
| `tests/test_config_manager.py` | `agent/config_manager.py` | `monkeypatch` CONFIG_FILE to tmp_path |
| `tests/test_api_extensions.py` | `backend/api/extensions_api.py` | `TestClient(app)` + `isolated_config` |
| `tests/test_config_manager_erp.py` | `agent/config_manager.py` (ERP methods) | `monkeypatch` CONFIG_FILE |
| `tests/test_erp_clients_api.py` | `backend/api/erp_clients_api.py` | `TestClient(app)` + tmp config.json |
| `tests/test_erp_clients_base.py` | `agent/erp_clients/base.py` | Pure imports, no mocks |
| `tests/test_nc_mcp_starter.py` | `mcp_server/nc_mcp/mcp_starter.py` | `patch` config_manager + asyncio.run |
| `tests/test_nc_mcp_config.py` | `mcp_server/nc_mcp/config.py` | Pure functions |
| `tests/test_utils_data_dir.py` | `agent/utils.py` (_resolve_data_dir) | `monkeypatch` env vars + `importlib.reload` |

### 1.8 Common Modification Patterns

#### Pattern A: Add a new ERP system

1. Define ERP client class in `agent/erp_clients/<name>/` (if SDK needed)
2. Add entry to `ERP_REGISTRY` in `web/src/pages/SettingsERPPage.tsx` (label, badge, fields, MCP server name)
3. Add secret field names to both `config_manager.ERP_SECRET_FIELDS` and `erp_clients_api.SECRET_FIELDS`
4. Write MCP server in `mcp_server/<name>_mcp/` (or reuse existing)
5. Register MCP server entry in config.json mcp_servers (or use dynamic registration like nc)
6. Add toggle logic in `erp_clients_api.py` PUT handler

#### Pattern B: Add a new tool

1. Create a new file in `agent/tools/<new_tool>.py`
2. Define handler function that accepts `(args: dict) → str` (JSON)
3. Call `registry.register(name, toolset, schema, handler)` at module level
4. Tools auto-register on next import via `discover_tools()`

#### Pattern C: Add a new MCP server

1. Write MCP server implementing JSON-RPC over stdio or HTTP
2. Add `MCPServerEntry` to config.json mcp_servers
3. For builtin servers: add to `main.py` lifespan auto-registration
4. For ERP-linked servers (like nc): use `mcp_starter.sync_nc_mcp()` pattern
5. Frontend toggle: `builtin=True` → forbid delete; non-builtin → allow full CRUD

#### Pattern D: Add a new API route

1. Create new file in `backend/api/<name>_api.py` with `APIRouter`
2. Define Pydantic schemas in `backend/schemas/<name>.py` (if needed)
3. Mount router in `backend/main.py: app.include_router(router)`
4. For WebSocket: add to `backend/api/chat.py` router
5. Add frontend API client call in `web/src/api/` (if frontend consumes it)
6. Add page component in `web/src/pages/` + route in `App.tsx`



---

## Part 2: Human Developer Guide

### 2.1 Quick Start

```bash
# 1. Clone and enter
git clone <repo-url> zlink-agent && cd zlink-agent

# 2. Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Frontend dependencies
cd web && npm ci && cd ..

# 4. Start (development mode — backend + Vite hot-reload)
./start.sh --dev

# 5. Verify
#   Backend:  http://localhost:8089/api/health
#   Frontend: http://localhost:8088
#   WebSocket chat on ws://localhost:8089/api/chat
```

Expected output on backend start:
```
[ZLink Agent] Data directory: /Users/<user>/.zlink-agent/data
INFO:     Uvicorn running on http://0.0.0.0:8089
```

### 2.2 Command Reference

| Command | When to use |
|---------|-------------|
| `source .venv/bin/activate` | Before any Python command |
| `./start.sh` | Production mode (serves frontend from backend) |
| `./start.sh --dev` | Development mode (backend + Vite hot-reload) |
| `./start.sh stop` | Stop running services |
| `.venv/bin/python -m pytest tests/ -v` | Run all tests |
| `.venv/bin/python -m pytest tests/test_agent_loop.py -v` | Run a single test file |
| `ruff check . && ruff format --check .` | Lint + format check |
| `ruff check --fix . && ruff format .` | Auto-fix lint + format |
| `.venv/bin/python -c "from agent.tools.registry import registry, discover_tools; discover_tools(); print('OK:', len(registry.get_all_tool_names()), 'tools')"` | Verify tool registration |
| `echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \| .venv/bin/python -m mcp_server.ys_mcp_server` | Test YonSuite MCP server standalone |
| `bash scripts/build-app.sh` | Build macOS .app (after frontend changes) |
| `bash scripts/build-app.sh --no-frontend` | Build macOS .app (backend-only changes) |
| `cd web && npm run dev` | Start Vite dev server standalone |
| `cd web && npm install` | Install/update frontend deps |
| `pip install -r requirements.txt` | Install/update Python deps |

### 2.3 Architecture Overview

```
┌───────────────────────────────────────────────────────────────────┐
│                      React + Vite (port 8088)                     │
│  App.tsx → ChatPage, HistoryPage, ToolsPage, SkillsPage,         │
│            MemoryPage, McpPage, SettingsLLM, SettingsAgent,       │
│            SettingsERP, SettingsExtensions                        │
└────────────────────────┬──────────────────────────────────────────┘
                         │ WebSocket (ws://localhost:8089/api/chat)
                         │ REST     (http://localhost:8089/api/*)
                         ▼
┌───────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (port 8089)                     │
│  backend/main.py → lifespan (init search_index, connect MCP)     │
│  backend/api/ → 11 routers (chat, tools, skills, mcp, memory,    │
│                 config, erp-clients, extensions, metrics,         │
│                 sessions, system)                                 │
└────────────────────────┬──────────────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────────────────┐
│                      Agent Core (agent/)                          │
│  core/agent.py   → AIAgent.run_conversation()                     │
│  core/llm_*      → LLMClient + LLMProvider abstraction            │
│  tools/          → ToolRegistry + 14 tool modules                 │
│  events/         → EventBus + 8 event types + Extensions          │
│  skill_manager   → Skill lifecycle + prompt injection             │
│  config_manager  → Config load/save + fernet encryption           │
│  context_compactor → M6 three-level compaction                    │
│  session_manager, memory_manager, fact_memory, search_index       │
└──────┬────────────────────────────────────────────────────────────┘
       │
       ▼
┌───────────────────────────────────────────────────────────────────┐
│  MCP Servers (mcp_server/)       │  Runtime Data (~/.zlink-agent) │
│  ├─ ys_mcp_server (YonSuite)    │  ├─ config.json                │
│  └─ nc_mcp/ (NC, dynamic)       │  ├─ active_skills.json         │
│  (User-installed MCP servers)   │  ├─ sessions/                  │
│                                  │  ├─ memory/                   │
│                                  │  ├─ skills/                   │
│                                  │  └─ logs/                     │
└──────────────────────────────────┴────────────────────────────────┘
```

**Key design decisions:**
- **Synchronous agent loop** runs in a `ThreadPoolExecutor` via `run_in_executor` — avoids async rewrite of the 719-line agent loop
- **SSE parsing** in `openai_compat.py` handles both `data: {json}` (standard) and `data:{json}` (custom gateway) formats
- **Reasoning pipe** is a separate channel (`reasoning_callback`), not mixed with the content stream — frontend displays it in grey italic via `.reasoning-content` CSS class
- **ERP isolation**: only `enabled=true` ERP MCP tools are registered in the LLM's tool list; disabled systems are invisible to the LLM
- **Version number** must be synced across 5 locations (see section 2.5)

### 2.4 ERP Access Guide

Both YonSuite and NC are configured via the unified ERP settings page at `/settings/erp?tab=yonsuite` or `/settings/erp?tab=nc`.

#### YonSuite Setup

1. Go to **Settings → ERP** → **YonSuite** tab
2. Fill in:
   - **App Key** — from YonSuite developer console
   - **App Secret** — from YonSuite developer console
   - **Tenant ID** — your organization's tenant ID
3. Click **Save** — secrets are auto-encrypted with `encrypted:` prefix in config.json
4. Click **Test Connection** — backend calls YonSuite SDK directly to verify
5. Toggle **Enable** — when enabled, the YonSuite MCP server starts and its 11 tools become available to the LLM

#### NC Setup

1. Go to **Settings → ERP** → **NC** tab
2. Fill in:
   - **Host** (IP or domain), **Port** (default: 1521), **Service** (Oracle SID)
   - **User**, **Password**
   - Optionally set **Max Rows** (default: 100)
3. Click **Save** — password is auto-encrypted; on save, `mcp_starter.sync_nc_mcp()` dynamically registers and starts the `mcp-nc` server
4. Click **Test Connection** — backend checks if the mcp-nc server process is running
5. Toggle **Enable** — when enabled, the NC MCP server's tools are available to the LLM

**Troubleshooting:**
- If tools don't appear after enabling an ERP, check `GET /api/config/mcp-servers` to verify server status
- Check `~/.zlink-agent/data/logs/app.log` for MCP server connection errors
- NC uses environment variables (`ORACLE_HOST`, `ORACLE_PORT`, `ORACLE_SERVICE`, `ORACLE_USER`, `ORACLE_PASSWORD`) — verify in `mcp_server/nc_mcp/config.py`
- YonSuite credentials are injected into the MCP subprocess's environment (`YONSUITE_APP_KEY`, `YONSUITE_APP_SECRET`, `YONSUITE_TENANT_ID`)

### 2.5 Build & Release

#### Version Number Update (5-step, all required)

When bumping version:

```bash
# Step 1: pyproject.toml — update version field
# Step 2: VERSION — update version string
# Step 3: CHANGELOG.md — add release notes
# Step 4: README.md — update version + feature list + project structure
# Step 5: Git tag
git tag vX.Y.Z && git push origin vX.Y.Z
```

Always do all five steps. Missing one causes version mismatch between displays.

#### Build macOS .app

```bash
# Full build (frontend + backend)
bash scripts/build-app.sh

# Backend-only (skip frontend rebuild)
bash scripts/build-app.sh --no-frontend

# Open result
open dist/ZLink-Agent.app
```

The build script does: build frontend → pre-cache MCP npx packages → PyInstaller → package as .app.

### 2.6 Debugging Tips

#### Logs

| Log source | Location | Content |
|------------|----------|---------|
| Backend runtime | `~/.zlink-agent/data/logs/app.log` | All log levels, stderr mirror |
| Backend startup | Terminal stderr | `[ZLink Agent] Data directory: ...` |
| MCP server stderr | Backend logs (app.log) | MCP subprocess stderr captured by `_connect_stdio` |
| Frontend console | Browser DevTools → Console | React errors, API call failures |
| Frontend network | Browser DevTools → Network | API request/response payloads |

#### WebSocket Debugging

The chat WebSocket at `ws://localhost:8089/api/chat` sends typed JSON messages. Message types:

```json
{"seq": 1, "phase": "turn", "type": "token", "payload": {"text": "思考中..."}}
{"seq": 2, "phase": "turn", "type": "reasoning_token", "payload": {"text": "..."}}
{"seq": 3, "phase": "turn", "type": "tool_call", "payload": {"name": "web_search", ...}}
{"seq": 4, "phase": "idle", "type": "final", "payload": {"text": "回答完毕", ...}}
```

WebSocket frames use the `Envelope` format defined in `agent/core/agent.py:110-123`:
- `seq` — monotonically incrementing sequence number
- `phase` — agent lifecycle phase (`idle` / `turn` / `compaction` / `retry`)
- `type` — payload type (`token` / `reasoning_token` / `tool_call` / `final` / `error`)
- `payload` — message-specific data

Use browser DevTools to inspect WebSocket frames: **Network → WS → Messages**.

#### MCP Server Debugging

- Check `GET /api/config/mcp-servers` for server status (connected/disconnected/error)
- Circuit breaker state: 3 consecutive failures → 60s cooldown; see `_circuit_breaker_blocks()`
- Test a standalone MCP server:
  ```bash
  echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | .venv/bin/python -m mcp_server.ys_mcp_server
  ```
  Expected response: JSON-RPC response with server capabilities

#### Config Direct Edit

In emergencies, config can be edited directly:

```bash
# View decrypted config
python -c "from agent import config_manager; cfg = config_manager.load(); print(cfg.model_dump_json(indent=2))"

# Edit raw file, then reload backend
vim ~/.zlink-agent/data/config.json
```

Warning: Editing `encrypted:` fields by hand will break decryption. Use the Settings UI for secret fields, or use `config_manager.encrypt_secret()` to generate new encrypted values.

#### Checking Tool Registration

```bash
python -c "from agent.tools.registry import discover_tools, registry; discover_tools(); tools = registry.get_all_tool_names(); print(f'{len(tools)} tools registered:'); print('\n'.join(sorted(tools)))"
```

Expected: ~27 tool names printed (terminal, file, web, skills, MCP, todo, clarify, memory, session_search).

#### Test Coverage

```bash
.venv/bin/python -m pytest tests/ --cov=agent --cov=backend --cov-report=term-missing
```

Target: 70%+ coverage overall.

<!-- END_DOCUMENT -->
