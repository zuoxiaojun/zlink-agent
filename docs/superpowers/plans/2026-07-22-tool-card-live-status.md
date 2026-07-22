# 工具卡即时状态更新 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-subagent-driven-development (recommended) or superpowers-executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 `SET_RESULT` 去重误杀 Bug + 实现工具执行完成后卡片即时变绿，用户在一轮多工具调用中看到每个工具依次"执行中"→转为绿色勾选+结果预览，且工具名不再错误显示为 `"tool"`。

**Architecture:** 后端在 `agent.py` 新增 `tool_result_callback` 参数（默认 None，向后兼容），在 `_run_tool_calls` 的工具结果就绪后通过该回调推送给 chat.py WebSocket 层；前端新增 `REPLACE_PENDING_TOOL` reducer action 将 pending 卡原地替换为 `_tool_done` 标记消息 + 结果内容；`ToolStepCard.tsx` 加 `!_tool_done` 条件使卡片即时从 spinner 切换到绿色勾。SET_RESULT 去重逻辑改为只跳过 `user` 消息，不再按 `role+content` 去重。

**Tech Stack:** Python 3.11+ / FastAPI / React 19 / TypeScript / pytest / MockLLMProvider

---

## 状态跟踪

| 任务 | 状态 |
|------|------|
| Task 1: 后端 — tool_result_callback 接入 + 测试 | `[x]` |
| Task 2: 前端 — SET_RESULT 去重修复 + REPLACE_PENDING_TOOL + types + ToolStepCard | `[x]` |
| Task 3: 端到端验证 — pytest + build/lint + chrome-devtools 实测 | `[ ]` |

---

## Task 1: 后端 — tool_result_callback 接入 + 测试

**目标:** 在 `AIAgent` 新增 `tool_result_callback` 参数，在 `_run_tool_calls` 的工具结果就绪后调用；`chat.py` 中定义回调并传给 AIAgent；新增 2 个 pytest 用例覆盖正向调用和回调顺序。

**改动文件:**
- Modify: `agent/core/agent.py` — `__init__` 新增参数 + `_run_tool_calls` 插入回调调用
- Modify: `backend/api/chat.py` — 定义 `tool_result_callback` 函数 + 传入 AIAgent
- Modify: `tests/test_agent_loop.py` — 新增 2 个测试用例

---

- [ ] **Step 1.1: agent.py `__init__` 新增 `tool_result_callback` 参数**

**位置:** `agent/core/agent.py` 第 266 行 `tool_call_callback` 参数之后

**当前代码（第 264-270 行）:**
```python
        temperature: float = 0.7,
        progress_callback: Callable | None = None,
        tool_call_callback: Callable | None = None,
        compaction_settings: CompactionSettings | None = None,
        max_retries: int = 3,
        max_retry_delay: float = 30.0,
        approval_callback: Callable[[ApprovalRequest], None] | None = None,
    ):
```

**修改后:**
```python
        temperature: float = 0.7,
        progress_callback: Callable | None = None,
        tool_call_callback: Callable | None = None,
        tool_result_callback: Callable | None = None,
        compaction_settings: CompactionSettings | None = None,
        max_retries: int = 3,
        max_retry_delay: float = 30.0,
        approval_callback: Callable[[ApprovalRequest], None] | None = None,
    ):
```

**当前代码（第 282-284 行）:**
```python
        self.tool_call_callback = tool_call_callback
        self.compaction_settings = compaction_settings or CompactionSettings()
```

**修改后:**
```python
        self.tool_call_callback = tool_call_callback
        self.tool_result_callback = tool_result_callback
        self.compaction_settings = compaction_settings or CompactionSettings()
```

---

- [ ] **Step 1.2: agent.py `_run_tool_calls` 插入回调调用**

**位置:** `agent/core/agent.py` 第 693-695 行之间（`result = post_event.result` 之后、`messages.append(` 之前）

**当前代码（第 692-695 行）:**
```python
            event_bus.publish(post_event)
            result = post_event.result

            messages.append(
```

**修改后:**
```python
            event_bus.publish(post_event)
            result = post_event.result

            # 工具执行后通知前端（渐进式 tool_result）
            if self.tool_result_callback:
                self.tool_result_callback(tc.name, result)

            messages.append(
```

**注意:** 这段代码位于所有分支（JSON 解析失败 / 事件拦截 / Bridge 工具 / 正常分发 / 审批重试 / 用户拒绝）的统一出口——即 `messages.append(...)` 之前。一个调用点覆盖全部路径。

---

- [ ] **Step 1.3: chat.py 新增 `tool_result_callback` 函数定义**

**位置:** `backend/api/chat.py` 第 314-318 行 `tool_call_callback` 函数之后

**当前代码（第 314-319 行）:**
```python
    def tool_call_callback(name: str, args: str):
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"type": "tool_call", "name": name, "arguments": args},
        )

    # Approval callback — called from agent thread when ApprovalBlockedError is caught
```

**修改后:**
```python
    def tool_call_callback(name: str, args: str):
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"type": "tool_call", "name": name, "arguments": args},
        )

    def tool_result_callback(name: str, result: str):
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"type": "tool_result", "name": name, "result": result},
        )

    # Approval callback — called from agent thread when ApprovalBlockedError is caught
```

---

- [ ] **Step 1.4: chat.py AIAgent 构造传入 `tool_result_callback`**

**位置:** `backend/api/chat.py` 第 338-347 行

**当前代码（第 338-347 行）:**
```python
            agent = AIAgent(
                api_key=api_key,
                base_url=base_url,
                model=model,
                max_iterations=max_iterations,
                progress_callback=progress_callback,
                tool_call_callback=tool_call_callback,
                compaction_settings=compaction_settings,
                approval_callback=_on_approval_request,
            )
```

**修改后:**
```python
            agent = AIAgent(
                api_key=api_key,
                base_url=base_url,
                model=model,
                max_iterations=max_iterations,
                progress_callback=progress_callback,
                tool_call_callback=tool_call_callback,
                tool_result_callback=tool_result_callback,
                compaction_settings=compaction_settings,
                approval_callback=_on_approval_request,
            )
```

---

- [ ] **Step 1.5: 新增 pytest 测试用例**

**文件:** `tests/test_agent_loop.py`，在文件末尾追加

**测试 1: `test_tool_result_callback_invoked`**

```python
# ────────────────────────────────────────────────────────────────────
# 10) tool_result_callback — 渐进式工具结果推送
# ────────────────────────────────────────────────────────────────────


def test_tool_result_callback_invoked(monkeypatch):
    """tool_result_callback must be called with (tool_name, result_str)
    after a tool executes."""
    from agent.config_model import AppConfig

    monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))

    captured: list[tuple[str, str]] = []

    def spy(name: str, result: str) -> None:
        captured.append((name, result))

    provider = MockLLMProvider(
        responses=[
            make_tool_call_response("terminal", {"command": "echo hi"}),
            make_text_response("done"),
        ]
    )
    agent = AIAgent(
        api_key="sk-fake",
        base_url="x",
        model="gpt-4o",
        max_iterations=3,
        tool_result_callback=spy,
    )
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    result = agent.run_conversation("run echo")
    assert result["completed"] is True
    assert len(captured) == 1, f"expected 1 call, got {captured}"
    name, res = captured[0]
    assert name == "terminal"
    payload = json.loads(res)
    assert payload["success"] is True
```

**测试 2: `test_tool_call_and_result_callbacks_both_invoked_in_order`**

```python
def test_tool_call_and_result_callbacks_both_invoked_in_order(monkeypatch):
    """tool_call_callback must fire before tool_result_callback,
    in the same execution pass."""
    from agent.config_model import AppConfig

    monkeypatch.setattr("agent.config_manager.load", lambda: AppConfig(approval_mode="allow_all"))

    order: list[str] = []

    def call_cb(name: str, args: str) -> None:
        order.append(f"call:{name}")

    def result_cb(name: str, result: str) -> None:
        order.append(f"result:{name}")

    provider = MockLLMProvider(
        responses=[
            make_tool_call_response("terminal", {"command": "echo hi"}),
            make_text_response("done"),
        ]
    )
    agent = AIAgent(
        api_key="sk-fake",
        base_url="x",
        model="gpt-4o",
        max_iterations=3,
        tool_call_callback=call_cb,
        tool_result_callback=result_cb,
    )
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=provider)

    result = agent.run_conversation("run echo")
    assert result["completed"] is True
    assert order == ["call:terminal", "result:terminal"], f"unexpected order: {order}"
```

---

- [ ] **Step 1.6: 运行 pytest 验证两个新增用例通过**

```bash
.venv/bin/python -m pytest tests/test_agent_loop.py -v -k "tool_result"
```

**预期输出:**
```
tests/test_agent_loop.py::test_tool_result_callback_invoked PASSED
tests/test_agent_loop.py::test_tool_call_and_result_callbacks_both_invoked_in_order PASSED
```

---

- [ ] **Step 1.7: 全量回归确认零失败**

```bash
.venv/bin/python -m pytest tests/ -q
```

**预期输出:** 全部通过，无失败（当前约 395 个用例）。

---

- [ ] **Step 1.8: Commit（后端改动 + 测试）**

```bash
git add -f docs/superpowers/plans/2026-07-22-tool-card-live-status.md
git add agent/core/agent.py backend/api/chat.py tests/test_agent_loop.py
git commit -m "feat: add tool_result_callback for progressive tool status updates

- AIAgent.__init__: new tool_result_callback param (default None, backward-compat)
- _run_tool_calls: call tool_result_callback(name, result) before messages.append
- chat.py: define tool_result_callback, wire WS queue message type 'tool_result'
- tests: 2 new cases verifying callback invocation and call-order"
```

---

## Task 2: 前端 — SET_RESULT 去重修复 + REPLACE_PENDING_TOOL + types + ToolStepCard

**目标:** 修复 `AppContext.tsx` SET_RESULT 按 `role+content` 去重误杀多轮 assistant 消息的 bug；新增 `REPLACE_PENDING_TOOL` action 实现渐进式结果替换；扩展 TypeScript 类型；`useChat.ts` 处理 `tool_result` 消息；`ToolStepCard.tsx` 根据 `_tool_done` 即时切换状态。

**改动文件:**
- Modify: `web/src/types/index.ts` — Message 加 `_tool_done`；WsServerMessage 加 `tool_result`
- Modify: `web/src/context/AppContext.tsx` — 修复 SET_RESULT；新增 REPLACE_PENDING_TOOL action+case
- Modify: `web/src/hooks/useChat.ts` — 新增 `case "tool_result"`
- Modify: `web/src/components/ToolStepCard.tsx` — `isPendingTool` 追加 `!_tool_done`

---

- [ ] **Step 2.1: types/index.ts — Message 接口新增 `_tool_done` 字段**

**位置:** `web/src/types/index.ts` 第 21 行 `_agent_info` 之后

**当前代码（第 15-22 行）:**
```typescript
export interface Message {
  role: "user" | "assistant" | "tool";
  content: string | ContentPart[];
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  reasoning_content?: string;
  _agent_info?: AgentInfo;
}
```

**修改后:**
```typescript
export interface Message {
  role: "user" | "assistant" | "tool";
  content: string | ContentPart[];
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  reasoning_content?: string;
  _agent_info?: AgentInfo;
  _tool_done?: boolean;  // 前端临时标记：工具已执行完成
}
```

---

- [ ] **Step 2.2: types/index.ts — WsServerMessage 新增 `tool_result` 类型**

**位置:** `web/src/types/index.ts` 第 193 行（`tool_call` 之后）

**当前代码（第 190-194 行）:**
```typescript
export type WsServerMessage =
  | { type: "token"; content: string }
  | { type: "reasoning_token"; content: string }
  | { type: "tool_call"; name: string; arguments: string }
  | { type: "progress"; message: string }
```

**修改后:**
```typescript
export type WsServerMessage =
  | { type: "token"; content: string }
  | { type: "reasoning_token"; content: string }
  | { type: "tool_call"; name: string; arguments: string }
  | { type: "tool_result"; name: string; result: string }
  | { type: "progress"; message: string }
```

---

- [ ] **Step 2.3: AppContext.tsx — AppAction 新增 `REPLACE_PENDING_TOOL`**

**位置:** `web/src/context/AppContext.tsx` 第 62-63 行

**当前代码（第 62-64 行）:**
```typescript
  | { type: "ADD_PENDING_TOOL"; message: Message }
  | { type: "SET_RESULT"; messages: Message[]; tokenUsage: TokenUsage | null; apiCalls: number; error: string | null }
```

**修改后:**
```typescript
  | { type: "ADD_PENDING_TOOL"; message: Message }
  | { type: "REPLACE_PENDING_TOOL"; name: string; result: string }
  | { type: "SET_RESULT"; messages: Message[]; tokenUsage: TokenUsage | null; apiCalls: number; error: string | null }
```

---

- [ ] **Step 2.4: AppContext.tsx — 修复 SET_RESULT 去重逻辑**

**位置:** `web/src/context/AppContext.tsx` 第 120-128 行

**当前代码（第 120-128 行）:**
```typescript
    case "SET_RESULT": {
      // 先移除 pending 工具消息（tool_call_id 以 "pending:" 开头）
      const msgs = state.messages.filter(m => !(m.role === "tool" && m.tool_call_id && m.tool_call_id.startsWith("pending:")));
      for (const m of action.messages) {
        const key = m.role + (typeof m.content === "string" ? m.content : "");
        if (!msgs.some(existing => existing.role + (typeof existing.content === "string" ? existing.content : "") === key)) {
          msgs.push(m);
        }
      }
```

**修改后:**
```typescript
    case "SET_RESULT": {
      // 先移除 pending 工具消息（tool_call_id 以 "pending:" 开头）
      const msgs = state.messages.filter(m => !(m.role === "tool" && m.tool_call_id && m.tool_call_id.startsWith("pending:")));
      for (const m of action.messages) {
        // 用户消息前端已通过 SET_MESSAGES 加入，避免重复
        if (m.role === "user") continue;
        msgs.push(m);
      }
```

**改动说明:** 移除了基于 `role + content` 的内容去重循环，改为只跳过 `role === "user"` 的消息。assistant 和 tool 消息直接追加，不再做内容级别的去重。这样第二轮 assistant 消息（`role="assistant"`, `content=""`）不会被误判为重复。

---

- [ ] **Step 2.5: AppContext.tsx — 新增 REPLACE_PENDING_TOOL reducer case**

**位置:** `web/src/context/AppContext.tsx`，在 `ADD_PENDING_TOOL` case 之后（第 119 行之后）、`SET_RESULT` case 之前

**插入代码:**
```typescript
    case "REPLACE_PENDING_TOOL": {
      const id = "pending:" + action.name;
      // 从后往前遍历，替换最新一条匹配的 pending 卡
      let targetIdx = -1;
      for (let i = state.messages.length - 1; i >= 0; i--) {
        const m = state.messages[i];
        if (m.role === "tool" && m.tool_call_id === id) {
          targetIdx = i;
          break;
        }
      }
      if (targetIdx < 0) return state;
      const msgs = [...state.messages];
      msgs[targetIdx] = { ...msgs[targetIdx], content: action.result, _tool_done: true };
      return { ...state, messages: msgs };
    }
```

**关键设计:** 保留 `tool_call_id` 为 `"pending:工具名"` 不变，仅更新 `content` 和新增 `_tool_done`。这样 `SET_RESULT` 的移除逻辑（`pending:` 前缀过滤）保持不变，而 `ToolStepCard.tsx` 的 `isPendingTool` 检测可通过 `_tool_done` 判断。

---

- [ ] **Step 2.6: useChat.ts — 新增 `case "tool_result"`**

**位置:** `web/src/hooks/useChat.ts` 第 76-78 行（`case "progress"` 和 `case "done"` 之间）

**当前代码（第 76-79 行）:**
```typescript
          case "progress":
            dispatch({ type: "SET_PROGRESS", message: msg.message });
            break;
          case "done":
```

**修改后:**
```typescript
          case "progress":
            dispatch({ type: "SET_PROGRESS", message: msg.message });
            break;
          case "tool_result":
            dispatch({ type: "REPLACE_PENDING_TOOL", name: msg.name, result: msg.result });
            break;
          case "done":
```

---

- [ ] **Step 2.7: ToolStepCard.tsx — 修改 `isPendingTool` 判断**

**位置:** `web/src/components/ToolStepCard.tsx` 第 104 行

**当前代码（第 104 行）:**
```typescript
  const isPendingTool = result && result.tool_call_id && (result.tool_call_id.startsWith("running:") || result.tool_call_id.startsWith("pending:"));
```

**修改后:**
```typescript
  const isPendingTool = result && result.tool_call_id && (result.tool_call_id.startsWith("running:") || result.tool_call_id.startsWith("pending:")) && !result._tool_done;
```

**改动说明:** 追加 `&& !result._tool_done` 条件。当 `_tool_done === true` 时（REPLACE_PENDING_TOOL 已设置），`isPendingTool` 为 `false`，卡片立即显示绿色勾 + 结果预览。

---

- [ ] **Step 2.8: 验证前端构建和 lint 通过**

```bash
cd web && npm run build
```

**预期输出:** 零 TypeScript 编译错误，零 vite 构建错误。

```bash
cd web && npm run lint
```

**预期输出:** 零 eslint error/warning。

---

- [ ] **Step 2.9: Commit（前端改动）**

```bash
git add web/src/types/index.ts web/src/context/AppContext.tsx web/src/hooks/useChat.ts web/src/components/ToolStepCard.tsx
git commit -m "feat: fix SET_RESULT dedup bug and add progressive tool card status

- types: add _tool_done to Message, tool_result to WsServerMessage
- AppContext: fix SET_RESULT to skip only user messages instead of content dedup
- AppContext: add REPLACE_PENDING_TOOL action for in-place pending card replacement
- useChat: handle tool_result WS message -> dispatch REPLACE_PENDING_TOOL
- ToolStepCard: check _tool_done to switch from spinner to green check"
```

---

## Task 3: 端到端验证 — pytest + build/lint + chrome-devtools 实测

**目标:** 确保全部测试通过、前端构建无误、并实际通过浏览器验证工具卡即时状态更新和工具名正确显示。

---

- [ ] **Step 3.1: 全量 pytest 回归**

```bash
.venv/bin/python -m pytest tests/ -q
```

**预期输出:** 全部通过（约 395 个测试用例），不得有任何 FAILED。

---

- [ ] **Step 3.2: 前端 TypeScript 编译 + vite build**

```bash
cd web && npm run build
```

**预期输出:** 零错误。

---

- [ ] **Step 3.3: 前端 eslint lint**

```bash
cd web && npm run lint
```

**预期输出:** 零 error/warning（项目已有 baseline lint 规则，不得新增）。

---

- [ ] **Step 3.4: 启动 dev 环境**

```bash
./start.sh --dev
```

**预期:** 后端启动在 8089，前端 vite 启动在 8088，浏览器自动打开 `http://127.0.0.1:8088`。

---

- [ ] **Step 3.5: 打开 chrome-devtools 准备观察 WebSocket 消息**

1. 在浏览器中打开 http://127.0.0.1:8088
2. 打开 Chrome DevTools → Network → WS
3. 确认已配置 LLM API Key（Settings → LLM → 输入 API Key 和 Base URL）
4. 确认 YonSuite 或至少一个 ERP 已启用（Settings → ERP）
5. 刷新页面，在 DevTools 的 WS 面板中选中 `ws://127.0.0.1:8089/ws/chat/` 的连接

---

- [ ] **Step 3.6: 发送触发多工具调用的消息并观察**

在聊天输入框中发送一条能触发多轮工具调用的消息，例如 `"查 YonSuite 所有销售订单和客户数据"`。

**在 DevTools 的 WS 面板中观察消息序列:**

确认 WebSocket 消息流中包含以下顺序：
```
← tool_call  {type: "tool_call", name: "query_sale_orders", arguments: "..."}
← tool_result {type: "tool_result", name: "query_sale_orders", result: "{...}"}
← tool_call  {type: "tool_call", name: "query_customers", arguments: "..."}
← tool_result {type: "tool_result", name: "query_customers", result: "{...}"}
← done       {type: "done", ...}
```

**在 UI 中观察:**

1. 第一个工具卡（query_sale_orders）出现 spinner "正在执行…"
2. 此卡片立即变为绿色勾 + 显示结果预览（不等整轮结束）
3. 第二个工具卡（query_customers）出现 spinner
4. 此卡片立即变为绿色勾 + 显示结果预览
5. 所有工具卡的名称正确显示（如 `查询销售订单`、`查询客户`），而非 `"tool"`
6. 整轮结束后，所有工具卡正常显示，无残留 pending 标记

---

- [ ] **Step 3.7: 验证边界场景 — 审批拒绝时卡片行为**

如果有配置审批的工具（如 `terminal`），发送一条触发审批的消息。在审批弹窗中点击拒绝。观察：该工具的卡片保持 spinner 直到 `done` 消息到来后被 SET_RESULT 替换（tool_result_callback 不会在审批拒绝路径触发）。

---

- [ ] **Step 3.8: 最终确认并 Commit（剩余文件）**

如有需要补充的中间修复，一并提交。

```bash
git add -A
git status  # 确认没有意外改动
git commit -m "chore: finalize tool card live status implementation

- verify all tests pass, build succeeds, lint clean
- manual chrome-devtools verification of progressive tool_result flow"
```

---

## 自审清单

| 检查项 | 状态 |
|--------|------|
| Spec 覆盖率：SET_RESULT 去重修复 | Task 2 Step 2.4 |
| Spec 覆盖率：tool_result_callback 参数 | Task 1 Step 1.1 |
| Spec 覆盖率：_run_tool_calls 调用 | Task 1 Step 1.2 |
| Spec 覆盖率：chat.py 接线 | Task 1 Step 1.3-1.4 |
| Spec 覆盖率：WsServerMessage 新类型 | Task 2 Step 2.2 |
| Spec 覆盖率：Message._tool_done | Task 2 Step 2.1 |
| Spec 覆盖率：REPLACE_PENDING_TOOL action + case | Task 2 Step 2.3, 2.5 |
| Spec 覆盖率：useChat tool_result 处理 | Task 2 Step 2.6 |
| Spec 覆盖率：ToolStepCard isPendingTool 更新 | Task 2 Step 2.7 |
| Spec 覆盖率：pytest 测试用例 | Task 1 Step 1.5 |
| Spec 覆盖率：chrome-devtools 验证 | Task 3 Step 3.4-3.6 |
| 无 TBD/TODO 占位符 | ✅ |
| 任务间依赖清晰（Task 1 → Task 2 → Task 3） | ✅ |
| 每个验证步骤有精确命令和预期输出 | ✅ |
| 不修改 registry.py/security_hooks.py/backend/schemas | ✅ |
| agent.py 新参数默认值 None 向后兼容 | Task 1 Step 1.1 |
