# 借鉴 Pi 架构重写 Agent 内核设计（Pi-style Kernel Redesign）

> 用 Python 原生重写 `agent/core/`，对照本地 Pi agent harness（TypeScript，`/Users/zuoxiaojun/vibecoding/agent-frameworks/pi/packages/agent/src/`）的分层与事件模型，把内核从"单体 `AIAgent` 类 + 隐式策略"重构为"极简零策略 async loop + 有状态 Agent 包装 + 全钩子化策略"。动机是让项目建立在更现代、更优雅的底座上，**不是功能缺失驱动**。

## 1. 背景与动机

### 1.1 现状（已核实）

`agent/core/agent.py` 是 M1–M7 历次演进叠加的产物，957 行的 `AIAgent` 类承担了全部职责：

- **同步 agent loop** 在 `backend/api/chat.py` 中经 `run_in_executor` 跑进 `ThreadPoolExecutor`，`stream_callback`/`reasoning_callback` 用 `loop.call_soon_threadsafe` 推入 asyncio 队列 —— 线程池 ↔ 事件循环两侧来回搬运；
- **策略内嵌在循环里**：迭代预算（`IterationBudget`）、上下文压缩（`_maybe_compact`）、安全钩子（`security_hooks` + `BeforeToolCallEvent` 双重路径）、工具截断（`_run_tool_calls` 内联）、重试决策全部以 `if/else` 形式散落在 `run_conversation` 与 `_run_tool_calls` 中；
- **工具串行执行**：`_run_tool_calls` 对 `tool_calls` 逐个 `for` 循环执行，无并行、无执行模式概念；
- 已有 M7 的 Phase 机（`idle/turn/compaction/retry`）、TurnSnapshot、Envelope（`seq/phase/type/payload`）作为兼容层雏形。

### 1.2 Pi 提供的参考（已核实）

Pi 的 `packages/agent/src/` 把同一件事切成三层，各司其职：

- **`agent-loop.ts`（极简 loop，零策略）**：`runAgentLoop` / `runAgentLoopContinue` 两个纯函数，双层循环（内层 = tool_calls/steering 消息、外层 = follow-up 消息），所有"该不该继续/要不要压缩/怎么准备下一轮"都通过 `AgentLoopConfig` 上的钩子回调出去；
- **`agent.ts`（有状态包装）**：`Agent` 类持有 state、`subscribe()` 事件订阅、`steer()` / `followUp()` 队列、`abort()` / `waitForIdle()` 生命周期；
- **`types.ts`（类型契约）**：`AgentEvent` 联合类型、`AgentLoopConfig` 钩子签名、`ToolExecutionMode`（`sequential` / `parallel`）、`QueueMode`（`one-at-a-time` / `all`）。

Pi 值得借鉴的核心：**loop 与策略彻底解耦、事件驱动流式协议、工具并行 + 截断防护、取消令牌全链路传递**。

### 1.3 不借鉴的部分（明确划界）

- **Pi 自定义消息类型体系**（`AgentMessage` 联合类型 + declaration merging 扩展）—— zlink 的消息就是 OpenAI 格式的 `list[dict]`，重造消息类型收益为零；
- **session tree 分支回溯** —— zlink 是线性会话 + SQLite 存储，无多分支需求；
- **TypeScript 特有机制**（`AbortSignal`、流式 stream 对象）—— 用 Python 惯用 `asyncio` + `CancelToken` 替代。

### 1.4 保留的 zlink 优势（重构不得削弱）

- **三层安全**：system prompt 约束 → `security_hooks` before-hook 链 → `SecurityEventExtension` 订阅 `BeforeToolCallEvent` 取消；
- **tool_search 惰性加载**：bridge 工具（`tool_search` / `tool_describe` / `tool_call`）+ 渐进式工具披露；
- **ERP 上下文注入**：`_build_erp_context()` 每轮读配置生成启用状态注入 system prompt；
- **Approval 审批流**：`ApprovalBlockedError` → `ApprovalRequest` → WS 层 `approval_response`。

## 2. 目标 / 非目标

### 2.1 目标

1. 新内核位于 `agent/core/`，对照 Pi 分层为 `loop.py`（极简 async loop）、`kernel_types.py`（类型契约）、`agent.py`（有状态包装）；
2. 所有策略钩子化：`transform_context` / `before_tool_call` / `after_tool_call` / `prepare_next_turn` / `should_stop_after_turn` / `get_steering_messages` / `get_follow_up_messages`；
3. 工具并行执行 + `execution_mode` 审计 + `stop_reason=="length"` 截断防护；
4. `CancelToken` 全链路传递，steering 队列提供 WS 入口；
5. 四契约冻结，存量测试全绿，双跑可回退。

### 2.2 非目标（明确不做）

- **不重写 ERP 客户端**：`agent/erp_clients/`（yonsuite、nc）与 `erp_*_tools.py` 取数逻辑零改动；
- **不动技能/记忆系统**：`skill_manager`、`memory_manager`、`fact_memory`、`search_index` 零改动；
- **不引入 session tree**：不实现多分支/回溯，会话模型保持线性；
- **不做 follow-up UI**：`followUp()` 只留接口与内核支持，不接前端、不加 WS 消息；
- **不改 API schema**：`backend/schemas/` 零改动，所有 HTTP/WS 对外消息结构与字段不变；
- **不改 `message_builder.py` / `llm_client.py` / `llm_providers/`**：LLM 层作为既有契约原样复用（唯一的例外见 §8 R3：为透出 `stop_reason=="length"`，`openai_compat.py` / `anthropic.py` 各加一处 finish_reason 映射，属必需的最小改动）；
- **不引入新依赖**：全程标准库 `asyncio` / `concurrent.futures`，无第三方框架。

## 3. 总体设计

### 3.1 内核分层与文件结构

```
agent/core/
├── kernel_types.py      # 新增：AgentLoopConfig / AgentEvent / ToolResult / CancelToken（纯类型 + 常量）
├── loop.py              # 新增：run_agent_loop / run_agent_loop_continue，极简双层循环，零策略
├── agent.py             # 重写为有状态 Agent 包装类（state / subscribe / steer / follow_up / cancel / wait_idle）
├── agent_adapter.py     # 新增：旧 AIAgent 兼容适配层（run_conversation + EventBus 8 事件映射 + Envelope）
├── tool_dispatcher.py   # 改造：async 化，prepare 串行 + handler 并发，execution_mode 判定，截断
├── iteration_budget.py  # 改造：IterationBudget 保留为纯计数器，但消费点挪入 should_stop_after_turn 钩子
├── message_builder.py   # 不动
├── llm_client.py        # 不动
└── llm_providers/       # 不动（除 §8 R3 的 finish_reason 映射）
```

对应 Pi：`loop.py` ↔ `agent-loop.ts`，`kernel_types.py` ↔ `types.ts`，`agent.py` ↔ `agent.ts`，`agent_adapter.py` ↔ zlink 特有的兼容层（Pi 没有对应物）。

**loop 全 asyncio**：`loop.py` 内 `await` 贯穿；同步工具 handler 在 dispatch 层用 `asyncio.to_thread`（内部即 `run_in_executor`）包裹，不要求现有 57 个工具改成 async。`chat.py` 由"线程池 + 跨线程回调"改为"直接 `await` 新 Agent"（见 §3.5），删除 `run_in_executor` 与 `call_soon_threadsafe` 搬运。

### 3.2 事件流与流式协议

新内核定义 **AgentEvent 联合类型**（9 种），作为内核唯一的对外事件通道：

| 事件 | 含义 |
|------|------|
| `AgentStart` | 一次 run 开始 |
| `AgentEnd` | 一次 run 结束（携带完整 messages），**任何路径的最后事件** |
| `TurnStart` / `TurnEnd` | 一个 turn 开始 / 结束（turn = 一次 assistant 响应 + 其 tool 批次） |
| `MessageStart` / `MessageUpdate` / `MessageEnd` | 消息生命周期；`MessageUpdate` 仅流式 assistant 消息触发（携带 `delta` 文本增量与 `reasoning_delta`） |
| `ToolExecutionStart` / `ToolExecutionUpdate` / `ToolExecutionEnd` | 工具执行生命周期 |

事件流向两级适配（均**不修改现有消费方**）：

- **WS 适配层**（`backend/api/chat.py` 内改造）：消费 AgentEvent，产出现有扁平 WS 消息（`token` / `reasoning_token` / `progress` / `tool_call` / `tool_result` / `approval_request` / `done` / `error`），字段与现有完全一致。内核内部仍维护 Envelope（`seq/phase/type/payload`）四元组序列号与 phase，但**前端不接收 Envelope**（已核实：`web/src/api/ws.ts`、`web/src/types/index.ts` 均无 phase 字段），因此 WS 消息集合与字段零改动、前端零改动。
- **EventBus 适配层**（`agent_adapter.py`）：从 AgentEvent 映射出现有 8 类事件（映射表见 §4.4），扩展现有订阅方零改动。

**错误编码进消息流，不抛异常**：LLM 失败 / 工具失败 / 取消都表现为对应消息的 `is_error` 或 `errorMessage` 字段，loop 本身不 raise；`Agent.handleRunFailure` 兜底：即使有意外异常，也构造一条失败 assistant 消息并以 `AgentEnd` 收尾。

**`ToolExecutionUpdate` 铺管道但不强制改造**：事件类型、WS 透传通道、Agent 订阅接口都支持，但现有工具 handler 不要求接入（§4.3 的 update 回调为可选参数，旧工具不传即不产生该事件）。

### 3.3 工具并行与截断防护

`registry.register()` 增加 `execution_mode` 参数（`"parallel"` | `"sequential"`，默认 `"parallel"`）。一次 assistant 消息的 tool_calls 批次执行规则（对照 Pi `agent-loop.ts:executeToolCalls`）：

1. **prepare 阶段串行**：逐条解析参数 JSON、跑 `before_tool_call` 钩子（含安全钩子与 `BeforeToolCallEvent` 取消检查），阻塞/取消的工具直接产出错误 ToolResult；
2. **handler 执行并发**：全部 prepare 通过的工具用 `asyncio.gather` 并发执行；同步 handler 经 `asyncio.to_thread` 包裹；
3. **transcript 按原始顺序保序**：gather 完成后按 assistant `tool_calls` 的原始顺序组装 tool 消息追加进 messages，`tool_result` 类 WS 消息也按原始顺序下发；
4. **sequential 降级**：批次中任一工具的 `execution_mode == "sequential"`，则整批退回串行执行（与 Pi 一致：`hasSequentialToolCall → executeToolCallsSequential`）；
5. **`stop_reason=="length"` 截断防护**：assistant 消息因输出 token 上限被截断时，该消息内的所有 tool call **一律不执行**，逐条返回"参数可能被截断，请重新完整发出"的错误 ToolResult，让模型重新发起（Pi `failToolCallsFromTruncatedMessage` 同款语义）。**前置条件**：审计并补齐 `openai_compat` / `anthropic` 对 finish_reason 的映射（见 §8 R3，当前两 provider 均未透出 length）。

### 3.4 策略钩子化

`AgentLoopConfig` 上的全部钩子（签名见 §4.2）：

| 钩子 | 现有实现来源 | 说明 |
|------|------------|------|
| `transform_context` | `context_compactor`（`_maybe_compact` 搬入） | 每次 LLM 调用前对 messages 做上下文变换；compaction 的 Phase 机联动由适配层在此钩子内维护 |
| `before_tool_call` | `security_hooks` before 链 + `BeforeToolCallEvent` | 返回修改后的 args，或 `{"__block__": True, "__reason__": <原因>}` 阻塞 |
| `after_tool_call` | `security_hooks` after 链 + `AfterToolCallEvent` | 返回修改后的 result 字符串 |
| `prepare_next_turn` | （新）TurnSnapshot 更新点 | 返回下一轮使用的 model/temp/max_tokens 覆盖，未提供则沿用当前 |
| `should_stop_after_turn` | `IterationBudget`（消费点挪入此钩子） | 每 turn 后询问是否停止；预算耗尽 → 返回 True |
| `get_steering_messages` | （新）steering 队列 | 每 turn 后（`should_stop_after_turn` 之前）询问是否有插队消息 |
| `get_follow_up_messages` | （新）follow-up 队列 | 内层循环退出后询问是否有后续消息，有则开启外层下一轮 |

### 3.5 适配层：旧 `AIAgent` 变薄

- `agent/core/agent.py` 重写为新的有状态 `Agent` 类；旧 `AIAgent` 变薄为兼容适配层，位于新文件 `agent/core/agent_adapter.py`（保留类名与构造签名）；
- **`run_conversation()` 签名与返回 keys 不变**：`{final_response, messages, api_calls, token_usage, completed, error}`，`chat.py` 对返回值的消费逻辑零改动；
- **Phase 机语义保留**：`idle/turn/compaction/retry` 由适配层根据 AgentEvent 流维护，`run_conversation` 仍拒绝非 idle 重入；
- **`Agent` 包装类对外提供**：`state`（只读视图）、`subscribe(listener)`、`steer(msg)`、`follow_up(msg)`、`clear_steering_queue()`、`cancel()`、`wait_idle()`；
- **`agent/agent.py` 的 re-export 保持**：`from agent.agent import AIAgent` 继续可用（指向适配层）。

## 4. 详细设计

### 4.1 `kernel_types.py`（Python 伪代码）

```python
"""内核类型契约 —— loop 与策略之间的唯一接口。"""


@dataclass(frozen=True)
class AgentLoopConfig:
    """一次 run 的配置 + 全部策略钩子（均可选）。"""

    model: str
    temperature: float = 0.7
    max_tokens: int | None = None
    system_prompt: str = ""
    tool_defs: list[dict] = field(default_factory=list)  # OpenAI 格式工具定义
    max_tool_result_length: int = sys.maxsize
    # ── 策略钩子（可选，缺省走默认行为；签名见下方注释块）──
    transform_context: Callable[[list[dict], CancelToken], list[dict] | Awaitable[list[dict]]] | None = None
    before_tool_call: Callable | None = None
    after_tool_call: Callable | None = None
    prepare_next_turn: Callable | None = None
    should_stop_after_turn: Callable | None = None
    get_steering_messages: Callable[[CancelToken], list[dict]] | None = None
    get_follow_up_messages: Callable[[CancelToken], list[dict]] | None = None


# ── 钩子签名（全部可选；同步或 async 均可，loop 统一 await）──
# before_tool_call: (tool_name: str, args: dict, token: CancelToken) -> dict
#   返回修改后的 args；返回 {"__block__": True, "__reason__": <原因>} 则阻塞该工具
# after_tool_call: (tool_name: str, args: dict, result: str, token: CancelToken) -> str
#   result 为 JSON 字符串；返回值将替换该工具结果
# prepare_next_turn: (ctx: dict, token: CancelToken) -> TurnUpdate | None
# should_stop_after_turn: (ctx: dict, token: CancelToken) -> bool
#   ctx = {"message": dict, "tool_results": list[ToolResult], "messages": list[dict], "api_calls": int}


@dataclass(frozen=True)
class TurnUpdate:
    """prepare_next_turn 的返回值：对下一轮的覆盖。"""

    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass
class ToolResult:
    tool_call_id: str
    tool_name: str
    result: str  # JSON 字符串（与现有 tool 消息 content 一致）
    is_error: bool = False
    terminate: bool = False  # 未来扩展：全批次 terminate 时提前停止


class CancelToken:
    """取消令牌：等价于 Pi 的 AbortSignal。全链路传递。"""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()  # 挂起直到被取消

    def check(self) -> None:
        if self._event.is_set():
            raise asyncio.CancelledError  # 已取消则中断当前步骤


# ── AgentEvent 联合类型：用 dataclass 区分（type 字段为判别式，置于字段末尾以符合 dataclass 规则）──
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
```

### 4.2 `loop.py`（Python 伪代码）

```python
"""极简 async loop —— 不含任何业务策略，只编排事件流。"""


async def run_agent_loop(
    prompts: list[dict],
    context: AgentContext,
    config: AgentLoopConfig,
    emit: Callable[[AgentEvent], Awaitable[None]],
    token: CancelToken,
) -> list[dict]:
    """带新 prompt 开始一轮 run。"""
    new_messages = list(prompts)
    context.messages += prompts
    await emit(AgentStart())
    await emit(TurnStart())
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
    """从当前 context 继续（context 末条须为 user/tool 消息，否则抛 ValueError）。"""
    if not context.messages or context.messages[-1]["role"] == "assistant":
        raise ValueError("Cannot continue from message role: assistant")
    new_messages: list[dict] = []
    await emit(AgentStart())
    await emit(TurnStart())
    await _run_loop(context, new_messages, config, emit, token)
    return new_messages


async def _run_loop(context, new_messages, config, emit, token) -> None:
    """双层循环：内层 = tool_calls/steering，外层 = follow-up。"""

    async def _no_messages(token) -> list[dict]:
        return []

    get_steering = config.get_steering_messages or _no_messages
    get_followup = config.get_follow_up_messages or _no_messages
    pending = await get_steering(token)
    while True:  # ── 外层循环 ──
        has_more_tool_calls = True
        while has_more_tool_calls or pending:  # ── 内层循环 ──
            token.check()
            await emit(TurnStart())
            if pending:  # steering 消息注入
                for msg in pending:
                    await emit(MessageStart(msg))
                    await emit(MessageEnd(msg))
                    context.messages.append(msg)
                    new_messages.append(msg)
                pending = []
            # 1) 上下文变换（compaction 钩子）
            if config.transform_context:
                context.messages = await config.transform_context(context.messages, token)
            # 2) LLM 调用（不抛异常：失败编码进消息）
            message = await _stream_assistant_response(context, config, emit, token)
            new_messages.append(message)
            if message.failed or message.stop_reason in ("error", "aborted"):
                await emit(TurnEnd(message, []))
                await emit(AgentEnd(new_messages))
                return
            # 3) 工具批次执行
            tool_calls = message.get("tool_calls") or []
            tool_results: list[ToolResult] = []
            has_more_tool_calls = False
            if tool_calls:
                executed = (
                    await _fail_truncated_batch(tool_calls, emit)  # stop_reason=="length"
                    if message.stop_reason == "length"
                    else await _execute_tool_batch(context, message, config, emit, token)
                )
                tool_results = executed.messages
                has_more_tool_calls = not executed.terminate
                for r in tool_results:
                    context.messages.append(_to_tool_message(r))
                    new_messages.append(_to_tool_message(r))
            await emit(TurnEnd(message, tool_results))
            # 4) 下一轮覆盖（model/temperature/max_tokens）
            if config.prepare_next_turn:
                ctx = {
                    "message": message,
                    "tool_results": tool_results,
                    "messages": new_messages,
                    "api_calls": api_calls,
                }
                update = await config.prepare_next_turn(ctx, token)
                if update:
                    config = _apply_update(config, update)
            # 5) 停止判定（IterationBudget 消费点）
            if config.should_stop_after_turn and await config.should_stop_after_turn(ctx, token):
                await emit(AgentEnd(new_messages))
                return
            # 6) steering 再取（one-at-a-time 由 Agent 队列 drain 语义保证）
            pending = await get_steering(token)
        # ── 外层：follow-up 消息 ──
        follow_ups = await get_followup(token)
        if follow_ups:
            pending = follow_ups
            continue
        break
    await emit(AgentEnd(new_messages))
```

要点：

- `emit` 是唯一的对外输出通道，`AgentEnd` 保证任何 return 路径都收尾；
- loop 内**零业务判断**：compaction、预算、安全、steering 全部是钩子；
- `_execute_tool_batch` 内部调用 §4.3 的并行 dispatch，逻辑在 `tool_dispatcher.py`；
- `_stream_assistant_response` 复用现有 `LLMClient.chat`（含流式回调），把流式 delta 转换为 `MessageUpdate` 事件；`stop_reason` 从 `LLMResponse` 透传（§8 R3 补齐后）。

### 4.3 `tool_dispatcher.py` 改造（Python 伪代码）

```python
async def dispatch_tool_batch(
    calls: list[ToolCallPayload],
    *,
    max_result_length: int,
    token: CancelToken,
    emit: Callable[[AgentEvent], Awaitable[None]],
    config: AgentLoopConfig,
) -> "ExecutedToolBatch":
    # 1) 判定模式：全局 sequential 或批次含 sequential 工具 → 串行
    sequential = any(_entry(tc.name).execution_mode == "sequential" for tc in calls)
    if sequential:
        return await _dispatch_sequential(
            calls, max_result_length=max_result_length, token=token, emit=emit, config=config
        )
    return await _dispatch_parallel(
        calls, max_result_length=max_result_length, token=token, emit=emit, config=config
    )

async def _dispatch_parallel(calls, *, max_result_length, token, emit, config) -> ExecutedToolBatch:
    prepared: list[Prepared | Immediate] = []
    for tc in calls:                     # prepare 串行：解析 + before_tool_call + 取消检查
        token.check()
        prepared.append(await _prepare(tc, config, token, emit))
    # 2) handler 并发执行（同步 handler 经 asyncio.to_thread 包裹）；结果携带原始 index 以便保序
    async def _run(prep: Prepared) -> FinalizedToolCall:
        try:
            raw = await asyncio.to_thread(prep.entry.handler, prep.args)
        except Exception as e:           # ApprovalBlockedError 原样上抛，由上层处理
            raw = json.dumps({"success": False, "error": str(e)})
        return await _finalize(prep, raw, config, token)      # 内含 after_tool_call 钩子
    finalized = await asyncio.gather(*(_run(p) for p in prepared if p.kind == "prepared"))
    # 3) 按原始顺序组装 ToolResult + 保序 emit ToolExecutionEnd / tool 消息
    ordered = _restore_order(prepared, finalized)             # Immediate 错误结果也占位
    # 4) 遍历 ordered：构造 ToolResult（按 max_result_length 截断）、emit ToolExecutionEnd、
    #    由调用方按序追加 tool 消息进 transcript
    return _build_batch(ordered)

async def _dispatch_sequential(calls, *, max_result_length, token, emit, config) -> ExecutedToolBatch:
    for tc in calls:                     # 串行：prepare → execute → finalize，逐个推进
        prep = await _prepare(tc, config, token, emit)
        if prep.kind == "immediate":
            continue                     # 错误结果已入列
        raw = await asyncio.to_thread(prep.entry.handler, prep.args)
        finalized = await _finalize(prep, raw, config, token)
        _collect(finalized)              # 按调用顺序收集 + emit ToolExecutionEnd
    return _build_batch(_collected)

同步 handler 包装约定：

```python
# 旧工具 handler 签名 (args: dict) -> str，原样运行、无需改造：
result = await asyncio.to_thread(entry.handler, args)
# 新增可选能力（不强制）：
# handler(args, token=token, on_update=cb)  —— 声明接收 CancelToken 与进度回调；
# 通过 inspect.signature 探测，未声明则按旧签名调用。
```

### 4.4 `agent_adapter.py`：事件映射表

| AgentEvent | EventBus 事件 | 说明 |
|-----------|--------------|------|
| `AgentStart` + 首个 `TurnStart` | `SessionStartEvent(session_id, history)` | 归并为一个 |
| 用户 `MessageStart` | `UserMessageEvent(content)` | 保留取消语义：cancel → 消息被拒 |
| 每次 LLM 调用前（`_stream_assistant_response` 内） | `BeforeLLMCallEvent(model, messages, api_kwargs)` | 保留取消语义 |
| 每次 LLM 调用后 | `AfterLLMCallEvent(model, response)` | |
| `before_tool_call` 钩子内 | `BeforeToolCallEvent(tool_name, args)` | 保留取消语义；`security_hooks` 与扩展共用此事件 |
| `after_tool_call` 钩子内 | `AfterToolCallEvent(tool_name, args, result)` | |
| 适配层维护的 phase 迁移 | `PhaseChangeEvent(from, to, reason, session_id)` | phase 由适配层从事件流推导（`AgentStart→turn`、compaction 钩子运行中→`compaction`、LLM 错误→`retry`） |
| `AgentEnd` | `SessionEndEvent(session_id, final_response, error, api_calls)` | |

`SessionBeforeCompactEvent` 仍由 `context_compactor` 在 `transform_context` 钩子内发出（compaction 代码整体搬入钩子，事件类型与消费方不变）。

### 4.5 `registry.register()` 扩展

```python
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
    execution_mode: str = "parallel",     # ← 新增，默认 parallel
) -> None:
    # 实现与现状相同，仅在 ToolEntry 上多存一个 execution_mode 字段
```

- `ToolEntry` 增加 `execution_mode` 字段；`get_definitions` 输出不变（execution_mode 不进 schema，避免 LLM 侧感知）；
- **写操作工具逐个审计标 `sequential`**：约 57 个已注册工具（含 3 个 bridge 工具）逐文件审计，标定清单作为 P2 的落地任务。审计起点（以工具名与风险等级初判，最终以逐文件 handler 行为为准）：

  | 初判 sequential | 初判 parallel（只读/查询类） |
  |---|---|
  | `execute_code`、`patch`、`write_file`、`terminal`、`process` | `read_file`、`ls`、`glob`、`search_files`、`web_search`、`web_extract`、全部 `query_*`（YonSuite 11 个）、`nc_query`/`nc_list_tables`/`nc_describe_table`、`session_search`、`vision_analyze` |
  | `memory`（写存储）、`todo`（写） | `clarify`、`skill_list`/`skill_view` |
  | `skill_install`/`skill_activate`/`skill_deactivate`/`skill_export` | 3 个 bridge 工具（`tool_search`/`tool_describe`/`tool_call`） |
  | `cronjob_create`/`cronjob_update`/`cronjob_delete`/`cronjob_toggle` | `mcp_list_servers`/`mcp_test_server` |
  | `mcp_add_server`/`mcp_delete_server`/`mcp_toggle_server`/`mcp_reload_servers` | |
  | `project_create`/`project_switch` | |
  | `ys_api`（写接口，须审计）、`nc_raw_sql`（写 SQL，须审计） | |
  | `close_terminal`（状态突变，须审计） | |

  **审计原则**：拿不准的工具一律标 `sequential`（并行是优化，串行是安全基线）。

### 4.6 WS 适配层（`chat.py` 改造）

```
改造前：run_sync() 线程池执行 AIAgent → call_soon_threadsafe 推队列 → 主协程 drain 队列 → send_json
改造后：async def _run_agent():
            await agent.run_conversation_async(user_message=content, history=history, session_id=session_id)
            # 事件订阅器把 AgentEvent 同步转换为现有 WS 消息类型直接 send_json
```

WS 消息类型映射：`MessageUpdate`（assistant）→ `token`（delta 文本）+ `reasoning_token`（reasoning_delta）；`ToolExecutionStart` → `tool_call`（name + arguments 截断 200 字符）；`ToolExecutionEnd` → `tool_result`；`AgentEnd` → `done`（携带 final_response / api_calls / token_usage / completed / error / session_id / session_title，字段与现状一致）；异常兜底 → `error`。用户消息与 tool 消息本身不产生 WS 消息（现状即如此，前端从 `send_message` 回显与 `tool_result` 渲染）。stop 语义：WS `stop` 消息 → `agent.cancel()`。approval：`approval_request` 消息与 `_pending_approvals` 机制不变，`ApprovalBlockedError` 在 `_dispatch_sequential`/`_dispatch_parallel` 的 handler 包装中捕获后经 `approval_callback` 阻塞（与现状相同，改用 `asyncio` 事件等待）。

## 5. 契约兼容性清单（四契约冻结）

| # | 契约 | 冻结范围 |
|---|------|---------|
| C1 | `run_conversation` | 构造签名、`run_conversation(user_message, system_message, conversation_history, stream_callback, reasoning_callback, stop_event, session_id)` 签名、返回 dict 的 6 个 keys 与语义（`{final_response, messages, api_calls, token_usage, completed, error}`） |
| C2 | WS Envelope/消息协议 | `backend/api/chat.py` 下发的扁平消息 `type` 集合与字段不变；前端 `web/src/api/ws.ts`、`web/src/types/index.ts`、`ChatPage` 零改动 |
| C3 | EventBus 8 事件 | `SessionStart/End`、`UserMessage`、`Before/AfterLLMCall`、`Before/AfterToolCall`、`PhaseChange` 的类型、字段、取消语义不变；`SessionBeforeCompactEvent` 不变 |
| C4 | registry 公开接口 | `register`（新增可选参数 `execution_mode`，向后兼容）、`deregister`、`dispatch`、`get_definitions`、`get_all_tool_names`、before/after hook 增删、block 协议（`{"__block__": True, "__reason__": <原因>}`）全部不变 |

冻结验收：存量 371 个测试全绿（见 §6），且 `tests/test_agent*.py`、`tests/test_chat*.py`、`tests/test_events*.py`、`tests/test_registry*.py` 在 P1 完成后**不改一行**通过。

## 6. 测试计划

### 6.1 存量安全网

371 个存量测试全量作为回归基线（`MockLLMProvider` + FastAPI `TestClient` + tmp 配置隔离，零网络）。P1 目标：存量测试在**新旧两个内核**上都通过（双跑验证，见 §7）。

### 6.2 新增测试清单

| 组 | 用例 |
|----|------|
| 并行执行 | 批内 N 个 sleep 工具，总耗时 ≈ max(单个)，远小于 Σ(单个)；`asyncio.to_thread` 下同步 handler 正确运行 |
| 保序 | 并行批次完成后，messages 中 tool 消息顺序与 assistant `tool_calls` 原始顺序一致；`tool_result` WS 消息同样保序 |
| sequential 降级 | 批次含 1 个 `execution_mode="sequential"` 工具 → 整批串行（执行顺序即调用顺序）；纯 parallel 批次不降级 |
| prepare 串行 | before_tool_call 钩子被按序调用一次/工具；阻塞/取消的工具产出错误 ToolResult 且不执行 handler |
| length 截断 | `stop_reason="length"` 时该消息所有 tool call 不执行、各自返回截断错误文本；模型可基于错误重新发起 |
| 取消语义 | `cancel()` 后：进行中的 LLM 调用/工具批次尽快停止；loop 仍以 `AgentEnd` 收尾；`wait_idle()` 返回；`state.pendingToolCalls` 清空 |
| steering | 一次 run 中 `steer()` 注入消息被下一个 turn 消费（one-at-a-time：一次只消费最旧一条）；drain 后清空；无消息时行为不变 |
| AgentEnd 完整性 | LLM 失败、工具抛异常、取消、预算耗尽、正常结束五条路径，事件流均以 `AgentEnd` 收尾且无未捕获异常 |
| 契约回归 | C1–C4 逐条断言（返回 keys、WS 消息集合、EventBus 8 事件、registry 接口） |
| 截断防护 | 单条 tool result 超过 `max_tool_result_length` 被截断并附 `\n\n...`（沿用现有行为） |

### 6.3 兼容性测试用例（新内核 + 旧内核双跑）

- 同一输入（用户消息 + MockLLMResponse 脚本）跑新旧内核，对比：`final_response` 等价、`messages` 结构等价（tool 消息序列一致）、`completed`/`error` 语义一致；
- `ZLINK_KERNEL=old` 时行为与现状完全一致（可逐位 diff WS 消息序列）。

## 7. 实施分期

每期独立可交付，测试全绿才进入下一期（严格门禁）。

- **P1 —— 新 loop 骨架 + Agent 类 + 事件流 + 契约适配 + Budget 钩子化**
  - 新建 `kernel_types.py`、`loop.py`；`agent.py` 重构为 Agent + AIAgent 适配层；`chat.py` 改直接 await；`IterationBudget` 消费点挪入 `should_stop_after_turn`；`transform_context` 接入现有 `context_compactor`。
  - 行为目标：**与现状等价**（串行工具、无 steering）；四契约冻结；371 存量测试全绿；双跑验证上线（`ZLINK_KERNEL` 默认 `new`）。
- **P2 —— 并行工具 + execution_mode 审计 + 截断防护**
  - `registry.register` 加 `execution_mode`；57 个工具逐文件审计标定（清单见 §4.5，作为本期内任务）；`tool_dispatcher` 并行化 + 保序 + sequential 降级；`openai_compat`/`anthropic` 补 finish_reason→`stop_reason` 映射；length 截断防护。
- **P3 —— CancelToken 全链路 + steering 队列 + WS 入口**
  - `CancelToken` 替换/包装现有 `stop_event`；`Agent.steer()` + WS **入站**消息类型 `steering`（前端可选接入：现有前端发送的消息类型集合不受影响，不接入时内核行为与 P1/P2 完全一致）；follow-up 接口就绪但**不接 UI、不加出站消息**。
- **P4 —— 删旧内核 + 文档更新**
  - 移除旧内核分支与 `ZLINK_KERNEL` 回退开关（随下一个大版本）；更新 `AGENTS.md` 架构章节与 `HANDOVER` 相关记录。

## 8. 风险与回退

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | **工具并行引入竞态**：共享可变状态（文件系统、配置、进程、MCP 连接）的工具并发执行导致数据错乱 | 高 | execution_mode 审计（写操作/状态突变工具标 sequential，拿不准一律 sequential）；并行仅限同批次内 prepare 已通过的工具；`file_mutation_queue` 等既有串行机制保持不变；P2 先并行只读类工具小步验证 |
| R2 | **重构期间行为漂移**：新内核与旧内核细节差异导致存量测试外的问题 | 高 | 双跑验证：`ZLINK_KERNEL=new\|old`（默认 `new`，下个大版本删除）一键回退；371 存量测试为安全网；P1 明确"行为与现状等价"为验收门槛；兼容性用例做新旧内核输出 diff |
| R3 | **`stop_reason` 未透出导致截断防护失效**：已核实 `openai_compat.py`/`anthropic.py` 构造 `LLMResponse` 均未传 `stop_reason`（仅 `base.py` 错误路径设 `"error"`），length 截断防护将静默失效 | 中 | P2 内先行补齐 finish_reason 映射并有单测覆盖；防护逻辑在 `stop_reason` 缺失时退化为"照常执行"（现状行为），不回退也不抛错 |
| R4 | **线程池→asyncio 改造的并发模型错误**：`asyncio.to_thread` 包装后的事件顺序、`ApprovalBlockedError` 跨线程等待、WS 层直接 await 的取消传播出问题 | 中 | 复用现有 `_pending_approvals` 机制（改 asyncio.Event）；WS 消息保序由"按原始顺序组装"保证；新增取消语义测试（§6.2）专门覆盖；P1 阶段 `chat.py` 保持队列 drain 的发送骨架，仅换事件来源 |
| R5 | **迁移期双内核并存增加维护面** | 低 | 双跑窗口限一个版本周期；P4 定时删除；`ZLINK_KERNEL` 只在启动时读一次并日志记录，避免每请求判断 |

## 9. 决策摘要

- **分层**：`loop.py`（零策略 async loop）+ `kernel_types.py`（类型契约）+ `agent.py`（有状态 Agent）+ `agent_adapter.py`（兼容层），对照 Pi 三层，`message_builder`/`llm_client`/`llm_providers` 不动；
- **不借鉴**：Pi 自定义消息类型体系、session tree；**保留**：三层安全、tool_search 惰性加载、ERP 上下文注入、Approval 审批流；
- **事件**：9 种 AgentEvent 为内核唯一事件通道；WS 适配层产出现有扁平消息（前端零改动）；EventBus 适配层映射现有 8 类事件（扩展零改动）；错误编码进消息流、任何路径以 `AgentEnd` 收尾；`ToolExecutionUpdate` 铺管道不强制改造；
- **工具**：`execution_mode` 默认 `parallel`，写操作逐个审计标 `sequential`（拿不准一律 sequential）；prepare 串行、handler 并发（`asyncio.gather` + `asyncio.to_thread`）、transcript 保序；含 sequential 工具整批串行；`stop_reason=="length"` 批次全部不执行并返回截断错误；
- **取消与队列**：`CancelToken` 全链路传递，工具 handler 可选声明接收（旧工具原样运行）；steering 队列 WS 入口（one-at-a-time）；follow-up 只留接口不接 UI；
- **迁移**：四契约冻结（run_conversation、WS Envelope/消息协议、EventBus 8 事件、registry 接口）；371 存量测试为安全网；`ZLINK_KERNEL=new|old`（默认 new）双跑回退，下个大版本删除；
- **分期**：P1 骨架等价 → P2 并行+审计+截断 → P3 CancelToken+steering → P4 删旧+文档；每期测试全绿才进入下一期；
- **范围外**：不重写 ERP 客户端、不动技能/记忆系统、不引入 session tree、不做 follow-up UI、不改 API schema、不加新依赖。
