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

<!-- NEXT: SECTION_1_6 -->
