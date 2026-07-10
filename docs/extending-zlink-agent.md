# 扩展 ZLink Agent —— 写你的第一个 Extension

最后更新：2026-06-02

## 一句话

> ZLink Agent 的 Extension 系统借鉴自 Pi（earendil-works/pi）：写一个 Python 类，重写 `on_xxx` 方法，调用 `register_extensions([...])` 即可插入到 agent loop 的任何位置。

## 5 行最小例子

```python
from agent.events import Extension
from agent.events.extensions import register_extensions

class HelloExtension(Extension):
    name = "hello"
    enabled = True
    def on_session_start(self, event):
        print(f"Session starting with {len(event.history)} prior messages")

register_extensions([HelloExtension()])
```

把这个文件放到 `agent/extensions/my_extension.py`，在 `agent/extensions/__init__.py` 导入即可。

## Extension 类长什么样

```python
class Extension:
    name: str = "unnamed"          # 给 log 用的标识
    enabled: bool = True            # False 时 runner 跳过

    def on_event(self, event: Event) -> None:
        """通吃所有事件。typed handler 之后才跑。"""
        ...
```

子类按事件名实现 `on_<event_type>` 方法。**实现哪个就跑哪个**，不实现就忽略。

| 事件 type | handler 名 | 触发时机 | 可取消？ | 可改写？ |
|---|---|---|---|---|
| `session_start` | `on_session_start` | 一次 agent 调用的开始 | ❌ | — |
| `session_end` | `on_session_end` | 一次 agent 调用的结束 | ❌ | — |
| `user_message` | `on_user_message` | 用户消息到达（处理前） | ✅ | `event.content` |
| `before_llm_call` | `on_before_llm_call` | LLM 调用前 | ✅ | `event.messages`, `event.api_kwargs` |
| `after_llm_call` | `on_after_llm_call` | LLM 返回后 | ❌ | — |
| `before_tool_call` | `on_before_tool_call` | 工具 dispatch 前 | ✅ | `event.args` |
| `after_tool_call` | `on_after_tool_call` | 工具返回后 | ❌ | `event.result` |
| `session_before_compact` | `on_session_before_compact` | 压缩 LLM 调用前 | ❌ | `event.extra: list[str]` |

**字段名**严格对应 `agent/events/types.py` 里的 dataclass 字段。改前先 grep 一下。

## 取消（cancel）机制

3 个事件可取消（`event.cancel(reason="...")`）：

```python
def on_before_tool_call(self, event):
    if event.tool_name == "dangerous_tool":
        event.cancel(reason="forbidden by my policy")
```

agent loop 在 `publish()` 返回后检查 `event.cancelled`。True 就：
- `BeforeLLMCallEvent` → 跳过 LLM 调用，返回 `error="LLM call cancelled by extension: <reason>"`
- `BeforeToolCallEvent` → 不执行工具，把 `{"success": False, "error": "Blocked by extension: <reason>"}` 当作工具结果写回消息列表
- `UserMessageEvent` → 直接拒绝，返回 `error="User message rejected: <reason>"`

> 取消 = 阻断主流程。**慎用**——读者是 LLM，它会看到 "Blocked by extension: ..." 当作反馈，可能重试或换方案。

## 改写（mutate）机制

事件对象的字段可以在 handler 里改：

```python
def on_before_llm_call(self, event):
    # 追加一条 system 消息（伪装的系统提示）
    event.messages.insert(0, {
        "role": "system",
        "content": "当前用户是 YonSuite 财务，请优先用 YonSuite 业务工具。",
    })

def on_after_tool_call(self, event):
    # 把工具结果裁短
    if len(event.result) > 1000:
        event.result = event.result[:1000] + "…(已裁短)"

def on_user_message(self, event):
    # PII 脱敏
    import re
    event.content = re.sub(r"\d{17,18}", "[身份证已隐去]", event.content)
```

agent loop 读 `event.xxx` 时拿到的就是改后的值。

## 实战例子

### 例 1：调用审计（log 所有工具调用）

```python
import logging
from agent.events import Extension, BeforeToolCallEvent, AfterToolCallEvent

audit_log = logging.getLogger("zlink-agent.audit")

class AuditExtension(Extension):
    name = "audit"
    enabled = True

    def on_before_tool_call(self, event: BeforeToolCallEvent):
        audit_log.info("tool_call", extra={
            "tool": event.tool_name,
            "args": event.args,
        })

    def on_after_tool_call(self, event: AfterToolCallEvent):
        audit_log.info("tool_result", extra={
            "tool": event.tool_name,
            "result_length": len(event.result),
        })
```

### 例 2：PII 脱敏

```python
import re
from agent.events import Extension, UserMessageEvent

class PIIScrubber(Extension):
    name = "pii-scrubber"
    enabled = True

    PHONE_RE = re.compile(r"1[3-9]\d{9}")
    ID_RE = re.compile(r"\d{17}[\dXx]")

    def on_user_message(self, event: UserMessageEvent):
        if isinstance(event.content, str):
            text = event.content
            text = self.PHONE_RE.sub("[手机号已隐去]", text)
            text = self.ID_RE.sub("[身份证已隐去]", text)
            event.content = text
```

### 例 3：危险操作阻断（替换/补充 security_hooks）

```python
from agent.events import Extension, BeforeToolCallEvent

class DangerousOpBlocker(Extension):
    name = "dangerous-blocker"
    enabled = True

    def on_before_tool_call(self, event: BeforeToolCallEvent):
        # write_file 不允许写 /etc /System /Library
        if event.tool_name in ("write_file", "patch"):
            path = event.args.get("path", "")
            for denied in ("/etc/", "/System/", "/Library/", "~/.ssh/"):
                if denied in path:
                    event.cancel(reason=f"拒绝写入 {denied}")
                    return
```

> M5 期间 `security_hooks.py` 的老钩子和事件钩子**并存**。M5 之后会清理，建议新代码走事件钩子。

### 例 4：压缩时附加项目上下文

```python
from agent.events import Extension, SessionBeforeCompactEvent

class ProjectContextExtension(Extension):
    name = "project-context"
    enabled = True

    def on_session_before_compact(self, event: SessionBeforeCompactEvent):
        # 从旧消息里抽 YonSuite 单据 ID
        import re
        ids = set()
        for msg in event.old_messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                ids.update(re.findall(r"\b[A-Z]{2}\d{10,}\b", content))
        if ids:
            event.extra.append(
                "## 引用过的 YonSuite 单据\n" +
                "\n".join(f"- {i}" for i in sorted(ids))
            )
```

`event.extra` 是 `list[str]`，会按顺序拼到 final summary 后面。

## 注册 Extension

### 一次性注册（测试/快速实验）

```python
from agent.events.extensions import register_extensions, shutdown_all_extensions

register_extensions([MyExt()])
# ... 跑 agent loop ...
shutdown_all_extensions()  # 测试结束清理
```

### 进程级注册（生产）

在 `agent/extensions/__init__.py` 末尾：

```python
from agent.extensions.audit import AuditExtension
from agent.extensions.pii_scrubber import PIIScrubber

# M5: 显式列出，避免 import 副作用。
# 改 enabled = False 可以禁掉某个 extension。
_always_on = [
    AuditExtension(),
    PIIScrubber(),
]

from agent.events.extensions import register_extensions
register_extensions(_always_on)
```

在 `agent/agent.py` 顶部 import 这个模块即可（已经 import `agent.tools`，多加一个无害）。

> **M5+ 已上线**：内置的 extension（`log-everything` / `security-event`）走"扩展管理"页面（侧边栏 → 设置 → 扩展管理），用户可运行时停用 / 启用，状态持久化到 `config.json`。新增的扩展如果用 `_built_in_classes()` 列表注册，**自动出现在 UI** 上；否则要进 settings 列表需要在 `backend/api/extensions_api.py:_KIND_BY_NAME` 里加一项（name → 描述 + kind）。
>
> 想把内置 extension 加入 `_built_in_classes` 之外的"自定义路径"？用 `register_extensions([...])` 在自己的脚本里调，会进 `_all_extensions` 全局表，UI 也能看到 —— 但不会持久化，进程重启就消失。

## 事件流时序

```text
run_conversation() 调用一次发出:
    session_start   ← on_session_start
    user_message    ← on_user_message (可改 event.content / cancel)
    ──── 循环开始 ────
    before_llm_call  ← on_before_llm_call (可改 event.messages / cancel)
    LLM 调用
    after_llm_call   ← on_after_llm_call (只读)
    ── 如果有 tool_calls ──
    before_tool_call (每个工具)  ← on_before_tool_call (可改 event.args / cancel)
    工具 dispatch
    after_tool_call (每个工具)   ← on_after_tool_call (可改 event.result)
    ──── 下一轮或退出循环 ────
    session_end     ← on_session_end
```

`session_before_compact` 在**压缩 LLM 调用前**单独触发，不在主循环时序里。

## 限制 / 注意事项

1. **同步执行**：handler 阻塞主循环。**不要**做 I/O 重活——自己开 `threading.Thread(...).start()`。
2. **错误吞掉**：handler 抛异常会被 bus 捕获并 log（`logger.exception`），不会打断 agent。但要自己保证关键路径的错误处理。
3. **字段名严格匹配**：`on_before_tool_call` 收到的 `event.args` 是 dict，**不要假设 args 一定有 `path` 字段**（不同工具的 args 不同）。先 `event.args.get(...)`。
4. **不要**修改 `event.messages` 的内部 list 元素（list 元素是共享引用）——要改就 `event.messages = [new_list]`。
5. **cancel 不级联**：`BeforeToolCallEvent` cancel 只阻止这一个工具，**不会**让 `AfterToolCallEvent` 跳过发（agent 不发 after 事件，直接走 cancel 路径）。

## 调试

最快方法：写一个全捕获的 `LogEverythingExtension`：

```python
from agent.events import Extension, Event

class LogEverything(Extension):
    name = "log-everything"
    enabled = True
    def __init__(self):
        super().__init__()
        self.events = []
    def on_event(self, event: Event):
        self.events.append(event.type)
```

跑一个对话，事后 `print(log_ext.events)` 看到全部事件顺序。

## 完整 API 参考

- 事件类：`agent/events/types.py` —— 8 个 class
- Event 基类：`agent/events/bus.py:Event` —— `cancel(reason)` / `cancelled` / `cancel_reason`
- EventBus：`agent.events.event_bus` —— 全局单例；高级用法可以直接 `event_bus.publish(...)` / `event_bus.subscribe(...)`，跳过 ExtensionRunner
- Extension 基类：`agent/events/extensions.py:Extension`
- ExtensionRunner：`agent/events/extensions.py:ExtensionRunner`
- `register_extensions(extensions, bus=None) -> list[ExtensionRunner]`
- `shutdown_all_extensions()`

> **M5 局限**：目前 extension 注册是进程级、源码改的。配置文件开关 / 动态启停是 M5+ 工作。
