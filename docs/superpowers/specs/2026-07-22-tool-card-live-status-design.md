# 工具卡即时状态更新：修复 SET_RESULT 去重 Bug + 工具完成后卡片即时变绿

## 目标

实现两个紧密关联的改进：(1) 修复 `AppContext.tsx` 中 `SET_RESULT` action 按 `role+content` 去重导致多轮工具调用时助理消息被误丢弃的 bug，使第二轮及后续工具卡正确显示工具名称；(2) 在工具执行完成后，前端工具卡立即从旋转 spinner 变为绿色勾选状态并显示结果预览，无需等待整轮 agent 循环结束。最终用户在一轮多工具调用的对话中，应当看到每个工具依次进入"执行中"状态、依次变为"已完成"并显示结果预览、且所有工具卡的工具名始终正确。

## 验收标准

1. **Bug 修复可验证**：打开 chrome-devtools，通过 chat WebSocket 发送一次涉及两轮工具调用的请求（例如 "查 YonSuite 销售订单"，它触发 `query_sale_orders`，LLM 看结果后可能再调用 `query_customers`），观察第二轮工具卡的名称不再是 "tool"，而是正确的 `query_customers`（或其他实际工具名）。
2. **渐进式 tool_result 可验证**：在第一轮工具调用中，观察 WebSocket 消息流——`tool_call` 消息之后出现 `tool_result` 消息；前端工具卡从 spinner → 绿色勾 + 结果预览的过渡在 `tool_result` 到达时即时发生，而不是等到 `done` 消息。
3. **回归**：`pytest tests/ -q` 全部通过；`cd web && npm run build && npm run lint` 零错误。

## 现状分析

### 数据流链路（已有）

```
agent.py _run_tool_calls()
  → tool_call_callback(name, args_str)     // 执行前推送 {type: "tool_call", name, arguments}
  → dispatch_tool(name, args)              // 执行工具，返回 (result, preview)
  → 结果 append 进 messages

chat.py 侧：
  tool_call_callback → loop.call_soon_threadsafe(queue.put_nowait, {type:"tool_call", ...})
  异步 drain 循环 → websocket.send_json()

前端：
  useChat.ts case "tool_call" → dispatch ADD_PENDING_TOOL
  AppContext.tsx reducer → 追加 {role:"tool", content:args, tool_call_id:"pending:"+name}
  ToolStepCard.tsx isPendingTool → 检测 pending: 前缀 → 显示 spinner "正在执行…"
  
  整轮结束后：
  useChat.ts case "done" → dispatch SET_RESULT
  AppContext.tsx reducer → 过滤掉 pending: 消息，追加 action.messages
  ToolStepCard.tsx → 根据 real message 显示结果
```

### Bug：SET_RESULT 去重误杀

`AppContext.tsx` 中 `SET_RESULT` 处理（第 120-143 行）：

```typescript
case "SET_RESULT": {
  const msgs = state.messages.filter(m => !(m.role === "tool" && m.tool_call_id && m.tool_call_id.startsWith("pending:")));
  for (const m of action.messages) {
    const key = m.role + (typeof m.content === "string" ? m.content : "");
    if (!msgs.some(existing => existing.role + (typeof existing.content === "string" ? existing.content : "") === key)) {
      msgs.push(m);
    }
  }
  ...
}
```

去重 key 为 `role + content`。携带 `tool_calls` 的 assistant 消息 `content` 为空字符串 `""`，因此 key 为 `"assistant"`。同一会话中第二轮工具调用的 assistant 消息（同样是 `role="assistant"`, `content=""`）被误判为重复而丢弃。

后果：`ChatMessage.tsx` 在渲染 tool 消息时，从 assistant 消息提取 `ToolCall` 列表（`pending` 数组），由于第二轮 assistant 消息缺失，pending 数组为空，无法通过 `tool_call_id` 匹配到 `ToolCall`，最终回退显示 `"tool"` 作为工具名。

### 缺少的渐进式 tool_result

当前 `dispatch_tool` 返回后没有通知前端。前端要等待整轮 agent 循环结束后 `done` 消息中的 `SET_RESULT` 才能看到工具结果，导致卡片长时间停留在 spinner 状态。

## 改动 1：修复 SET_RESULT 去重误杀

### 设计

移除 `SET_RESULT` 中基于 `role + content` 的内容去重逻辑，改为两阶段过滤：

1. 先移除 `pending:` 占位消息（保留现有行为）
2. 遍历 `action.messages` 时跳过 `role === "user"` 的消息（用户消息已由 `SET_MESSAGES` 在前端发送时加入，agent 返回的消息列表中包含它们，不加过滤会导致重复）
3. 其余消息直接追加，不做内容去重

### 修改文件

**`web/src/context/AppContext.tsx`** — `SET_RESULT` case：

```typescript
case "SET_RESULT": {
  // 先移除 pending 工具消息（tool_call_id 以 "pending:" 开头）
  const msgs = state.messages.filter(
    m => !(m.role === "tool" && m.tool_call_id && m.tool_call_id.startsWith("pending:"))
  );
  for (const m of action.messages) {
    // 用户消息前端已通过 SET_MESSAGES 加入，避免重复
    if (m.role === "user") continue;
    msgs.push(m);
  }
  if (action.error) {
    msgs.push({ role: "assistant", content: `❌ ${action.error}` });
  }
  return {
    ...state,
    messages: msgs,
    agentRunning: false,
    streamingText: "",
    ...
  };
}
```

### 关键约束

- 用户消息去重是唯一需要的过滤逻辑。`user` 消息的 `content` 每次都不相同且在前端 `sendMessage()` 时已加入 `state.messages`。
- 不去重 `assistant` 和 `tool` 消息，即使它们内容相同也允许重复（正常场景不会出现完全相同的两轮输出；预防重复任务交给后端会话管理）。
- `pending:` 过滤逻辑保持不变，确保 `REPLACE_PENDING_TOOL`（改动 2）产生的中间态消息在整轮结束时被清除。

## 改动 2：渐进式 tool_result

### 数据流

```
agent.py _run_tool_calls()
  → tool_call_callback(name, args_str)          // 执行前（已有）
  → dispatch_tool(name, args) → result
  → tool_result_callback(name, result)           // ✨ 新增：执行后通知前端
  → 结果 append 进 messages

chat.py：
  tool_result_callback → loop.call_soon_threadsafe(queue.put_nowait, {type:"tool_result", name, result})

WebSocket 消息序列（一轮工具调用）：
  {"type": "tool_call", "name": "query_sale_orders", "arguments": "..."}
  → 前端插入 pending 卡片（spinner）
  {"type": "tool_result", "name": "query_sale_orders", "result": "..."}
  → 前端卡片即时变绿
  ... 后续其他工具同理 ...
  {"type": "done", "messages": [...], ...}
  → SET_RESULT 清理 pending 残留，最终持久化
```

### 后端改动文件

**`agent/core/agent.py`**

1. 构造函数 `__init__` 新增参数 `tool_result_callback: Callable | None = None`（与 `tool_call_callback` 对称，放在其后，默认值 `None` 保持向后兼容）。
2. 存储：`self.tool_result_callback = tool_result_callback`。
3. `_run_tool_calls()` 方法中，在工具结果就绪后（`result` 变量已赋值，`messages.append(...)` 之前）插入：

```python
# 工具执行后通知前端
if self.tool_result_callback:
    self.tool_result_callback(tc.name, result)
```

这段代码放在所有分支（JSON 解析失败 / 事件拦截 / Bridge 工具 / 正常分发 / 审批重试 / 用户拒绝）之后的统一出口——即第 695 行 `messages.append(...)` 之前。一个调用点覆盖全部路径。

**`backend/api/chat.py`**

1. 在 `_run_agent` 函数中 `tool_call_callback` 定义之后、`run_sync` 定义之前，新增：

```python
def tool_result_callback(name: str, result: str):
    loop.call_soon_threadsafe(
        queue.put_nowait,
        {"type": "tool_result", "name": name, "result": result},
    )
```

2. `AIAgent` 构造调用处新增参数：

```python
agent = AIAgent(
    ...
    tool_call_callback=tool_call_callback,
    tool_result_callback=tool_result_callback,   # ✨ 新增
    compaction_settings=compaction_settings,
    ...
)
```

### 前端改动文件

**`web/src/types/index.ts`**

1. `Message` 接口新增字段：

```typescript
export interface Message {
  role: "user" | "assistant" | "tool";
  content: string | ContentPart[];
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  reasoning_content?: string;
  _agent_info?: AgentInfo;
  _tool_done?: boolean;  // ✨ 新增：前端临时标记，表示工具已执行完成
}
```

2. `WsServerMessage` 联合类型新增成员：

```typescript
export type WsServerMessage =
  | { type: "token"; content: string }
  | { type: "reasoning_token"; content: string }
  | { type: "tool_call"; name: string; arguments: string }
  | { type: "tool_result"; name: string; result: string }  // ✨ 新增
  | { type: "progress"; message: string }
  | ...
```

**`web/src/hooks/useChat.ts`**

在 WS `onMessage` switch 中新增 `case "tool_result"`：

```typescript
case "tool_result":
  dispatch({ type: "REPLACE_PENDING_TOOL", name: msg.name, result: msg.result });
  break;
```

放在 `case "progress"` 和 `case "done"` 之间。

**`web/src/context/AppContext.tsx`**

1. `AppAction` 联合类型新增：

```typescript
| { type: "REPLACE_PENDING_TOOL"; name: string; result: string }
```

2. reducer 新增 case：

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

**关键设计决策**：保留 `tool_call_id` 为 `"pending:工具名"` 不变，仅更新 `content` 和新增 `_tool_done`。这样 `ToolStepCard.tsx` 的 `isPendingTool` 检测修改后仍能从 `tool_call_id` 解析工具名，且卡片状态逻辑一致。

**`web/src/components/ToolStepCard.tsx`**

将第 104 行的 `isPendingTool` 判断从：

```typescript
const isPendingTool = result && result.tool_call_id && 
  (result.tool_call_id.startsWith("running:") || result.tool_call_id.startsWith("pending:"));
```

改为：

```typescript
const isPendingTool = result && result.tool_call_id && 
  (result.tool_call_id.startsWith("running:") || result.tool_call_id.startsWith("pending:")) &&
  !result._tool_done;
```

当 `_tool_done === true` 时，`isPendingTool` 为 `false`，卡片立即显示绿色勾 + 结果预览（通过已有的 `raw` 和 `open` 逻辑）。

### 关键约束

1. **`_tool_done` 仅是前端临时标记**：`SET_RESULT` 时 `pending:` 占位消息（含 `_tool_done`）被统一过滤掉，替换为 agent 返回的真实 tool 消息。`_tool_done` 不会泄漏到会话持久化（`session_manager.save_session`）中。
2. **并行同名工具调用**：`REPLACE_PENDING_TOOL` 从后往前查找匹配的 pending 消息。最坏情况下（同一轮中两次调用同名工具）会替换最后一个匹配项。这是可接受的边缘行为——agent 循环中极少先直接并行同工具两次，且即使用户观察到短暂错位，整轮结束后 `SET_RESULT` 会纠正所有消息。
3. **`result` 直接透传**：使用 `dispatch_tool` 返回的截断后 JSON 字符串（即 `dispatch_tool` 返回的 `(truncated, preview)` 中的第一个元素），原样传给 `tool_result_callback`。前端直接设置为 `content`，与最终持久化的格式一致。
4. **`findLastIndex` 兼容性**：TypeScript 目标如果低于 ES2023，需手动实现从后往前遍历或以 `lastIndexOf` 模式实现。

## 边界情况与错误处理

| 场景 | 行为 |
|------|------|
| 工具执行异常（dispatch_tool 内部抛异常） | `_run_tool_calls` 的 `except` 分支会 raise（非 `ApprovalBlockedError`），`tool_result_callback` 不会被调用，pending 卡一直转圈直到 `done` 消息到来后 `SET_RESULT` 替换 |
| 审批拒绝 | 用户拒绝后 `result` 为错误 JSON，`tool_result_callback` 会发送该错误结果；卡片变为绿色但内容为 "用户拒绝了操作" |
| 审批超时 | 同上，`result` 为 None → `tool_result_callback` 不会被调用（`_handle_approval_block` 返回 None 后走用户拒绝路径） |
| `stop_event` 中断 | 循环中 `stop_event.is_set()` 检查后 `break`，未执行的工具不会有 `tool_result_callback`；已执行完的工具会触发回调 |
| WebSocket 提前关闭 | `queue.put_nowait` 无阻塞，消息堆积在队列中，drain 循环发现 WS 已关则退出 |
| 工具结果截断 | `tool_result_callback` 传递的是 `dispatch_tool` 截断后的结果，与追加到 messages 的内容一致 |
| 多轮工具调用中第二轮工具名 `"tool"` 修复 | 改动 1 修复后将不再丢弃第二轮 assistant 消息，`ChatMessage.tsx` 配对逻辑正常工作 |

## 测试计划

### 后端 pytest

在 `tests/test_agent_loop.py` 中新增测试用例：

1. **`test_tool_result_callback_invoked()`**: 使用 `MockLLMProvider` 模拟一次工具调用 + 文本回复。构造 `AIAgent` 时传入 `tool_result_callback` spy，执行后断言 spy 被调用一次，参数为 `(工具名, 结果字符串)`。

2. **`test_tool_result_callback_not_invoked_on_approval_deny()`** (可选): 验证审批拒绝时回调不被触发。

3. **`test_tool_call_callback_and_result_callback_both_invoked()`**: 验证 `tool_call_callback` 在 `tool_result_callback` 之前被调用，且参数正确。

4. **回归**：`pytest tests/ -q` 全部通过，不得新增失败。

### 前端验证

1. `cd web && npm run build` 零错误。
2. `cd web && npm run lint` 零 warning/error。

### Live 验证（chrome-devtools）

1. 打开 chrome-devtools → Network → WS。
2. 发送一条触发多工具调用的请求（如 "查 YonSuite 销售订单"）。
3. 验证 WS 消息流：`tool_call` → `tool_result` → `tool_call` → `tool_result` → `done`。
4. 验证 UI：每个工具依次出现 spinner → 即时变绿 → 显示预览。
5. 验证第二轮工具卡名称正确（不是 "tool"）。
6. 验证整轮结束后所有工具卡正确显示（不残留 pending 标记）。

## 明确不做的事（YAGNI）

- 不改 WebSocket Envelope 格式（`agent/core/agent.py` 中的 `Envelope` 类、`_enveloped` 方法、前端 Envelope 解析均不涉及）。
- 不动会话持久化结构（`session_manager.py`、`data/sessions/` 格式不变）。
- 不处理同名并行工具的精确配对——当前 `tool_call_callback` 和 `tool_result_callback` 都只用工具名标识，没有唯一调用 ID。一对一同名工具场景已足够覆盖绝大多数使用场景。
- 不做后端 oracledb/进程树修复（那是另一项已记录的待办）。
- 不重构 `_run_tool_calls` 中的多分支 result 赋值逻辑——仅在统一出口插入一行回调调用。

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| `REPLACE_PENDING_TOOL` 在消息数组中查找时发现 `pending:` 消息已被用户操作或并发移除→找不到索引→静默失败 | `findLastIndex` 返回 -1 时直接 `return state`，不做任何操作；后续 `SET_RESULT` 仍能正确恢复 |
| `tool_result_callback` 中队列消息堆积导致 `done` 消息之前大量 `tool_result` 消息冲刷前端 | 每个工具一条消息，上限由 `max_iterations`（默认 30）控制，可安全处理无队列挤压 |
| `_tool_done` 字段随消息传入 socket 并持久化到会话文件 | `_tool_done` 是前端添加的属性，后端 agent 和 session_manager 不感知该字段。前端 `SET_RESULT` 会移除所有 `pending:` 前缀消息（含 `_tool_done`），不会持久化 |

## 决策总结

| 决策 | 选项 | 选择理由 |
|------|------|----------|
| 去重策略 | 保留现有逻辑 vs 跳过 user 消息 | 保留现有逻辑有 bug；只跳过 user 消息最简洁且可覆盖去重的唯一正确场景 |
| `tool_result_callback` 传什么 | `(name, result_str)` vs `(name, args, result_str)` | 与 `tool_call_callback` 签名对称，前端只需要 name 做匹配和 result 做显示 |
| `_tool_done` vs 移除 `pending:` 前缀再插工具结果 | `_tool_done` 标记 | 保持 `tool_call_id` 前缀不变，`ToolStepCard.tsx` 只需改一行判断条件；SET_RESULT 自然清理 |
| `REPLACE_PENDING_TOOL` 匹配策略 | 从后往前找 vs 从前往后 | 从后往前匹配最后一个（最新）的 pending 项，减少并行同名工具的竞争窗口 |
| `dispatch_tool` 返回哪个结果 | 截断后的完整结果（`truncated`） | 与追加到 `messages` 的内容一致，前端预览和最终持久化一致 |

## 文件改动清单

| 文件 | 改动类型 | 改动说明 |
|------|----------|----------|
| `agent/core/agent.py` | 修改 | 构造函数新增 `tool_result_callback` 参数；`_run_tool_calls` 中 `messages.append` 前调用回调 |
| `backend/api/chat.py` | 修改 | 新增 `tool_result_callback` 定义；`AIAgent` 构造传入 |
| `web/src/types/index.ts` | 修改 | `Message` 加 `_tool_done`；`WsServerMessage` 加 `tool_result` 类型 |
| `web/src/hooks/useChat.ts` | 修改 | 新增 `case "tool_result"` → dispatch `REPLACE_PENDING_TOOL` |
| `web/src/context/AppContext.tsx` | 修改 | 新增 `REPLACE_PENDING_TOOL` action + case；修复 `SET_RESULT` 去重逻辑 |
| `web/src/components/ToolStepCard.tsx` | 修改 | `isPendingTool` 追加 `!result._tool_done` 条件 |
| `tests/test_agent_loop.py` | 修改 | 新增 `tool_result_callback` 相关测试用例 |
| `docs/superpowers/specs/2026-07-22-tool-card-live-status-design.md` | 新增 | 本设计文档 |
