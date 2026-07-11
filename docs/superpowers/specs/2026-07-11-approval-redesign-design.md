# 审批机制重构设计文档

> 2026-07-11 — 从 LLM 驱动的审批改为 Agent 线程阻塞式审批

---

## 1. 背景

### 1.1 当前方案的问题

现有审批机制使用 LLM 驱动的模式：

```
用户发消息 → LLM → 调工具 → approval_hook 阻断 → 返回错误给 LLM
→ LLM 问用户 → 用户回复 → LLM 调 confirm_tool_execution
→ LLM 重试原工具 → 执行
```

这个方案有三个严重问题：

1. **双重执行**：confirm_tool_execution 返回成功后 LLM 重试原工具，但由于阻断消息仍在历史中，LLM 可能再次触发审批循环
2. **缓存 key 不匹配**：LLM 重试时参数格式可能变化（额外添加 description 字段等），导致审批缓存无法命中
3. **用户体验差**：需要 LLM 理解审批流程并正确调度，LLM 的行为不可控

### 1.2 Hermes Agent 的参考方案

Hermes Agent 使用线程阻塞模式：

```
调工具 → approval_hook 阻断 → Agent 线程阻塞(threading.Event.wait())
→ 发审批请求到前端 → 用户响应 → 线程恢复 → 工具执行一次
```

优势：一次审批一次执行，LLM 完全不参与审批流程。

---

## 2. 设计方案

### 2.1 核心变更

将审批控制点从 `approval_hook`（BeforeHook）移到 `_run_tool_calls`（Agent 循环层）。

| 组件 | 变更 |
|------|------|
| `agent/tools/security_hooks.py` | `approval_hook` 不再返回 block 消息，改为抛出 `ApprovalBlockedError` |
| `agent/core/agent.py` | `_run_tool_calls` 捕获异常，通过回调通知外部，阻塞等待审批结果 |
| `backend/api/chat.py` | WebSocket 处理 `approval_response` 消息类型，唤醒阻塞的 Agent 线程 |
| `web/src/types/index.ts` | 添加 `approval_request` / `approval_response` WebSocket 消息类型 |
| `web/src/pages/ChatPage.tsx` | 处理 `approval_request` 消息，显示审批对话框 |
| `web/src/components/` | 审批确认对话框组件 |

### 2.2 新增类型

**Python: `ApprovalBlockedError`**（在 `agent/tools/security_hooks.py`）：

```python
class ApprovalBlockedError(Exception):
    """Raised by approval_hook when a high-risk tool is blocked in approve mode."""
    def __init__(self, tool_name: str, args: dict, reason: str):
        self.tool_name = tool_name
        self.args = args
        self.reason = reason
```

**Python: `ApprovalRequest`**（dataclass，在 `agent/core/agent.py`）：

```python
@dataclass
class ApprovalRequest:
    tool_name: str
    args: dict
    reason: str
    # 用于阻塞 Agent 线程的同步原语
    event: threading.Event
    result: str | None  # "approved" | "denied"
```

**TypeScript: WebSocket 消息类型更新**（在 `web/src/types/index.ts`）：

```typescript
// 后端 → 前端：请求审批
{ type: "approval_request"; payload: { tool_name: string; args: object; reason: string } }

// 前端 → 后端：审批结果  
{ type: "approval_response"; payload: { approved: boolean } }
```

### 2.3 数据流

```
┌─────────────────────────────────────────────────────────────────────┐
│ Agent 线程 (run_in_executor)                                        │
│                                                                     │
│  _run_tool_calls:                                                   │
│    dispatch_tool("terminal", {command: "rm file"})                  │
│      → approval_hook 检测到 high risk + approve mode                │
│      → 抛出 ApprovalBlockedError                                    │
│                                                                     │
│    捕获异常:                                                        │
│      1. 创建 ApprovalRequest(event=threading.Event())               │
│      2. 通过 approval_callback(request) 发出审批请求                 │
│      3. event.wait(timeout=120)  // 阻塞等待用户响应                │
│      4. 如果 result == "approved":                                  │
│          重新 dispatch_tool (不走 hook)                              │
│        如果 result == "denied" ∨ timeout:                           │
│          返回拒绝消息                                                │
│                                                                     │
└──────────────────────┬──────────────────────────────────────────────┘
                       │ approval_callback
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│ WebSocket 协程                                                      │
│                                                                     │
│  收到 approval_request:                                             │
│    → send_json({type: "approval_request", payload: {...}})          │
│                                                                     │
│  收到前端 approval_response:                                        │
│    → 找到对应的 PendingApproval                                     │
│    → 设置 event + result                                            │
│    → Agent 线程恢复                                                  │
│                                                                     │
└──────────────────────┬──────────────────────────────────────────────┘
                       │ WebSocket
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 前端 React                                                          │
│                                                                     │
│  收到 approval_request:                                             │
│    → 在聊天界面显示审批卡片（工具名 + 参数 + 批准/拒绝按钮）        │
│                                                                     │
│  用户点「批准」:                                                     │
│    → send({type: "approval_response", payload: {approved: true}})   │
│    → 按钮隐藏，显示"已批准"                                          │
│                                                                     │
│  用户点「拒绝」:                                                     │
│    → send({type: "approval_response", payload: {approved: false}})   │
│    → 按钮隐藏，显示"已拒绝"                                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.4 Agent 线程阻塞机制

关键设计点：

- **线程安全**：ApprovalRequest.event 是 `threading.Event`，Agent 线程 wait()，WebSocket 协程 set()
- **超时**：event.wait(timeout=120) 120 秒超时后视为拒绝
- **清理**：会话结束时调用 clear_pending_approval() 唤醒所有阻塞线程
- **单次执行**：审批通过后绕过 hook 链直接调用 entry.handler()，确保只执行一次
- **并发安全**：同一时间只有一个待审批请求（新的审批会覆盖旧的）

### 2.5 审批请求管理

在 `chat.py` 中管理待处理的审批：

```python
# 当前待处理的审批请求（全局）
_pending_approval: ApprovalRequest | None = None
_pending_lock = threading.Lock()


def set_pending_approval(req: ApprovalRequest) -> None:
    with _pending_lock:
        global _pending_approval
        _pending_approval = req


def resolve_pending_approval(approved: bool) -> bool:
    """返回是否有待处理的审批被解决"""
    with _pending_lock:
        req = _pending_approval
        _pending_approval = None
    if req is None:
        return False
    req.result = "approved" if approved else "denied"
    req.event.set()
    return True
```

### 2.6 前端审批卡片

审批卡片不是普通的消息气泡，而是独立于消息列表的 UI 元素：

```
┌──────────────────────────────────────────────┐
│ ⚠️ 需要你的确认                                │
│                                              │
│ 工具: terminal                                │
│ 参数: {"command": "rm /tmp/test.sql"}         │
│                                              │
│ [✅ 批准]  [❌ 拒绝]                           │
└──────────────────────────────────────────────┘
```

设计要点：
- 固定在聊天输入框上方，不随消息滚动
- 点击后立即消失，不可重复点击
- Agent 空闲时（无待审批）隐藏
- 支持键盘快捷操作（Enter 批准，Esc 拒绝）

### 2.7 清理逻辑

当 WebSocket 断开或会话结束时，必须清理：

```python
# 会话结束清理
resolve_pending_approval(False)  # 唤醒并拒绝

# WebSocket 断开清理
@websocket.on_disconnect
def cleanup():
    resolve_pending_approval(False)
    clear_pending_approval()
```

### 2.8 安全考虑

- 超时机制：120 秒无响应自动拒绝
- 断线保护：WebSocket 断开时自动拒绝所有待审批
- 幂等性：拒绝后不能再次批准
- 审计日志：所有审批操作记录到 audit-log

---

## 3. 涉及文件

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `agent/tools/security_hooks.py` | 改 | 添加 `ApprovalBlockedError`，`approval_hook` 改为抛异常 |
| `agent/core/agent.py` | 改 | `_run_tool_calls` 添加审批捕获逻辑，添加 `approval_callback` 参数 |
| `backend/api/chat.py` | 改 | WebSocket 处理 `approval_response`，管理 `_pending_approval` |
| `web/src/types/index.ts` | 改 | 添加 `approval_request` / `approval_response` 消息类型 |
| `web/src/pages/ChatPage.tsx` | 改 | 处理审批消息，显示审批卡片 |
| `web/src/styles/global.css` | 改 | 审批卡片样式 |
| `agent/tools/confirm_tool.py` | 删 | 不再需要，LLM 不参与审批 |
| `agent/core/message_builder.py` | 改 | 移除审批相关的系统提示词 section |
| `tests/` | 改 | 更新 approval 测试 |

---

## 4. 实施顺序

```
1. security_hooks.py — 添加 ApprovalBlockedError + 改 approval_hook 抛异常
2. agent.py — _run_tool_calls 添加审批捕获 + approval_callback
3. chat.py — WebSocket 处理 approval_response + _pending_approval 管理
4. 前端 — 类型 + 审批卡片 + ChatPage 处理
5. 测试 — 单元测试 + 集成测试
6. 清理 — 删除 confirm_tool.py + message_builder 清理
```
