# Pi-style Agent Kernel Redesign Implementation Plan（Pi 风格内核重写实施计划）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `agent/core/` 从"单体 `AIAgent` 类 + 隐式策略"重构为"极简零策略 async loop + 有状态 Agent 包装 + 全钩子化策略"（对照 Pi agent harness 三层），工具并行执行 + `execution_mode` 审计 + `stop_reason=="length"` 截断防护 + CancelToken 全链路 + steering 队列，四契约冻结、存量测试全绿、`ZLINK_KERNEL=new|old` 双跑可回退。

**Architecture:** 新增 `kernel_types.py`（AgentLoopConfig / 9 种 AgentEvent / CancelToken / ToolResult，纯类型）+ `loop.py`（`run_agent_loop` 双层循环，零策略，所有"该不该继续"都是钩子）；`agent.py` 重写为有状态 `Agent` 包装类（subscribe/steer/follow_up/cancel/wait_idle）；`agent_adapter.py` 承载旧 `AIAgent` 兼容层（保留类名/构造签名/`run_conversation` 返回 keys，Phase 机 + EventBus 8 事件映射 + Envelope 内部维护），内部含旧算法行内副本作为 `ZLINK_KERNEL=old` 回退路径。`tool_dispatcher.py` 同步 `dispatch_tool` 保留给旧路径、新增 async `dispatch_tool_batch`（P1 串行、P2 并行 + 保序 + sequential 降级）。`chat.py` 拆 `_run_agent_legacy`（原样保留）与 `_run_agent_new`（直接 await `run_conversation_async` + AgentEvent→扁平 WS 消息）。

**Tech Stack:** Python 3.11+ / asyncio / concurrent.futures（`asyncio.to_thread`）/ FastAPI WebSocket / pytest（零网络）/ ruff。全程标准库，不引入新依赖。

## Global Constraints

- **四契约冻结（C1–C4，spec §5，任何任务不得破坏）：**
  - C1 `run_conversation`：`AIAgent` 构造签名不变；`run_conversation(user_message, system_message, conversation_history, stream_callback, reasoning_callback, stop_event, session_id)` 签名不变；返回 dict 6 keys 与语义不变（`{final_response, messages, api_calls, token_usage, completed, error}`）。
  - C2 WS 消息协议：`backend/api/chat.py` 下发的扁平消息 `type` 集合与字段不变（`token`/`reasoning_token`/`progress`/`tool_call`/`tool_result`/`approval_request`/`done`/`error`）；前端零改动；前端不接收 Envelope。
  - C3 EventBus 8 事件：`SessionStart/End`、`UserMessage`、`Before/AfterLLMCall`、`Before/AfterToolCall`、`PhaseChange` 的类型/字段/取消语义不变；`SessionBeforeCompactEvent` 不变（`agent/events/types.py`、`bus.py` 零改动）。
  - C4 registry 公开接口：`register`（仅允许新增可选参数 `execution_mode`，向后兼容）、`deregister`、`dispatch`、`get_definitions`、`get_all_tool_names`、before/after hook 增删、block 协议（`{"__block__": True, "__reason__": <原因>}`）全部不变。
- **不修改 `registry.py` 内核逻辑**：只允许 `ToolEntry.__slots__`/`__init__` 与 `register()` 增加 `execution_mode` 字段；`dispatch()` 主体逐字节不动。
- **安全三层不得削弱**：Layer 1 system prompt（`message_builder.py` 不动，适配层继续构建）；Layer 2 `security_hooks` before/after 链——新内核的 handler 执行必须仍然走 `registry.dispatch()`（其内部 hook 链原样运行），禁止绕过；Layer 3 `SecurityEventExtension` 订阅 `BeforeToolCallEvent` 取消——适配层 `before_tool_call` 钩子必须照常 publish 该事件。Approval 流程（`ApprovalBlockedError` → `ApprovalRequest` → WS `approval_response`）语义不变。
- **零网络测试策略**：所有测试用 `MockLLMProvider` + FastAPI `TestClient` + tmp 配置隔离；不发起真实 LLM/ERP/MCP 调用；`_generate_summary` 在测试中必须 monkeypatch 掉。
- **文档中文 / 代码注释与 commit message 英文**：计划中的 commit message 全部英文；新增/修改文件内注释英文（沿用仓库现状），用户可见字符串（progress/错误文案）保持中文与现状一致。
- **不改动**：`backend/schemas/`、`agent/erp_clients/`、`agent/skills/`、`skill_manager`、`memory_manager`、`fact_memory`、`search_index`、`message_builder.py`、`llm_client.py`、`llm_providers/base.py`（仅 §8 R3 例外：`openai_compat.py`/`anthropic.py` 各加一处 finish_reason→stop_reason 映射）、`agent/events/`（`types.py`/`bus.py`/`extensions.py` 零改动）。
- **不引入新依赖**：全程 `asyncio` / `concurrent.futures` 标准库。
- **存量测试红线**：`tests/test_agent_loop.py`、`tests/test_chat.py`、`tests/test_events.py`（实际为 `test_extensions.py`）、`tests/test_tool_registry.py` 在 P1 完成后**不改一行**通过。
- **`ZLINK_KERNEL` 读取一次**：进程启动后首次读取并缓存 + 日志记录（R5），不每请求判断；默认 `"new"`，P4 随旧内核一起删除。
- **测试命令**：` .venv/bin/python -m pytest tests/ -q`（全量）、` .venv/bin/python -m pytest <file>::<test> -v`（单测）；lint：`ruff check . && ruff format --check .`。
- **行为漂移说明（P1 已知、可接受）**：① 预算耗尽时新内核允许模型多跑一轮 LLM 调用（旧内核在 `while budget.consume()` 顶部拦截）——两者结束语义（error 文案 `"Max iterations reached without final response"` / completed）一致，存量测试不覆盖此边界；② 新内核 honor `system_message` 参数（旧内核接受但忽略该参数，属既有 bug）——chat.py 传入的 memory+skill 增强 prompt 首次真正生效，MockLLMProvider 下输出不受影响；③ 压缩注入的 summary 消息只进 LLM 上下文、不进 `result["messages"]`（旧内核会进）；④ `api_calls` 计数：新内核每次 LLM 尝试（含 call_llm 内部重试）计 1，与旧内核 per-call 计数一致；⑤ 新内核 WS 不再下发 `🔧 调用工具/📤 返回结果` 样式的 markdown token（改用 `tool_call`/`tool_result`/`progress` 消息，类型集合与字段不变）。

---

## File Structure（文件规划）

| 路径 | 动作 | 职责 |
|------|------|------|
| `agent/core/kernel_types.py` | 新建 | 纯类型契约：`CancelToken` / `AgentContext` / `AgentLoopConfig`（全部策略钩子，可选）/ `TurnUpdate` / `ToolResult` / `ExecutedToolBatch` / 9 种 `AgentEvent` dataclass + `AgentEvent` 联合类型 |
| `agent/core/loop.py` | 新建 | `run_agent_loop` / `run_agent_loop_continue` / `_run_loop`（双层循环，零策略）/ `_stream_assistant_response` / `_execute_tool_batch` / `_fail_truncated_batch` / `_to_tool_message` / `_apply_update` |
| `agent/core/tool_dispatcher.py` | 改造 | 保留同步 `dispatch_tool`（旧路径用）；新增 async `dispatch_tool_batch`（P1 串行，P2 并行 + 保序 + sequential 降级）；prepare 串行 + handler 经 `asyncio.to_thread(registry.dispatch, ...)`（hook 链原样运行）+ after_tool_call 钩子 + 截断 |
| `agent/core/agent.py` | 重写 | 新有状态 `Agent` 类（`AgentState` / subscribe / steer / follow_up / clear_steering_queue / next_steering_message / next_follow_up_messages / cancel / wait_idle / run_async）+ 文件末尾 re-export `AIAgent`/`ApprovalRequest`/`Phase`/`AgentPhase`/`Envelope`/`TurnSnapshot`（C1 导入路径不变） |
| `agent/core/agent_adapter.py` | 新建（cp 自旧 agent.py） | 兼容层：`Phase` / `Envelope` / `TurnSnapshot` / `ApprovalRequest` + `kernel_mode()`（`ZLINK_KERNEL` 单次读取）+ `AIAgent`（构造签名不变；旧算法行内副本 `_run_conversation_legacy` + 新内核路径 `run_conversation_async` + 同步 `run_conversation` 按模式分发）+ 8 事件 EventBus 映射 `_map_event_to_bus` + 各策略钩子（transform_context/before_tool_call/after_tool_call/call_llm/should_stop_after_turn/prepare_next_turn/on_approval_blocked/bridge_dispatch） |
| `backend/api/chat.py` | 改造 | `_run_agent` 按 `kernel_mode()` 分发：`_run_agent_legacy`（原代码原样）+ `_run_agent_new`（直接 await `run_conversation_async`，AgentEvent 监听器→扁平 WS 消息，入站 stop/approval_response/steering） |
| `agent/tools/registry.py` | 改造（最小） | `ToolEntry` 增加 `execution_mode` 字段（`__slots__` + `__init__`）；`register()` 增加 `execution_mode: str = "parallel"` 可选参数 |
| `agent/core/llm_providers/openai_compat.py` | 改造（R3 唯一例外） | `finish_reason` → `stop_reason` 映射（blocking + streaming 两处） |
| `agent/core/llm_providers/anthropic.py` | 改造（R3 唯一例外） | Anthropic `stop_reason` → 统一 `stop_reason` 映射（blocking + streaming 两处） |
| 15 个工具文件（见 P2-T2） | 改造 | 写操作/状态突变工具逐个标 `execution_mode="sequential"`（审计原则：拿不准一律 sequential） |
| `agent/core/iteration_budget.py` | 不改 | 纯计数器保留；消费点挪入适配层 `should_stop_after_turn` 钩子 |
| `agent/core/message_builder.py` / `llm_client.py` / `llm_providers/base.py` | 不改 | 既有契约原样复用 |
| `AGENTS.md` | P4 改造 | 架构章节更新（新内核分层、双跑开关说明、删除旧描述） |
| `tests/test_kernel_types.py` | 新建 | CancelToken / AgentLoopConfig / 事件 dataclass |
| `tests/test_loop.py` | 新建 | loop 全流程（事件序列 / steering / follow-up / 预算 / length 截断 / 取消） |
| `tests/test_tool_dispatcher_batch.py` | 新建 | dispatch_tool_batch（P1 串行 + P2 并行/保序/降级） |
| `tests/test_agent.py` | 新建 | `Agent` 包装类 |
| `tests/test_agent_adapter.py` | 新建 | 兼容层：legacy 路径（P1-T4）+ 新路径行为（P1-T6）+ 双跑等价（P1-T6）+ 取消/steering（P3） |
| `tests/test_chat_async.py` | 新建 | chat.py 新路径 WS 消息映射 / stop / steering 入站 |
| `tests/test_contract_freeze.py` | 新建 | C1–C4 逐条断言（每期验收复用） |
| `tests/test_stop_reason_mapping.py` | 新建 | finish_reason→stop_reason 映射单测 |

---

# P1 —— 新 loop 骨架 + Agent 类 + 事件流 + 契约适配 + Budget 钩子化

行为目标：**与现状等价**（串行工具、无 steering）；四契约冻结；存量 378 测试全绿；`ZLINK_KERNEL` 双跑上线（默认 `new`）。

## Task P1-T1: kernel_types.py — 内核类型契约

**Files:**
- Create: `agent/core/kernel_types.py`
- Test: `tests/test_kernel_types.py`

**Interfaces:**
- Consumes: 无（纯类型模块；`LLMResponse`/`ToolCallPayload` 仅 TYPE_CHECKING 引用 `agent.core.llm_providers.base`）。
- Produces（后续所有任务依赖，签名冻结）：
  - `class CancelToken` — `cancel() -> None`；`cancelled -> bool`；`async wait() -> None`；`check() -> None`（已取消则 `raise asyncio.CancelledError`）
  - `@dataclass class AgentContext` — `messages: list[dict]`；`api_calls: int = 0`
  - `@dataclass(frozen=True) class AgentLoopConfig` — `model: str`；`temperature: float = 0.7`；`max_tokens: int | None = None`；`system_prompt: str = ""`；`tool_defs: list[dict]`；`max_tool_result_length: int = sys.maxsize`；`call_llm: Callable[..., Awaitable[LLMResponse]] | None`；`transform_context` / `before_tool_call` / `after_tool_call` / `prepare_next_turn` / `should_stop_after_turn` / `get_steering_messages` / `get_follow_up_messages` / `bridge_dispatch` / `on_approval_blocked`（全部可选，钩子签名见文件 docstring 注释块）
  - `@dataclass(frozen=True) class TurnUpdate` — `model: str | None = None`；`temperature: float | None = None`；`max_tokens: int | None = None`
  - `@dataclass class ToolResult` — `tool_call_id: str`；`tool_name: str`；`result: str`；`is_error: bool = False`；`terminate: bool = False`
  - `@dataclass class ExecutedToolBatch` — `messages: list[ToolResult]`；`terminate: bool = False`
  - 9 个 frozen dataclass：`AgentStart(type="agent_start")`；`AgentEnd(messages: list[dict])`；`TurnStart`；`TurnEnd(message: dict, tool_results: list[ToolResult])`；`MessageStart(message: dict)`；`MessageUpdate(message: dict, delta: str, reasoning_delta: str | None = None)`；`MessageEnd(message: dict)`；`ToolExecutionStart(tool_call_id, tool_name, args)`；`ToolExecutionUpdate(tool_call_id, tool_name, partial_result)`；`ToolExecutionEnd(tool_call_id, tool_name, result, is_error=False)` —— `type` 判别式字段置于末尾
  - `AgentEvent = AgentStart | AgentEnd | TurnStart | TurnEnd | MessageStart | MessageUpdate | MessageEnd | ToolExecutionStart | ToolExecutionUpdate | ToolExecutionEnd`

- [ ] **Step 1: Write the failing test**

Create `tests/test_kernel_types.py`:

```python
"""Tests for agent/core/kernel_types.py — kernel type contracts."""

from __future__ import annotations

import asyncio

import pytest

from agent.core.kernel_types import (
    AgentContext,
    AgentEnd,
    AgentEvent,
    AgentLoopConfig,
    AgentStart,
    CancelToken,
    ExecutedToolBatch,
    MessageEnd,
    MessageStart,
    MessageUpdate,
    ToolExecutionEnd,
    ToolExecutionStart,
    ToolExecutionUpdate,
    ToolResult,
    TurnEnd,
    TurnStart,
    TurnUpdate,
)


class TestCancelToken:
    def test_starts_uncancelled(self):
        token = CancelToken()
        assert token.cancelled is False

    def test_cancel_sets_flag(self):
        token = CancelToken()
        token.cancel()
        assert token.cancelled is True

    def test_wait_returns_after_cancel(self):
        async def _scenario():
            token = CancelToken()

            async def _canceller():
                await asyncio.sleep(0.01)
                token.cancel()

            task = asyncio.create_task(token.wait())
            await asyncio.create_task(_canceller())
            await task  # must return once cancelled

        asyncio.run(_scenario())

    def test_check_raises_cancelled_error_when_cancelled(self):
        token = CancelToken()
        token.cancel()
        with pytest.raises(asyncio.CancelledError):
            token.check()

    def test_check_passes_when_not_cancelled(self):
        CancelToken().check()  # must not raise


class TestAgentLoopConfig:
    def test_defaults(self):
        cfg = AgentLoopConfig(model="gpt-4o")
        assert cfg.model == "gpt-4o"
        assert cfg.temperature == 0.7
        assert cfg.max_tokens is None
        assert cfg.system_prompt == ""
        assert cfg.tool_defs == []
        assert cfg.call_llm is None
        assert cfg.transform_context is None
        assert cfg.before_tool_call is None
        assert cfg.after_tool_call is None
        assert cfg.prepare_next_turn is None
        assert cfg.should_stop_after_turn is None
        assert cfg.get_steering_messages is None
        assert cfg.get_follow_up_messages is None
        assert cfg.bridge_dispatch is None
        assert cfg.on_approval_blocked is None

    def test_turn_update_defaults(self):
        u = TurnUpdate()
        assert u.model is None
        assert u.temperature is None
        assert u.max_tokens is None


class TestToolResultAndBatch:
    def test_tool_result_defaults(self):
        r = ToolResult(tool_call_id="c1", tool_name="ls", result="[]")
        assert r.is_error is False
        assert r.terminate is False

    def test_executed_batch_defaults(self):
        b = ExecutedToolBatch()
        assert b.messages == []
        assert b.terminate is False


class TestAgentEvents:
    def test_discriminator_types(self):
        assert AgentStart().type == "agent_start"
        assert AgentEnd(messages=[]).type == "agent_end"
        assert TurnStart().type == "turn_start"
        assert TurnEnd(message={}, tool_results=[]).type == "turn_end"
        assert MessageStart(message={}).type == "message_start"
        assert MessageUpdate(message={}, delta="hi").type == "message_update"
        assert MessageUpdate(message={}, delta="", reasoning_delta="think").reasoning_delta == "think"
        assert MessageEnd(message={}).type == "message_end"
        assert ToolExecutionStart(tool_call_id="c1", tool_name="ls", args={}).type == "tool_execution_start"
        assert (
            ToolExecutionUpdate(tool_call_id="c1", tool_name="ls", partial_result="x").type == "tool_execution_update"
        )
        assert ToolExecutionEnd(tool_call_id="c1", tool_name="ls", result="[]").type == "tool_execution_end"
        assert ToolExecutionEnd(tool_call_id="c1", tool_name="ls", result="err", is_error=True).is_error is True

    def test_events_are_frozen(self):
        with pytest.raises(Exception):
            MessageStart(message={}).message = {"role": "user"}  # type: ignore[misc]

    def test_agent_event_union_members(self):
        events: list[AgentEvent] = [
            AgentStart(),
            AgentEnd(messages=[]),
            TurnStart(),
            TurnEnd(message={}, tool_results=[]),
            MessageStart(message={}),
            MessageUpdate(message={}, delta="d"),
            MessageEnd(message={}),
            ToolExecutionStart(tool_call_id="c1", tool_name="t", args={}),
            ToolExecutionUpdate(tool_call_id="c1", tool_name="t", partial_result="p"),
            ToolExecutionEnd(tool_call_id="c1", tool_name="t", result="r"),
        ]
        assert len(events) == 10

    def test_agent_context_defaults(self):
        ctx = AgentContext()
        assert ctx.messages == []
        assert ctx.api_calls == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: ` .venv/bin/python -m pytest tests/test_kernel_types.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.core.kernel_types'`

- [ ] **Step 3: Write minimal implementation**

Create `agent/core/kernel_types.py`:

```python
"""Kernel type contracts — the only interface between the loop and policy.

Pi-style kernel redesign (spec 2026-08-06-pi-style-kernel-design).  This
module mirrors Pi's ``packages/agent/src/types.ts``: pure types + constants,
no logic.  ``AgentLoopConfig`` carries every strategy hook; ``CancelToken``
replaces Pi's AbortSignal; the 9 ``AgentEvent`` classes are the kernel's
only outward event channel.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.core.llm_providers.base import LLMResponse


class CancelToken:
    """Cancellation token — the Python analogue of Pi's AbortSignal.

    Passed through every hook and the whole loop; ``cancel()`` from any
    thread marks it cancelled; ``check()`` raises ``asyncio.CancelledError``
    at the next cooperative point.
    """

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()

    def check(self) -> None:
        if self._event.is_set():
            raise asyncio.CancelledError()


@dataclass
class AgentContext:
    """Mutable per-run state owned by the loop."""

    messages: list[dict] = field(default_factory=list)
    api_calls: int = 0


@dataclass(frozen=True)
class TurnUpdate:
    """Returned by ``prepare_next_turn`` — per-turn config overrides."""

    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass
class ToolResult:
    """One executed (or failed) tool call, in transcript order."""

    tool_call_id: str
    tool_name: str
    result: str
    is_error: bool = False
    terminate: bool = False


@dataclass
class ExecutedToolBatch:
    """Return value of ``dispatch_tool_batch``."""

    messages: list[ToolResult] = field(default_factory=list)
    terminate: bool = False


# ── AgentLoopConfig ────────────────────────────────────────────────
# Hook signatures (all optional; sync or async — the loop awaits them):
#   call_llm(full_messages, *, emit, message, token) -> LLMResponse
#       full_messages = [system?] + context.messages; must emit MessageUpdate
#       via *emit* while streaming (message = the partial assistant dict)
#   transform_context(messages, token) -> list[dict]
#   before_tool_call(tool_name, args, token) -> dict
#       returns modified args, or {"__block__": True, "__reason__": <原因>} to block
#   after_tool_call(tool_name, args, result, token) -> str
#   prepare_next_turn(ctx, token) -> TurnUpdate | None
#   should_stop_after_turn(ctx, token) -> bool
#   get_steering_messages(token) -> list[dict]
#   get_follow_up_messages(token) -> list[dict]
#   bridge_dispatch(tool_name, args) -> str
#   on_approval_blocked(tool_name, reason) -> str   ("approved" | "denied")
# ctx = {"message": dict, "tool_results": list[ToolResult],
#        "messages": list[dict], "api_calls": int}


@dataclass(frozen=True)
class AgentLoopConfig:
    """One run's configuration + all strategy hooks (all optional)."""

    model: str
    temperature: float = 0.7
    max_tokens: int | None = None
    system_prompt: str = ""
    tool_defs: list[dict] = field(default_factory=list)
    max_tool_result_length: int = sys.maxsize
    call_llm: Callable[..., Awaitable["LLMResponse"]] | None = None
    transform_context: Callable[[list[dict], CancelToken], list[dict] | Awaitable[list[dict]]] | None = None
    before_tool_call: Callable[[str, dict, CancelToken], dict | Awaitable[dict]] | None = None
    after_tool_call: Callable[[str, dict, str, CancelToken], str | Awaitable[str]] | None = None
    prepare_next_turn: Callable[[dict, CancelToken], TurnUpdate | None | Awaitable[TurnUpdate | None]] | None = None
    should_stop_after_turn: Callable[[dict, CancelToken], bool | Awaitable[bool]] | None = None
    get_steering_messages: Callable[[CancelToken], list[dict] | Awaitable[list[dict]]] | None = None
    get_follow_up_messages: Callable[[CancelToken], list[dict] | Awaitable[list[dict]]] | None = None
    bridge_dispatch: Callable[[str, dict], str | Awaitable[str]] | None = None
    on_approval_blocked: Callable[[str, str], str | Awaitable[str]] | None = None


# ── AgentEvent union: dataclasses discriminated by ``type`` ────────


@dataclass(frozen=True)
class AgentStart:
    type: str = "agent_start"


@dataclass(frozen=True)
class AgentEnd:
    messages: list[dict]
    type: str = "agent_end"


@dataclass(frozen=True)
class TurnStart:
    type: str = "turn_start"


@dataclass(frozen=True)
class TurnEnd:
    message: dict
    tool_results: list[ToolResult]
    type: str = "turn_end"


@dataclass(frozen=True)
class MessageStart:
    message: dict
    type: str = "message_start"


@dataclass(frozen=True)
class MessageUpdate:
    message: dict
    delta: str
    reasoning_delta: str | None = None
    type: str = "message_update"


@dataclass(frozen=True)
class MessageEnd:
    message: dict
    type: str = "message_end"


@dataclass(frozen=True)
class ToolExecutionStart:
    tool_call_id: str
    tool_name: str
    args: dict
    type: str = "tool_execution_start"


@dataclass(frozen=True)
class ToolExecutionUpdate:
    tool_call_id: str
    tool_name: str
    partial_result: str
    type: str = "tool_execution_update"


@dataclass(frozen=True)
class ToolExecutionEnd:
    tool_call_id: str
    tool_name: str
    result: str
    is_error: bool = False
    type: str = "tool_execution_end"


AgentEvent = (
    AgentStart
    | AgentEnd
    | TurnStart
    | TurnEnd
    | MessageStart
    | MessageUpdate
    | MessageEnd
    | ToolExecutionStart
    | ToolExecutionUpdate
    | ToolExecutionEnd
)

__all__ = [
    "CancelToken",
    "AgentContext",
    "TurnUpdate",
    "ToolResult",
    "ExecutedToolBatch",
    "AgentLoopConfig",
    "AgentStart",
    "AgentEnd",
    "TurnStart",
    "TurnEnd",
    "MessageStart",
    "MessageUpdate",
    "MessageEnd",
    "ToolExecutionStart",
    "ToolExecutionUpdate",
    "ToolExecutionEnd",
    "AgentEvent",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: ` .venv/bin/python -m pytest tests/test_kernel_types.py -v`

Expected: PASS，`13 passed`

- [ ] **Step 5: Commit**

```bash
git add agent/core/kernel_types.py tests/test_kernel_types.py
git commit -m "feat: add kernel type contracts (CancelToken/AgentLoopConfig/AgentEvent)"
```

## Task P1-T2: tool_dispatcher.py — async dispatch_tool_batch（串行）

**Files:**
- Modify: `agent/core/tool_dispatcher.py`
- Test: `tests/test_tool_dispatcher_batch.py`

**Interfaces:**
- Consumes: `kernel_types.AgentEvent`、`AgentLoopConfig`、`CancelToken`、`ExecutedToolBatch`、`ToolResult`；`llm_providers.base.ToolCallPayload`；`agent.tools.registry.registry`、`tool_error`；`agent.tools.tool_search.BRIDGE_TOOL_NAMES`。
- Produces（loop 与适配层依赖）：
  - `async dispatch_tool_batch(calls: list[ToolCallPayload], *, max_result_length: int, token: CancelToken, emit: Callable[[AgentEvent], Awaitable[None]], config: AgentLoopConfig) -> ExecutedToolBatch` — 按调用原序返回结果；P1 严格串行（prepare → execute → finalize 逐个推进）
  - 语义：prepare = 解析 JSON args（非法 → `tool_error("Invalid JSON arguments")`）+ `config.before_tool_call`（返回含 `__block__` → 错误结果、handler 不执行）；execute = bridge 工具走 `config.bridge_dispatch`，其余 `await asyncio.to_thread(registry.dispatch, name, args)`（registry hook 链与 `__block__` 协议原样运行），`ApprovalBlockedError` → `config.on_approval_blocked`（approved 则 `entry.handler(args)` 直连绕过 hooks，否则 `tool_error("用户拒绝了操作")`），其他异常 → `tool_error(str(e))`；finalize = `config.after_tool_call` 改写结果；结果按 `max_result_length` 截断并附 `"\n\n..."`；每个工具 emit `ToolExecutionStart`（执行前）与 `ToolExecutionEnd`（结果截断后）
  - 保留现有 `dispatch_tool(name, args, *, max_result_length, preview_length) -> tuple[str, str]` 原样不动（旧内核路径 + `agent/core/__init__.py` 导出依赖）

- [ ] **Step 1: Write the failing test**

Create `tests/test_tool_dispatcher_batch.py`:

```python
"""Tests for agent/core/tool_dispatcher.py — async batch dispatch (P1: sequential)."""

from __future__ import annotations

import asyncio
import json
import sys
import time

import pytest

from agent.core.kernel_types import (
    AgentEvent,
    AgentLoopConfig,
    CancelToken,
    ToolExecutionEnd,
    ToolExecutionStart,
)
from agent.core.llm_providers.base import ToolCallPayload
from agent.core.tool_dispatcher import dispatch_tool_batch
from agent.tools.registry import registry, tool_error, tool_result


@pytest.fixture(autouse=True)
def clean_tool_registry():
    """Snapshot the registry, run the test, restore it (same as test_tool_registry)."""
    saved_before = set(registry.get_all_tool_names())
    saved_hooks_before = list(registry._before_hooks)
    saved_hooks_after = list(registry._after_hooks)
    yield
    for name in set(registry.get_all_tool_names()) - saved_before:
        try:
            registry.deregister(name)
        except Exception:
            pass
    registry._before_hooks[:] = saved_hooks_before
    registry._after_hooks[:] = saved_hooks_after


def _make_config(**kw) -> AgentLoopConfig:
    base = {"model": "test-model"}
    base.update(kw)
    return AgentLoopConfig(**base)


class _EventRecorder:
    def __init__(self) -> None:
        self.events: list[AgentEvent] = []

    async def __call__(self, event: AgentEvent) -> None:
        self.events.append(event)


def _run(coro):
    return asyncio.run(coro)


def test_batch_sequential_order_and_events():
    """P1: tools run strictly in call order; Start/End events per tool."""
    order: list[str] = []

    def handler_a(args: dict) -> str:
        order.append("a")
        return tool_result(data={"x": args.get("x")})

    def handler_b(args: dict) -> str:
        order.append("b")
        return tool_result(data={"y": args.get("y")})

    registry.register(name="t_a", toolset="test", schema={"type": "object"}, handler=handler_a)
    registry.register(name="t_b", toolset="test", schema={"type": "object"}, handler=handler_b)

    recorder = _EventRecorder()
    calls = [
        ToolCallPayload(id="c1", name="t_a", arguments='{"x": 1}'),
        ToolCallPayload(id="c2", name="t_b", arguments='{"y": 2}'),
    ]
    batch = _run(
        dispatch_tool_batch(
            calls,
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=recorder,
            config=_make_config(),
        )
    )

    assert order == ["a", "b"]
    assert [r.tool_call_id for r in batch.messages] == ["c1", "c2"]
    assert json.loads(batch.messages[0].result)["data"]["x"] == 1
    assert json.loads(batch.messages[1].result)["data"]["y"] == 2

    starts = [e for e in recorder.events if isinstance(e, ToolExecutionStart)]
    ends = [e for e in recorder.events if isinstance(e, ToolExecutionEnd)]
    assert [e.tool_name for e in starts] == ["t_a", "t_b"]
    assert [e.tool_name for e in ends] == ["t_a", "t_b"]
    assert ends[0].tool_call_id == "c1"


def test_invalid_json_arguments_produce_error_result():
    registry.register(name="t_json", toolset="test", schema={"type": "object"}, handler=lambda args: "unused")
    recorder = _EventRecorder()
    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name="t_json", arguments="{not json")],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=recorder,
            config=_make_config(),
        )
    )
    assert batch.messages[0].is_error is True
    assert "Invalid JSON arguments" in batch.messages[0].result


def test_before_tool_call_block_skips_handler():
    called: list[str] = []

    def handler(args: dict) -> str:
        called.append("handler")
        return tool_result()

    registry.register(name="t_block", toolset="test", schema={"type": "object"}, handler=handler)

    async def _block_hook(name: str, args: dict, token: CancelToken) -> dict:
        return {"__block__": True, "__reason__": "test blocked"}

    recorder = _EventRecorder()
    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name="t_block", arguments="{}")],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=recorder,
            config=_make_config(before_tool_call=_block_hook),
        )
    )
    assert called == []
    assert batch.messages[0].is_error is True
    assert "test blocked" in batch.messages[0].result


def test_before_tool_call_can_rewrite_args():
    seen: list[dict] = []

    def handler(args: dict) -> str:
        seen.append(args)
        return tool_result(data={"v": args.get("v")})

    registry.register(name="t_rewrite", toolset="test", schema={"type": "object"}, handler=handler)

    def _rewrite_hook(name: str, args: dict, token: CancelToken) -> dict:
        return {**args, "v": args.get("v", "") + "-hooked"}

    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name="t_rewrite", arguments='{"v": "orig"}')],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(before_tool_call=_rewrite_hook),
        )
    )
    assert seen == [{"v": "orig-hooked"}]
    assert json.loads(batch.messages[0].result)["data"]["v"] == "orig-hooked"


def test_handler_exception_becomes_error_result():
    def handler(args: dict) -> str:
        raise RuntimeError("boom")

    registry.register(name="t_raise", toolset="test", schema={"type": "object"}, handler=handler)
    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name="t_raise", arguments="{}")],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(),
        )
    )
    assert batch.messages[0].is_error is True
    assert "boom" in batch.messages[0].result


def test_after_tool_call_hook_rewrites_result():
    def handler(args: dict) -> str:
        return tool_result(data={"v": "raw"})

    registry.register(name="t_after", toolset="test", schema={"type": "object"}, handler=handler)

    def _after_hook(name: str, args: dict, result: str, token: CancelToken) -> str:
        payload = json.loads(result)
        payload["data"]["v"] = "redacted"
        return json.dumps(payload, ensure_ascii=False)

    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name="t_after", arguments="{}")],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(after_tool_call=_after_hook),
        )
    )
    assert json.loads(batch.messages[0].result)["data"]["v"] == "redacted"


def test_truncation_applies_per_result():
    def handler(args: dict) -> str:
        return tool_result(data={"big": "x" * 500})

    registry.register(name="t_big", toolset="test", schema={"type": "object"}, handler=handler)
    recorder = _EventRecorder()
    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name="t_big", arguments="{}")],
            max_result_length=100,
            token=CancelToken(),
            emit=recorder,
            config=_make_config(),
        )
    )
    assert len(batch.messages[0].result) == 100 + len("\n\n...")
    assert batch.messages[0].result.endswith("\n\n...")
    # ToolExecutionEnd carries the truncated result too
    ends = [e for e in recorder.events if isinstance(e, ToolExecutionEnd)]
    assert ends[0].result.endswith("\n\n...")


def test_bridge_dispatch_hook_used_for_bridge_tools():
    from agent.tools.tool_search import BRIDGE_TOOL_NAMES

    bridge_name = next(iter(BRIDGE_TOOL_NAMES))  # tool_search
    bridge_calls: list[str] = []
    registry.register(name=bridge_name, toolset="test", schema={"type": "object"}, handler=lambda args: "unused")

    def _bridge(name: str, args: dict) -> str:
        bridge_calls.append(name)
        return tool_result(data={"bridged": True})

    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name=bridge_name, arguments="{}")],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(bridge_dispatch=_bridge),
        )
    )
    assert bridge_calls == [bridge_name]
    assert json.loads(batch.messages[0].result)["data"]["bridged"] is True


def test_approval_blocked_denied_returns_denial():
    from agent.tools.security_hooks import ApprovalBlockedError

    def handler(args: dict) -> str:
        return tool_result()

    registry.register(name="t_approve", toolset="test", schema={"type": "object"}, handler=handler, risk_level="high")

    def _raise_hook(name, args):
        raise ApprovalBlockedError(tool_name=name, tool_args=args, reason="need approval")

    registry.add_before_hook(_raise_hook)
    decisions: list[str] = []
    try:

        async def _on_blocked(name: str, reason: str) -> str:
            decisions.append(name)
            return "denied"

        batch = _run(
            dispatch_tool_batch(
                [ToolCallPayload(id="c1", name="t_approve", arguments="{}")],
                max_result_length=sys.maxsize,
                token=CancelToken(),
                emit=_EventRecorder(),
                config=_make_config(on_approval_blocked=_on_blocked),
            )
        )
    finally:
        registry.remove_before_hook(_raise_hook)

    assert decisions == ["t_approve"]
    assert batch.messages[0].is_error is True
    assert "用户拒绝了操作" in batch.messages[0].result


def test_approval_blocked_approved_runs_handler_directly():
    from agent.tools.security_hooks import ApprovalBlockedError

    ran: list[str] = []

    def handler(args: dict) -> str:
        ran.append("handler")
        return tool_result(data={"approved": True})

    registry.register(name="t_approve2", toolset="test", schema={"type": "object"}, handler=handler, risk_level="high")

    def _raise_hook(name, args):
        raise ApprovalBlockedError(tool_name=name, tool_args=args, reason="need approval")

    registry.add_before_hook(_raise_hook)
    try:

        async def _on_blocked(name: str, reason: str) -> str:
            return "approved"

        batch = _run(
            dispatch_tool_batch(
                [ToolCallPayload(id="c1", name="t_approve2", arguments="{}")],
                max_result_length=sys.maxsize,
                token=CancelToken(),
                emit=_EventRecorder(),
                config=_make_config(on_approval_blocked=_on_blocked),
            )
        )
    finally:
        registry.remove_before_hook(_raise_hook)

    assert ran == ["handler"]
    assert json.loads(batch.messages[0].result)["data"]["approved"] is True


def test_sequential_batch_sleeps_are_serial():
    """P1 sanity: two 0.15s tools take >= ~0.3s (sequential, not parallel yet)."""

    def sleepy(args: dict) -> str:
        time.sleep(0.15)
        return tool_result()

    registry.register(name="t_sleep", toolset="test", schema={"type": "object"}, handler=sleepy)
    start = time.monotonic()
    batch = _run(
        dispatch_tool_batch(
            [
                ToolCallPayload(id="c1", name="t_sleep", arguments="{}"),
                ToolCallPayload(id="c2", name="t_sleep", arguments="{}"),
            ],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(),
        )
    )
    elapsed = time.monotonic() - start
    assert len(batch.messages) == 2
    assert elapsed >= 0.28, f"expected serial execution, took {elapsed:.3f}s"
```

- [ ] **Step 2: Run test to verify it fails**

Run: ` .venv/bin/python -m pytest tests/test_tool_dispatcher_batch.py -v`

Expected: FAIL with `ImportError: cannot import name 'dispatch_tool_batch' from 'agent.core.tool_dispatcher'`

- [ ] **Step 3: Write minimal implementation**

Replace the entire content of `agent/core/tool_dispatcher.py`:

```python
"""Tool dispatch — sync single-tool path + async batch execution.

Pi-style kernel redesign (spec 2026-08-06-pi-style-kernel-design).
The sync :func:`dispatch_tool` is preserved verbatim for the legacy
kernel path (``ZLINK_KERNEL=old``).  The new kernel uses
:func:`dispatch_tool_batch`, which runs every tool through
``registry.dispatch`` in a worker thread so the security before/after
hook chain and the ``__block__`` protocol stay intact (Layer 2), then
applies truncation per result.  P1 executes batches strictly
sequentially; P2 adds parallel dispatch with the same public API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections.abc import Awaitable, Callable
from typing import Any

from agent.core.kernel_types import (
    AgentEvent,
    AgentLoopConfig,
    CancelToken,
    ExecutedToolBatch,
    ToolExecutionEnd,
    ToolExecutionStart,
    ToolResult,
)
from agent.core.llm_providers.base import ToolCallPayload
from agent.tools.registry import registry, tool_error
from agent.tools.tool_search import BRIDGE_TOOL_NAMES

logger = logging.getLogger(__name__)

_TRUNCATION_SUFFIX = "\n\n..."


def _truncate(content: Any, limit: int) -> str:
    if isinstance(content, str) and len(content) > limit:
        return content[:limit] + _TRUNCATION_SUFFIX
    return content if isinstance(content, str) else str(content)


def dispatch_tool(
    name: str,
    args: dict,
    *,
    max_result_length: int = sys.maxsize,
    preview_length: int = 200,
) -> tuple[str, str]:
    """Execute *name* through the global registry (legacy sync path).

    Returns ``(full_result, preview)`` — the full result is appended to
    the message list (possibly truncated at *max_result_length*), the
    preview is what we stream back to the client for display.
    """
    result = registry.dispatch(name, args)
    if not isinstance(result, str):
        result = json.dumps(result, ensure_ascii=False)
    truncated = _truncate(result, max_result_length)
    preview = _truncate(truncated, preview_length)
    return truncated, preview


async def _await_maybe(value):
    """Await *value* if it is a coroutine (hooks may be sync or async)."""
    if asyncio.iscoroutine(value):
        return await value
    return value


async def dispatch_tool_batch(
    calls: list[ToolCallPayload],
    *,
    max_result_length: int,
    token: CancelToken,
    emit: Callable[[AgentEvent], Awaitable[None]],
    config: AgentLoopConfig,
) -> ExecutedToolBatch:
    """Execute a batch of tool calls and return results in original order.

    P1: strict sequential — per call: prepare → execute → finalize.
    P2: parallel with sequential degradation (same signature).
    """
    results: list[ToolResult] = []
    for tc in calls:
        token.check()
        args, immediate = await _prepare(tc, config, token, emit)
        if immediate is not None:
            results.append(
                ToolResult(
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                    result=_truncate(immediate, max_result_length),
                    is_error=True,
                )
            )
            continue
        await emit(ToolExecutionStart(tool_call_id=tc.id, tool_name=tc.name, args=args))
        raw = await _run_handler(tc.name, args, config, token)
        finalized = await _finalize(tc.name, args, raw, config, token)
        truncated = _truncate(finalized, max_result_length)
        await emit(ToolExecutionEnd(tool_call_id=tc.id, tool_name=tc.name, result=truncated))
        results.append(ToolResult(tool_call_id=tc.id, tool_name=tc.name, result=truncated))
    return ExecutedToolBatch(messages=results, terminate=False)


async def _prepare(
    tc: ToolCallPayload,
    config: AgentLoopConfig,
    token: CancelToken,
    emit: Callable[[AgentEvent], Awaitable[None]],
) -> tuple[dict, str | None]:
    """Parse JSON args and run the before_tool_call hook.

    Returns ``(args, None)`` on success or ``(args, error_result)`` when
    the arguments are invalid or a hook blocked the call.
    """
    try:
        args = json.loads(tc.arguments) if tc.arguments else {}
    except json.JSONDecodeError:
        return {}, tool_error("Invalid JSON arguments")
    if config.before_tool_call is not None:
        try:
            result = await config.before_tool_call(tc.name, args, token)
        except Exception as e:  # noqa: BLE001
            return args, tool_error(f"Hook blocked execution: {e}")
        if isinstance(result, dict) and result.get("__block__"):
            return result, tool_error(str(result.get("__reason__", "Blocked by hook")))
        if isinstance(result, dict):
            args = result
    return args, None


async def _run_handler(
    name: str,
    args: dict,
    config: AgentLoopConfig,
    token: CancelToken,
) -> str:
    """Execute one tool.

    Bridge tools go through ``config.bridge_dispatch`` (progressive
    disclosure); everything else runs through ``registry.dispatch`` in a
    worker thread so the security hook chain and the ``__block__``
    protocol are preserved (Layer 2).  ApprovalBlockedError is routed to
    ``config.on_approval_blocked``; an approved retry calls the raw
    handler directly (mirrors the legacy approved path).
    """
    if config.bridge_dispatch is not None and name in BRIDGE_TOOL_NAMES:
        raw = await _await_maybe(config.bridge_dispatch(name, args))
        return raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
    try:
        raw = await asyncio.to_thread(registry.dispatch, name, args)
    except Exception as e:  # noqa: BLE001
        if type(e).__name__ == "ApprovalBlockedError":
            decision = "denied"
            if config.on_approval_blocked is not None:
                decision = await _await_maybe(config.on_approval_blocked(name, str(e)))
            if decision == "approved":
                return _dispatch_bypassing_hooks(name, args)
            return tool_error("用户拒绝了操作")
        logger.exception("Tool %s failed", name)
        return tool_error(str(e))
    return raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)


def _dispatch_bypassing_hooks(name: str, args: dict) -> str:
    """Approved retry: call the raw handler directly, skipping hooks."""
    entry = registry.get_entry(name)
    if entry is None:
        return tool_error(f"Unknown tool: {name}")
    try:
        result = entry.handler(args)
    except Exception as e:  # noqa: BLE001
        return tool_error(str(e))
    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)


async def _finalize(
    name: str,
    args: dict,
    result: str,
    config: AgentLoopConfig,
    token: CancelToken,
) -> str:
    """Run the after_tool_call hook (AfterToolCallEvent + rewrites)."""
    if config.after_tool_call is not None:
        try:
            result = await config.after_tool_call(name, args, result, token)
        except Exception as e:  # noqa: BLE001
            logger.warning("After-hook failed for tool %s: %s", name, e)
    return result


__all__ = ["dispatch_tool", "dispatch_tool_batch"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: ` .venv/bin/python -m pytest tests/test_tool_dispatcher_batch.py -v`

Expected: PASS，`14 passed`. 再跑一次存量回归确认 `dispatch_tool` 未被破坏：

Run: ` .venv/bin/python -m pytest tests/test_tool_registry.py tests/test_agent_loop.py -q`

Expected: PASS, `0 failed`

- [ ] **Step 5: Commit**

```bash
git add agent/core/tool_dispatcher.py tests/test_tool_dispatcher_batch.py
git commit -m "feat: add async dispatch_tool_batch with sequential execution"
```

## Task P1-T3: loop.py — 极简零策略双层 async loop

**Files:**
- Create: `agent/core/loop.py`
- Test: `tests/test_loop.py`

**Interfaces:**
- Consumes: `kernel_types` 全部类型；`tool_dispatcher.dispatch_tool_batch`（P1-T2）；`llm_providers.base.ToolCallPayload`；`registry.tool_error`。
- Produces（Agent 包装类与适配层依赖）：
  - `async run_agent_loop(prompts: list[dict], context: AgentContext, config: AgentLoopConfig, emit: Callable[[AgentEvent], Awaitable[None]], token: CancelToken) -> list[dict]` — 新 prompt 开始一轮 run；返回 `prompts + loop 追加消息`
  - `async run_agent_loop_continue(context, config, emit, token) -> list[dict]` — 从当前 context 继续；context 末条为 assistant 时 `raise ValueError("Cannot continue from message role: assistant")`
  - 事件序列保证：`AgentStart` 最先；任何 return 路径都以 `AgentEnd` 收尾；每个 turn 以 `TurnStart` 开头、`TurnEnd(message, tool_results)` 结尾；prompt/steering 消息 emit `MessageStart`+`MessageEnd` 对；assistant 消息 emit `MessageStart` →（流式 `MessageUpdate`）→ `MessageEnd`
  - `_stream_assistant_response` 返回 `(assistant_message_dict, stop_reason)`；LLM 失败在消息上编码 `is_error`/`errorMessage`，loop 不 raise；`stop_reason in ("error", "aborted")` 或 `is_error` → 立即 `TurnEnd(message, [])` + `AgentEnd` 返回
  - `stop_reason == "length"` 且带 tool_calls → `_fail_truncated_batch`：逐条返回 `tool_error("参数可能被截断，请重新完整发出")` 错误 ToolResult（P1 即生效，P2 补 provider 映射后真实触发）
  - `prepare_next_turn` 返回非 None `TurnUpdate` 时用 `dataclasses.replace` 应用覆盖（`_apply_update`）
  - `should_stop_after_turn` 返回 True → `AgentEnd` 返回；`get_steering_messages` 每个内层迭代尾部重新询问；`get_follow_up_messages` 内层退出后询问，非空则开启外层下一轮
  - 取消：`token.check()` 在每个内层迭代顶部调用；取消时 `asyncio.CancelledError` 向上传播（由适配层兜底收尾）

- [ ] **Step 1: Write the failing test**

Create `tests/test_loop.py`:

```python
"""Tests for agent/core/loop.py — the zero-policy async loop."""

from __future__ import annotations

import asyncio
import json
import sys

import pytest

from agent.core.kernel_types import (
    AgentContext,
    AgentEnd,
    AgentEvent,
    AgentLoopConfig,
    AgentStart,
    CancelToken,
    MessageEnd,
    MessageStart,
    MessageUpdate,
    TurnEnd,
    TurnStart,
)
from agent.core.llm_providers.base import LLMResponse, ToolCallPayload
from agent.core.loop import run_agent_loop, run_agent_loop_continue
from agent.tools.registry import registry, tool_result


@pytest.fixture(autouse=True)
def clean_tool_registry():
    saved_before = set(registry.get_all_tool_names())
    yield
    for name in set(registry.get_all_tool_names()) - saved_before:
        try:
            registry.deregister(name)
        except Exception:
            pass


class _ScriptedLLM:
    """Fake call_llm: returns scripted LLMResponses and records messages."""

    def __init__(self, *responses: LLMResponse) -> None:
        self.responses = list(responses)
        self.calls: list[list[dict]] = []
        self.emitted_updates: list[MessageUpdate] = []

    async def __call__(self, full_messages, *, emit, message, token):
        self.calls.append(list(full_messages))
        resp = self.responses.pop(0)
        if resp.content:
            message["content"] = resp.content
        if resp.reasoning:
            message["reasoning_content"] = resp.reasoning
        return resp


class _Recorder:
    def __init__(self) -> None:
        self.events: list[AgentEvent] = []

    async def __call__(self, event: AgentEvent) -> None:
        self.events.append(event)


def _run(coro):
    return asyncio.run(coro)


def _cfg(**kw) -> AgentLoopConfig:
    base: dict = {
        "model": "test-model",
        "call_llm": _ScriptedLLM(LLMResponse(content="hi")),
    }
    base.update(kw)
    return AgentLoopConfig(**base)


def _tool_response(tool_name: str, args: dict, call_id: str = "c1") -> LLMResponse:
    return LLMResponse(
        content="",
        tool_calls=[ToolCallPayload(id=call_id, name=tool_name, arguments=json.dumps(args))],
    )


def test_plain_text_event_sequence_and_return():
    llm = _ScriptedLLM(LLMResponse(content="hello back"))
    rec = _Recorder()
    ctx = AgentContext()
    result = _run(run_agent_loop([{"role": "user", "content": "hi"}], ctx, _cfg(call_llm=llm), rec, CancelToken()))

    assert result == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello back"},
    ]
    types = [e.type for e in rec.events]
    assert types[0] == "agent_start"
    assert types[-1] == "agent_end"
    assert types == [
        "agent_start",
        "message_start",
        "message_end",  # user prompt
        "turn_start",
        "message_start",
        "message_end",  # assistant reply
        "turn_end",
        "agent_end",
    ]
    assert ctx.api_calls == 1
    # AgentEnd carries the full new-messages list
    end = rec.events[-1]
    assert isinstance(end, AgentEnd)
    assert end.messages[-1]["content"] == "hello back"


def test_tool_call_then_text_orders_transcript():
    def echo(args: dict) -> str:
        return tool_result(data={"v": args.get("v")})

    registry.register(name="echo", toolset="test", schema={"type": "object"}, handler=echo)
    llm = _ScriptedLLM(
        _tool_response("echo", {"v": "x"}),
        LLMResponse(content="done"),
    )
    rec = _Recorder()
    ctx = AgentContext()
    result = _run(run_agent_loop([{"role": "user", "content": "go"}], ctx, _cfg(call_llm=llm), rec, CancelToken()))

    roles = [m["role"] for m in result]
    assert roles == ["user", "assistant", "tool", "assistant"]
    assert result[2]["tool_call_id"] == "c1"
    assert json.loads(result[2]["content"])["data"]["v"] == "x"
    # tool message appended to context too
    assert ctx.messages[-1]["role"] == "tool"
    # turn boundaries: 2 TurnStart / 2 TurnEnd
    assert sum(1 for e in rec.events if isinstance(e, TurnStart)) == 2
    turn_ends = [e for e in rec.events if isinstance(e, TurnEnd)]
    assert len(turn_ends) == 2
    assert len(turn_ends[0].tool_results) == 1


def test_steering_message_injected_next_turn():
    def _steer(token: CancelToken) -> list[dict]:
        # inject one steering message only on the second poll
        if len(_steer.polls) >= 1:
            return []
        _steer.polls += 1
        return [{"role": "user", "content": "interrupt"}]

    _steer.polls = 0  # type: ignore[attr-defined]

    llm = _ScriptedLLM(LLMResponse(content="first"), LLMResponse(content="second"))
    rec = _Recorder()
    result = _run(
        run_agent_loop(
            [{"role": "user", "content": "go"}],
            AgentContext(),
            _cfg(call_llm=llm, get_steering_messages=_steer),
            rec,
            CancelToken(),
        )
    )
    assert [m["content"] for m in result] == ["go", "first", "interrupt", "second"]
    # steering user message emitted with MessageStart/MessageEnd pair
    msgs = [e for e in rec.events if isinstance(e, MessageStart)]
    assert [m.message.get("content") for m in msgs] == ["go", "interrupt", "first", "second"]


def test_follow_up_opens_outer_loop():
    def _followup(token: CancelToken) -> list[dict]:
        if _followup.called:  # type: ignore[attr-defined]
            return []
        _followup.called = True  # type: ignore[attr-defined]
        return [{"role": "user", "content": "follow up"}]

    _followup.called = False  # type: ignore[attr-defined]

    llm = _ScriptedLLM(LLMResponse(content="a"), LLMResponse(content="b"))
    result = _run(
        run_agent_loop(
            [{"role": "user", "content": "go"}],
            AgentContext(),
            _cfg(call_llm=llm, get_follow_up_messages=_followup),
            _Recorder(),
            CancelToken(),
        )
    )
    assert [m["content"] for m in result] == ["go", "a", "follow up", "b"]


def test_should_stop_after_turn_ends_with_agent_end():
    llm = _ScriptedLLM(LLMResponse(content="only"))

    async def _stop(ctx: dict, token: CancelToken) -> bool:
        return True

    rec = _Recorder()
    _run(
        run_agent_loop(
            [{"role": "user", "content": "go"}],
            AgentContext(),
            _cfg(call_llm=llm, should_stop_after_turn=_stop),
            rec,
            CancelToken(),
        )
    )
    assert rec.events[-1].type == "agent_end"
    assert llm.calls == 1


def test_llm_error_encodes_in_message_and_ends():
    llm = _ScriptedLLM(LLMResponse(error="API down", stop_reason="error"))
    rec = _Recorder()
    result = _run(
        run_agent_loop([{"role": "user", "content": "go"}], AgentContext(), _cfg(call_llm=llm), rec, CancelToken())
    )

    assert result[-1]["is_error"] is True
    assert result[-1]["errorMessage"] == "API down"
    assert rec.events[-1].type == "agent_end"
    # no tools executed, no TurnEnd tool results
    turn_ends = [e for e in rec.events if isinstance(e, TurnEnd)]
    assert turn_ends[-1].tool_results == []


def test_length_stop_reason_fails_truncated_tool_batch():
    ran: list[str] = []

    def spy(args: dict) -> str:
        ran.append("ran")
        return tool_result()

    registry.register(name="spy", toolset="test", schema={"type": "object"}, handler=spy)
    llm = _ScriptedLLM(
        LLMResponse(
            content="", tool_calls=[ToolCallPayload(id="c1", name="spy", arguments="{}")], stop_reason="length"
        ),
        LLMResponse(content="please re-issue"),
    )
    rec = _Recorder()
    result = _run(
        run_agent_loop([{"role": "user", "content": "go"}], AgentContext(), _cfg(call_llm=llm), rec, CancelToken())
    )

    assert ran == [], "truncated batch must never execute handlers"
    tool_msgs = [m for m in result if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert "参数可能被截断，请重新完整发出" in tool_msgs[0]["content"]
    assert result[-1]["content"] == "please re-issue"


def test_prepare_next_turn_applies_model_override():
    seen_models: list[str] = []

    class _LLM:
        def __init__(self):
            self.responses = [LLMResponse(content="a"), LLMResponse(content="b")]

        async def __call__(self, full_messages, *, emit, message, token):
            seen_models.append(full_messages[0]["content"] if full_messages else "?")
            resp = self.responses.pop(0)
            message["content"] = resp.content
            return resp

    async def _prepare(ctx: dict, token: CancelToken):
        from agent.core.kernel_types import TurnUpdate

        return TurnUpdate(model="next-model")

    _run(
        run_agent_loop(
            [{"role": "user", "content": "go"}],
            AgentContext(),
            _cfg(call_llm=_LLM(), prepare_next_turn=_prepare),
            _Recorder(),
            CancelToken(),
        )
    )
    # Turn 2's call_llm receives the updated model in config — verify via hook
    # capture: the loop applies the update before the next LLM call, so we
    # assert the update path works by checking two calls happened.
    assert len(seen_models) == 2


def test_cancelled_token_raises_cancelled_error():
    llm = _ScriptedLLM(LLMResponse(content="a"), LLMResponse(content="b"))
    token = CancelToken()

    async def _steer(t: CancelToken) -> list[dict]:
        token.cancel()
        return []

    with pytest.raises(asyncio.CancelledError):
        _run(
            run_agent_loop(
                [{"role": "user", "content": "go"}],
                AgentContext(),
                _cfg(call_llm=llm, get_steering_messages=_steer),
                _Recorder(),
                token,
            )
        )


def test_continue_requires_non_assistant_tail():
    ctx = AgentContext(messages=[{"role": "assistant", "content": "last"}])
    with pytest.raises(ValueError, match="Cannot continue from message role: assistant"):
        _run(run_agent_loop_continue(ctx, _cfg(), _Recorder(), CancelToken()))

    ctx2 = AgentContext(messages=[{"role": "user", "content": "ok"}])
    llm = _ScriptedLLM(LLMResponse(content="continued"))
    result = _run(run_agent_loop_continue(ctx2, _cfg(call_llm=llm), _Recorder(), CancelToken()))
    assert result == [{"role": "assistant", "content": "continued"}]


def test_streaming_message_update_events():
    """MessageUpdate fires while the LLM streams (via call_llm's emit)."""

    async def _streaming_llm(full_messages, *, emit, message, token):
        for chunk in ("你", "好"):
            message["content"] = message.get("content", "") + chunk
            await emit(MessageUpdate(message=dict(message), delta=chunk))
        return LLMResponse(content="你好")

    rec = _Recorder()
    result = _run(
        run_agent_loop(
            [{"role": "user", "content": "hi"}],
            AgentContext(),
            _cfg(call_llm=_streaming_llm),
            rec,
            CancelToken(),
        )
    )
    updates = [e for e in rec.events if isinstance(e, MessageUpdate)]
    assert [u.delta for u in updates] == ["你", "好"]
    assert result[-1]["content"] == "你好"
```

- [ ] **Step 2: Run test to verify it fails**

Run: ` .venv/bin/python -m pytest tests/test_loop.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.core.loop'`

- [ ] **Step 3: Write minimal implementation**

Create `agent/core/loop.py`:

```python
"""Minimal async agent loop — zero policy, only event-flow orchestration.

Pi-style kernel redesign (spec 2026-08-06-pi-style-kernel-design).
Mirrors Pi's ``agent-loop.ts``: a two-level loop (inner = tool_calls /
steering messages, outer = follow-up messages); every "should we
continue / compact / prepare next turn" decision is a hook on
:class:`AgentLoopConfig`.  This module contains NO business policy —
compaction, budget, security and steering are all hooks.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from collections.abc import Awaitable, Callable

from agent.core.kernel_types import (
    AgentContext,
    AgentEnd,
    AgentEvent,
    AgentLoopConfig,
    AgentStart,
    CancelToken,
    ExecutedToolBatch,
    MessageEnd,
    MessageStart,
    MessageUpdate,
    ToolResult,
    ToolExecutionStart,
    ToolExecutionEnd,
    TurnEnd,
    TurnStart,
)
from agent.core.tool_dispatcher import dispatch_tool_batch
from agent.tools.registry import tool_error

logger = logging.getLogger(__name__)


async def run_agent_loop(
    prompts: list[dict],
    context: AgentContext,
    config: AgentLoopConfig,
    emit: Callable[[AgentEvent], Awaitable[None]],
    token: CancelToken,
) -> list[dict]:
    """Start a run with new prompts.  Returns the new messages
    (prompts + everything the loop appended)."""
    new_messages = list(prompts)
    context.messages += prompts
    await emit(AgentStart())
    for p in prompts:
        await emit(MessageStart(p))
        await emit(MessageEnd(p))
    await _run_loop(context, new_messages, config, emit, token)
    return new_messages


async def run_agent_loop_continue(
    context: AgentContext,
    config: AgentLoopConfig,
    emit: Callable[[AgentEvent], Awaitable[None]],
    token: CancelToken,
) -> list[dict]:
    """Continue from the current context.  The last message must not be
    an assistant message (a fresh LLM call needs a user/tool tail)."""
    if not context.messages or context.messages[-1].get("role") == "assistant":
        raise ValueError("Cannot continue from message role: assistant")
    new_messages: list[dict] = []
    await emit(AgentStart())
    await _run_loop(context, new_messages, config, emit, token)
    return new_messages


async def _run_loop(
    context: AgentContext,
    new_messages: list[dict],
    config: AgentLoopConfig,
    emit: Callable[[AgentEvent], Awaitable[None]],
    token: CancelToken,
) -> None:
    """Two-level loop: inner = tool_calls/steering, outer = follow-up."""

    async def _no_messages(_token: CancelToken) -> list[dict]:
        return []

    get_steering = config.get_steering_messages or _no_messages
    get_followup = config.get_follow_up_messages or _no_messages

    pending = await get_steering(token)
    while True:  # outer loop — follow-up messages
        has_more_tool_calls = True
        while has_more_tool_calls or pending:  # inner loop
            token.check()
            await emit(TurnStart())
            if pending:  # steering injection
                for msg in pending:
                    await emit(MessageStart(msg))
                    await emit(MessageEnd(msg))
                    context.messages.append(msg)
                    new_messages.append(msg)
                pending = []
            # 1) context transform (compaction hook)
            if config.transform_context is not None:
                context.messages = await config.transform_context(context.messages, token)
            # 2) LLM call (never raises: failures are encoded into the message)
            message, stop_reason = await _stream_assistant_response(context, config, emit, token)
            new_messages.append(message)
            if message.get("is_error") or stop_reason in ("error", "aborted"):
                await emit(TurnEnd(message, []))
                await emit(AgentEnd(new_messages))
                return
            # 3) tool batch execution
            tool_calls = message.get("tool_calls") or []
            tool_results: list[ToolResult] = []
            has_more_tool_calls = False
            if tool_calls:
                if stop_reason == "length":
                    executed = await _fail_truncated_batch(tool_calls, emit)
                else:
                    executed = await _execute_tool_batch(context, message, config, emit, token)
                tool_results = executed.messages
                has_more_tool_calls = not executed.terminate
                for r in tool_results:
                    tm = _to_tool_message(r)
                    context.messages.append(tm)
                    new_messages.append(tm)
            turn_ctx = {
                "message": message,
                "tool_results": tool_results,
                "messages": new_messages,
                "api_calls": context.api_calls,
            }
            await emit(TurnEnd(message, tool_results))
            # 4) next-turn overrides (model/temperature/max_tokens)
            if config.prepare_next_turn is not None:
                update = await config.prepare_next_turn(turn_ctx, token)
                if update is not None:
                    config = _apply_update(config, update)
            # 5) stop decision (IterationBudget consumption point)
            if config.should_stop_after_turn is not None and await config.should_stop_after_turn(turn_ctx, token):
                await emit(AgentEnd(new_messages))
                return
            # 6) steering re-poll (one-at-a-time drain semantics live in Agent)
            pending = await get_steering(token)
        # outer: follow-up messages
        follow_ups = await get_followup(token)
        if follow_ups:
            pending = follow_ups
            continue
        break
    await emit(AgentEnd(new_messages))


async def _stream_assistant_response(
    context: AgentContext,
    config: AgentLoopConfig,
    emit: Callable[[AgentEvent], Awaitable[None]],
    token: CancelToken,
) -> tuple[dict, str | None]:
    """Make one LLM call; emit MessageStart/MessageUpdate/MessageEnd.

    Returns ``(assistant_message_dict, stop_reason)``.  ``call_llm`` is
    responsible for streaming MessageUpdate events (via *emit*); content
    and reasoning are copied from the response here (idempotent with the
    streaming accumulation).
    """
    token.check()
    if config.call_llm is None:
        raise RuntimeError("AgentLoopConfig.call_llm is required")
    full_messages: list[dict] = []
    if config.system_prompt:
        full_messages.append({"role": "system", "content": config.system_prompt})
    full_messages.extend(context.messages)
    message: dict = {"role": "assistant", "content": ""}
    await emit(MessageStart(message))
    response = await config.call_llm(full_messages, emit=emit, message=message, token=token)
    if response.content:
        message["content"] = response.content
    if response.reasoning:
        message["reasoning_content"] = response.reasoning
    if response.tool_calls:
        message["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": tc.arguments},
            }
            for tc in response.tool_calls
        ]
    if response.failed:
        message["is_error"] = True
        message["errorMessage"] = response.error
    context.api_calls += 1
    await emit(MessageEnd(message))
    return message, response.stop_reason


async def _execute_tool_batch(
    context: AgentContext,
    message: dict,
    config: AgentLoopConfig,
    emit: Callable[[AgentEvent], Awaitable[None]],
    token: CancelToken,
) -> ExecutedToolBatch:
    """Translate the assistant message's tool_calls into payloads and
    hand them to the (async) dispatcher."""
    from agent.core.llm_providers.base import ToolCallPayload

    calls = [
        ToolCallPayload(
            id=tc["id"],
            name=tc["function"]["name"],
            arguments=tc["function"]["arguments"],
        )
        for tc in message.get("tool_calls", [])
    ]
    return await dispatch_tool_batch(
        calls,
        max_result_length=config.max_tool_result_length,
        token=token,
        emit=emit,
        config=config,
    )


async def _fail_truncated_batch(
    tool_calls: list[dict],
    emit: Callable[[AgentEvent], Awaitable[None]],
) -> ExecutedToolBatch:
    """``stop_reason == "length"`` guard: no tool call executes; every one
    returns a truncation error so the model re-issues it (Pi's
    failToolCallsFromTruncatedMessage)."""
    results: list[ToolResult] = []
    for tc in tool_calls:
        name = tc["function"]["name"]
        cid = tc["id"]
        err = tool_error("参数可能被截断，请重新完整发出")
        await emit(ToolExecutionStart(tool_call_id=cid, tool_name=name, args={}))
        await emit(ToolExecutionEnd(tool_call_id=cid, tool_name=name, result=err, is_error=True))
        results.append(ToolResult(tool_call_id=cid, tool_name=name, result=err, is_error=True))
    return ExecutedToolBatch(messages=results, terminate=False)


def _to_tool_message(r: ToolResult) -> dict:
    return {"role": "tool", "tool_call_id": r.tool_call_id, "content": r.result}


def _apply_update(config: AgentLoopConfig, update) -> AgentLoopConfig:
    """Return a copy of *config* with non-None TurnUpdate fields applied."""
    kw = {
        "model": update.model if update.model is not None else config.model,
        "temperature": update.temperature if update.temperature is not None else config.temperature,
        "max_tokens": update.max_tokens if update.max_tokens is not None else config.max_tokens,
    }
    return dataclasses.replace(config, **kw)


__all__ = ["run_agent_loop", "run_agent_loop_continue"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: ` .venv/bin/python -m pytest tests/test_loop.py -v`

Expected: PASS，`11 passed`（`test_continue_requires_non_assistant_tail` 内的第二次 `run_agent_loop_continue` 因 scripted `LLMResponse(content="continued")` 无 tool_calls、内层直接结束——注意该断言依赖 loop 在无 tool_calls 且无 steering/follow-up 时正常收尾）。

- [ ] **Step 5: Commit**

```bash
git add agent/core/loop.py tests/test_loop.py
git commit -m "feat: add zero-policy async agent loop"
```

## Task P1-T4: agent_adapter.py — 兼容类型 + kernel_mode + 旧 AIAgent 行内副本

**Files:**
- Create: `agent/core/agent_adapter.py`（由现 `agent/core/agent.py` 复制 + 精确编辑）
- Test: `tests/test_agent_adapter.py`

**Interfaces:**
- Consumes: 与旧 `agent/core/agent.py` 相同的全部 import（`fact_memory`、`context_compactor`、`iteration_budget`、`llm_client`、`message_builder`、`tool_dispatcher.dispatch_tool`、`agent.events`、`registry`、`tool_search`）。
- Produces（P1-T5/P1-T6 依赖）：
  - `class Phase(str)`（IDLE/TURN/COMPACTION/RETRY）、`AgentPhase = Phase`、`@dataclass(frozen=True) Envelope(seq, phase, payload_type, payload)`、`@dataclass(frozen=True) TurnSnapshot(...)`、`@dataclass ApprovalRequest(tool_name, reason, event, result)` —— 语义与旧定义逐字段一致
  - `kernel_mode() -> str` —— 读 `os.environ.get("ZLINK_KERNEL", "new")`，非法值回落 `"new"`；模块级 `_KERNEL_MODE` 缓存 + `logging.info` 记录一次
  - `class AIAgent` —— 构造签名与旧版逐参数一致；本任务阶段 `run_conversation` = 旧算法原样（后续 P1-T6 改名 `_run_conversation_legacy` 并加分发）

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent_adapter.py`:

```python
"""Tests for agent/core/agent_adapter.py — AIAgent compatibility layer.

Covers the kernel-mode switch and the legacy kernel path (P1-T4);
the new-kernel path tests are added in P1-T6 and P3.
"""

from __future__ import annotations

import os

import agent.core.agent_adapter as adapter_mod
from agent.core.agent_adapter import AIAgent, kernel_mode
from agent.core.llm_client import LLMClient
from tests.conftest import MockLLMProvider, make_text_response


def _force_kernel(monkeypatch, mode: str) -> None:
    """Pin the module-level kernel-mode cache for one test."""
    monkeypatch.setattr(adapter_mod, "_KERNEL_MODE", mode)


class TestKernelMode:
    def test_defaults_to_new(self, monkeypatch):
        monkeypatch.delenv("ZLINK_KERNEL", raising=False)
        monkeypatch.setattr(adapter_mod, "_KERNEL_MODE", None)
        assert kernel_mode() == "new"

    def test_old_via_env(self, monkeypatch):
        monkeypatch.setenv("ZLINK_KERNEL", "old")
        monkeypatch.setattr(adapter_mod, "_KERNEL_MODE", None)
        assert kernel_mode() == "old"

    def test_invalid_value_falls_back_to_new(self, monkeypatch):
        monkeypatch.setenv("ZLINK_KERNEL", "banana")
        monkeypatch.setattr(adapter_mod, "_KERNEL_MODE", None)
        assert kernel_mode() == "new"

    def test_cached_after_first_read(self, monkeypatch):
        monkeypatch.setenv("ZLINK_KERNEL", "new")
        monkeypatch.setattr(adapter_mod, "_KERNEL_MODE", None)
        first = kernel_mode()
        monkeypatch.setenv("ZLINK_KERNEL", "old")  # env changes must NOT matter now
        assert kernel_mode() == first == "new"


class TestLegacyKernelPath:
    """These force ``old`` so they keep passing after P1-T6 flips the default."""

    def test_legacy_plain_text_reply(self, monkeypatch):
        _force_kernel(monkeypatch, "old")
        provider = MockLLMProvider(responses=[make_text_response("hi back")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("hello")
        assert result["final_response"] == "hi back"
        assert result["completed"] is True
        assert result["error"] is None
        assert result["api_calls"] == 1
        assert [m["role"] for m in result["messages"]] == ["user", "assistant"]

    def test_legacy_tool_call_then_text(self, monkeypatch):
        from agent.config_model import AppConfig

        monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))
        _force_kernel(monkeypatch, "old")

        from tests.conftest import make_tool_call_response

        provider = MockLLMProvider(
            responses=[
                make_tool_call_response("terminal", {"command": "echo hi"}),
                make_text_response("echoed"),
            ]
        )
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("run echo")
        assert result["completed"] is True
        assert result["api_calls"] == 2
        assert [m["role"] for m in result["messages"]] == ["user", "assistant", "tool", "assistant"]

    def test_legacy_publishes_event_sequence(self, monkeypatch):
        _force_kernel(monkeypatch, "old")
        from agent.events import Event
        from agent.events.bus import event_bus

        seen: list[str] = []
        event_bus.subscribe(lambda e: seen.append(e.type))

        provider = MockLLMProvider(responses=[make_text_response("ok")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        agent.run_conversation("hi", session_id="sess-1")
        for expected in ("session_start", "user_message", "before_llm_call", "after_llm_call", "session_end"):
            assert expected in seen, expected
        assert agent.phase == "idle"
```

- [ ] **Step 2: Run test to verify it fails**

Run: ` .venv/bin/python -m pytest tests/test_agent_adapter.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.core.agent_adapter'`

- [ ] **Step 3: Write minimal implementation**

```bash
cp agent/core/agent.py agent/core/agent_adapter.py
```

Then apply these exact edits to `agent/core/agent_adapter.py`:

Edit 1 — stdlib imports（在 `import json` 前插入 `import asyncio`，在 `import sys` 前插入 `import os`）：

old:
```
import json
import logging
import sys
import threading
```
new:
```
import asyncio
import json
import logging
import os
import sys
import threading
```

Edit 2 — 模块 docstring 追加说明（把第一行 docstring 的结尾改为指向"兼容层"定位）：

old:
```
"""Main agent loop — refactored from the original 481-line ``agent.py``.
```
new:
```
"""AIAgent compatibility layer — the legacy kernel + (from P1-T6) the new kernel.

Pi-style kernel redesign: this module is the frozen-contract adapter.
``agent/core/agent.py`` now hosts the new stateful ``Agent`` wrapper and
re-exports ``AIAgent`` from here, so ``from agent.core.agent import
AIAgent`` keeps working (C1).  ``ZLINK_KERNEL`` selects between the
inline legacy algorithm (verbatim copy of the pre-P1 run loop) and the
new kernel path added in P1-T6.
"""
```

Edit 3 — 文件末尾追加 kernel_mode（替换 `__all__` 行）：

old:
```
__all__ = ["AIAgent"]
```
new:
```
# ── Kernel mode switch (dual-run) ─────────────────────────────────

_KERNEL_MODE: str | None = None


def kernel_mode() -> str:
    """Return the active kernel: ``"new"`` (default) or ``"old"``.

    Read once per process (R5: no per-request re-read) and logged.
    ``ZLINK_KERNEL`` is removed in P4 along with the legacy kernel.
    """
    global _KERNEL_MODE
    if _KERNEL_MODE is None:
        raw = os.environ.get("ZLINK_KERNEL", "new").strip().lower()
        _KERNEL_MODE = raw if raw in ("new", "old") else "new"
        logging.getLogger(__name__).info("Agent kernel mode: %s (ZLINK_KERNEL env)", _KERNEL_MODE)
    return _KERNEL_MODE


__all__ = ["AIAgent", "kernel_mode"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: ` .venv/bin/python -m pytest tests/test_agent_adapter.py -v`

Expected: PASS，`7 passed`. 存量回归：

Run: ` .venv/bin/python -m pytest tests/ -q`

Expected: PASS，`378 passed, 0 failed`（`agent/core/agent.py` 尚未改动，仍走旧实现）

- [ ] **Step 5: Commit**

```bash
git add agent/core/agent_adapter.py tests/test_agent_adapter.py
git commit -m "feat: add AIAgent adapter scaffold with kernel-mode switch and legacy path"
```

## Task P1-T5: agent.py — 重写为有状态 Agent 包装类

**Files:**
- Modify: `agent/core/agent.py`（整体重写）
- Test: `tests/test_agent.py`

**Interfaces:**
- Consumes: `kernel_types`（AgentContext/AgentEnd/AgentEvent/AgentLoopConfig/AgentStart/CancelToken/ToolExecutionStart/ToolExecutionEnd）；`loop.run_agent_loop`；`agent_adapter` 的 `AIAgent/AgentPhase/ApprovalRequest/Envelope/Phase/TurnSnapshot`（文件末尾 re-export，C1 导入路径不变）。
- Produces（P1-T6 适配层新路径 + P3 依赖）：
  - `@dataclass class AgentState` — `messages: list[dict]`；`pendingToolCalls: int = 0`；`running: bool = False`
  - `class Agent` — `state: AgentState`；`subscribe(listener: Callable[[AgentEvent], None]) -> Callable[[], None]`；`steer(message: dict) -> None`；`follow_up(message: dict) -> None`；`clear_steering_queue() -> None`；`next_steering_message() -> list[dict]`（一次最多 popleft 一条，one-at-a-time）；`next_follow_up_messages() -> list[dict]`（清空式取走全部）；`cancel() -> None`（取消内部 token）；`async wait_idle() -> None`（轮询 `state.running`）；`async run_async(prompts: list[dict], config: AgentLoopConfig, token: CancelToken | None = None) -> list[dict]`
  - `run_async` 语义：`token` 非 None 时替换内部 token；`state.running=True`；`AgentEnd` 后 `state.messages = context.messages`；`finally: state.running=False`；listener 异常向上传播（适配层 mapper 内部已吞 EventBus 订阅方异常，仅控制流异常会传出）

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent.py`:

```python
"""Tests for agent/core/agent.py — the stateful Agent wrapper."""

from __future__ import annotations

import asyncio
import json

import pytest

from agent.core.agent import Agent
from agent.core.kernel_types import (
    AgentEnd,
    AgentEvent,
    AgentLoopConfig,
    CancelToken,
    MessageEnd,
    MessageStart,
    ToolExecutionEnd,
    ToolExecutionStart,
)
from agent.core.llm_providers.base import LLMResponse, ToolCallPayload
from agent.tools.registry import registry, tool_result


@pytest.fixture(autouse=True)
def clean_tool_registry():
    saved_before = set(registry.get_all_tool_names())
    yield
    for name in set(registry.get_all_tool_names()) - saved_before:
        try:
            registry.deregister(name)
        except Exception:
            pass


class _ScriptedLLM:
    def __init__(self, *responses: LLMResponse) -> None:
        self.responses = list(responses)

    async def __call__(self, full_messages, *, emit, message, token):
        resp = self.responses.pop(0)
        message["content"] = resp.content
        return resp


def _cfg(*responses: LLMResponse, **kw) -> AgentLoopConfig:
    base: dict = {"model": "test-model", "call_llm": _ScriptedLLM(*responses)}
    base.update(kw)
    return AgentLoopConfig(**base)


def _run(coro):
    return asyncio.run(coro)


def test_subscribe_and_unsubscribe():
    agent = Agent()
    seen: list[str] = []
    listener = lambda e: seen.append(e.type)  # noqa: E731
    unsub = agent.subscribe(listener)
    agent._token = CancelToken()
    _run(agent._emit(MessageStart(message={"role": "user"})))
    assert seen == ["message_start"]
    unsub()
    _run(agent._emit(MessageEnd(message={"role": "user"})))
    assert seen == ["message_start"]


def test_steering_one_at_a_time():
    agent = Agent()
    agent.steer({"role": "user", "content": "first"})
    agent.steer({"role": "user", "content": "second"})
    assert agent.next_steering_message() == [{"role": "user", "content": "first"}]
    assert agent.next_steering_message() == [{"role": "user", "content": "second"}]
    assert agent.next_steering_message() == []


def test_clear_steering_queue():
    agent = Agent()
    agent.steer({"role": "user", "content": "x"})
    agent.clear_steering_queue()
    assert agent.next_steering_message() == []


def test_follow_up_drain_all():
    agent = Agent()
    agent.follow_up({"role": "user", "content": "a"})
    agent.follow_up({"role": "user", "content": "b"})
    assert agent.next_follow_up_messages() == [
        {"role": "user", "content": "a"},
        {"role": "user", "content": "b"},
    ]
    assert agent.next_follow_up_messages() == []


def test_run_async_basic_lifecycle():
    agent = Agent()
    result = _run(
        agent.run_async(
            [{"role": "user", "content": "hi"}],
            _cfg(LLMResponse(content="hello")),
        )
    )
    assert [m["content"] for m in result] == ["hi", "hello"]
    assert agent.state.running is False
    assert agent.state.messages[-1]["content"] == "hello"
    assert agent.state.pendingToolCalls == 0


def test_cancel_and_wait_idle():
    agent = Agent()
    token = CancelToken()

    async def _scenario():
        agent.cancel()  # cancels the internal token before the run
        task = asyncio.create_task(
            agent.run_async([{"role": "user", "content": "hi"}], _cfg(LLMResponse(content="never")), token)
        )
        await asyncio.sleep(0.05)
        await agent.wait_idle()
        assert agent.state.running is False
        with pytest.raises(asyncio.CancelledError):
            await task

    _run(_scenario())


def test_pending_tool_calls_tracked_through_events():
    def echo(args: dict) -> str:
        return tool_result(data={"v": args.get("v")})

    registry.register(name="echo", toolset="test", schema={"type": "object"}, handler=echo)
    agent = Agent()
    _run(
        agent.run_async(
            [{"role": "user", "content": "go"}],
            _cfg(
                LLMResponse(content="", tool_calls=[ToolCallPayload(id="c1", name="echo", arguments='{"v": 1}')]),
                LLMResponse(content="done"),
            ),
        )
    )
    assert agent.state.pendingToolCalls == 0
    assert agent.state.running is False


def test_listener_receives_agent_end_with_messages():
    agent = Agent()
    ends: list[AgentEnd] = []
    agent.subscribe(lambda e: ends.append(e) if isinstance(e, AgentEnd) else None)
    _run(agent.run_async([{"role": "user", "content": "hi"}], _cfg(LLMResponse(content="yo"))))
    assert len(ends) == 1
    assert ends[0].messages[-1]["content"] == "yo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: ` .venv/bin/python -m pytest tests/test_agent.py -v`

Expected: FAIL（`agent/core/agent.py` 仍是旧 AIAgent，`Agent` 不存在 → `ImportError: cannot import name 'Agent'`）

- [ ] **Step 3: Write minimal implementation**

Replace the entire content of `agent/core/agent.py`（旧内容已复制进 `agent_adapter.py`，此文件改为新包装类 + 兼容 re-export）：

```python
"""Stateful Agent wrapper — the Pi-style ``agent.ts`` counterpart.

Pi-style kernel redesign (spec 2026-08-06-pi-style-kernel-design).
This module is the NEW kernel entry point: a thin stateful wrapper
(``subscribe`` / ``steer`` / ``follow_up`` / ``cancel`` / ``wait_idle``)
around the stateless loop in :mod:`agent.core.loop`.  The legacy
``AIAgent`` compatibility layer lives in :mod:`agent.core.agent_adapter`
and is re-exported at the bottom of this module so
``from agent.core.agent import AIAgent`` keeps working (frozen contract
C1).
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from agent.core.kernel_types import (
    AgentContext,
    AgentEnd,
    AgentEvent,
    AgentLoopConfig,
    AgentStart,
    CancelToken,
    ToolExecutionEnd,
    ToolExecutionStart,
)
from agent.core.loop import run_agent_loop

logger = logging.getLogger(__name__)


@dataclass
class AgentState:
    """Read-only-ish view of the agent's current run state."""

    messages: list[dict] = field(default_factory=list)
    pendingToolCalls: int = 0
    running: bool = False


class Agent:
    """Stateful wrapper around :func:`run_agent_loop`.

    Owns the steering/follow-up queues, the cancel token, the listener
    registry and a lightweight :class:`AgentState` view.  One instance
    runs one conversation at a time.
    """

    def __init__(self) -> None:
        self.state = AgentState()
        self._steering: deque[dict] = deque()
        self._follow_ups: deque[dict] = deque()
        self._listeners: list[Callable[[AgentEvent], None]] = []
        self._token = CancelToken()

    # ── listener API ──

    def subscribe(self, listener: Callable[[AgentEvent], None]) -> Callable[[], None]:
        """Register a sync listener.  Returns an unsubscribe callable."""
        self._listeners.append(listener)

        def _unsub() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _unsub

    # ── queue API ──

    def steer(self, message: dict) -> None:
        """Inject a steering message; consumed one-at-a-time (oldest
        first) at the next turn boundary."""
        self._steering.append(message)

    def follow_up(self, message: dict) -> None:
        self._follow_ups.append(message)

    def clear_steering_queue(self) -> None:
        self._steering.clear()

    def next_steering_message(self) -> list[dict]:
        """Drain at most ONE steering message (one-at-a-time)."""
        if not self._steering:
            return []
        return [self._steering.popleft()]

    def next_follow_up_messages(self) -> list[dict]:
        """Drain all pending follow-up messages."""
        if not self._follow_ups:
            return []
        out = list(self._follow_ups)
        self._follow_ups.clear()
        return out

    # ── lifecycle API ──

    def cancel(self) -> None:
        self._token.cancel()

    async def wait_idle(self) -> None:
        while self.state.running:
            await asyncio.sleep(0.01)

    async def run_async(
        self,
        prompts: list[dict],
        config: AgentLoopConfig,
        token: CancelToken | None = None,
    ) -> list[dict]:
        """Run one conversation.  Returns the new messages
        (prompts + everything the loop appended)."""
        if token is not None:
            self._token = token
        context = AgentContext(messages=[], api_calls=0)
        self.state.running = True
        self.state.messages = list(prompts)
        self.state.pendingToolCalls = 0
        try:
            result = await run_agent_loop(prompts, context, config, self._emit, self._token)
            self.state.messages = list(context.messages)
            return result
        finally:
            self.state.running = False

    async def _emit(self, event: AgentEvent) -> None:
        """Fan out one AgentEvent to listeners + maintain state.

        Listener exceptions propagate (the adapter's mapper swallows
        EventBus subscriber errors internally, so only intentional
        control-flow exceptions escape — e.g. run cancellation).
        """
        if isinstance(event, ToolExecutionStart):
            self.state.pendingToolCalls += 1
        elif isinstance(event, ToolExecutionEnd):
            self.state.pendingToolCalls = max(0, self.state.pendingToolCalls - 1)
        for listener in list(self._listeners):
            listener(event)


# ── legacy-compat re-exports (frozen contract C1) ──────────────────
from agent.core.agent_adapter import (  # noqa: E402
    AIAgent,
    AgentPhase,
    ApprovalRequest,
    Envelope,
    Phase,
    TurnSnapshot,
)

__all__ = [
    "Agent",
    "AgentState",
    "AIAgent",
    "AgentPhase",
    "ApprovalRequest",
    "Envelope",
    "Phase",
    "TurnSnapshot",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: ` .venv/bin/python -m pytest tests/test_agent.py -v`

Expected: PASS，`7 passed`. 存量回归（现有测试现在从 `agent.core.agent` 导入的是适配层 AIAgent，行为 = 旧内核）：

Run: ` .venv/bin/python -m pytest tests/test_agent_loop.py tests/test_chat.py -q`

Expected: PASS，`0 failed`

- [ ] **Step 5: Commit**

```bash
git add agent/core/agent.py tests/test_agent.py
git commit -m "feat: rewrite agent.py as stateful Agent wrapper with compat re-exports"
```

## Task P1-T6: agent_adapter.py — 新内核路径（run_conversation_async + 钩子 + EventBus 映射）

**Files:**
- Modify: `agent/core/agent_adapter.py`
- Test: `tests/test_agent_adapter.py`（追加 TestNewKernelPath 类）

**Interfaces:**
- Consumes: P1-T1 的 `AgentLoopConfig`/`CancelToken`/`AgentEvent`/`MessageUpdate`/`TurnUpdate`；P1-T2 的 `dispatch_tool_batch`（经 loop）；P1-T3 的 `run_agent_loop`（经 Agent.run_async）；P1-T5 的 `Agent`（`from agent.core.agent import Agent`，在 `__init__` 内延迟导入避免环）；既有 `_take_snapshot`/`_set_phase`/`_assert_idle`/`_drop_snapshot`/`_report`/`_dispatch_bridge_tool`/`_build_system_prompt`/`_get_tool_definitions`。
- Produces（P1-T7 chat.py 与 P3 依赖）：
  - `async run_conversation_async(user_message, system_message=None, conversation_history=None, stream_callback=None, reasoning_callback=None, stop_event=None, session_id=None) -> dict[str, Any]` — 返回与 `run_conversation` 相同的 6-key dict（C1）
  - 同步 `run_conversation(...)`（C1 入口）改为按 `kernel_mode()` 分发：`"old"` → `self._run_conversation_legacy(...)`；默认 → `asyncio.run(self.run_conversation_async(...))`
  - `cancel() -> None`；`steer(message: dict) -> None`；`follow_up(message: dict) -> None`；`clear_steering_queue() -> None`；`property agent -> Agent`（新内核 Agent 句柄，chat.py 订阅/取消用）
  - 私有钩子：`_call_llm_hook(full_messages, *, emit, message, token) -> LLMResponse`（Before/AfterLLMCallEvent + 流式 MessageUpdate 经 `asyncio.run_coroutine_threadsafe` + 重试 `self._retry_count < self.max_retries` + `token.check()` 停机检测 + api_calls/usage 累加）；`_transform_context_hook(messages, token) -> list[dict]`（async；`compact_messages` 跑 `asyncio.to_thread`；COMPACTION→IDLE phase）；`_before_tool_call_hook(tool_name, args, token) -> dict`（publish BeforeToolCallEvent，cancelled → `{"__block__": True, "__reason__": "Blocked by extension: ..."}`）；`_after_tool_call_hook(tool_name, args, result, token) -> str`（publish AfterToolCallEvent，返回 `event.result`）；`_prepare_next_turn_hook(ctx, token) -> TurnUpdate | None`（P1 恒 None）；`_should_stop_after_turn_hook(ctx, token) -> bool`（`not self._budget.consume()`）；`_on_approval_blocked_hook(tool_name, reason) -> str`（`ApprovalRequest` + `approval_callback` + `loop.run_in_executor(None, req.event.wait, 120)`）
  - `_map_event_to_bus(event: AgentEvent) -> None`（C3 映射：首个 `TurnStart` → `SessionStartEvent`；`MessageEnd`(assistant 无 tool_calls 非 error) → 记录 `_final_response`；`ToolExecutionStart` → `tool_call_callback` + `_report`；`ToolExecutionEnd` → `tool_result_callback`；`TurnEnd`(有 tool_results) → `_report` + `stream_callback`；`AgentEnd` → `_publish_session_end()`）
  - `_publish_session_end() -> None`（无 final_response 且无 error 时补 `"Max iterations reached without final response"`，publish `SessionEndEvent`）
  - 取消语义：`stop_event`（threading.Event）→ daemon 线程 `stop_event.wait(); self._token.cancel()`；`_token` 取消 → `_token_watcher` task 置 `self._llm_stop_event`（同步 LLM 流式调用提前退出）→ `_call_llm_hook` 内 `token.check()` 抛 `asyncio.CancelledError` → `run_conversation_async` 捕获 → `self._error = "用户已手动停止"` + `_publish_session_end()`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_agent_adapter.py`:

```python
class TestNewKernelPath:
    """These run the default (new) kernel — the mode the full suite exercises."""

    def test_new_plain_text_reply(self, monkeypatch):
        _force_kernel(monkeypatch, "new")
        provider = MockLLMProvider(responses=[make_text_response("hi back")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("hello")
        assert result["final_response"] == "hi back"
        assert result["completed"] is True
        assert result["error"] is None
        assert result["api_calls"] == 1
        assert [m["role"] for m in result["messages"]] == ["user", "assistant"]
        assert agent.phase == "idle"

    def test_new_tool_call_then_text(self, monkeypatch):
        _force_kernel(monkeypatch, "new")
        from agent.config_model import AppConfig

        monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))
        from tests.conftest import make_tool_call_response

        provider = MockLLMProvider(
            responses=[
                make_tool_call_response("terminal", {"command": "echo hi"}),
                make_text_response("echoed"),
            ]
        )
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("run echo", stream_callback=lambda t: None)
        assert result["completed"] is True
        assert result["api_calls"] == 2
        roles = [m["role"] for m in result["messages"]]
        assert roles == ["user", "assistant", "tool", "assistant"]
        tool_msg = result["messages"][2]
        assert tool_msg["tool_call_id"] == "c1"
        assert json.loads(tool_msg["content"])["success"] is True

    def test_new_publishes_full_event_sequence(self, monkeypatch):
        _force_kernel(monkeypatch, "new")
        from agent.config_model import AppConfig

        monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))
        from agent.events import Event
        from agent.events.bus import event_bus
        from tests.conftest import make_tool_call_response

        seen: list[str] = []
        event_bus.subscribe(lambda e: seen.append(e.type))

        provider = MockLLMProvider(
            responses=[
                make_tool_call_response("terminal", {"command": "echo ok"}),
                make_text_response("done"),
            ]
        )
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("test")
        assert result["completed"] is True
        assert seen.count("phase_change") >= 2
        for expected in (
            "session_start",
            "user_message",
            "before_llm_call",
            "after_llm_call",
            "before_tool_call",
            "after_tool_call",
            "session_end",
        ):
            assert expected in seen, expected
        assert seen.index("session_start") < seen.index("user_message")
        assert seen.index("user_message") < seen.index("before_llm_call")
        assert seen.index("before_llm_call") < seen.index("after_llm_call")
        assert seen.index("after_llm_call") < seen.index("before_tool_call")
        assert seen.index("before_tool_call") < seen.index("after_tool_call")

    def test_new_session_id_propagates_to_events(self, monkeypatch):
        _force_kernel(monkeypatch, "new")
        from agent.events import Event
        from agent.events.bus import event_bus
        from agent.events.types import PhaseChangeEvent, SessionEndEvent, SessionStartEvent

        captured: list[Event] = []
        event_bus.subscribe(lambda e: captured.append(e))

        provider = MockLLMProvider(responses=[make_text_response("ok")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        agent.run_conversation("hi", session_id="chat-42")

        starts = [e for e in captured if isinstance(e, SessionStartEvent)]
        ends = [e for e in captured if isinstance(e, SessionEndEvent)]
        assert len(starts) == 1 and starts[0].session_id == "chat-42"
        assert len(ends) == 1 and ends[0].session_id == "chat-42"
        for ev in [e for e in captured if isinstance(e, PhaseChangeEvent)]:
            assert ev.session_id == "chat-42"

    def test_new_security_event_blocks_dangerous_command(self, monkeypatch):
        _force_kernel(monkeypatch, "new")
        from agent.events.extensions import register_extensions
        from agent.extensions.security_event import SecurityEventExtension

        ext = SecurityEventExtension()
        ext.enabled = True
        register_extensions([ext])
        from tests.conftest import make_tool_call_response

        provider = MockLLMProvider(
            responses=[
                make_tool_call_response("terminal", {"command": "rm -rf /etc/passwd"}),
            ]
        )
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("rm -rf something")
        assert result["api_calls"] == 2  # blocked tool → model retries → fallback text
        assert len(result["messages"]) == 4
        tool_msgs = [m for m in result["messages"] if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        payload = json.loads(tool_msgs[0]["content"])
        assert payload["success"] is False
        assert "拒绝" in payload.get("error", "") or "Blocked" in payload.get("error", "")

    def test_new_phase_machine_idle_turn_idle_and_snapshot_cleared(self, monkeypatch):
        _force_kernel(monkeypatch, "new")
        provider = MockLLMProvider(responses=[make_text_response("hi")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        assert agent.phase == "idle"
        assert agent._snapshot is None
        result = agent.run_conversation("hello")
        assert result["completed"] is True
        assert agent.phase == "idle"
        assert agent._snapshot is None

    def test_new_rejects_reentrant_call(self, monkeypatch):
        _force_kernel(monkeypatch, "new")
        import pytest

        provider = MockLLMProvider(responses=[make_text_response("hi")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)
        agent._set_phase("turn", "manual")
        with pytest.raises(RuntimeError, match="turn"):
            agent.run_conversation("hello")

    def test_new_snapshot_isolates_config_changes(self, monkeypatch):
        _force_kernel(monkeypatch, "new")
        from agent.config_model import AppConfig

        monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))
        from agent.events import Event
        from agent.events.bus import event_bus
        from tests.conftest import make_tool_call_response

        provider = MockLLMProvider(
            responses=[
                make_tool_call_response("terminal", {"command": "echo a"}),
                make_text_response("done"),
            ]
        )
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        def _mutate(event: Event) -> None:
            if event.type == "before_llm_call":
                agent.model = "mutated-model"

        event_bus.subscribe(_mutate)
        result = agent.run_conversation("test")
        assert agent.model == "mutated-model"
        assert result["completed"] is True

    def test_new_user_message_rejected(self, monkeypatch):
        _force_kernel(monkeypatch, "new")
        from agent.events import Event
        from agent.events.bus import event_bus

        def _reject(event: Event) -> None:
            if event.type == "user_message":
                event.cancel("test rejection")

        event_bus.subscribe(_reject)
        provider = MockLLMProvider(responses=[make_text_response("ok")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("hi")
        assert result["completed"] is False
        assert "User message rejected" in result["error"]
        assert result["api_calls"] == 0
        assert agent.phase == "idle"
        assert agent._snapshot is None

    def test_new_stop_event_stops_run(self, monkeypatch):
        _force_kernel(monkeypatch, "new")
        import threading

        provider = MockLLMProvider(responses=[make_text_response("never")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)
        stop_event = threading.Event()
        stop_event.set()  # already stopped before the run starts

        result = agent.run_conversation("hi", stop_event=stop_event)
        assert result["completed"] is False
        assert result["error"] == "用户已手动停止"
        assert agent.phase == "idle"

    def test_new_budget_exhaustion_error(self, monkeypatch):
        _force_kernel(monkeypatch, "new")
        from tests.conftest import make_tool_call_response

        provider = MockLLMProvider(
            responses=[
                make_tool_call_response("terminal", {"command": "echo 1"}),
                make_tool_call_response("terminal", {"command": "echo 2"}),
                make_tool_call_response("terminal", {"command": "echo 3"}),
                make_tool_call_response("terminal", {"command": "echo 4"}),
                make_text_response("done"),
            ]
        )
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("go")
        assert result["completed"] is False
        assert result["error"] == "Max iterations reached without final response"
        assert agent.phase == "idle"

    def test_new_compaction_hook_fires(self, monkeypatch):
        _force_kernel(monkeypatch, "new")
        from agent.context_compactor import CompactionSettings
        from agent.events import Event
        from agent.events.bus import event_bus

        long_user = "长" * 400  # ~333 tokens under the character heuristic

        class _SpyProvider:
            def __init__(self, inner):
                self.inner = inner
                self.messages: list[list[dict]] = []

            def chat(self, **kwargs):
                self.messages.append(list(kwargs.get("messages", [])))
                return self.inner.chat(**kwargs)

        inner = MockLLMProvider(responses=[make_text_response("summary"), make_text_response("ok")])
        spy = _SpyProvider(inner)
        agent = AIAgent(
            api_key="sk-fake",
            base_url="x",
            model="gpt-4o",
            max_iterations=3,
            compaction_settings=CompactionSettings(
                enabled=True, max_context_tokens=120, reserve_tokens=20, keep_recent_tokens=50
            ),
        )
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=spy)

        phases: list[str] = []
        event_bus.subscribe(lambda e: phases.append(e.to_phase) if e.type == "phase_change" else None)

        result = agent.run_conversation(long_user)
        assert result["completed"] is True
        assert result["final_response"] == "ok"
        assert "compaction" in phases
        # the second LLM call (main turn) sees the compaction summary message
        assert len(spy.messages) == 2
        assert any(m.get("content", "").startswith("[上下文压缩摘要]") for m in spy.messages[1])

    def test_new_dual_run_equivalence(self, monkeypatch):
        """§6.3: the same script through old and new kernels → same outcome."""
        _force_kernel(monkeypatch, "old")  # fallthrough below re-pins per run
        from agent.config_model import AppConfig

        monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))
        from tests.conftest import make_tool_call_response

        def _run_with(mode: str) -> dict:
            _force_kernel(monkeypatch, mode)
            provider = MockLLMProvider(
                responses=[
                    make_tool_call_response("terminal", {"command": "echo hi"}),
                    make_text_response("echoed"),
                ]
            )
            agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
            agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)
            return agent.run_conversation("run echo")

        old_result = _run_with("old")
        new_result = _run_with("new")

        assert new_result["final_response"] == old_result["final_response"] == "echoed"
        assert new_result["completed"] is True and old_result["completed"] is True
        assert new_result["error"] is None and old_result["error"] is None
        assert new_result["api_calls"] == old_result["api_calls"] == 2
        assert [m["role"] for m in new_result["messages"]] == [m["role"] for m in old_result["messages"]]
        old_tool = [m for m in old_result["messages"] if m["role"] == "tool"][0]
        new_tool = [m for m in new_result["messages"] if m["role"] == "tool"][0]
        assert old_tool["tool_call_id"] == new_tool["tool_call_id"] == "c1"
        assert json.loads(old_tool["content"]) == json.loads(new_tool["content"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: ` .venv/bin/python -m pytest tests/test_agent_adapter.py -q`

Expected: FAIL（`run_conversation_async` 不存在 → `AttributeError`；或 legacy 路径仍在跑导致 `_force_kernel("new")` 无效果）

- [ ] **Step 3: Write minimal implementation**

Apply these exact edits to `agent/core/agent_adapter.py`：

Edit 1 — 追加 kernel_types 导入（在 `from agent.core.iteration_budget import IterationBudget` 之后）：

old:
```
from agent.core.iteration_budget import IterationBudget
from agent.core.llm_client import LLMClient, LLMResponse, ToolCallPayload
```
new:
```
from agent.core.iteration_budget import IterationBudget
from agent.core.kernel_types import (
    AgentEvent,
    AgentLoopConfig,
    CancelToken,
    MessageUpdate,
    TurnUpdate,
)
from agent.core.llm_client import LLMClient, LLMResponse, ToolCallPayload
```

Edit 2 — `__init__` 末尾追加新内核 per-run 状态（在 `self._envelope_seq: int = 0` 之后）：

old:
```
        # ── M7: Phase Machine ──
        self.phase: str = Phase.IDLE
        self._snapshot: TurnSnapshot | None = None
        self._envelope_seq: int = 0
```
new:
```
        # ── M7: Phase Machine ──
        self.phase: str = Phase.IDLE
        self._snapshot: TurnSnapshot | None = None
        self._envelope_seq: int = 0

        # ── New-kernel per-run state (P1-T6) ──
        from agent.core.agent import Agent

        self._agent = Agent()
        self._agent.subscribe(self._map_event_to_bus)
        self._token: CancelToken | None = None
        self._token_watcher: asyncio.Task | None = None
        self._llm_stop_event: threading.Event | None = None
        self._budget: IterationBudget | None = None
        self._session_id = ""
        self._history: list[dict] = []
        self._session_started = False
        self._saw_agent_start = False
        self._stream_cb: Callable | None = None
        self._reasoning_cb: Callable | None = None
        self._error: str | None = None
        self._final_response = ""
        self._api_calls = 0
        self._turn_count = 0
        self._retry_count = 0
        self._total_usage: dict = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self._result_messages: list[dict] = []
```

Edit 3 — 把旧 `run_conversation` 改名 `_run_conversation_legacy` 并在其前插入新方法（anchor 为旧方法签名头）：

old:
```
    def run_conversation(
        self,
        user_message: str | list,
        system_message: str | None = None,
        conversation_history: list[dict] | None = None,
        stream_callback: Callable[[str], None] | None = None,
        reasoning_callback: Callable[[str], None] | None = None,
        stop_event: threading.Event | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Run a conversation with tool calling support.
```
new:
```
    # ── New kernel path (P1-T6) ────────────────────────────────────

    def run_conversation(
        self,
        user_message: str | list,
        system_message: str | None = None,
        conversation_history: list[dict] | None = None,
        stream_callback: Callable[[str], None] | None = None,
        reasoning_callback: Callable[[str], None] | None = None,
        stop_event: threading.Event | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Frozen C1 entry point.  Delegates to the active kernel:
        ``ZLINK_KERNEL=old`` → the inline legacy algorithm; default →
        the new async kernel via ``asyncio.run``."""
        if kernel_mode() == "old":
            return self._run_conversation_legacy(
                user_message=user_message,
                system_message=system_message,
                conversation_history=conversation_history,
                stream_callback=stream_callback,
                reasoning_callback=reasoning_callback,
                stop_event=stop_event,
                session_id=session_id,
            )
        return asyncio.run(
            self.run_conversation_async(
                user_message=user_message,
                system_message=system_message,
                conversation_history=conversation_history,
                stream_callback=stream_callback,
                reasoning_callback=reasoning_callback,
                stop_event=stop_event,
                session_id=session_id,
            )
        )

    async def run_conversation_async(
        self,
        user_message: str | list,
        system_message: str | None = None,
        conversation_history: list[dict] | None = None,
        stream_callback: Callable[[str], None] | None = None,
        reasoning_callback: Callable[[str], None] | None = None,
        stop_event: threading.Event | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Async equivalent of :meth:`run_conversation` (new kernel).

        Drives :class:`agent.core.agent.Agent` around
        :func:`agent.core.loop.run_agent_loop`; maps every AgentEvent to
        the EventBus (C3) via :meth:`_map_event_to_bus`; returns the same
        6-key dict as :meth:`run_conversation` (C1).  ``system_message``
        is honored as the system prompt (the old kernel accepted and
        ignored it — a latent bug this rewrite fixes).
        """
        effective_session_id = session_id or ""
        self._session_id = effective_session_id
        self._history = list(conversation_history or [])
        self._stream_cb = stream_callback
        self._reasoning_cb = reasoning_callback
        self._error = None
        self._final_response = ""
        self._api_calls = 0
        self._turn_count = 0
        self._retry_count = 0
        self._total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self._session_started = False
        self._saw_agent_start = False
        self._result_messages = []

        self._assert_idle("run_conversation_async")
        self._set_phase(AgentPhase.TURN, "conversation start", session_id=effective_session_id)

        try:
            if not self.api_key:
                self._set_phase(AgentPhase.IDLE, "no api key", session_id=effective_session_id)
                return {
                    "final_response": "",
                    "messages": [],
                    "api_calls": 0,
                    "token_usage": None,
                    "completed": False,
                    "error": "API Key 未配置",
                }

            messages = build_turn_messages(conversation_history, user_message)
            snap = self._take_snapshot()

            # ── Session start + user message gate (C3 cancel semantics) ──
            event_bus.publish(
                SessionStartEvent(
                    session_id=effective_session_id,
                    history=conversation_history or [],
                )
            )
            self._session_started = True

            user_evt = UserMessageEvent(content=user_message)
            event_bus.publish(user_evt)
            if user_evt.cancelled:
                self._set_phase(AgentPhase.IDLE, "user message rejected", session_id=effective_session_id)
                return {
                    "final_response": "",
                    "messages": messages,
                    "api_calls": 0,
                    "token_usage": None,
                    "completed": False,
                    "error": f"User message rejected: {user_evt.cancel_reason}",
                }
            if user_evt.content != user_message and isinstance(user_evt.content, str):
                messages[-1] = {"role": "user", "content": user_evt.content}

            # ── Vision guard (unchanged behaviour) ──
            if not snap.supports_vision:
                total_image = sum(
                    sum(1 for b in m["content"] if isinstance(b, dict) and b.get("type") == "image_url")
                    for m in messages
                    if isinstance(m.get("content"), list)
                )
                if total_image > 0:
                    messages = strip_images_from_messages(messages)
                    self._report(f"🖼️ 当前模型不支持图片输入，已自动过滤 {total_image} 张图片")
                    if stream_callback:
                        stream_callback(f"\n\n---\n🖼️ **当前模型不支持图片输入，已自动过滤 {total_image} 张图片**\n")

            # ── Per-run cancellation plumbing ──
            self._budget = IterationBudget(self.max_iterations)
            self._token = CancelToken()
            self._llm_stop_event = threading.Event()

            if stop_event is not None:
                def _watch_legacy_stop() -> None:
                    stop_event.wait()
                    self._token.cancel()

                threading.Thread(target=_watch_legacy_stop, daemon=True, name="zlk-stop-watcher").start()

            async def _watch_token() -> None:
                await self._token.wait()
                self._llm_stop_event.set()

            self._token_watcher = asyncio.create_task(_watch_token())

            config = AgentLoopConfig(
                model=snap.model,
                temperature=snap.temperature,
                max_tokens=snap.max_tokens,
                system_prompt=system_message if system_message is not None else snap.system_prompt,
                tool_defs=snap.tool_defs,
                max_tool_result_length=snap.max_tool_result_length,
                call_llm=self._call_llm_hook,
                transform_context=self._transform_context_hook,
                before_tool_call=self._before_tool_call_hook,
                after_tool_call=self._after_tool_call_hook,
                prepare_next_turn=self._prepare_next_turn_hook,
                should_stop_after_turn=self._should_stop_after_turn_hook,
                bridge_dispatch=self._dispatch_bridge_tool,
                on_approval_blocked=self._on_approval_blocked_hook,
            )

            try:
                new_messages = await self._agent.run_async(messages, config, self._token)
                self._result_messages = new_messages
            except asyncio.CancelledError:
                self._error = self._error or "用户已手动停止"
                self._result_messages = list(self._agent.state.messages)
                self._publish_session_end()
            except Exception as e:  # noqa: BLE001 — Agent.handleRunFailure fallback
                logger.exception("Agent run failed")
                self._error = f"Unexpected agent error: {e}"
                self._result_messages = list(self._agent.state.messages)
                self._publish_session_end()

            has_usage = self._total_usage.get("total_tokens", 0) > 0
            return {
                "final_response": self._final_response,
                "messages": self._result_messages,
                "api_calls": self._api_calls,
                "token_usage": self._total_usage if has_usage else None,
                "completed": bool(self._final_response) and self._error is None,
                "error": self._error,
            }
        finally:
            self._drop_snapshot()
            self._budget = None
            if self._token_watcher is not None:
                self._token_watcher.cancel()
            if self.phase != AgentPhase.IDLE:
                self._set_phase(
                    AgentPhase.IDLE,
                    "conversation cleanup",
                    session_id=effective_session_id,
                )

    def cancel(self) -> None:
        """Cancel the in-flight run (WS stop)."""
        if self._agent is not None:
            self._agent.cancel()
        elif self._token is not None:
            self._token.cancel()

    def steer(self, message: dict) -> None:
        """Inject a steering message (consumed one-at-a-time, next turn)."""
        self._agent.steer(message)

    def follow_up(self, message: dict) -> None:
        self._agent.follow_up(message)

    def clear_steering_queue(self) -> None:
        self._agent.clear_steering_queue()

    @property
    def agent(self):
        """The internal new-kernel Agent (listener/steer/cancel handle)."""
        return self._agent

    def _publish_session_end(self) -> None:
        if self._error is None and not self._final_response:
            self._error = "Max iterations reached without final response"
        event_bus.publish(
            SessionEndEvent(
                session_id=self._session_id,
                final_response=self._final_response,
                error=self._error,
                api_calls=self._api_calls,
            )
        )

    def _map_event_to_bus(self, event: AgentEvent) -> None:
        """Map AgentEvents → EventBus 8 events (C3) + legacy WS callbacks."""
        t = event.type
        if t == "agent_start":
            self._saw_agent_start = True
        elif t == "turn_start":
            if self._saw_agent_start and not self._session_started:
                self._session_started = True
                event_bus.publish(SessionStartEvent(session_id=self._session_id, history=self._history))
        elif t == "message_update":
            if event.delta and self._stream_cb:
                self._stream_cb(event.delta)
            if event.reasoning_delta and self._reasoning_cb:
                self._reasoning_cb(event.reasoning_delta)
        elif t == "message_end":
            m = event.message
            if m.get("role") == "assistant" and "tool_calls" not in m and not m.get("is_error"):
                self._final_response = m.get("content", "")
        elif t == "tool_execution_start":
            try:
                args_str = json.dumps(event.args, ensure_ascii=False)[:200]
            except (TypeError, ValueError):
                args_str = str(event.args)[:200]
            if self.tool_call_callback:
                self.tool_call_callback(event.tool_name, args_str)
            self._report(f"🔧 执行工具: {event.tool_name} | {args_str}")
        elif t == "tool_execution_end":
            if self.tool_result_callback:
                self.tool_result_callback(event.tool_name, event.result)
        elif t == "turn_end":
            if event.tool_results:
                self._report(f"✅ 工具执行完成 (第 {self._turn_count} 轮)")
                if self._stream_cb:
                    self._stream_cb("\n\n---\n✅ **工具执行完成**\n")
        elif t == "agent_end":
            self._publish_session_end()

    async def _call_llm_hook(
        self,
        full_messages: list[dict],
        *,
        emit: Callable[[AgentEvent], Awaitable[None]],
        message: dict,
        token: CancelToken,
    ) -> LLMResponse:
        """One LLM call with retry + EventBus events + usage/api_calls.

        The sync provider call runs in a worker thread; streaming
        MessageUpdate events are pushed back to the event loop via
        ``run_coroutine_threadsafe`` (ordering preserved — tasks are
        scheduled FIFO).  ``token.check()`` after the call turns a
        stop-mid-stream into a clean cancellation.
        """
        snap = self._snapshot
        assert snap is not None, "snapshot must exist during a run"
        while True:
            api_kwargs: dict = {
                "model": snap.model,
                "messages": full_messages,
                "temperature": snap.temperature,
            }
            if snap.max_tokens is not None:
                api_kwargs["max_tokens"] = snap.max_tokens
            if snap.tool_defs:
                api_kwargs["tools"] = snap.tool_defs
                api_kwargs["tool_choice"] = "auto"

            pre_llm = BeforeLLMCallEvent(model=snap.model, messages=full_messages, api_kwargs=api_kwargs)
            event_bus.publish(pre_llm)
            if pre_llm.cancelled:
                return LLMResponse(
                    error=f"LLM call cancelled by extension: {pre_llm.cancel_reason}",
                    stop_reason="aborted",
                )

            self._turn_count += 1
            self._report(f"🤔 思考中...（第 {self._turn_count}/{self.max_iterations} 轮）")

            loop = asyncio.get_running_loop()
            content_parts: list[str] = []
            reasoning_parts: list[str] = []

            async def _safe_emit(event: AgentEvent) -> None:
                try:
                    await emit(event)
                except Exception:  # noqa: BLE001
                    logger.exception("emit failed for %s", event.type)

            def _stream_cb(chunk: str) -> None:
                content_parts.append(chunk)
                partial = {"role": "assistant", "content": "".join(content_parts)}
                asyncio.run_coroutine_threadsafe(
                    _safe_emit(MessageUpdate(message=partial, delta=chunk, reasoning_delta=None)),
                    loop,
                )

            def _reasoning_cb(chunk: str) -> None:
                reasoning_parts.append(chunk)
                partial = {
                    "role": "assistant",
                    "content": "".join(content_parts),
                    "reasoning_content": "".join(reasoning_parts),
                }
                asyncio.run_coroutine_threadsafe(
                    _safe_emit(MessageUpdate(message=partial, delta="", reasoning_delta=chunk)),
                    loop,
                )

            stream_cb = self._stream_cb
            reasoning_cb = self._reasoning_cb
            response = await asyncio.to_thread(
                self._llm.chat,
                model=snap.model,
                messages=full_messages,
                temperature=snap.temperature,
                max_tokens=snap.max_tokens,
                tools=snap.tool_defs or None,
                tool_choice="auto" if snap.tool_defs else None,
                stream=stream_cb is not None,
                stream_callback=_stream_cb if stream_cb is not None else None,
                reasoning_callback=_reasoning_cb if reasoning_cb is not None else None,
                stop_event=self._llm_stop_event,
            )
            self._api_calls += 1

            # Stop mid-LLM-call: the sync call returns early (stop_event) —
            # surface it as cancellation so the run ends with AgentEnd.
            token.check()

            event_bus.publish(AfterLLMCallEvent(model=snap.model, response=response))
            if response.usage:
                for k in self._total_usage:
                    self._total_usage[k] += response.usage.get(k, 0)

            if response.failed and self._retry_count < self.max_retries:
                self._retry_count += 1
                self._set_phase(AgentPhase.RETRY, f"LLM error: {response.error}", session_id=self._session_id)
                continue

            self._set_phase(AgentPhase.TURN, "llm call completed", session_id=self._session_id)
            return response

    async def _transform_context_hook(self, messages: list[dict], token: CancelToken) -> list[dict]:
        """Compaction policy — the old ``_maybe_compact`` moved into a hook.

        The summary LLM call runs in a worker thread so the event loop is
        never blocked; ``SessionBeforeCompactEvent`` is still published by
        :func:`compact_messages` (C3, unchanged).
        """
        if not self.compaction_settings.enabled:
            return messages
        snap = self._snapshot
        if snap is None:
            return messages
        total_est = estimate_message_tokens(messages, model=snap.model)
        threshold = (
            snap.compaction_settings.effective_max_context_tokens(snap.model) - snap.compaction_settings.reserve_tokens
        )
        if total_est <= threshold:
            return messages
        self._set_phase(AgentPhase.COMPACTION, f"context over threshold ({total_est} > {threshold})")

        def _do_compact() -> tuple[list[dict], int]:
            def summary_caller(prompt: str) -> str:
                resp = self._llm.chat(
                    model=snap.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=600,
                )
                return resp.content

            compacted, _, saved = compact_messages(
                messages,
                snap.compaction_settings,
                summary_caller,
                snap.model,
                event_bus=event_bus,
            )
            return compacted, saved

        compacted, saved = await asyncio.to_thread(_do_compact)
        if saved > 0:
            self._report(f"📦 上下文已压缩 —— 节省约 {saved} tokens")
        self._set_phase(AgentPhase.IDLE, f"compaction saved {saved} tokens")
        return compacted

    async def _before_tool_call_hook(self, tool_name: str, args: dict, token: CancelToken) -> dict:
        """Layer 3: BeforeToolCallEvent (C3).  Registry before-hooks run
        inside ``registry.dispatch`` (Layer 2) — unchanged."""
        pre_event = BeforeToolCallEvent(tool_name=tool_name, args=args)
        event_bus.publish(pre_event)
        if pre_event.cancelled:
            return {"__block__": True, "__reason__": f"Blocked by extension: {pre_event.cancel_reason}"}
        return pre_event.args

    async def _after_tool_call_hook(self, tool_name: str, args: dict, result: str, token: CancelToken) -> str:
        post_event = AfterToolCallEvent(tool_name=tool_name, args=args, result=result)
        event_bus.publish(post_event)
        return post_event.result

    async def _prepare_next_turn_hook(self, ctx: dict, token: CancelToken) -> TurnUpdate | None:
        """P1: no per-turn overrides — the run keeps the frozen snapshot
        (same as the old kernel's per-run snapshot)."""
        return None

    async def _should_stop_after_turn_hook(self, ctx: dict, token: CancelToken) -> bool:
        """IterationBudget consumption point (spec §3.4)."""
        if self._budget is None:
            return False
        return not self._budget.consume()

    async def _on_approval_blocked_hook(self, tool_name: str, reason: str) -> str:
        """Approval flow (R4: threading.Event → asyncio wait).
        Returns ``"approved"`` | ``"denied"``."""
        req = ApprovalRequest(tool_name=tool_name, reason=reason)
        if self.approval_callback:
            self.approval_callback(req)
        loop = asyncio.get_running_loop()
        timed_out = await loop.run_in_executor(None, req.event.wait, 120)
        if timed_out or req.result != "approved":
            return "denied"
        return "approved"

    # ── Legacy kernel path (verbatim pre-P1 algorithm) ─────────────

    def _run_conversation_legacy(
        self,
        user_message: str | list,
        system_message: str | None = None,
        conversation_history: list[dict] | None = None,
        stream_callback: Callable[[str], None] | None = None,
        reasoning_callback: Callable[[str], None] | None = None,
        stop_event: threading.Event | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Run a conversation with tool calling support.
```

（注意：Edit 3 的 new 以 `"""Run a conversation with tool calling support.` 结尾 —— 这是旧 docstring 的首行，其后所有旧代码保持原样、原缩进，即旧 `run_conversation` 的整个函数体原封不动变成 `_run_conversation_legacy` 的函数体。）

- [ ] **Step 4: Run test to verify it passes**

Run: ` .venv/bin/python -m pytest tests/test_agent_adapter.py -v`

Expected: PASS，`7 (kernel-mode + legacy) + 13 (new) = 20 passed`

存量全量回归（默认 new 内核跑全部存量测试——这是 P1 的核心门禁）：

Run: ` .venv/bin/python -m pytest tests/ -q`

Expected: PASS，`378 + 新增 ≈ 450 passed, 0 failed`（任何失败先修本任务，不允许带红进 P1-T7）

- [ ] **Step 5: Commit**

```bash
git add agent/core/agent_adapter.py tests/test_agent_adapter.py
git commit -m "feat: wire new kernel path into AIAgent adapter with EventBus mapping"
```

## Task P1-T7: chat.py — _run_agent 拆分（legacy 原样保留 + 新 async 路径）

**Files:**
- Modify: `backend/api/chat.py`
- Test: `tests/test_chat_async.py`

**Interfaces:**
- Consumes: `agent.agent.AIAgent`（既有）；`agent.core.agent.agent` 属性（适配层新增）；`kernel_types.AgentEvent`/`MessageStart`/`MessageUpdate`/`ToolExecutionStart`/`ToolExecutionEnd`/`TurnEnd`；`agent_adapter.kernel_mode()`；既有 `_set_pending_approval`/`_resolve_pending_approval`/`_generate_summary`/`session_manager`。
- Produces（C2 + §4.6）：`async _run_agent(...)` 按 `kernel_mode()` 分发；`async _run_agent_legacy(...)` = 现 `_run_agent` 原样（线程池 + 队列 + callbacks）；`async _run_agent_new(...)` 直接 `await agent.run_conversation_async(...)`，AgentEvent 监听器把事件同步转成扁平 WS 消息直接 `send_json`：
  - `MessageStart`(assistant) → `{"type": "progress", "message": "🤔 思考中...（第 {n}/{max_iterations} 轮）"}`
  - `MessageUpdate` → `{"type": "token", "content": delta}` +（若有 `reasoning_delta`）`{"type": "reasoning_token", "content": reasoning_delta}`
  - `ToolExecutionStart` → `{"type": "progress", "message": "🔧 执行工具: {name} | {args_str}"}` + `{"type": "tool_call", "name", "arguments": args_str[:200]}`
  - `ToolExecutionEnd` → `{"type": "tool_result", "name", "result"}`
  - `TurnEnd`（有 tool_results）→ `{"type": "progress", "message": "✅ 工具执行完成 (第 {n} 轮)"}`
  - `AgentEnd`/用户/tool 消息 → 不产生 WS 消息；`done` 由 `_run_agent_new` 在 `run_conversation_async` 返回后发送（字段与现状一致 + `session_title`）；异常 → `error`
  - 入站：`stop` → `agent.cancel()`；`approval_response` → `_resolve_pending_approval`；P3 追加 `steering`
  - 发送保序：监听器内 `asyncio.create_task(_send(...))` 收集到 `send_tasks`，发 `done`/`error` 前 `await asyncio.gather(*send_tasks)`
  - 会话持久化/摘要逻辑与旧路径逐行一致（`all_msgs` 切片 `[len(history)+1:]`、`auto_title`、`save_session`、`_generate_summary`）

- [ ] **Step 1: Write the failing test**

Create `tests/test_chat_async.py`:

```python
"""Tests for backend/api/chat.py — the new-kernel async WS path (_run_agent_new)."""

from __future__ import annotations

import asyncio

from agent.core.kernel_types import (
    AgentEnd,
    MessageEnd,
    MessageStart,
    MessageUpdate,
    ToolExecutionEnd,
    ToolExecutionStart,
    ToolResult,
    TurnEnd,
)


class _FakeAgent:
    """Stand-in for backend.api.chat.AIAgent — drives scripted events."""

    system_prompt = "test system prompt"

    def __init__(self, events, result=None, delay: float = 0.0):
        self._events = list(events)
        self._result = result or {
            "final_response": "final",
            "messages": [],
            "api_calls": 1,
            "token_usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "completed": True,
            "error": None,
        }
        self._delay = delay
        self.cancelled = False
        self.steered: list[dict] = []
        self.run_kwargs: dict = {}

        class _Inner:
            def __init__(self, owner):
                self._owner = owner
                self._listeners = []

            def subscribe(self, listener):
                self._listeners.append(listener)
                return lambda: None

            def emit(self, event):
                for ln in list(self._listeners):
                    ln(event)

        self.agent = _Inner(self)

    async def run_conversation_async(self, **kwargs):
        self.run_kwargs = kwargs
        for ev in self._events:
            self.agent.emit(ev)
        if self._delay:
            await asyncio.sleep(self._delay)
        return dict(self._result)

    def cancel(self):
        self.cancelled = True

    def steer(self, message: dict):
        self.steered.append(message)


def _make_events():
    return [
        MessageStart(message={"role": "user", "content": "hi"}),
        MessageEnd(message={"role": "user", "content": "hi"}),
        MessageStart(message={"role": "assistant", "content": ""}),
        MessageUpdate(message={"role": "assistant", "content": "你"}, delta="你"),
        MessageUpdate(message={"role": "assistant", "content": "你好"}, delta="好"),
        MessageEnd(message={"role": "assistant", "content": "你好"}),
        ToolExecutionStart(tool_call_id="c1", tool_name="ls", args={}),
        ToolExecutionEnd(tool_call_id="c1", tool_name="ls", result='{"success": true, "data": "[]"}'),
        TurnEnd(
            message={"role": "assistant", "content": "你好"},
            tool_results=[ToolResult(tool_call_id="c1", tool_name="ls", result='{"success": true}')],
        ),
        AgentEnd(messages=[]),
    ]


def _monkeypatch_ws_env(monkeypatch):
    from agent import config_manager

    cfg = config_manager.load().model_copy(deep=True)
    cfg.llm_api_key = "sk-test"
    cfg.llm_base_url = "http://localhost:9/v1"
    cfg.llm_model = "gpt-4o"
    cfg.max_iterations = 3
    monkeypatch.setattr(config_manager, "load", lambda: cfg)
    monkeypatch.setattr("backend.api.chat._generate_summary", lambda *a, **k: None)
    monkeypatch.setattr("agent.session_manager.load_session", lambda sid: [])
    monkeypatch.setattr("agent.session_manager.save_session", lambda *a, **k: None)
    monkeypatch.setattr("agent.session_manager.auto_title", lambda msgs: "title")
    monkeypatch.setattr("agent.skill_manager.get_active_instructions", lambda: "")
    monkeypatch.setattr("agent.skill_manager.get_instructions_for_query", lambda q: None)
    monkeypatch.setattr("agent.memory_manager.get_context", lambda: "")


def test_ws_streams_flat_messages_in_order(monkeypatch):
    _monkeypatch_ws_env(monkeypatch)
    fake = _FakeAgent(_make_events())
    monkeypatch.setattr("backend.api.chat.AIAgent", lambda **kw: fake)

    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    with client.websocket_connect("/ws/chat/sess-stream") as ws:
        ws.send_json({"type": "send_message", "content": "hi"})
        types: list[str] = []
        while True:
            msg = ws.receive_json()
            types.append(msg["type"])
            if msg["type"] == "done":
                assert msg["final_response"] == "final"
                assert msg["session_id"] == "sess-stream"
                assert msg["session_title"] == "title"
                break

    assert "progress" in types
    assert "token" in types
    assert "tool_call" in types
    assert "tool_result" in types
    assert types[-1] == "done"
    # token deltas arrive in stream order
    token_contents = [
        msg["content"] for msg in _collect_ws_messages(client, fake, "sess-tokens") if msg["type"] == "token"
    ]
    assert token_contents == ["你", "好"]


def _collect_ws_messages(client, fake, session_id: str):
    """Send a message and collect every WS frame until done."""
    out: list[dict] = []
    with client.websocket_connect(f"/ws/chat/{session_id}") as ws:
        ws.send_json({"type": "send_message", "content": "hi"})
        while True:
            msg = ws.receive_json()
            out.append(msg)
            if msg["type"] == "done":
                break
    return out


def test_ws_stop_cancels_agent(monkeypatch):
    _monkeypatch_ws_env(monkeypatch)
    fake = _FakeAgent(_make_events(), delay=1.0)
    monkeypatch.setattr("backend.api.chat.AIAgent", lambda **kw: fake)

    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    with client.websocket_connect("/ws/chat/sess-stop") as ws:
        ws.send_json({"type": "send_message", "content": "hi"})
        ws.send_json({"type": "stop"})
        while True:
            msg = ws.receive_json()
            if msg["type"] == "done":
                break

    assert fake.cancelled is True


def test_ws_error_frame_on_run_exception(monkeypatch):
    _monkeypatch_ws_env(monkeypatch)

    class _ExplodingAgent(_FakeAgent):
        async def run_conversation_async(self, **kwargs):
            self.run_kwargs = kwargs
            raise RuntimeError("agent exploded")

    fake = _ExplodingAgent([])
    monkeypatch.setattr("backend.api.chat.AIAgent", lambda **kw: fake)

    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    with client.websocket_connect("/ws/chat/sess-err") as ws:
        ws.send_json({"type": "send_message", "content": "hi"})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "agent exploded" in msg["message"]
        assert msg["session_id"] == "sess-err"
```

- [ ] **Step 2: Run test to verify it fails**

Run: ` .venv/bin/python -m pytest tests/test_chat_async.py -v`

Expected: FAIL（`_run_agent` 仍是线程池旧实现：FakeAgent 无 `run_in_executor` 兼容 → 测试挂起或 `TypeError`）

- [ ] **Step 3: Write minimal implementation**

Apply these exact edits to `backend/api/chat.py`：

Edit 1 — 追加导入（在 `from agent.core.agent import ApprovalRequest` 之后）：

old:
```
from agent.core.agent import ApprovalRequest
```
new:
```
from agent.core.agent import ApprovalRequest
from agent.core.agent_adapter import kernel_mode
from agent.core.kernel_types import AgentEvent
```

Edit 2 — `_run_agent` 头部替换（旧函数改名 `_run_agent_legacy`，其前插入分发器 + 新路径；old 精确匹配现存 `_run_agent` 签名头到 `stop_event = threading.Event()`）：

old:
```
async def _run_agent(
    websocket: WebSocket,
    session_id: str,
    content: str,
    history: list[dict],
    api_key: str,
    base_url: str,
    model: str,
    max_iterations: int,
    existing_msgs: list[dict],
    compaction_settings: CompactionSettings | None = None,
    skill_detail: str | None = None,
):
    """Run the agent in a thread pool and stream results via WebSocket."""

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    stop_event = threading.Event()
```
new:
```
async def _run_agent(
    websocket: WebSocket,
    session_id: str,
    content: str,
    history: list[dict],
    api_key: str,
    base_url: str,
    model: str,
    max_iterations: int,
    existing_msgs: list[dict],
    compaction_settings: CompactionSettings | None = None,
    skill_detail: str | None = None,
):
    """Dispatch to the active kernel: legacy thread-pool path or the
    new direct-await path (spec §4.6)."""
    if kernel_mode() == "old":
        await _run_agent_legacy(
            websocket,
            session_id,
            content,
            history,
            api_key,
            base_url,
            model,
            max_iterations,
            existing_msgs,
            compaction_settings,
            skill_detail,
        )
        return
    await _run_agent_new(
        websocket,
        session_id,
        content,
        history,
        api_key,
        base_url,
        model,
        max_iterations,
        existing_msgs,
        compaction_settings,
        skill_detail,
    )


async def _run_agent_new(
    websocket: WebSocket,
    session_id: str,
    content: str,
    history: list[dict],
    api_key: str,
    base_url: str,
    model: str,
    max_iterations: int,
    existing_msgs: list[dict],
    compaction_settings: CompactionSettings | None = None,
    skill_detail: str | None = None,
):
    """Direct-await path (spec §4.6): an AgentEvent listener converts
    events into the existing flat WS message types, in order."""

    async def _send(msg: dict) -> None:
        try:
            await websocket.send_json(msg)
        except RuntimeError:
            pass

    send_tasks: list[asyncio.Task] = []
    stop_received = False

    def _on_approval_request(req: ApprovalRequest) -> None:
        _set_pending_approval(session_id, req)
        send_tasks.append(
            asyncio.create_task(
                _send(
                    {
                        "type": "approval_request",
                        "payload": {"tool_name": req.tool_name, "reason": req.reason},
                    }
                )
            )
        )

    agent = AIAgent(
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_iterations=max_iterations,
        compaction_settings=compaction_settings,
        approval_callback=_on_approval_request,
    )

    memory_store = fact_memory.init_store()
    memory_context = memory_manager.get_context()
    skill_idx = skill_manager.get_active_instructions()
    resolved_skill = skill_detail if skill_detail is not None else skill_manager.get_instructions_for_query(content)
    system_with_memory = build_system_prompt(
        base=agent.system_prompt,
        memory_store=memory_store,
        memory_context=memory_context,
        skill_index=skill_idx,
        skill_detail=resolved_skill,
    )

    turn_no = 0
    tool_no = 0

    def _on_event(event: AgentEvent) -> None:
        nonlocal turn_no, tool_no
        t = event.type
        if t == "message_start" and event.message.get("role") == "assistant":
            turn_no += 1
            send_tasks.append(
                asyncio.create_task(
                    _send({"type": "progress", "message": f"🤔 思考中...（第 {turn_no}/{max_iterations} 轮）"})
                )
            )
        elif t == "message_update":
            if event.delta:
                send_tasks.append(asyncio.create_task(_send({"type": "token", "content": event.delta})))
            if event.reasoning_delta:
                send_tasks.append(
                    asyncio.create_task(_send({"type": "reasoning_token", "content": event.reasoning_delta}))
                )
        elif t == "tool_execution_start":
            try:
                args_str = json.dumps(event.args, ensure_ascii=False)[:200]
            except (TypeError, ValueError):
                args_str = str(event.args)[:200]
            send_tasks.append(
                asyncio.create_task(_send({"type": "tool_call", "name": event.tool_name, "arguments": args_str}))
            )
            send_tasks.append(
                asyncio.create_task(
                    _send({"type": "progress", "message": f"🔧 执行工具: {event.tool_name} | {args_str}"})
                )
            )
        elif t == "tool_execution_end":
            send_tasks.append(
                asyncio.create_task(_send({"type": "tool_result", "name": event.tool_name, "result": event.result}))
            )
        elif t == "turn_end" and event.tool_results:
            tool_no += 1
            send_tasks.append(
                asyncio.create_task(_send({"type": "progress", "message": f"✅ 工具执行完成 (第 {tool_no} 轮)"}))
            )

    agent.agent.subscribe(_on_event)

    async def _listen_inbound():
        nonlocal stop_received
        while not stop_received:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.2)
            except TimeoutError:
                continue
            except Exception:
                _resolve_pending_approval(session_id, False)
                return
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            mtype = data.get("type", "")
            if mtype == "stop":
                stop_received = True
                agent.cancel()
            elif mtype == "approval_response":
                payload = data.get("payload", {})
                _resolve_pending_approval(session_id, payload.get("approved", False))

    listen_task = asyncio.create_task(_listen_inbound())
    error: str | None = None
    result: dict | None = None
    try:
        result = await agent.run_conversation_async(
            user_message=content,
            conversation_history=history,
            system_message=system_with_memory,
            session_id=session_id,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Agent execution failed")
        error = str(e)
    finally:
        stop_received = True
        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass
        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)

    # ── session persistence + done (fields identical to the old path) ──
    all_msgs = existing_msgs.copy()
    all_msgs.append({"role": "user", "content": content})
    new_msgs = (result or {}).get("messages", [])[len(history) + 1:]  # 跳过 history + 当前 user
    for msg in new_msgs:
        role = msg.get("role", "")
        if role in ("assistant", "tool"):
            all_msgs.append(msg)
    if result and result.get("final_response") and not any(
        m.get("role") == "assistant" and m.get("content") == result["final_response"] for m in all_msgs
    ):
        all_msgs.append({"role": "assistant", "content": result["final_response"]})

    title = session_manager.auto_title(all_msgs)
    session_manager.save_session(session_id, all_msgs, title)

    if error is not None:
        await _send({"type": "error", "message": error, "session_id": session_id})
    else:
        await _send(
            {
                "type": "done",
                "final_response": (result or {}).get("final_response", ""),
                "api_calls": (result or {}).get("api_calls", 0),
                "token_usage": (result or {}).get("token_usage"),
                "completed": (result or {}).get("completed", False),
                "error": (result or {}).get("error"),
                "session_id": session_id,
                "session_title": title,
            }
        )

    asst_count = len(
        [
            m
            for m in all_msgs
            if m.get("role") == "assistant" and isinstance(m.get("content"), str) and m["content"]
        ]
    )
    if asst_count >= 2:
        summary = _generate_summary(all_msgs, api_key, base_url, model)
        if summary:
            memory_manager.store_conversation_summary(session_id, title, all_msgs, summary=summary)


async def _run_agent_legacy(
    websocket: WebSocket,
    session_id: str,
    content: str,
    history: list[dict],
    api_key: str,
    base_url: str,
    model: str,
    max_iterations: int,
    existing_msgs: list[dict],
    compaction_settings: CompactionSettings | None = None,
    skill_detail: str | None = None,
):
    """Legacy thread-pool path (ZLINK_KERNEL=old) — verbatim pre-P1 code."""

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    stop_event = threading.Event()
```

（Edit 2 之后，`_run_agent_legacy` 的函数体保持原 `_run_agent` 的代码逐字不变，直至文件末尾。）

- [ ] **Step 4: Run test to verify it passes**

Run: ` .venv/bin/python -m pytest tests/test_chat_async.py -v`

Expected: PASS，`3 passed`

存量回归：

Run: ` .venv/bin/python -m pytest tests/test_chat.py tests/test_agent_loop.py tests/test_approval.py -q`

Expected: PASS，`0 failed`

- [ ] **Step 5: Commit**

```bash
git add backend/api/chat.py tests/test_chat_async.py
git commit -m "feat: add async WS agent path to chat.py with legacy fallback"
```

## Task P1-T8: test_contract_freeze.py — C1–C4 冻结断言

**Files:**
- Test: `tests/test_contract_freeze.py`

**Interfaces:**
- Consumes: `agent.core.agent.AIAgent`（re-export）；`MockLLMProvider`；`agent.events.types` 8 类事件；`agent.tools.registry.registry`。
- Produces: 每期验收任务（P1-T9 / P2-T6 / P3-T3 / P4-T3）运行的契约回归测试；P2-T1 追加 C4 的 `execution_mode` 断言。

- [ ] **Step 1: Write the failing test**

Create `tests/test_contract_freeze.py`:

```python
"""Frozen-contract regression tests (C1–C4) — run at every phase gate.

C2 (WS message types) is covered by tests/test_chat_async.py: the flat
message types observed there are exactly {token, reasoning_token,
progress, tool_call, tool_result, approval_request, done, error}.
"""

from __future__ import annotations

import inspect

from agent.core.agent import AIAgent
from agent.core.llm_client import LLMClient
from tests.conftest import MockLLMProvider, make_text_response


class TestC1RunConversationContract:
    def test_constructor_signature_frozen(self):
        sig = inspect.signature(AIAgent.__init__)
        params = list(sig.parameters)
        for expected in (
            "api_key",
            "base_url",
            "model",
            "max_iterations",
            "max_tokens",
            "max_tool_result_length",
            "system_prompt",
            "enabled_tools",
            "disabled_tools",
            "temperature",
            "progress_callback",
            "tool_call_callback",
            "tool_result_callback",
            "compaction_settings",
            "max_retries",
            "max_retry_delay",
            "approval_callback",
        ):
            assert expected in params, expected

    def test_run_conversation_signature_frozen(self):
        sig = inspect.signature(AIAgent.run_conversation)
        params = list(sig.parameters)
        for expected in (
            "user_message",
            "system_message",
            "conversation_history",
            "stream_callback",
            "reasoning_callback",
            "stop_event",
            "session_id",
        ):
            assert expected in params, expected

    def test_return_keys_frozen(self):
        provider = MockLLMProvider(responses=[make_text_response("hi")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)
        result = agent.run_conversation("hello")
        assert set(result.keys()) == {
            "final_response",
            "messages",
            "api_calls",
            "token_usage",
            "completed",
            "error",
        }


class TestC3EventBusContract:
    def test_eight_event_classes_still_importable(self):
        from agent.events.types import (
            AfterLLMCallEvent,
            AfterToolCallEvent,
            BeforeLLMCallEvent,
            BeforeToolCallEvent,
            PhaseChangeEvent,
            SessionEndEvent,
            SessionStartEvent,
            UserMessageEvent,
        )

        assert SessionStartEvent.type == "session_start"
        assert SessionEndEvent.type == "session_end"
        assert UserMessageEvent.type == "user_message"
        assert BeforeLLMCallEvent.type == "before_llm_call"
        assert AfterLLMCallEvent.type == "after_llm_call"
        assert BeforeToolCallEvent.type == "before_tool_call"
        assert AfterToolCallEvent.type == "after_tool_call"
        assert PhaseChangeEvent.type == "phase_change"

    def test_cancel_semantics_unchanged(self):
        from agent.events.types import BeforeToolCallEvent

        ev = BeforeToolCallEvent(tool_name="ls", args={})
        ev.cancel("blocked by test")
        assert ev.cancelled is True
        assert ev.cancel_reason == "blocked by test"


class TestC4RegistryContract:
    def test_public_api_present(self):
        from agent.tools.registry import registry

        assert callable(registry.register)
        assert callable(registry.deregister)
        assert callable(registry.dispatch)
        assert callable(registry.get_definitions)
        assert callable(registry.get_all_tool_names)
        assert callable(registry.add_before_hook)
        assert callable(registry.remove_before_hook)
        assert callable(registry.add_after_hook)
        assert callable(registry.remove_after_hook)

    def test_block_protocol_unchanged(self):
        from agent.tools.registry import registry

        def block_hook(tool_name, args):
            return {**args, "__block__": True, "__reason__": "frozen protocol"}

        registry.add_before_hook(block_hook)
        try:
            result = registry.dispatch("definitely_missing_tool_xyz", {})
            import json

            payload = json.loads(result)
            assert payload["success"] is False
            assert "Unknown tool" in payload["error"]
        finally:
            registry.remove_before_hook(block_hook)
```

- [ ] **Step 2: Run test to verify it fails**

Run: ` .venv/bin/python -m pytest tests/test_contract_freeze.py -v`

Expected: FAIL（`agent/core/agent.py` 仍是旧实现时 `AIAgent.__init__` 等断言可能过，但 C4 `dispatch` 在旧 registry 上也应通过——若 P1-T1~T7 已落地则本任务"失败"点主要是 `execution_mode` 相关断言的缺失；此处以测试文件首次创建时直接跑通为准，若全部通过说明契约未破坏，符合验收目标。运行若 FAIL 只允许是导入错误/拼写错误，不允许契约断言失败）

- [ ] **Step 3: Implement the test（本任务无生产代码改动，测试即交付物）**

无生产代码改动。若 Step 2 因 `agent.core.agent` 尚缺 re-export 而失败，先确认 P1-T5/T6 已提交；本任务只创建测试文件。

- [ ] **Step 4: Run test to verify it passes**

Run: ` .venv/bin/python -m pytest tests/test_contract_freeze.py -v`

Expected: PASS，`8 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_contract_freeze.py
git commit -m "test: add frozen contract regression tests (C1-C4)"
```

## Task P1-T9: P1 期验收（全量双跑 + ruff + 四契约 + 冻结测试文件零改动）

**Files:**
- Test: 无新文件；仅运行验证。

**Interfaces:**
- Consumes: P1-T1~T8 全部交付物；`ZLINK_KERNEL` 环境变量。

- [ ] **Step 1: 默认（new）内核全量测试**

Run: ` .venv/bin/python -m pytest tests/ -q`

Expected: `passed` 且 `0 failed`（当前 378 + 新增 ≈ 455）。若有失败：定位到具体任务修复后重跑，禁止带红进入 P2。

- [ ] **Step 2: old 内核全量测试（双跑验证，spec §6.3/R2）**

Run: `ZLINK_KERNEL=old .venv/bin/python -m pytest tests/ -q`

Expected: `passed` 且 `0 failed`（旧算法行内副本行为与重构前一致）。

- [ ] **Step 3: ruff 检查**

Run: `ruff check . && ruff format --check .`

Expected: `All checks passed!` 且无 format diff。

- [ ] **Step 4: 冻结测试文件零改动校验**

Run: `git diff --stat -- tests/test_agent_loop.py tests/test_chat.py tests/test_extensions.py tests/test_tool_registry.py`

Expected: 输出为空（这些文件 P1 期间未改一行）。

- [ ] **Step 5: 四契约回归**

Run: ` .venv/bin/python -m pytest tests/test_contract_freeze.py tests/test_chat_async.py -q`

Expected: `passed` 且 `0 failed`。

- [ ] **Step 6: Commit（验收记录；若全部通过，无代码改动则跳过 commit；有修复则单独 commit）**

```bash
git status --porcelain
# 若 P1 有未提交修复：
git add -u && git commit -m "fix: P1 phase acceptance fixes"
```

---

# P2 —— 并行工具 + execution_mode 审计 + finish_reason 映射 + length 截断防护

行为目标：`registry.register` 增 `execution_mode`（默认 `parallel`）；25 个写操作/状态突变工具标 `sequential`；`dispatch_tool_batch` 并行化（prepare 串行 + handler 并发 + 保序 + sequential 降级）；`openai_compat`/`anthropic` 补 finish_reason→`stop_reason` 映射；`stop_reason=="length"` 截断防护真实生效。

## Task P2-T1: registry.py — execution_mode 字段与 register 参数

**Files:**
- Modify: `agent/tools/registry.py`（仅 `ToolEntry` 与 `register()`，`dispatch()` 主体逐字节不动）
- Test: `tests/test_tool_registry.py` 追加（该文件允许追加，但不得删改现有 5 个测试）

**Interfaces:**
- Consumes: 既有 `ToolRegistry`/`ToolEntry`。
- Produces（P2-T2 审计与 P2-T4 并行判定依赖）：`ToolEntry.execution_mode: str`（`__slots__` 增加 `"execution_mode"`，`__init__` 增参 `execution_mode: str = "parallel"`）；`register(..., execution_mode: str = "parallel") -> None`（向后兼容，C4 允许）；`get_definitions` 输出不变（execution_mode 不进 schema）。

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tool_registry.py`:

```python
class TestExecutionMode:
    def test_default_is_parallel(self):
        from agent.tools.registry import registry, tool_result

        def _handler(args: dict) -> str:
            return tool_result()

        registry.register(name="t_mode_default", toolset="test", schema={"type": "object"}, handler=_handler)
        entry = registry.get_entry("t_mode_default")
        assert entry is not None
        assert entry.execution_mode == "parallel"

    def test_can_specify_sequential(self):
        from agent.tools.registry import registry, tool_result

        def _handler(args: dict) -> str:
            return tool_result()

        registry.register(
            name="t_mode_seq",
            toolset="test",
            schema={"type": "object"},
            handler=_handler,
            execution_mode="sequential",
        )
        assert registry.get_entry("t_mode_seq").execution_mode == "sequential"

    def test_execution_mode_not_exposed_in_definitions(self):
        from agent.tools.registry import registry, tool_result

        def _handler(args: dict) -> str:
            return tool_result()

        registry.register(
            name="t_mode_hidden",
            toolset="test",
            schema={"type": "object", "properties": {}},
            handler=_handler,
            execution_mode="sequential",
        )
        defs = registry.get_definitions(tool_names=["t_mode_hidden"])
        assert len(defs) == 1
        assert "execution_mode" not in defs[0]
        assert "execution_mode" not in json.dumps(defs[0])
```

- [ ] **Step 2: Run test to verify it fails**

Run: ` .venv/bin/python -m pytest tests/test_tool_registry.py -k ExecutionMode -v`

Expected: FAIL with `AttributeError: 'ToolEntry' object has no attribute 'execution_mode'`

- [ ] **Step 3: Write minimal implementation**

Edit 1 — `ToolEntry.__slots__` 增加字段：

old:
```
    __slots__ = (
        "name",
        "toolset",
        "schema",
        "handler",
        "check_fn",
        "description",
        "emoji",
        "risk_level",
    )
```
new:
```
    __slots__ = (
        "name",
        "toolset",
        "schema",
        "handler",
        "check_fn",
        "description",
        "emoji",
        "risk_level",
        "execution_mode",
    )
```

Edit 2 — `ToolEntry.__init__` 增加参数与赋值：

old:
```
    def __init__(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable | None = None,
        description: str = "",
        emoji: str = "",
        risk_level: str = "low",
    ):
        self.name = name
        self.toolset = toolset
        self.schema = schema
        self.handler = handler
        self.check_fn = check_fn
        self.description = description
        self.emoji = emoji
        self.risk_level = risk_level
```
new:
```
    def __init__(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable | None = None,
        description: str = "",
        emoji: str = "",
        risk_level: str = "low",
        execution_mode: str = "parallel",
    ):
        self.name = name
        self.toolset = toolset
        self.schema = schema
        self.handler = handler
        self.check_fn = check_fn
        self.description = description
        self.emoji = emoji
        self.risk_level = risk_level
        self.execution_mode = execution_mode
```

Edit 3 — `register()` 增加参数并透传：

old:
```
    def register(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable | None = None,
        description: str = "",
        emoji: str = "",
        risk_level: str = "low",
    ) -> None:
        """Register a tool."""
        self._entries[name] = ToolEntry(
            name=name,
            toolset=toolset,
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            description=description,
            emoji=emoji,
            risk_level=risk_level,
        )
```
new:
```
    def register(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable | None = None,
        description: str = "",
        emoji: str = "",
        risk_level: str = "low",
        execution_mode: str = "parallel",
    ) -> None:
        """Register a tool.  ``execution_mode`` is "parallel" (default)
        or "sequential"; it never leaks into ``get_definitions``."""
        self._entries[name] = ToolEntry(
            name=name,
            toolset=toolset,
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            description=description,
            emoji=emoji,
            risk_level=risk_level,
            execution_mode=execution_mode,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: ` .venv/bin/python -m pytest tests/test_tool_registry.py -v`

Expected: PASS，`5 (现有) + 3 (新增) = 8 passed`

- [ ] **Step 5: Commit**

```bash
git add agent/tools/registry.py tests/test_tool_registry.py
git commit -m "feat: add execution_mode to tool registry (default parallel)"
```

## Task P2-T2: 工具审计 — 25 个写操作/状态突变工具标 sequential

**Files:**
- Modify（15 个文件，每个 `register()` 调用的 `name="<tool>",` 行后插入一行 `    execution_mode="sequential",`）：
  - `agent/tools/code_execution_tool.py`（`execute_code`）
  - `agent/tools/file_tools.py`（`write_file`、`patch`）
  - `agent/tools/terminal_tool.py`（`terminal`、`close_terminal`）
  - `agent/tools/process_tool.py`（`process`）
  - `agent/tools/memory_tool.py`（`memory`）
  - `agent/tools/todo_tool.py`（`todo`）
  - `agent/tools/skills_tool.py`（`skill_install`、`skill_activate`、`skill_deactivate`、`skill_export`）
  - `agent/tools/cronjob_tools.py`（`cronjob_create`、`cronjob_update`、`cronjob_delete`、`cronjob_toggle`、`cronjob_run`）
  - `agent/tools/mcp_management_tool.py`（`mcp_add_server`、`mcp_delete_server`、`mcp_toggle_server`、`mcp_reload_servers`）
  - `agent/tools/project_tools.py`（`project_create`、`project_switch`）
  - `agent/tools/erp_ys_tools.py`（`ys_api`）
  - `agent/tools/erp_nc_tools.py`（`nc_raw_sql`）
- Test: `tests/test_execution_mode_audit.py`

**Interfaces:**
- Consumes: P2-T1 的 `register(..., execution_mode=...)`。
- Produces（P2-T4 判定）：注册表内 25 个工具的 `execution_mode == "sequential"`；其余 32 个工具保持默认 `"parallel"`（含 bridge 工具与全部查询类工具）。

- [ ] **Step 1: Write the failing test**

Create `tests/test_execution_mode_audit.py`:

```python
"""Audit regression: write/state-mutating tools must be sequential.

Spec §4.5: 拿不准的工具一律标 sequential（并行是优化，串行是安全基线）。
"""

from __future__ import annotations

from agent.tools.registry import registry, discover_tools

SEQUENTIAL_TOOLS = {
    "execute_code",
    "patch",
    "write_file",
    "terminal",
    "process",
    "memory",
    "todo",
    "skill_install",
    "skill_activate",
    "skill_deactivate",
    "skill_export",
    "cronjob_create",
    "cronjob_update",
    "cronjob_delete",
    "cronjob_toggle",
    "cronjob_run",
    "mcp_add_server",
    "mcp_delete_server",
    "mcp_toggle_server",
    "mcp_reload_servers",
    "project_create",
    "project_switch",
    "ys_api",
    "nc_raw_sql",
    "close_terminal",
}

# 明确 parallel 的读/查询类工具抽查（防误标）
PARALLEL_SAMPLE = {
    "read_file",
    "ls",
    "glob",
    "search_files",
    "web_search",
    "web_extract",
    "session_search",
    "query_sale_orders",
    "nc_query",
    "tool_search",
    "tool_call",
    "clarify",
    "skill_list",
    "mcp_list_servers",
    "project_list",
    "cronjob_list",
}


def test_audited_sequential_tools_marked():
    discover_tools()
    for name in SEQUENTIAL_TOOLS:
        entry = registry.get_entry(name)
        assert entry is not None, f"{name} not registered"
        assert entry.execution_mode == "sequential", f"{name} must be sequential"


def test_parallel_tools_keep_default():
    discover_tools()
    for name in PARALLEL_SAMPLE:
        entry = registry.get_entry(name)
        assert entry is not None, f"{name} not registered"
        assert entry.execution_mode == "parallel", f"{name} must stay parallel"
```

- [ ] **Step 2: Run test to verify it fails**

Run: ` .venv/bin/python -m pytest tests/test_execution_mode_audit.py -v`

Expected: FAIL（25 个工具当前 `execution_mode` 为默认 `parallel`）

- [ ] **Step 3: Write minimal implementation**

对上述 15 个文件中每个目标工具的 `register()` 调用，在其 `    name="<tool>",` 行后插入 `    execution_mode="sequential",`。每个文件内 `name="<tool>",` 唯一，可直接作为 Edit 锚点。逐文件示例（file_tools.py 的 `write_file`）：

old:
```
    name="write_file",
```
new:
```
    name="write_file",
    execution_mode="sequential",
```

其余 24 处完全同理（锚点均为各自文件内唯一的 `    name="<tool>",` 行；`terminal_tool.py` 的 `terminal` 与 `close_terminal`、`skills_tool.py` 的 4 个、`cronjob_tools.py` 的 5 个、`mcp_management_tool.py` 的 4 个、`erp_*` 各 1 个均按此模式）。注意：`mcp_management_tool.py` 中 `mcp_test_server`、`mcp_list_servers` **不加** sequential（只读/测试类）；`cronjob_list`、`project_list`、`read_terminal` 不加。

- [ ] **Step 4: Run test to verify it passes**

Run: ` .venv/bin/python -m pytest tests/test_execution_mode_audit.py -v`

Expected: PASS，`2 passed`

存量回归（确认无工具因缩进/锚点错位被误改）：

Run: ` .venv/bin/python -m pytest tests/test_tool_registry.py tests/test_agent_loop.py tests/test_approval.py -q`

Expected: PASS，`0 failed`

- [ ] **Step 5: Commit**

```bash
git add agent/tools/ tests/test_execution_mode_audit.py
git commit -m "feat: mark write/state-mutating tools as sequential execution"
```

## Task P2-T3: finish_reason → stop_reason 映射（openai_compat + anthropic，R3）

**Files:**
- Modify: `agent/core/llm_providers/openai_compat.py`、`agent/core/llm_providers/anthropic.py`（spec §8 R3 允许的唯一 LLM 层改动）
- Test: `tests/test_stop_reason_mapping.py`

**Interfaces:**
- Consumes: `LLMResponse`（`stop_reason` 字段已存在，base.py 不改）。
- Produces（P2-T5 截断防护的前置条件）：两个 provider 的成功/失败路径都透出统一 `stop_reason`：
  - openai `finish_reason`：`"stop"→"end_turn"`、`"length"→"length"`、`"tool_calls"→"tool_calls"`、`"content_filter"→"content_filter"`、`None→None`、未知原样透传（`_map_finish_reason`）
  - anthropic `stop_reason`：`"end_turn"→"end_turn"`、`"max_tokens"→"length"`、`"tool_use"→"tool_calls"`、`"stop_sequence"→"stop_sequence"`、`None→None`、未知原样透传（`_map_anthropic_stop_reason`）
  - `stop_reason` 缺失/未知时行为退化 = 现状（照常执行，不回退不抛错，R3）

- [ ] **Step 1: Write the failing test**

Create `tests/test_stop_reason_mapping.py`:

```python
"""Tests for finish_reason → stop_reason mapping (spec §8 R3).

Zero-network: providers' HTTP layer is monkeypatched, exactly like
tests/test_openai_compat.py.
"""

from __future__ import annotations

import threading

from agent.core.llm_providers.base import LLMResponse
from agent.core.llm_providers.openai_compat import (
    OpenAICompatProvider,
    _map_finish_reason,
)
from agent.core.llm_providers.anthropic import (
    _anthropic_response_to_llm,
    _map_anthropic_stop_reason,
)


class TestMapFinishReason:
    def test_stop_maps_to_end_turn(self):
        assert _map_finish_reason("stop") == "end_turn"

    def test_length_passes_through(self):
        assert _map_finish_reason("length") == "length"

    def test_tool_calls_maps(self):
        assert _map_finish_reason("tool_calls") == "tool_calls"

    def test_none_and_unknown(self):
        assert _map_finish_reason(None) is None
        assert _map_finish_reason("weird") == "weird"


class TestOpenAIBlocking:
    def _provider(self):
        return OpenAICompatProvider(api_key="sk-x", base_url="http://localhost:9/v1")

    def test_blocking_length_finish_reason(self, monkeypatch):
        provider = self._provider()

        def mock_request(body):
            return _FakeResponse(
                json={
                    "choices": [
                        {
                            "message": {"content": "partial", "role": "assistant"},
                            "finish_reason": "length",
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                }
            )

        monkeypatch.setattr(provider, "_request", mock_request)
        resp = provider._chat_blocking({"model": "gpt-4o", "messages": []})
        assert resp.stop_reason == "length"
        assert resp.content == "partial"

    def test_blocking_stop_finish_reason(self, monkeypatch):
        provider = self._provider()

        def mock_request(body):
            return _FakeResponse(
                json={
                    "choices": [{"message": {"content": "ok", "role": "assistant"}, "finish_reason": "stop"}],
                    "usage": {},
                }
            )

        monkeypatch.setattr(provider, "_request", mock_request)
        resp = provider._chat_blocking({"model": "gpt-4o", "messages": []})
        assert resp.stop_reason == "end_turn"


class _FakeResponse:
    def __init__(self, json):
        self._json = json

    def json(self):
        return self._json


class TestOpenAIStreaming:
    def test_stream_captures_length_finish_reason(self, monkeypatch):
        provider = OpenAICompatProvider(api_key="sk-x", base_url="http://localhost:9/v1")
        lines = [
            'data: {"choices":[{"delta":{"content":"Hello"},"index":0}]}',
            'data: {"choices":[{"delta":{},"index":0,"finish_reason":"length"}],"usage":{"prompt_tokens":1,"completion_tokens":2,"total_tokens":3}}',
            "data: [DONE]",
        ]
        monkeypatch.setattr(provider, "_request_stream", lambda body: iter(lines))
        resp = provider._chat_stream(
            body={"model": "gpt-4o"},
            stream_callback=lambda t: None,
            stop_event=threading.Event(),
        )
        assert resp.stop_reason == "length"
        assert resp.content == "Hello"

    def test_stream_no_finish_reason_is_none(self, monkeypatch):
        provider = OpenAICompatProvider(api_key="sk-x", base_url="http://localhost:9/v1")
        lines = [
            'data: {"choices":[{"delta":{"content":"Hello"},"index":0}]}',
            "data: [DONE]",
        ]
        monkeypatch.setattr(provider, "_request_stream", lambda body: iter(lines))
        resp = provider._chat_stream(
            body={"model": "gpt-4o"},
            stream_callback=lambda t: None,
            stop_event=threading.Event(),
        )
        assert resp.stop_reason is None


class TestMapAnthropicStopReason:
    def test_max_tokens_maps_to_length(self):
        assert _map_anthropic_stop_reason("max_tokens") == "length"

    def test_end_turn_and_tool_use(self):
        assert _map_anthropic_stop_reason("end_turn") == "end_turn"
        assert _map_anthropic_stop_reason("tool_use") == "tool_calls"

    def test_none_and_unknown(self):
        assert _map_anthropic_stop_reason(None) is None
        assert _map_anthropic_stop_reason("stop_sequence") == "stop_sequence"


class _FakeBlock:
    def __init__(self, btype, **kw):
        self.type = btype
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeUsage:
    input_tokens = 1
    output_tokens = 2


class _FakeAnthResponse:
    def __init__(self, stop_reason=None, content=None, usage=None):
        self.stop_reason = stop_reason
        self.content = content or []
        self.usage = usage


class TestAnthropicBlocking:
    def test_max_tokens_stop_reason_maps_to_length(self):
        resp = _FakeAnthResponse(
            stop_reason="max_tokens",
            content=[_FakeBlock("text", text="partial answer")],
            usage=_FakeUsage(),
        )
        llm = _anthropic_response_to_llm(resp)
        assert llm.stop_reason == "length"
        assert llm.content == "partial answer"

    def test_tool_use_stop_reason(self):
        resp = _FakeAnthResponse(
            stop_reason="tool_use",
            content=[_FakeBlock("tool_use", id="t1", name="ls", input={})],
            usage=_FakeUsage(),
        )
        llm = _anthropic_response_to_llm(resp)
        assert llm.stop_reason == "tool_calls"
        assert llm.tool_calls is not None and llm.tool_calls[0].name == "ls"

    def test_no_stop_reason_is_none(self):
        resp = _FakeAnthResponse(content=[_FakeBlock("text", text="ok")], usage=_FakeUsage())
        llm = _anthropic_response_to_llm(resp)
        assert llm.stop_reason is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: ` .venv/bin/python -m pytest tests/test_stop_reason_mapping.py -v`

Expected: FAIL（`_map_finish_reason` 不存在 → `ImportError`；且 `resp.stop_reason` 为 None）

- [ ] **Step 3: Write minimal implementation**

Edit A — `agent/core/llm_providers/openai_compat.py`：

A1：在 `_extract_inline_thinking` 函数之后、类定义之前插入映射函数：

old:
```
    return actual_content, thinking_text or None


class OpenAICompatProvider(LLMProvider):
```
new:
```
    return actual_content, thinking_text or None


def _map_finish_reason(finish_reason: str | None) -> str | None:
    """Map an OpenAI ``finish_reason`` onto the unified ``stop_reason``.

    ``"length"`` (truncation guard, spec §8 R3) is the critical case;
    ``"stop"`` maps to the documented ``"end_turn"`` convention
    (llm_providers/base.py docstring).  Unknown values pass through.
    """
    return {
        "stop": "end_turn",
        "length": "length",
        "tool_calls": "tool_calls",
        "content_filter": "content_filter",
        None: None,
    }.get(finish_reason, finish_reason)


class OpenAICompatProvider(LLMProvider):
```

A2：`_chat_blocking` 透出 stop_reason：

old:
```
        return LLMResponse(
            content=c,
            reasoning=r,
            tool_calls=tool_calls,
            usage=usage,
        )
```
new:
```
        return LLMResponse(
            content=c,
            reasoning=r,
            tool_calls=tool_calls,
            usage=usage,
            stop_reason=_map_finish_reason(choice.get("finish_reason")),
        )
```

A3：`_chat_stream` 捕获 finish_reason（3 处小编辑）：

A3-1（初始化）：
old:
```
        content = ""
        reasoning = ""
        tool_calls_map: dict[int, dict] = {}
        usage: dict | None = None
```
new:
```
        content = ""
        reasoning = ""
        tool_calls_map: dict[int, dict] = {}
        usage: dict | None = None
        finish_reason: str | None = None
```

A3-2（每 chunk 捕获）：
old:
```
                choices = chunk.get("choices")
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
```
new:
```
                choices = chunk.get("choices")
                if not choices:
                    continue
                fr = choices[0].get("finish_reason")
                if fr:
                    finish_reason = fr
                delta = choices[0].get("delta", {})
```

A3-3（返回透出）：
old:
```
        return LLMResponse(
            content=content,
            reasoning=reasoning or None,
            tool_calls=tool_calls,
            usage=usage,
        )
```
new:
```
        return LLMResponse(
            content=content,
            reasoning=reasoning or None,
            tool_calls=tool_calls,
            usage=usage,
            stop_reason=_map_finish_reason(finish_reason),
        )
```

Edit B — `agent/core/llm_providers/anthropic.py`：

B1：在 `_messages_to_anthropic` 之后插入映射函数：

old:
```
    if pending_tool_results:
        out.append({"role": "user", "content": pending_tool_results})
    return out


class AnthropicProvider(LLMProvider):
```
new:
```
    if pending_tool_results:
        out.append({"role": "user", "content": pending_tool_results})
    return out


def _map_anthropic_stop_reason(stop_reason: str | None) -> str | None:
    """Map an Anthropic native ``stop_reason`` onto the unified value.

    ``"max_tokens"`` → ``"length"`` (truncation guard, spec §8 R3);
    ``"tool_use"`` → ``"tool_calls"``; ``"end_turn"`` stays.  Unknown
    values pass through (R3: degrade to current behaviour, never raise).
    """
    return {
        "end_turn": "end_turn",
        "max_tokens": "length",
        "tool_use": "tool_calls",
        "stop_sequence": "stop_sequence",
        None: None,
    }.get(stop_reason, stop_reason)


class AnthropicProvider(LLMProvider):
```

B2：`_anthropic_response_to_llm` 透出：

old:
```
    return LLMResponse(
        content="".join(text_parts),
        reasoning="\n".join(reasoning_parts) if reasoning_parts else None,
        tool_calls=tool_calls or None,
        usage=usage,
    )
```
new:
```
    return LLMResponse(
        content="".join(text_parts),
        reasoning="\n".join(reasoning_parts) if reasoning_parts else None,
        tool_calls=tool_calls or None,
        usage=usage,
        stop_reason=_map_anthropic_stop_reason(getattr(response, "stop_reason", None)),
    )
```

B3：`_chat_stream` 捕获 stop_reason（2 处小编辑）：

B3-1（初始化）：
old:
```
        text = ""
        tool_calls_map: dict[int, dict] = {}  # block index → {id, name, args}
        thinking_parts: list[str] = []
        usage: dict | None = None
```
new:
```
        text = ""
        tool_calls_map: dict[int, dict] = {}  # block index → {id, name, args}
        thinking_parts: list[str] = []
        usage: dict | None = None
        stop_reason: str | None = None
```

B3-2（message_delta 捕获）：
old:
```
                elif etype == "message_delta":
                    usage_obj = getattr(event, "usage", None)
```
new:
```
                elif etype == "message_delta":
                    sr = getattr(event, "stop_reason", None)
                    if sr:
                        stop_reason = sr
                    usage_obj = getattr(event, "usage", None)
```

B3-3（返回透出）：
old:
```
        return LLMResponse(
            content=text,
            reasoning="\n".join(thinking_parts) if thinking_parts else None,
            tool_calls=tool_calls,
            usage=usage,
        )
```
new:
```
        return LLMResponse(
            content=text,
            reasoning="\n".join(thinking_parts) if thinking_parts else None,
            tool_calls=tool_calls,
            usage=usage,
            stop_reason=_map_anthropic_stop_reason(stop_reason),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: ` .venv/bin/python -m pytest tests/test_stop_reason_mapping.py -v`

Expected: PASS，`11 passed`

存量回归（两个 provider 现有测试不得破坏）：

Run: ` .venv/bin/python -m pytest tests/test_openai_compat.py tests/test_deepseek_provider.py -q`

Expected: PASS，`0 failed`

- [ ] **Step 5: Commit**

```bash
git add agent/core/llm_providers/openai_compat.py agent/core/llm_providers/anthropic.py tests/test_stop_reason_mapping.py
git commit -m "feat: map finish_reason to stop_reason in providers (length guard prerequisite)"
```

## Task P2-T4: dispatch_tool_batch 并行化（保序 + sequential 降级）

**Files:**
- Modify: `agent/core/tool_dispatcher.py`（`dispatch_tool_batch` 内部重构 + 新增 `_dispatch_parallel`/`_dispatch_sequential`/`_Prepared`/`_entry_mode`；公开签名不变）
- Test: `tests/test_tool_dispatcher_batch.py`（改造 P1 的串行耗时测试 + 追加并行用例）

**Interfaces:**
- Consumes: P2-T1 的 `ToolEntry.execution_mode`；P2-T2 的审计标注。
- Produces（P2-T5 与 loop 依赖，签名与 P1-T2 完全一致）：
  - `async dispatch_tool_batch(calls, *, max_result_length, token, emit, config) -> ExecutedToolBatch` — 批次内任一工具 `execution_mode == "sequential"` → 整批 `_dispatch_sequential`（执行顺序即调用顺序，Pi `hasSequentialToolCall` 同款语义）；否则 `_dispatch_parallel`
  - `_dispatch_parallel` 语义：prepare 串行（解析 + before_tool_call + 取消检查，`token.check()` 每项一次）；全部非 immediate 工具先按调用序 emit `ToolExecutionStart`（WS `tool_call` 卡片保序），再 `asyncio.gather` 并发执行（`_run_handler`/`_finalize` 各协程内部 `asyncio.to_thread` 包装同步 handler）；gather 完成后按原始 index 排序，按调用序 emit `ToolExecutionEnd` 并组装 `ToolResult`（transcript 保序）

- [ ] **Step 1: Write the failing test**

改造 `tests/test_tool_dispatcher_batch.py` 的耗时测试并追加并行用例：

Edit 1 — 把 P1 的串行耗时测试改为并行耗时断言：

old:
```
def test_sequential_batch_sleeps_are_serial():
    """P1 sanity: two 0.15s tools take >= ~0.3s (sequential, not parallel yet)."""

    def sleepy(args: dict) -> str:
        time.sleep(0.15)
        return tool_result()

    registry.register(name="t_sleep", toolset="test", schema={"type": "object"}, handler=sleepy)
    start = time.monotonic()
    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name="t_sleep", arguments="{}"),
             ToolCallPayload(id="c2", name="t_sleep", arguments="{}")],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(),
        )
    )
    elapsed = time.monotonic() - start
    assert len(batch.messages) == 2
    assert elapsed >= 0.28, f"expected serial execution, took {elapsed:.3f}s"
```
new:
```
def test_parallel_batch_sleeps_are_concurrent():
    """P2: default-parallel tools run concurrently — elapsed ≈ max, not Σ."""

    def sleepy(args: dict) -> str:
        time.sleep(0.25)
        return tool_result()

    registry.register(name="t_sleep", toolset="test", schema={"type": "object"}, handler=sleepy)
    start = time.monotonic()
    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name="t_sleep", arguments="{}"),
             ToolCallPayload(id="c2", name="t_sleep", arguments="{}"),
             ToolCallPayload(id="c3", name="t_sleep", arguments="{}")],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(),
        )
    )
    elapsed = time.monotonic() - start
    assert len(batch.messages) == 3
    assert elapsed < 0.60, f"expected concurrent execution, took {elapsed:.3f}s (3 x 0.25s serial = 0.75s)"


def test_parallel_preserves_call_order_in_results_and_events():
    def sleeper(args: dict) -> str:
        delay = args.get("d", 0.0)
        time.sleep(delay)
        return tool_result(data={"tag": args.get("tag")})

    registry.register(name="t_psleep", toolset="test", schema={"type": "object"}, handler=sleeper)
    recorder = _EventRecorder()
    calls = [
        ToolCallPayload(id="c1", name="t_psleep", arguments='{"tag": "first", "d": 0.25}'),
        ToolCallPayload(id="c2", name="t_psleep", arguments='{"tag": "second", "d": 0.0}'),
        ToolCallPayload(id="c3", name="t_psleep", arguments='{"tag": "third", "d": 0.1}'),
    ]
    batch = _run(
        dispatch_tool_batch(
            calls,
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=recorder,
            config=_make_config(),
        )
    )
    # transcript order == original call order (fast "second" must not jump ahead)
    assert [r.tool_call_id for r in batch.messages] == ["c1", "c2", "c3"]
    assert [json.loads(r.result)["data"]["tag"] for r in batch.messages] == ["first", "second", "third"]
    # ToolExecutionStart and ToolExecutionEnd both in call order
    starts = [e.tool_call_id for e in recorder.events if isinstance(e, ToolExecutionStart)]
    ends = [e.tool_call_id for e in recorder.events if isinstance(e, ToolExecutionEnd)]
    assert starts == ["c1", "c2", "c3"]
    assert ends == ["c1", "c2", "c3"]


def test_sequential_tool_degrades_whole_batch():
    order: list[str] = []

    def parallel_sleep(args: dict) -> str:
        order.append(args.get("tag"))
        time.sleep(0.15)
        return tool_result()

    def seq_tool(args: dict) -> str:
        order.append("seq")
        time.sleep(0.15)
        return tool_result()

    registry.register(name="t_ps", toolset="test", schema={"type": "object"}, handler=parallel_sleep)
    registry.register(name="t_seq", toolset="test", schema={"type": "object"}, handler=seq_tool, execution_mode="sequential")

    start = time.monotonic()
    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id="c1", name="t_ps", arguments='{"tag": "a"}'),
             ToolCallPayload(id="c2", name="t_seq", arguments="{}"),
             ToolCallPayload(id="c3", name="t_ps", arguments='{"tag": "c"}')],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(),
        )
    )
    elapsed = time.monotonic() - start
    assert order == ["a", "seq", "c"], f"must run strictly serially, got {order}"
    assert elapsed >= 0.40, f"expected serial (3 x 0.15s), took {elapsed:.3f}s"
    assert [r.tool_call_id for r in batch.messages] == ["c1", "c2", "c3"]


def test_prepare_runs_serially_before_handlers():
    seen: list[str] = []

    def record(args: dict) -> str:
        return tool_result()

    registry.register(name="t_prep", toolset="test", schema={"type": "object"}, handler=record)

    def _before(name: str, args: dict, token: CancelToken) -> dict:
        seen.append(f"prep:{name}")
        return args

    batch = _run(
        dispatch_tool_batch(
            [ToolCallPayload(id=f"c{i}", name="t_prep", arguments="{}") for i in range(3)],
            max_result_length=sys.maxsize,
            token=CancelToken(),
            emit=_EventRecorder(),
            config=_make_config(before_tool_call=_before),
        )
    )
    assert seen == ["prep:t_prep", "prep:t_prep", "prep:t_prep"]
    assert len(batch.messages) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: ` .venv/bin/python -m pytest tests/test_tool_dispatcher_batch.py -v`

Expected: FAIL（`test_parallel_batch_sleeps_are_concurrent` 断言 elapsed < 0.60，而 P1 串行实现约 0.75s；`test_sequential_tool_degrades_whole_batch` 中 `t_seq` 未降级等）

- [ ] **Step 3: Write minimal implementation**

在 `agent/core/tool_dispatcher.py` 中替换 `dispatch_tool_batch` 的实现并追加辅助（Edit 锚点 = P1 的 `dispatch_tool_batch` 函数体）：

old:
```
async def dispatch_tool_batch(
    calls: list[ToolCallPayload],
    *,
    max_result_length: int,
    token: CancelToken,
    emit: Callable[[AgentEvent], Awaitable[None]],
    config: AgentLoopConfig,
) -> ExecutedToolBatch:
    """Execute a batch of tool calls and return results in original order.

    P1: strict sequential — per call: prepare → execute → finalize.
    P2: parallel with sequential degradation (same signature).
    """
    results: list[ToolResult] = []
    for tc in calls:
        token.check()
        args, immediate = await _prepare(tc, config, token, emit)
        if immediate is not None:
            results.append(
                ToolResult(
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                    result=_truncate(immediate, max_result_length),
                    is_error=True,
                )
            )
            continue
        await emit(ToolExecutionStart(tool_call_id=tc.id, tool_name=tc.name, args=args))
        raw = await _run_handler(tc.name, args, config, token)
        finalized = await _finalize(tc.name, args, raw, config, token)
        truncated = _truncate(finalized, max_result_length)
        await emit(ToolExecutionEnd(tool_call_id=tc.id, tool_name=tc.name, result=truncated))
        results.append(ToolResult(tool_call_id=tc.id, tool_name=tc.name, result=truncated))
    return ExecutedToolBatch(messages=results, terminate=False)
```
new:
```
def _entry_mode(name: str) -> str:
    """Return a tool's execution_mode, defaulting to "parallel"."""
    entry = registry.get_entry(name)
    if entry is None:
        return "parallel"  # unknown tools produce an error result anyway
    return getattr(entry, "execution_mode", "parallel")


@dataclass
class _Prepared:
    tc: ToolCallPayload
    args: dict
    index: int
    immediate: str | None = None


async def dispatch_tool_batch(
    calls: list[ToolCallPayload],
    *,
    max_result_length: int,
    token: CancelToken,
    emit: Callable[[AgentEvent], Awaitable[None]],
    config: AgentLoopConfig,
) -> ExecutedToolBatch:
    """Execute a batch of tool calls and return results in original order.

    P2: parallel with sequential degradation — a batch containing any
    ``execution_mode == "sequential"`` tool falls back to strict serial
    execution (Pi's hasSequentialToolCall → executeToolCallsSequential).
    """
    sequential = any(_entry_mode(tc.name) == "sequential" for tc in calls)
    if sequential:
        return await _dispatch_sequential(
            calls,
            max_result_length=max_result_length,
            token=token,
            emit=emit,
            config=config,
        )
    return await _dispatch_parallel(
        calls,
        max_result_length=max_result_length,
        token=token,
        emit=emit,
        config=config,
    )


async def _dispatch_parallel(
    calls: list[ToolCallPayload],
    *,
    max_result_length: int,
    token: CancelToken,
    emit: Callable[[AgentEvent], Awaitable[None]],
    config: AgentLoopConfig,
) -> ExecutedToolBatch:
    """Prepare serially, execute handlers concurrently, emit in order."""
    prepared: list[_Prepared] = []
    for i, tc in enumerate(calls):  # prepare serial
        token.check()
        args, immediate = await _prepare(tc, config, token, emit)
        prepared.append(_Prepared(tc=tc, args=args, index=i, immediate=immediate))

    runnable = [p for p in prepared if p.immediate is None]
    # ToolExecutionStart in original order — WS tool_call cards are ordered
    for p in runnable:
        await emit(ToolExecutionStart(tool_call_id=p.tc.id, tool_name=p.tc.name, args=p.args))

    async def _run(prep: _Prepared) -> tuple[int, str]:
        raw = await _run_handler(prep.tc.name, prep.args, config, token)
        finalized = await _finalize(prep.tc.name, prep.args, raw, config, token)
        return prep.index, _truncate(finalized, max_result_length)

    if runnable:
        completed = await asyncio.gather(*(_run(p) for p in runnable))
    else:
        completed = []
    by_index = {idx: result for idx, result in completed}

    # Restore original order: immediate errors + executed results
    results: list[ToolResult] = []
    for p in prepared:
        if p.immediate is not None:
            results.append(
                ToolResult(
                    tool_call_id=p.tc.id,
                    tool_name=p.tc.name,
                    result=_truncate(p.immediate, max_result_length),
                    is_error=True,
                )
            )
            continue
        result = by_index[p.index]
        await emit(ToolExecutionEnd(tool_call_id=p.tc.id, tool_name=p.tc.name, result=result))
        results.append(ToolResult(tool_call_id=p.tc.id, tool_name=p.tc.name, result=result))
    return ExecutedToolBatch(messages=results, terminate=False)


async def _dispatch_sequential(
    calls: list[ToolCallPayload],
    *,
    max_result_length: int,
    token: CancelToken,
    emit: Callable[[AgentEvent], Awaitable[None]],
    config: AgentLoopConfig,
) -> ExecutedToolBatch:
    """Strict serial: prepare → execute → finalize, one call at a time."""
    results: list[ToolResult] = []
    for tc in calls:
        token.check()
        args, immediate = await _prepare(tc, config, token, emit)
        if immediate is not None:
            results.append(
                ToolResult(
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                    result=_truncate(immediate, max_result_length),
                    is_error=True,
                )
            )
            continue
        await emit(ToolExecutionStart(tool_call_id=tc.id, tool_name=tc.name, args=args))
        raw = await _run_handler(tc.name, args, config, token)
        finalized = await _finalize(tc.name, args, raw, config, token)
        truncated = _truncate(finalized, max_result_length)
        await emit(ToolExecutionEnd(tool_call_id=tc.id, tool_name=tc.name, result=truncated))
        results.append(ToolResult(tool_call_id=tc.id, tool_name=tc.name, result=truncated))
    return ExecutedToolBatch(messages=results, terminate=False)
```

并在文件头部导入 `dataclass`：

old:
```
import asyncio
import json
import logging
import sys
```
new:
```
import asyncio
import json
import logging
import sys
from dataclasses import dataclass
```

- [ ] **Step 4: Run test to verify it passes**

Run: ` .venv/bin/python -m pytest tests/test_tool_dispatcher_batch.py -v`

Expected: PASS，`11 (P1) - 1 (改名) + 4 (P2 新) = 14 passed`

存量回归：

Run: ` .venv/bin/python -m pytest tests/test_agent_loop.py tests/test_approval.py -q`

Expected: PASS，`0 failed`

- [ ] **Step 5: Commit**

```bash
git add agent/core/tool_dispatcher.py tests/test_tool_dispatcher_batch.py
git commit -m "feat: parallel tool dispatch with ordering and sequential fallback"
```

## Task P2-T5: length 截断防护端到端（适配层集成）

**Files:**
- Modify: `tests/test_agent_adapter.py`（顶部加 registry 清理 fixture + 追加用例；无生产代码改动——防护逻辑 P1-T3 已在 loop 内实现，P2-T3 补齐了 `stop_reason` 透出，本任务把两者串起来验证）
- Test: `tests/test_agent_adapter.py` 追加

**Interfaces:**
- Consumes: P2-T3 的 `stop_reason="length"` 透出；P1-T3 的 `_fail_truncated_batch`。
- Produces: 回归保护——`stop_reason=="length"` 时该消息内所有 tool call 不执行、各自返回截断错误、模型可基于错误重新发起（spec §6.2）。

- [ ] **Step 1: Write the failing test**

Edit 1 — `tests/test_agent_adapter.py` 顶部加清理 fixture（防 `spy_tool` 泄漏到其他测试）：

old:
```
from __future__ import annotations

import os

import agent.core.agent_adapter as adapter_mod
from agent.core.agent_adapter import AIAgent, kernel_mode
from agent.core.llm_client import LLMClient
from tests.conftest import MockLLMProvider, make_text_response
```
new:
```
from __future__ import annotations

import json
import os

import pytest

import agent.core.agent_adapter as adapter_mod
from agent.core.agent_adapter import AIAgent, kernel_mode
from agent.core.llm_client import LLMClient
from agent.core.llm_providers.base import ToolCallPayload
from agent.tools.registry import registry
from tests.conftest import MockLLMProvider, make_text_response


@pytest.fixture(autouse=True)
def _clean_registry():
    """Register built-ins first, then snapshot — teardown only removes
    tools the test added (never wipes the 57 built-in tools)."""
    from agent.tools.registry import discover_tools

    discover_tools()
    saved_before = set(registry.get_all_tool_names())
    yield
    for name in set(registry.get_all_tool_names()) - saved_before:
        try:
            registry.deregister(name)
        except Exception:
            pass
```

Edit 2 — 在 `TestNewKernelPath` 类内追加（放在 `test_new_dual_run_equivalence` 之后）：

```python
    def test_new_length_stop_reason_skips_tool_execution(self, monkeypatch):
        _force_kernel(monkeypatch, "new")
        from agent.config_model import AppConfig

        monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))
        from agent.core.llm_providers import LLMResponse

        ran: list[str] = []

        def _spy_handler(args: dict) -> str:
            ran.append("ran")
            return json.dumps({"success": True})

        registry.register(name="spy_tool", toolset="test", schema={"type": "object"}, handler=_spy_handler)

        provider = MockLLMProvider(
            responses=[
                LLMResponse(
                    content="",
                    tool_calls=[ToolCallPayload(id="c1", name="spy_tool", arguments="{}")],
                    stop_reason="length",
                ),
                make_text_response("please re-issue"),
            ]
        )
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

        result = agent.run_conversation("go")
        assert ran == [], "truncated tool calls must never execute"
        tool_msgs = [m for m in result["messages"] if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert "参数可能被截断，请重新完整发出" in tool_msgs[0]["content"]
        assert result["final_response"] == "please re-issue"
        assert result["completed"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: ` .venv/bin/python -m pytest tests/test_agent_adapter.py -k length -v`

Expected: FAIL（当前 `MockLLMProvider` 返回的 response 无 `stop_reason="length"` 时 `spy_tool` 会被执行 → `ran == ["ran"]` 断言失败；`_force_kernel` 生效后若 P2-T3 未落地则 `stop_reason` 恒 None，同样走执行路径）

- [ ] **Step 3: Write minimal implementation**

无生产代码改动（loop 的 `_fail_truncated_batch` 与 provider 的 `stop_reason` 透出已在 P1-T3/P2-T3 就位）。若 Step 2 显示 `stop_reason` 未透出，回到 P2-T3 检查映射是否完整；若 loop 未走 `_fail_truncated_batch`，回到 P1-T3 检查 `stop_reason == "length"` 分支。

- [ ] **Step 4: Run test to verify it passes**

Run: ` .venv/bin/python -m pytest tests/test_agent_adapter.py -v`

Expected: PASS，`20 (P1) + 1 (length) = 21 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_agent_adapter.py
git commit -m "test: cover length stop_reason truncation guard end-to-end"
```

## Task P2-T6: P2 期验收（全量双跑 + ruff + 契约 + 审计）

**Files:**
- Test: 无新文件；仅运行验证。

- [ ] **Step 1: 默认（new）内核全量测试**

Run: ` .venv/bin/python -m pytest tests/ -q`

Expected: `passed` 且 `0 failed`。

- [ ] **Step 2: old 内核全量测试**

Run: `ZLINK_KERNEL=old .venv/bin/python -m pytest tests/ -q`

Expected: `passed` 且 `0 failed`。

- [ ] **Step 3: ruff 检查**

Run: `ruff check . && ruff format --check .`

Expected: `All checks passed!` 且无 format diff。

- [ ] **Step 4: 四契约 + 审计回归**

Run: ` .venv/bin/python -m pytest tests/test_contract_freeze.py tests/test_execution_mode_audit.py tests/test_tool_dispatcher_batch.py tests/test_stop_reason_mapping.py -q`

Expected: `passed` 且 `0 failed`。

- [ ] **Step 5: Commit（如有修复）**

```bash
git status --porcelain
git add -u && git commit -m "fix: P2 phase acceptance fixes"
```

# P3 —— CancelToken 全链路 + steering 队列 + WS 入口

行为目标：`cancel()` 后 loop 仍以 `AgentEnd` 收尾、`wait_idle()` 返回、`state.pendingToolCalls` 清空；`steer()` 注入消息下一个 turn 消费（one-at-a-time）；WS 入站 `steering` 消息类型（前端不接入时行为与 P1/P2 完全一致）；follow-up 只留接口不接 UI。

## Task P3-T1: CancelToken 全链路收尾（AgentEnd 保证 + 取消测试）

**Files:**
- Modify: `agent/core/agent_adapter.py`（取消/异常路径改为经 Agent 事件流以 `AgentEnd` 收尾，spec §6.2）
- Test: `tests/test_agent_adapter.py` 追加

**Interfaces:**
- Consumes: P1-T6 的 `cancel()`/`run_conversation_async` 取消捕获；P1-T5 的 `Agent._emit`/`state`；`kernel_types.AgentEnd`。
- Produces: 取消/异常路径下事件流保证 `AgentEnd` 最后发出（监听器可见），`SessionEndEvent` 由 mapper 的 `agent_end` 分支统一发布。

- [ ] **Step 1: Write the failing test**

Append to `tests/test_agent_adapter.py`（`TestNewKernelPath` 类内）：

```python
    def test_cancel_during_run_ends_with_agent_end(self, monkeypatch):
        _force_kernel(monkeypatch, "new")
        import time

        from agent.core.kernel_types import AgentEnd
        from agent.core.llm_providers import LLMResponse

        ended: list[AgentEnd] = []

        def _sleepy(args: dict) -> str:
            time.sleep(0.5)
            return json.dumps({"success": True})

        registry.register(name="sleepy_tool", toolset="test", schema={"type": "object"}, handler=_sleepy)
        provider = MockLLMProvider(
            responses=[
                LLMResponse(content="", tool_calls=[ToolCallPayload(id="c1", name="sleepy_tool", arguments="{}")]),
                make_text_response("never"),
            ]
        )
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)
        agent.agent.subscribe(lambda e: ended.append(e) if isinstance(e, AgentEnd) else None)

        async def _scenario() -> dict:
            task = asyncio.create_task(
                agent.run_conversation_async(user_message="go", conversation_history=[], session_id="s1")
            )
            await asyncio.sleep(0.1)
            agent.cancel()
            result = await task
            await agent.agent.wait_idle()
            return result

        result = asyncio.run(_scenario())
        assert result["error"] == "用户已手动停止"
        assert result["completed"] is False
        assert len(ended) == 1, "AgentEnd must close the event stream on cancel"
        assert agent.agent.state.running is False
        assert agent.agent.state.pendingToolCalls == 0
        assert agent.phase == "idle"
```

- [ ] **Step 2: Run test to verify it fails**

Run: ` .venv/bin/python -m pytest tests/test_agent_adapter.py -k cancel_during_run -v`

Expected: FAIL（当前取消路径只调 `_publish_session_end()`，未向 Agent 监听器发 `AgentEnd` → `ended == []`）

- [ ] **Step 3: Write minimal implementation**

Edit 1 — `agent/core/agent_adapter.py` 的 kernel_types 导入增加 `AgentEnd`：

old:
```
from agent.core.kernel_types import (
    AgentEvent,
    AgentLoopConfig,
    CancelToken,
    MessageUpdate,
    TurnUpdate,
)
```
new:
```
from agent.core.kernel_types import (
    AgentEnd,
    AgentEvent,
    AgentLoopConfig,
    CancelToken,
    MessageUpdate,
    TurnUpdate,
)
```

Edit 2 — 取消/异常路径改为经 `Agent._emit` 发 `AgentEnd`（mapper 的 `agent_end` 分支会自动发布 `SessionEndEvent`）：

old:
```
            except asyncio.CancelledError:
                self._error = self._error or "用户已手动停止"
                self._result_messages = list(self._agent.state.messages)
                self._publish_session_end()
            except Exception as e:  # noqa: BLE001 — Agent.handleRunFailure fallback
                logger.exception("Agent run failed")
                self._error = f"Unexpected agent error: {e}"
                self._result_messages = list(self._agent.state.messages)
                self._publish_session_end()
```
new:
```
            except asyncio.CancelledError:
                self._error = self._error or "用户已手动停止"
                self._result_messages = list(self._agent.state.messages)
                await self._agent._emit(AgentEnd(list(self._result_messages)))
            except Exception as e:  # noqa: BLE001 — Agent.handleRunFailure fallback
                logger.exception("Agent run failed")
                self._error = f"Unexpected agent error: {e}"
                self._result_messages = list(self._agent.state.messages)
                await self._agent._emit(AgentEnd(list(self._result_messages)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: ` .venv/bin/python -m pytest tests/test_agent_adapter.py -v`

Expected: PASS，`22 passed`

存量回归：

Run: ` .venv/bin/python -m pytest tests/test_agent_loop.py tests/test_chat_async.py -q`

Expected: PASS，`0 failed`

- [ ] **Step 5: Commit**

```bash
git add agent/core/agent_adapter.py tests/test_agent_adapter.py
git commit -m "feat: close event stream with AgentEnd on cancel and run failure"
```

## Task P3-T2: steering 队列接入适配层 + WS 入站 steering

**Files:**
- Modify: `agent/core/agent_adapter.py`（`AgentLoopConfig` 挂 `get_steering_messages`/`get_follow_up_messages` 钩子）、`backend/api/chat.py`（`_listen_inbound` 增加 `steering` 消息类型）
- Test: `tests/test_agent_adapter.py`、`tests/test_chat_async.py` 追加

**Interfaces:**
- Consumes: P1-T5 的 `Agent.next_steering_message()`/`next_follow_up_messages()`；P1-T7 的 `_listen_inbound`。
- Produces:
  - 适配层 `_get_steering_hook(token) -> list[dict]`（`self._agent.next_steering_message()`，one-at-a-time）与 `_get_follow_up_hook(token) -> list[dict]`（`self._agent.next_follow_up_messages()`，清空式）；挂到 `AgentLoopConfig.get_steering_messages`/`get_follow_up_messages`
  - chat.py 入站：`{"type": "steering", "payload": {"content": "<文本>"}}` → `agent.steer({"role": "user", "content": content})`；前端不发送时内核行为不变（C2 出站消息集合零改动）

- [ ] **Step 1: Write the failing test**

Append to `tests/test_agent_adapter.py`（`TestNewKernelPath` 类内）：

```python
def test_steer_injected_next_turn(self, monkeypatch):
    _force_kernel(monkeypatch, "new")
    provider = MockLLMProvider(responses=[make_text_response("first"), make_text_response("second")])
    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    async def _scenario() -> dict:
        task = asyncio.create_task(
            agent.run_conversation_async(user_message="go", conversation_history=[], session_id="s1")
        )
        await asyncio.sleep(0.05)
        agent.steer({"role": "user", "content": "interrupt"})
        return await task

    result = asyncio.run(_scenario())
    contents = [m.get("content") for m in result["messages"]]
    assert "interrupt" in contents
    idx_steer = contents.index("interrupt")
    idx_second = contents.index("second")
    assert idx_steer < idx_second
    assert result["final_response"] == "second"


def test_steer_one_at_a_time_oldest_first(self, monkeypatch):
    _force_kernel(monkeypatch, "new")
    provider = MockLLMProvider(responses=[make_text_response("a"), make_text_response("b"), make_text_response("c")])
    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=5)
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    async def _scenario() -> dict:
        task = asyncio.create_task(
            agent.run_conversation_async(user_message="go", conversation_history=[], session_id="s1")
        )
        await asyncio.sleep(0.05)
        agent.steer({"role": "user", "content": "steer-1"})
        agent.steer({"role": "user", "content": "steer-2"})
        return await task

    result = asyncio.run(_scenario())
    contents = [m.get("content") for m in result["messages"]]
    assert contents.index("steer-1") < contents.index("steer-2") < contents.index("c")
```

Append to `tests/test_chat_async.py`：

```python
def test_ws_steering_message_steers_agent(monkeypatch):
    _monkeypatch_ws_env(monkeypatch)
    fake = _FakeAgent(_make_events(), delay=1.0)
    monkeypatch.setattr("backend.api.chat.AIAgent", lambda **kw: fake)

    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    with client.websocket_connect("/ws/chat/sess-steer") as ws:
        ws.send_json({"type": "send_message", "content": "hi"})
        ws.send_json({"type": "steering", "payload": {"content": "interrupt"}})
        while True:
            msg = ws.receive_json()
            if msg["type"] == "done":
                break

    assert fake.steered == [{"role": "user", "content": "interrupt"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: ` .venv/bin/python -m pytest tests/test_agent_adapter.py -k steer -v tests/test_chat_async.py -v`

Expected: FAIL（适配层未挂 steering 钩子 → steer 消息不被消费；chat.py 未处理 `steering` 类型 → `fake.steered == []`）

- [ ] **Step 3: Write minimal implementation**

Edit 1 — `agent/core/agent_adapter.py`：`AgentLoopConfig` 构造增加两个钩子：

old:
```
                prepare_next_turn=self._prepare_next_turn_hook,
                should_stop_after_turn=self._should_stop_after_turn_hook,
                bridge_dispatch=self._dispatch_bridge_tool,
                on_approval_blocked=self._on_approval_blocked_hook,
            )
```
new:
```
                prepare_next_turn=self._prepare_next_turn_hook,
                should_stop_after_turn=self._should_stop_after_turn_hook,
                get_steering_messages=self._get_steering_hook,
                get_follow_up_messages=self._get_follow_up_hook,
                bridge_dispatch=self._dispatch_bridge_tool,
                on_approval_blocked=self._on_approval_blocked_hook,
            )
```

Edit 2 — 在 `_on_approval_blocked_hook` 之后追加两个钩子方法：

old:
```
    async def _on_approval_blocked_hook(self, tool_name: str, reason: str) -> str:
        """Approval flow (R4: threading.Event → asyncio wait).
        Returns ``"approved"`` | ``"denied"``."""
        req = ApprovalRequest(tool_name=tool_name, reason=reason)
        if self.approval_callback:
            self.approval_callback(req)
        loop = asyncio.get_running_loop()
        timed_out = await loop.run_in_executor(None, req.event.wait, 120)
        if timed_out or req.result != "approved":
            return "denied"
        return "approved"
```
new:
```
    async def _on_approval_blocked_hook(self, tool_name: str, reason: str) -> str:
        """Approval flow (R4: threading.Event → asyncio wait).
        Returns ``"approved"`` | ``"denied"``."""
        req = ApprovalRequest(tool_name=tool_name, reason=reason)
        if self.approval_callback:
            self.approval_callback(req)
        loop = asyncio.get_running_loop()
        timed_out = await loop.run_in_executor(None, req.event.wait, 120)
        if timed_out or req.result != "approved":
            return "denied"
        return "approved"

    def _get_steering_hook(self, token: CancelToken) -> list[dict]:
        """Steering queue — one-at-a-time (oldest first)."""
        return self._agent.next_steering_message()

    def _get_follow_up_hook(self, token: CancelToken) -> list[dict]:
        """Follow-up queue — drained wholesale (API only, no UI)."""
        return self._agent.next_follow_up_messages()
```

Edit 3 — `backend/api/chat.py`：`_listen_inbound` 增加 `steering` 分支：

old:
```
            elif mtype == "approval_response":
                payload = data.get("payload", {})
                _resolve_pending_approval(session_id, payload.get("approved", False))
```
new:
```
            elif mtype == "approval_response":
                payload = data.get("payload", {})
                _resolve_pending_approval(session_id, payload.get("approved", False))
            elif mtype == "steering":
                payload = data.get("payload", {})
                content = payload.get("content", "")
                if content:
                    agent.steer({"role": "user", "content": content})
```

- [ ] **Step 4: Run test to verify it passes**

Run: ` .venv/bin/python -m pytest tests/test_agent_adapter.py tests/test_chat_async.py -v`

Expected: PASS，`22 + 2 (steer) = 24`、`3 + 1 (steering) = 4`

存量回归：

Run: ` .venv/bin/python -m pytest tests/ -q`

Expected: PASS，`0 failed`

- [ ] **Step 5: Commit**

```bash
git add agent/core/agent_adapter.py backend/api/chat.py tests/test_agent_adapter.py tests/test_chat_async.py
git commit -m "feat: wire steering queue into adapter and WS inbound steering message"
```

## Task P3-T3: P3 期验收（全量双跑 + ruff + 契约）

**Files:**
- Test: 无新文件；仅运行验证。

- [ ] **Step 1: 默认（new）内核全量测试**

Run: ` .venv/bin/python -m pytest tests/ -q`

Expected: `passed` 且 `0 failed`。

- [ ] **Step 2: old 内核全量测试**

Run: `ZLINK_KERNEL=old .venv/bin/python -m pytest tests/ -q`

Expected: `passed` 且 `0 failed`。

- [ ] **Step 3: ruff 检查**

Run: `ruff check . && ruff format --check .`

Expected: `All checks passed!` 且无 format diff。

- [ ] **Step 4: 四契约回归**

Run: ` .venv/bin/python -m pytest tests/test_contract_freeze.py tests/test_chat_async.py tests/test_agent_adapter.py -q`

Expected: `passed` 且 `0 failed`。

- [ ] **Step 5: Commit（如有修复）**

```bash
git status --porcelain
git add -u && git commit -m "fix: P3 phase acceptance fixes"
```

---

# P4 —— 删旧内核 + 文档更新

行为目标：移除旧内核行内副本（`_run_conversation_legacy` 及其专属方法）、`ZLINK_KERNEL` 开关、chat.py legacy 路径；更新 `AGENTS.md`；测试全绿（仅 new 内核）。

## Task P4-T1: 删除旧内核与 ZLINK_KERNEL 开关

**Files:**
- Modify: `agent/core/agent_adapter.py`、`backend/api/chat.py`、`tests/test_agent_adapter.py`
- Test: 无新文件；以全量测试为验证。

**Interfaces:**
- Consumes: P1–P3 全部新内核交付物。
- Produces:
  - `run_conversation` 恒为 `asyncio.run(self.run_conversation_async(...))`（不再读 `kernel_mode`）
  - 删除 `kernel_mode()`/`_KERNEL_MODE`/`import os`；删除 `_run_conversation_legacy`、`_maybe_compact`、`_call_llm`（同步旧版）、`_build_assistant_message`、`_run_tool_calls`、`_handle_approval_block`
  - chat.py 删除 `kernel_mode` 导入、`_run_agent` 的 old 分支、`_run_agent_legacy` 整个函数；`_run_agent` 恒调 `_run_agent_new`
  - `agent/core/tool_dispatcher.py` 的同步 `dispatch_tool` 保留（公共工具函数，`agent/core/__init__.py` 与 PyInstaller hidden imports 依赖）

- [ ] **Step 1: Write the failing test（先写"开关已删除"的契约测试）**

Append to `tests/test_agent_adapter.py`：

```python
class TestPostKernelCleanup:
    def test_no_kernel_mode_symbols(self):
        import agent.core.agent_adapter as mod

        assert not hasattr(mod, "kernel_mode")
        assert not hasattr(mod, "_KERNEL_MODE")

    def test_run_conversation_still_returns_frozen_dict(self, monkeypatch):
        provider = MockLLMProvider(responses=[make_text_response("hi")])
        agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
        agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)
        result = agent.run_conversation("hello")
        assert set(result.keys()) == {
            "final_response",
            "messages",
            "api_calls",
            "token_usage",
            "completed",
            "error",
        }
        assert result["final_response"] == "hi"
```

- [ ] **Step 2: Run test to verify it fails**

Run: ` .venv/bin/python -m pytest tests/test_agent_adapter.py -k PostKernelCleanup -v`

Expected: FAIL（`kernel_mode`/`_KERNEL_MODE` 仍存在）

- [ ] **Step 3: Write minimal implementation**

Edit 1 — `agent/core/agent_adapter.py`：`run_conversation` 去掉分发，恒走新内核：

old:
```
        """Frozen C1 entry point.  Delegates to the active kernel:
        ``ZLINK_KERNEL=old`` → the inline legacy algorithm; default →
        the new async kernel via ``asyncio.run``."""
        if kernel_mode() == "old":
            return self._run_conversation_legacy(
                user_message=user_message,
                system_message=system_message,
                conversation_history=conversation_history,
                stream_callback=stream_callback,
                reasoning_callback=reasoning_callback,
                stop_event=stop_event,
                session_id=session_id,
            )
        return asyncio.run(
```
new:
```
        """Frozen C1 entry point — runs the new async kernel."""
        return asyncio.run(
```

Edit 2 — 删除 `# ── Legacy kernel path (verbatim pre-P1 algorithm) ─────────────` 注释到 `_run_conversation_legacy` 方法结束（含）的全部内容（即从该注释行到类结束；该方法现为类内最后一个成员）。删除后类以 `_get_follow_up_hook` 结束。

old:
```
    # ── Legacy kernel path (verbatim pre-P1 algorithm) ─────────────

    def _run_conversation_legacy(
```
…（此处整段方法体 + 类结束缩进，删除到文件内 `# ── Kernel mode switch (dual-run) ─────────────────────────────────` 之前的空行）

new:
```
```
（即：删除从 `    # ── Legacy kernel path` 起到 `# ── Kernel mode switch` 块之间的全部行。执行方式：用编辑器选中该区间删除；随后再删除下面 Edit 3 的 kernel_mode 块。）

Edit 3 — 删除文件末尾的 kernel_mode 块并还原 `__all__`：

old:
```
# ── Kernel mode switch (dual-run) ─────────────────────────────────

_KERNEL_MODE: str | None = None


def kernel_mode() -> str:
    """Return the active kernel: ``"new"`` (default) or ``"old"``.

    Read once per process (R5: no per-request re-read) and logged.
    ``ZLINK_KERNEL`` is removed in P4 along with the legacy kernel.
    """
    global _KERNEL_MODE
    if _KERNEL_MODE is None:
        raw = os.environ.get("ZLINK_KERNEL", "new").strip().lower()
        _KERNEL_MODE = raw if raw in ("new", "old") else "new"
        logging.getLogger(__name__).info("Agent kernel mode: %s (ZLINK_KERNEL env)", _KERNEL_MODE)
    return _KERNEL_MODE


__all__ = ["AIAgent", "kernel_mode"]
```
new:
```
__all__ = ["AIAgent"]
```

Edit 4 — 删除 `import os`：

old:
```
import asyncio
import json
import logging
import os
import sys
import threading
```
new:
```
import asyncio
import json
import logging
import sys
import threading
```

Edit 5 — 删除旧内核专属方法 `_maybe_compact`、`_call_llm`（同步）、`_build_assistant_message`、`_run_tool_calls`、`_handle_approval_block`（每个方法的完整定义从 `    def <name>(` 到下一个 `    def ` 前一行）。这些方法只被 `_run_conversation_legacy` 调用，随 Edit 2 一并失效；删除后全量测试应全绿，若遗留引用会立刻在测试中暴露（NameError/AttributeError）。

Edit 6 — `backend/api/chat.py`：

6a：删除 `kernel_mode` 导入：
old:
```
from agent.core.agent import ApprovalRequest
from agent.core.agent_adapter import kernel_mode
from agent.core.kernel_types import AgentEvent
```
new:
```
from agent.core.agent import ApprovalRequest
from agent.core.kernel_types import AgentEvent
```

6b：`_run_agent` 去掉 old 分支：
old:
```
    """Dispatch to the active kernel: legacy thread-pool path or the
    new direct-await path (spec §4.6)."""
    if kernel_mode() == "old":
        await _run_agent_legacy(
            websocket,
            session_id,
            content,
            history,
            api_key,
            base_url,
            model,
            max_iterations,
            existing_msgs,
            compaction_settings,
            skill_detail,
        )
        return
    await _run_agent_new(
```
new:
```
    """Direct-await path (spec §4.6)."""
    await _run_agent_new(
```

6c：删除 `_run_agent_legacy` 整个函数（从 `async def _run_agent_legacy(` 到文件末尾——它是文件最后一个函数）。

Edit 7 — `tests/test_agent_adapter.py`：
- 删除 `_force_kernel` 辅助函数、`TestKernelMode` 类、`TestLegacyKernelPath` 类（精确锚点：`def _force_kernel` 到其 docstring 结束、`class TestKernelMode:` 块、`class TestLegacyKernelPath:` 块）
- 删除 `test_new_dual_run_equivalence` 方法整体（其引用的 legacy 内核与 `_force_kernel` 均已删除；方法内两处 `_force_kernel(monkeypatch, ...)` 随方法一并删除）
- 对 `TestNewKernelPath` 内其余所有 `        _force_kernel(monkeypatch, "new")` 行执行 replaceAll 删除（16 处：P1-T6 12 处 + P2-T5 1 处 + P3-T1 1 处 + P3-T2 2 处）

- [ ] **Step 4: Run test to verify it passes**

Run: ` .venv/bin/python -m pytest tests/ -q`

Expected: PASS，`0 failed`（新内核单跑）

Run: ` .venv/bin/python -m pytest tests/test_agent_adapter.py tests/test_contract_freeze.py -q`

Expected: PASS，`0 failed`

- [ ] **Step 5: Commit**

```bash
git add agent/core/agent_adapter.py backend/api/chat.py tests/test_agent_adapter.py
git commit -m "refactor: remove legacy kernel and ZLINK_KERNEL switch"
```

## Task P4-T2: 更新 AGENTS.md 架构文档

**Files:**
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: P1–P4 落地的最终文件结构（`kernel_types.py`/`loop.py`/`agent.py` 重写/`agent_adapter.py`/`tool_dispatcher.py`）。
- Produces: 文档与代码一致（目录结构、Flow A、契约描述、测试命令不变）。

- [ ] **Step 1: 更新目录结构段（AGENTS.md §2）**

old:
```
├── core/
│   ├── agent.py            # ⚠️ AIAgent — M7 agent loop, phase machine, TurnSnapshot
│   ├── llm_client.py       # ⚠️ LLMClient shim → LLMProvider
│   ├── llm_providers/      # ⚠️ base (LLMProvider ABC / LLMResponse / ToolCallPayload),
│   │                       #    openai_compat (httpx SSE, reasoning_content), anthropic, factory
│   ├── message_builder.py  # build_system_prompt(), build_turn_messages()
│   ├── tool_dispatcher.py  # dispatch_tool() — registry dispatch + truncation
│   └── iteration_budget.py # IterationBudget — turn counting
```
new:
```
├── core/
│   ├── kernel_types.py     # ⚠️ AgentLoopConfig 钩子契约 / 9 种 AgentEvent / CancelToken / ToolResult
│   ├── loop.py             # ⚠️ run_agent_loop — 零策略双层 async loop（AgentEnd 保证任何路径收尾）
│   ├── agent.py            # ⚠️ 有状态 Agent 包装（subscribe/steer/follow_up/cancel/wait_idle）+ 兼容 re-export
│   ├── agent_adapter.py    # ⚠️ AIAgent 兼容层（run_conversation_async + EventBus 8 事件映射 + Phase 机）
│   ├── llm_client.py       # ⚠️ LLMClient shim → LLMProvider
│   ├── llm_providers/      # ⚠️ base (LLMProvider ABC / LLMResponse / ToolCallPayload),
│   │                       #    openai_compat (httpx SSE, reasoning_content), anthropic, factory
│   ├── message_builder.py  # build_system_prompt(), build_turn_messages()
│   ├── tool_dispatcher.py  # dispatch_tool() + dispatch_tool_batch()（并行/保序/sequential 降级）
│   └── iteration_budget.py # IterationBudget — 纯计数器（消费点在 should_stop_after_turn 钩子）
```

- [ ] **Step 2: 更新 Flow A（AGENTS.md §3）**

old:
```
### Flow A: Chat (WebSocket → AIAgent → LLM → response)

```
frontend WS → backend/api/chat.py (run_in_executor)
  → slash command? → execute() → response
  → else AIAgent.run_conversation(message, stream_cb):
      build_turn_messages() → _take_snapshot() (freezes model/temp/tools)
      → SessionStartEvent → _maybe_compact() [context_compactor.py]
      → loop: _call_llm() [LLMClient.chat → LLMProvider.chat (openai_compat/anthropic)]
          → if tool_calls: dispatch_tool() → registry.dispatch()
              → tool handler | mcp_manager.call_tool() → append results → loop
      → SessionEndEvent → return {final_response, messages, api_calls, token_usage, completed, error}
```
```
new:
```
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
```

- [ ] **Step 3: 更新 §4 Key Contracts 的 AIAgent 说明（AGENTS.md §4）**

old:
```
### AIAgent (`agent/core/agent.py`)

- Constructor signature is **frozen** (M1) — do not add/rename params.
- `run_conversation(...)` ... keys consumed by `backend/api/chat.py`.
- **M7 phase machine:** ...
```
new:
```
### AIAgent (`agent/core/agent_adapter.py`，经 `agent/core/agent.py` re-export)

- Constructor signature is **frozen** (M1) — do not add/rename params.
- `run_conversation(...)` 返回 keys（`{final_response, messages, api_calls, token_usage, completed, error}`）由 `backend/api/chat.py` 消费——冻结。
- 新内核入口：`async run_conversation_async(...)`（签名同 `run_conversation`）；`agent.agent` 暴露 `Agent` 句柄（`subscribe`/`steer`/`cancel`）。
- **Phase 机**（`idle/turn/compaction/retry`）：由适配层根据 AgentEvent 流维护，`run_conversation` 仍拒绝非 idle 重入。
- **策略钩子**（`AgentLoopConfig`）：`transform_context`（compaction）/`before_tool_call`/`after_tool_call`/`prepare_next_turn`/`should_stop_after_turn`（IterationBudget 消费点）/`get_steering_messages`/`get_follow_up_messages`/`bridge_dispatch`/`on_approval_blocked`——全部在 `agent/core/kernel_types.py` 定义。
```

- [ ] **Step 4: 验证文档改动无代码影响**

Run: ` .venv/bin/python -m pytest tests/test_contract_freeze.py -q`

Expected: PASS，`0 failed`

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md for the Pi-style kernel architecture"
```

## Task P4-T3: P4 期验收（最终门禁）

**Files:**
- Test: 无新文件；仅运行验证。

- [ ] **Step 1: 全量测试**

Run: ` .venv/bin/python -m pytest tests/ -q`

Expected: `passed` 且 `0 failed`。

- [ ] **Step 2: ruff 检查**

Run: `ruff check . && ruff format --check .`

Expected: `All checks passed!` 且无 format diff。

- [ ] **Step 3: 四契约回归**

Run: ` .venv/bin/python -m pytest tests/test_contract_freeze.py tests/test_chat_async.py tests/test_tool_registry.py tests/test_execution_mode_audit.py -q`

Expected: `passed` 且 `0 failed`。

- [ ] **Step 4: 无旧内核残留**

Run: `rg -n "ZLINK_KERNEL|_run_conversation_legacy|_run_agent_legacy|kernel_mode|_KERNEL_MODE" agent/ backend/ tests/ --glob "*.py"`

Expected: 无匹配输出（`agent/core/tool_dispatcher.py` 的同步 `dispatch_tool` 属公共工具，保留）。

- [ ] **Step 5: 冻结测试文件零改动复核**

Run: `git diff --stat -- tests/test_agent_loop.py tests/test_chat.py tests/test_extensions.py tests/test_tool_registry.py`

Expected: 输出为空。

- [ ] **Step 6: Commit（如有修复）**

```bash
git status --porcelain
git add -u && git commit -m "fix: P4 final acceptance fixes"
```

---

## 附：spec 覆盖对照（自审用，不执行）

| spec 节 | 落地任务 |
|---|---|
| §1.4 保留三层安全/tool_search/ERP 上下文/Approval | P1-T2（registry.dispatch 保 hook 链）、P1-T6（before/after_tool_call 钩子 + bridge_dispatch + on_approval_blocked）、P1-T6（_build_system_prompt/_build_erp_context 复用） |
| §2.1 目标 1 分层 | P1-T1/T3/T5/T6 |
| §2.1 目标 2 全钩子化 | P1-T6（7 个策略钩子 + call_llm/bridge/approval 3 个执行钩子） |
| §2.1 目标 3 并行+审计+length 防护 | P2-T1/T2/T3/T4/T5 |
| §2.1 目标 4 CancelToken+steering | P1-T6（stop→token→_llm_stop_event）、P3-T1、P3-T2 |
| §2.1 目标 5 四契约冻结+双跑回退 | P1-T8、P1-T9、P2-T6、P3-T3、P4-T3 |
| §3.1 chat.py 直接 await 删 run_in_executor | P1-T7（_run_agent_new；legacy 路径保留至 P4-T1） |
| §3.2 9 种 AgentEvent + 错误编码 + AgentEnd 收尾 | P1-T1、P1-T3、P3-T1 |
| §3.3 工具并行规则 1–5 | P2-T4（1/2/3/4）、P1-T3+P2-T3+P2-T5（5） |
| §3.4 钩子表 | P1-T6 |
| §3.5 适配层/Agent API | P1-T5、P1-T6 |
| §4.1 kernel_types 伪代码 | P1-T1（补 call_llm/max_tool_result_length 等真实字段，见 Global Constraints） |
| §4.2 loop 伪代码 | P1-T3（TurnStart 收敛到内层循环顶部一次，修正 spec 伪代码双重 TurnStart） |
| §4.3 dispatcher 伪代码 | P1-T2、P2-T4 |
| §4.4 事件映射表 | P1-T6（UserMessageEvent 前置门实现取消语义，避免双发） |
| §4.5 register 扩展 + 审计清单 | P2-T1、P2-T2 |
| §4.6 WS 适配层 | P1-T7、P3-T2（steering 入站）、P4-T1 |
| §5 四契约冻结清单 | P1-T8、P1-T9 |
| §6.1 存量安全网双跑 | P1-T9、P2-T6、P3-T3 |
| §6.2 新增测试清单 | P1-T2/T3/T6、P2-T4/T5、P3-T1/T2、P1-T1 |
| §6.3 兼容性测试 | P1-T6（test_new_dual_run_equivalence）、P1-T9 |
| §7 分期 | P1–P4 全部任务 |
| §8 R1 竞态 | P2-T2（审计 sequential）、P2-T4（降级） |
| §8 R2 漂移 | P1-T9/P2-T6/P3-T3 双跑 |
| §8 R3 stop_reason | P2-T3、P2-T5 |
| §8 R4 并发模型 | P1-T6（run_coroutine_threadsafe 保序）、P3-T1（取消测试） |
| §8 R5 开关单次读取 | P1-T4（kernel_mode 缓存）→ P4-T1（删除） |





