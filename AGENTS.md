# ZLink Agent (智链 Agent)

> AI agent reference + developer guide. Keep this file under 32 KB — put detail in code, not here; look up signatures with Read instead of duplicating them.

## 1. Project Overview

ZLink Agent (智链 Agent) is an AI assistant with multi-ERP (YonSuite / NC / U8 / extensible) data retrieval, built-in MCP server management, a skill system, and long-term memory.

**Stack:** Python 3.11+ / FastAPI (port 8089) / React + Vite (port 8088) / MCP JSON-RPC / SQLite FTS5 / pytest / ruff

**Tests:** 602 tests, ~10s, zero network/LLM deps. Run: `.venv/bin/python -m pytest tests/ -v`

## 2. Directory Structure

```
zlink-agent/
├── backend/                    # FastAPI backend (port 8089)
│   ├── main.py                 # ⚠️ app, CORS, lifespan (init search_index, connect MCP), router mounts
│   ├── api/                    # 14 routers: chat(WS ⚠️), config, erp_clients(⚠️ env injection),
│   │                           #   mcp, skills, tools, slash_commands, cronjob, memory, metrics,
│   │                           #   sessions, session_artifacts(⚠️ 产物只读端点), extensions, system
│   └── schemas/                # ✅ Pydantic models (config, mcp, session, session_artifact,
│                               #    skill, slash_command, tool, extension)
├── agent/                      # Core logic (non-FastAPI, reusable)
│   ├── core/
│   │   ├── kernel_types.py     # ⚠️ AgentLoopConfig 钩子契约 / 10 种 AgentEvent / CancelToken / ToolResult
│   │   ├── loop.py             # ⚠️ run_agent_loop — 零策略双层 async loop（AgentEnd 保证任何路径收尾）
│   │   ├── agent.py            # ⚠️ 有状态 Agent 包装（subscribe/steer/follow_up/cancel/wait_idle）+ 兼容 re-export
│   │   ├── agent_adapter.py    # ⚠️ AIAgent 兼容层（run_conversation_async + EventBus 9 事件映射 + Phase 机）
│   │   ├── llm_client.py       # ⚠️ LLMClient shim → LLMProvider
│   │   ├── llm_providers/      # ⚠️ base (LLMProvider ABC / LLMResponse / ToolCallPayload),
│   │   │                       #    openai_compat (httpx SSE, reasoning_content), anthropic, factory
│   │   ├── message_builder.py  # build_system_prompt(), build_turn_messages()
│   │   ├── tool_dispatcher.py  # dispatch_tool_batch（并行/保序/sequential 降级）
│   │   ├── iteration_budget.py # IterationBudget — 纯计数器（消费点在 should_stop_after_turn 钩子）
│   │   └── metrics.py          # ⚠️ Prometheus metrics counters
│   ├── tools/                  # 28 tool files, 65 tools across 20 toolset modules +
│   │                           #   helpers (mcp_manager, tool_search, security_hooks, ...)
│   │   ├── registry.py         # ❌ ToolRegistry singleton — extend via register() only
│   │   ├── session_artifact_hook.py # ⚠️ 相对路径→<sid>/artifacts/ 归一 + 会话外写出登记 external.jsonl
│   │   ├── erp_ys_tools.py     # ⚠️ YonSuite 内置取数工具 (11 个, 替代旧 MCP 子进程)
│   │   ├── erp_nc_tools.py     # ⚠️ NC 内置取数工具 (4 个, 替代旧 MCP 子进程)
│   │   ├── erp_u8_tools.py     # ⚠️ U8 内置取数工具 (4 个, pymssql 直连 SQL Server)
│   │   ├── erp_u9c_tools.py    # ⚠️ U9C 内置取数工具 (4 个, pymssql 直连 SQL Server)
│   │   ├── mcp_manager.py      # ⚠️ MCP connections, circuit breaker, JSON-RPC
│   │   ├── security_hooks.py   # ❌ three-layer security enforcement
│   │   └── ...                 # 核心工具集 18 常驻，其余动态延迟（tool_search 桥 3 个）
│   ├── events/                 # ⚠️ bus.py (EventBus singleton), types.py (9 event classes),
│   │                           #    extensions.py (Extension base + runner)
│   ├── extensions/             # built-in: log_everything, security_event, monitoring, audit_log
│   ├── config_manager.py       # ⚠️ load()/save() — chmod 0600 on config.json
│   ├── config_model.py         # ⚠️ AppConfig + MCPServerEntry
│   ├── context_compactor.py    # ⚠️ M6 three-level compaction (truncate → LLM summary → drop)
│   ├── skill_manager.py        # ⚠️ skill CRUD, activation, prompt injection
│   ├── session_manager.py      # ⚠️ 会话持久化 —— data/sessions/<sid>/{session.json,artifacts/,external.jsonl}
│   ├── session_context.py      # ⚠️ 当前会话 ContextVar；工具层据此解析产物目录（未设=回退进程 cwd）
│   ├── node_env.py             # ⚠️ 打包版 node 可达性：启动时补 PATH（本机 node 优先 → Electron-as-node shim）
│   ├── search_index.py         # SQLite FTS5 session search
│   ├── memory_manager.py       # conversation summary memory (data/memory/)
│   ├── fact_memory.py          # autonomous memory (notes + user profile)
│   ├── slash_commands.py       # /help /model /compact /clear /login /cost
│   ├── utils.py                # DATA_DIR, atomic_json_write, _resolve_data_dir
│   ├── erp_clients/            # ERP SDK clients (yonsuite; NC/U8/U9C 直连 oracledb/pymssql 无需 SDK)
│   └── skills/                 # ❌ 24 built-in skills (read-only, not editable/deletable)
├── web/                        # React + Vite frontend (port 8088)
│   ├── src/                    # App.tsx (11 routes ⚠️), pages/, api/, components/, styles/, hooks/
│   └── vite.config.ts          # ⚠️ proxy /api + /ws → backend:8089
├── tests/                      # 52 files, 602 tests; conftest.py = shared fixtures
├── scripts/                    # build-electron.sh, zlink.sh, migrate.py
└── data/                       # runtime data (~/.zlink-agent/data/):
                                #   config.json (chmod 0600), active_skills.json, skills/,
                                #   sessions/, memory/, logs/, backups/
```

**Legend:** ✅ safe to modify | ⚠️ modify with caution (has dependents) | ❌ do not modify

**Hub nodes** (changing them affects many consumers): `agent/core/agent.py`, `agent/tools/registry.py`, `agent/tools/mcp_manager.py`, `backend/api/chat.py`, `agent/config_model.py`.

## 3. Architecture & Data Flows

### Flow A: Chat (WebSocket → AIAgent → 新内核 loop → LLM → response)

```
frontend WS → backend/api/chat.py (_run_agent_new 直接 await)
  → slash command? → execute() → response
  → else agent.run_conversation_async(message, history, session_id):
      build_turn_messages() → SessionStartEvent → UserMessageEvent（取消门）
      → Agent.run_async → run_agent_loop [agent/core/loop.py]:
          turn 循环: transform_context 钩子(compaction) → _stream_assistant_response
          → LLMResponse → tool_calls? → dispatch_tool_batch [tool_dispatcher.py]
              → prepare 串行(before_tool_call 钩子=BeforeToolCallEvent)
              → registry.dispatch()（security_hooks hook 链原样运行）
              → 并行 gather / sequential 降级 → 保序组装 tool 消息
          → should_stop_after_turn 钩子（IterationBudget 消费点）→ steering 钩子
      → AgentEnd → SessionEndEvent
      → 返回 {final_response, messages, api_calls, token_usage, completed, error}
```

### Flow B: MCP tool execution

`registry.dispatch()` → `mcp_manager.call_tool(server, tool, args)` → JSON-RPC `tools/call` over stdio (subprocess stdin/stdout, `asyncio.create_subprocess_exec`) or HTTP (httpx POST, timeout from `MCPServerEntry.timeout`).

**Circuit breaker:** 3 consecutive failures → 60s cooldown (`_CIRCUIT_BREAKER_THRESHOLD = 3`, `_CIRCUIT_BREAKER_COOLDOWN_SEC = 60.0`).

### Flow C: ERP config save → env injection

`PUT /api/config/erp-clients/{name}` → `erp_clients_api.py` merges + writes `config.json` → `_apply_erp_env(name, cfg)`:

- `nc` → injects `ORACLE_HOST/PORT/SERVICE/USER/PASSWORD` into `os.environ`
- `yonsuite` → injects `YONSUITE_APP_KEY/SECRET/TENANT_ID/GATEWAY_URL`
- `u8` → injects `U8_HOST/PORT/DATABASE/USER/PASSWORD/MAX_ROWS` into `os.environ`
- `u9c` → injects `U9C_HOST/PORT/DATABASE/USER/PASSWORD/MAX_ROWS` into `os.environ`

Built-in tools (`agent/tools/erp_*_tools.py`) read these env vars and connect directly.

### Flow D: Skill injection into system prompt

`skill_manager.get_skill_index_text()` → reads `active_skills.json` → Level 0 (name+desc list, always in system prompt). `get_instructions_for_query(user_message)` → n-gram matches name/description/tags → Level 1 (full SKILL.md, on-demand). Both go into `build_system_prompt(skill_index=..., skill_detail=...)`. **Default:** on first run (file missing) all built-in skills are activated and persisted; afterwards the file is authoritative — an explicit `[]` (all off) is respected.

### Events (`agent/events/bus.py`, EventBus singleton)

9 event types: `SessionStart → UserMessage → BeforeLLMCall → AfterLLMCall → BeforeToolCall → AfterToolCall → SessionEnd` (+ `PhaseChange` during turn lifecycle, `SessionBeforeCompact` before compaction). All Session*/PhaseChange events carry `session_id` so extensions can scope work per chat session.

### Key design decisions

- **Pi 风格新内核**：`agent/core/loop.py` 零策略 async loop + `kernel_types.py` 类型契约；`chat.py` 直接 await（`_run_agent_new` → `run_conversation_async`），不再跑 `run_in_executor`。
- **SSE parsing** in `openai_compat.py` handles both `data: {json}` (standard) and `data:{json}` (custom gateway) formats.
- **Reasoning pipe** is a separate channel (`reasoning_callback`), not mixed with content — frontend renders it grey italic via `.reasoning-content`.
- **ERP isolation**: only `enabled=true` ERP 的内置工具注册进 LLM 工具列表；禁用的系统对 LLM 不可见。每个 ERP 有独立 `check_fn` 门控，互不干扰。
- **Version number** single source of truth: `pyproject.toml` (see §10).

## 4. Key Contracts (do not break)

### AIAgent (`agent/core/agent_adapter.py`，经 `agent/core/agent.py` re-export)

- Constructor signature is **frozen** (M1) — do not add/rename params.
- `run_conversation(...)` 返回 keys（`{final_response, messages, api_calls, token_usage, completed, error}`）由 `backend/api/chat.py` 消费——冻结。
- 新内核入口：`async run_conversation_async(...)`（签名同 `run_conversation`）；`agent.core.agent` 暴露 `Agent` 句柄（`subscribe`/`steer`/`cancel`）。
- **Phase 机**（`idle/turn/compaction/retry`）：由适配层根据 AgentEvent 流维护，`run_conversation` 仍拒绝非 idle 重入。
- **策略钩子**（`AgentLoopConfig`）：`transform_context`（compaction）/`before_tool_call`/`after_tool_call`/`prepare_next_turn`/`should_stop_after_turn`（IterationBudget 消费点）/`get_steering_messages`/`get_follow_up_messages`/`bridge_dispatch`/`on_approval_blocked`——全部在 `agent/core/kernel_types.py` 定义。

### LLM layer

- `LLMClient.chat(*, model, messages, temperature, max_tokens, tools, tool_choice, stream, stream_callback, reasoning_callback, stop_event)` → `LLMResponse`. **Never throws** — errors returned with `.error` set, `.failed == True`.
- `LLMResponse` fields (consumed by `agent.py` + extensions): `content, reasoning, tool_calls, usage ({prompt_tokens, completion_tokens, total_tokens}), error, stop_reason`.
- `ToolCallPayload`: `id, name, arguments` (arguments = raw JSON string).

### ToolRegistry (`agent/tools/registry.py`, module-level singleton `registry`)

- `register(name, toolset, schema, handler)`, `deregister(name)`, `dispatch(name, args) → JSON str`, `get_definitions(tool_names, disabled_tools) → OpenAI-format tools`, `get_all_tool_names()`, `add/remove_before_hook`, `add/remove_after_hook`.
- `discover_tools()` imports all tool modules → each self-registers via `registry.register()`.
- **Before-hook block protocol:** to block execution return `{"__block__": True, "__reason__": "..."}`; otherwise modified args pass through to the handler.

### MCP (`agent/tools/mcp_manager.py`)

- `MCPServerConnection`: `connect/disconnect/call_tool`; properties `connected`, `status` ("connected"/"error"/"disconnected"), `tool_count`.
- Module helpers (called by `main.py` lifespan): `connect_all_servers`, `connect_server`, `disconnect_server`, `get_server_statuses`, `reload_all_servers`, `test_server_connection`.

### Config

- `config_manager.load() → AppConfig`; `save(cfg)` = atomic write + chmod 0600 (data dir 0700, best-effort); `get_erp_config(name)`; `resolve_placeholders(env, config)` resolves `${path.to.value}` in MCP env.
- `AppConfig` (`agent/config_model.py`): `llm_*`, `ys_*`, `max_iterations (5-50)`, `compaction_enabled`, `max_context_tokens (0=auto-detect)`, `reserve_tokens`, `keep_recent_tokens`, `mcp_servers`, `erp_clients`, `disabled_extensions`. Plain JSON — **no encryption layer** (no encrypt_secret/decrypt_secret).
- `MCPServerEntry`: `transport (stdio|http)`, `enabled`, `timeout`, `command`, `args`, `url`, `headers`, `env`, `builtin` (builtin=True → cannot be deleted via API).
- `build_system_prompt(base, memory_store, memory_context, skill_index, skill_detail, erp_context, artifact_dir)` — concatenates fragments; returns None if empty.

## 5. Development Constraints

### ❌ Do-Not-Modify Zones

| Path | Reason |
| ------ | -------- |
| `agent/skills/<name>/SKILL.md` | Built-in skills — API rejects DELETE/EDIT on builtin=True |
| `agent/tools/registry.py` | Tool dispatch hub — extend via `register()`, never edit internals |
| `agent/tools/security_hooks.py` | Three-layer security — modifying weakens the protection model |
| `backend/schemas/*.py` | Consumed by frontend API responses — renaming fields = breaking change |

### ⚠️ Modify-With-Caution Zones

| Path | Risk |
| ------ | ------ |
| `agent/core/agent.py` | Constructor frozen; changing `run_conversation()` return keys breaks `chat.py` |
| `agent/core/llm_providers/base.py` | LLMResponse field names consumed by `agent.py` and extensions |
| `agent/events/types.py` | Event field names are contracts — extensions read them by name |
| `backend/api/erp_clients_api.py` | `SECRET_FIELDS` is the source of truth for masked fields — new ERP secret fields must be added here |

### Naming Conventions

- **ERP 工具名**：内置工具用业务名（`ys_*`、`nc_*`、`u8_*`）；MCP 工具用 `mcp_<server_name>_<tool_name>`（如 `mcp_chart_chart_query`）
- **API routes**: all under `/api/*`, RESTful (`GET/POST /api/resources`), routers in `backend/api/`
- **Test files**: `tests/test_<module_name>.py`
- **Tool modules**: one file per toolset in `agent/tools/`
- **ERP client modules**: named after ERP system (yonsuite, nc; U8 直连 SQL Server 无需 SDK client)

### Security Three-Layer Protection

```
Layer 1: System prompt          — tells the LLM to avoid dangerous actions
Layer 2: Before-hook chain      — security_hooks.py intercepts tool calls, blocks rm -rf etc.
Layer 3: SecurityEventExtension — extensions/security_event.py subscribes BeforeToolCallEvent,
                                  cancels blocked operations
```

To add a blocked pattern: edit `agent/tools/security_hooks.py` or `agent/extensions/security_event.py`. Never disable all three layers at once.

### Config Secrets Convention

- Everything (incl. secrets) is plain JSON in `data/config.json`, chmod 0600; protection is file permissions, not cryptography.
- GET ERP API masks `SECRET_FIELDS` as `***`; the file always holds real values.
- New ERP with secrets → add field names to `SECRET_FIELDS` in `backend/api/erp_clients_api.py` (single source of truth; `config_manager` keeps no parallel list).
- Need at-rest encryption → run on encrypted filesystem (FileVault / LUKS / BitLocker).

## 6. Test System

- Run all: `.venv/bin/python -m pytest tests/ -v`; single file: append its path. 602 tests.
- Coverage target 70%+: `--cov=agent --cov=backend --cov-report=term-missing`.
- **Zero-network policy:** all tests use `MockLLMProvider`, FastAPI `TestClient`, tmp-file config isolation. No real LLM/YonSuite/MCP calls.
- Key fixtures (`tests/conftest.py`): `clean_extensions` (autouse, wipes event bus between tests), `isolated_config` (redirects config to tmp_path), `MockLLMProvider` (scripted LLMResponse).
- Tool-registry tests snapshot/restore the registry per test; config tests `monkeypatch` CONFIG_FILE to tmp_path.

## 7. Common Modification Patterns

**A. Add a new ERP system:**

1. ERP client class in `agent/erp_clients/<name>/` (if SDK needed; U8 直连 SQL Server 无需 SDK)
2. Entry in `ERP_REGISTRY` in `web/src/pages/SettingsERPPage.tsx` (label, badge, fields)
3. Secret field names → `SECRET_FIELDS` in `backend/api/erp_clients_api.py` (drives read-time masking + write semantics)
4. `_apply_erp_env()` injection logic in `erp_clients_api.py`
5. `_ERP_LABELS` in `agent/core/agent_adapter.py` (human label for system prompt)
6. `_build_erp_context()` in `agent_adapter.py` (table summary injection for enabled NC/U8/U9C)
7. Built-in tools in `agent/tools/erp_<name>_tools.py` (4 tools: `u8_query`, `u8_list_tables`, `u8_describe_table`, `u8_raw_sql`)
8. `backend/main.py` lifespan (env var injection via `os.environ.setdefault`)
9. PyInstaller known_tools list in `registry.py` (for frozen mode)

**B. Add a new tool:**

1. New file `agent/tools/<new_tool>.py`
2. Handler `(args: dict) → str` (JSON)
3. `registry.register(name, toolset, schema, handler)` at module level → auto-registers via `discover_tools()`

**C. Add a new MCP server:**

1. MCP server implementing JSON-RPC over stdio or HTTP
2. `MCPServerEntry` in config.json `mcp_servers`
3. Builtin → add to `main.py` lifespan auto-registration; `builtin=True` forbids delete, non-builtin allows full CRUD

**D. Add a new API route:**

1. `backend/api/<name>_api.py` with `APIRouter` (+ Pydantic schemas in `backend/schemas/` if needed)
2. Mount in `backend/main.py`: `app.include_router(router)` (WebSocket → `backend/api/chat.py`)
3. Frontend (if consumed): API client in `web/src/api/`, page in `web/src/pages/`, route in `App.tsx`

## 8. Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cd web && npm ci && cd ..

# Run
./start.sh              # production (backend serves frontend)
./start.sh --dev        # dev mode (backend :8089 + Vite hot-reload :8088)
./start.sh stop         # stop services

# Verify: http://localhost:8089/api/health, http://localhost:8088, ws://localhost:8089/ws/chat/{session_id}

# Test & lint
.venv/bin/python -m pytest tests/ -v
ruff check . && ruff format --check .     # check
ruff check --fix . && ruff format .       # auto-fix

# Verify tool registration (expect ~65 tools)
.venv/bin/python -c "from agent.tools.registry import registry, discover_tools; discover_tools(); print(len(registry.get_all_tool_names()), 'tools')"

# Build
bash scripts/build-electron.sh            # macOS .dmg; --win → .exe; --linux → .AppImage
```

## 9. ERP Setup (UI)

Settings → ERP → `yonsuite` / `nc` / `u8` tab.

- **YonSuite:** App Key / App Secret / Tenant ID → Save → Test → Enable → 11 tools (`ys_api`, `query_sale_orders`, …) become available.
- **NC:** Host / Port (1521) / Service (Oracle SID) / User / Password, optional Max Rows (100) → Save → Test (via oracledb) → Enable → 4 tools (`nc_query`, `nc_list_tables`, …).
- **U8:** Host / Port (1433) / Database / User / Password, optional Max Rows (200) → Save → Test (via pymssql) → Enable → 4 tools (`u8_query`, `u8_list_tables`, …).
- **U9C:** Host / Port (1433) / Database / User / Password, optional Max Rows (500) → Save → Test (via pymssql) → Enable → 4 tools (`u9c_query`, `u9c_list_tables`, …). 12 类预制业务查询（销售订单含行明细、采购订单含行明细、生产订单含产出明细等）。

**Troubleshooting:** tools missing after enable → check `GET /api/config/mcp-servers`; connection errors → `~/.zlink-agent/data/logs/app.log`.

## 10. Build & Release

Version bump (`pyproject.toml` = single source of truth):

1. `pyproject.toml` version field
2. 根目录 `package.json` version 字段（electron-builder 用它命名 DMG/App 版本，漏改会导致包名版本落后）
3. `CHANGELOG.md` release notes
4. `README.md` version + feature list + structure
5. `git tag vX.Y.Z && git push origin vX.Y.Z`

Build: `bash scripts/build-electron.sh` = frontend build → Python bundle → electron-builder → .dmg/.exe/.AppImage.

## 11. Debugging

- **Logs:** backend runtime + MCP subprocess stderr → `~/.zlink-agent/data/logs/app.log`; frontend → browser DevTools Console/Network.
- **WebSocket frames:** DevTools → Network → WS → Messages at `ws://localhost:8089/ws/chat/{session_id}` (Envelope format — see `agent/core/agent_adapter.py` Envelope).
- **Config direct edit:** `vim ~/.zlink-agent/data/config.json` then restart backend (or save from UI). Secrets are visible — file is owner-only.
- **MCP debugging:** `GET /api/config/mcp-servers` for status; circuit breaker = 3 failures → 60s cooldown. `mcp_server/` API was removed in v1.7.0 (YonSuite/NC are built-in tools now); Chart MCP is bundled in Electron builds only — for source dev use `mcp_add_server` tool or Settings → MCP.

## 12. 会话交接（Session Handover）

当单个 Kimi Code 会话积累了大量工具调用和文件改动后，应在 `HANDOVER.md` 记录当前状态以便新会话快速接续。

**何时写：** 以下任一条件满足时：

- 会话涉及 5+ 个 commit 或 3+ 个文件改动
- 有重要的架构决策、设计文档或用户明确的策略选择
- 当前会话即将结束、或上下文已明显变大

**HANDOVER.md 应包含：**

- 当前分支、版本、测试状态、构建产物
- 改动摘要（commit 列表 + 一句话说明）
- 关键决策记录（为什么做了/没做什么）
- 遗留待办 & 已知问题
- 新会话入口提示（第一个命令或 Read 什么文件）

**新会话流程：** `Read HANDOVER.md` → `git log --oneline -5` 确认分支 → `git diff --stat <last_tag>..HEAD` 看变更范围。如果 `HANDOVER.md` 不存在，说明上一个会话没有留下需要交接的工作。

## 13. Project-Specific Notes

- **不做暗色主题（2026-08-07 用户拍板）**：永远不投入暗色主题/主题切换，相关提议直接拒绝。

- **会话产物目录（2026-09-01）**：产物统一落 `~/.zlink-agent/data/sessions/<sid>/artifacts/`。文件/终端工具的相对路径由 `session_artifact_hook` 的 before-hook 归一（ContextVar 未设时退回进程 cwd，行为与改前逐字一致）；写到目录外的绝对路径被 after-hook 登记进同会话的 `external.jsonl`，侧边栏「会话外文件」组只给「在 Finder 显示 / 复制路径」。禁止再把产物写 `~/Desktop` 或仓库根目录（u8/nc/yonsuite 三个技能已改）。读端点 `backend/api/session_artifacts.py` 只允许 `<sid>/artifacts/` 子树（不用 StaticFiles 挂载，避免 `session.json` 被本机任意页面读到），html 响应带 `Content-Security-Policy: sandbox allow-scripts`。会话 id 统一过 `session_manager.is_valid_session_id()`（`^[A-Za-z0-9_-]{1,64}$`）—— 它来自客户端可控的 `/ws/chat/{session_id}`，不过滤就是路径穿越。

- **Git remote**: atomgit.com/gcw_cJbJuamU/zlink-agent.git (NOT GitHub)
- **BROWSER_URL**: start.sh 的 `open` 不能用 `$HOST`（默认 0.0.0.0），设 `BROWSER_URL="http://127.0.0.1:$PORT"`
- **NC65**: DBILLDATE 是 CHAR 类型，字符串比较；PO_ORDER 用 FORDERSTATUS（0=自由~5=输出）；SO_SALEORDER 用 FSTATUSFLAG
- **U8 主子表关联键**: 销售订单 `SO_SOMain.ID = SO_SODetails.ID`；采购订单 `PO_Pomain.POID = PO_Podetails.POID`；生产订单 `mom_orderdetail.MoCode` 串联 `mom_moallocate.MoCode`
- **U8 物料表**: `Inventory`（财务供应链用）与 `bas_part`（生产制造用）通过 `Inventory.cInvCode = bas_part.InvCode` 关联
- **桌面端网络绑定（2026-07-18）**：PyInstaller 入口默认 bind `127.0.0.1`（可用 `ZLINK_AGENT_HOST` 覆盖）；后端无鉴权，绝不能绑 0.0.0.0 暴露给局域网。Electron 生产模式启动顺序：loading.html → `electron/port.js` 抢占 8089（只杀命令行含 `zlink-backend` 的残留进程，外来进程则弹窗报错）→ 启动后端 → `/api/health` 就绪后加载前端。
- **`-webkit-app-region` 禁令（2026-07-18 事故）**：任何页面都不得设整页 `-webkit-app-region: drag`——拖拽区是窗口级状态，`loadURL` 换页后残留，整窗点击/悬停全被系统拿去拖窗口且 CDP 查不到（loading.html 曾因此导致打包版点击全灭）。标准做法：仅 `.electron .top-bar` 设 drag（`global.css`，顶栏纯文本无按钮）；hiddenInset 无原生拖动区，需要拖动必须靠此类小区域 CSS。
- **打包版 node 可达性（2026-09-02）**：从 Finder / Dock 启动的 GUI 进程不读 `~/.zshrc`、不读 `/etc/paths.d`，实测后端环境 `PATH=/usr/bin:/bin:/usr/sbin:/sbin` —— 本机 brew 装的 node 因此不可见，依赖 `node *.js` 的内置技能（china-hotdata / anysearch / minimax-pdf / pptx-generator）在客户端里一律 exit 127；dev 模式从登录 shell 起所以撞不到，只有打包版会出。`agent/node_env.py` 在 lifespan 早期（chart 的 node 解析与 `connect_all_servers` **之前**）补一次 PATH：本机真实 node 优先（brew / `/usr/local/bin` / nvm / volta / asdf / mise / pnpm / pi-node，Windows 加 `Program Files\nodejs`），探不到才用 `ELECTRON_NODE_PATH` 在 `<DATA_DIR>/bin/node` 生成 shim（每次启动重写，理由同 chart）。`ELECTRON_RUN_AS_NODE=1` **只能活在 shim 里** —— 泄进本进程环境会让被 spawn 的 Electron 应用以为自己是纯 node 而不开界面。
- **Chart MCP 打包（2026-07-18）**：build-electron.sh 对 `node_modules/@antv/mcp-server-chart` 跑 `npm install --omit=dev --ignore-scripts` 把依赖装进包目录（extraResources 一并拷贝，约 +29MB）。运行时 node 来源：`ELECTRON_NODE_PATH`（electron/main.js 注入 = Electron 二进制，配 `ELECTRON_RUN_AS_NODE=1`）优先，回退系统 `node`；两个都没有则跳过。内置 chart 条目是**应用托管**的：每次启动强制刷新 command/args/env（只保留用户的 enabled），防止 app 移动位置后旧路径残留导致 chart 永久失效。

### ERP 数据源路由（2026-07-13）

两个 Layer 确保 LLM 正确选择 ERP 取数，不再擅自猜测：

- **Layer 1 — System prompt 动态注入**（`skill_manager.py` + `agent_adapter.py`）：`get_skill_index_text()` 和 `get_instructions_for_query()` 都过滤已禁用的 ERP 技能，确保未启用的 ERP 不会出现在技能列表或触发加载中。`build_system_prompt()` 的 `erp_context` 参数由 `_build_erp_context()` 生成启用状态（✅/❌）。1 个启用 → 直接用对应工具；多个启用 → 用户未指明时先问查哪个。每轮重新读配置，开关即时生效。
- **Layer 2 — 工具描述标注**（`mcp_manager.py`）：`_convert_mcp_tool_schema()` 自动追加 `【数据源：YonSuite/NC】`；仅已知 ERP（`erp_source_labels = {"yonsuite": "YonSuite", "mcp-nc": "NC"}`）加标签，chart 等不加。U8/U9C 是内置工具直连，不走 MCP。

### 缓存路径（2026-07-13 修复）

所有运行时缓存必须写入 `~/.zlink-agent/data/`，而非源码目录（打包后不可写）：

- YonSuite 账簿缓存：`DATA_DIR / "yonsuite_cache" / "cache_accbook.json"`（修复前在 `agent/erp_clients/yonsuite/cache/`）
- YonSuite Token 缓存：`DATA_DIR / "yonsuite_cache"`（由 `main.py` 设置环境变量 `YONSUITE_CACHE_DIR`）

<!-- END_DOCUMENT -->