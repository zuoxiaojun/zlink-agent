# Slash Command Popup — Design Spec

## 1. 概述

在 ChatInput 文本框中增加斜杠命令（`/`）自动补全弹窗，让用户无需记忆命令名称即可发现和使用斜杠命令。后端斜杠命令系统已完整实现（`agent/slash_commands.py` + `chat.py` WebSocket 拦截），只需前端补全弹窗 + 后端暴露命令列表 API。

## 2. 架构

```
Frontend                          Backend
─────────────────                ─────────────
ChatInput                         GET /api/slash-commands
  └─ SlashCommandPopup ──fetch──→  └─ slash_commands.list_commands()
       │
       ├─ 输入 / → 弹出列表
       ├─ 键盘 ↑↓ 导航
       ├─ Enter 选择 → 填入文本框
       └─ Esc 关闭
                                     chat.py WebSocket
                                       └─ 已有 /cmd 拦截逻辑（不变）
```

**零改动文件：**
- `agent/slash_commands.py` — 不动
- `backend/api/chat.py` — 不动
- `agent/` 目录 — 不动

## 3. 后端 API

### 新增 `GET /api/slash-commands`

**位置：** `backend/api/tools_api.py`（已有 tools 相关路由，语义相近）

**响应格式：**
```json
{
  "commands": [
    { "name": "help", "description": "显示所有可用命令", "usage": "/help" },
    { "name": "model", "description": "切换 LLM 模型", "usage": "/model <模型名>" },
    { "name": "compact", "description": "手动触发上下文压缩", "usage": "/compact" },
    { "name": "clear", "description": "清空当前会话开始新对话", "usage": "/clear" },
    { "name": "login", "description": "显示 API Key 配置指引", "usage": "/login [供应商名]" },
    { "name": "cost", "description": "显示当前会话 Token 用量", "usage": "/cost" }
  ]
}
```

实现：从 `agent.slash_commands.list_commands()` 获取数据，序列化为 JSON。

## 4. 前端组件

### SlashCommandPopup

**文件：** `web/src/components/SlashCommandPopup.tsx`

**Props:**
```typescript
interface SlashCommandPopupProps {
  text: string;              // 当前文本框内容
  cursorPos: number;         // 光标位置
  onSelect: (command: string) => void;  // 选择回调
  onClose: () => void;
}
```

**定位：** 浮动在 textarea 上方，使用 `position: absolute` 相对于 `.chat-input-wrapper`。

**行为：**
1. 当 textarea 内容末尾刚输入 `/` 时显示（紧跟前一个空白或行首）
2. 继续输入字母 → 过滤命令列表（匹配 name 前缀）
3. ↑↓ 键导航，Enter 确认，Esc 取消
4. 点击命令项同样触发选择
5. 失焦（blur）时自动关闭

### ChatInput 集成

`ChatInput.tsx` 变更：
- 引入 `SlashCommandPopup`
- 在 `onChange` 中检测是否处于斜杠输入状态
- 传递 `text` 和 `cursorPos` 给弹窗
- 在 `onSelect` 回调中修改 textarea 内容

**检测逻辑：**
```typescript
// 获取光标之前最后一个单词
const beforeCursor = text.slice(0, cursorPos);
const lastWord = beforeCursor.split(/[\s\n]/).pop() || "";
const isSlashTyping = lastWord.startsWith("/") && lastWord.length > 0;
```

### CSS 样式

```css
.slash-popup {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  margin-bottom: 4px;
  background: var(--bg-secondary, #1a1a2e);
  border: 1px solid var(--border-color, #2d2d4a);
  border-radius: 8px;
  max-height: 240px;
  overflow-y: auto;
  box-shadow: 0 -4px 12px rgba(0,0,0,0.3);
  z-index: 100;
}
.slash-popup-item {
  padding: 8px 12px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.slash-popup-item:hover,
.slash-popup-item.active {
  background: var(--bg-hover, #2d2d4a);
}
.slash-popup-name {
  font-weight: 600;
  font-family: var(--font-mono, monospace);
}
.slash-popup-desc {
  font-size: 0.85em;
  opacity: 0.7;
}
```

## 5. 测试

不需要额外测试：
- 后端 `list_commands()` 已在 `agent/slash_commands.py` 中由 `@register_command` 装饰器保证正确
- 前端是纯展示组件，无业务逻辑

## 6. 边界情况

| 场景 | 行为 |
|------|------|
| 输入 `/` 后没有更多字符 | 显示全部命令列表 |
| 输入 `/mo` | 过滤出 `/model` |
| 输入 `/unknown` | 显示"无匹配命令"|
| 光标不在行首的 `/` | 不触发弹窗（仅在 `/` 前面是空白或行首时）|
| 已有 `/model ` 再输入 `/` | 另起一行后的 `/` 或当前行新的 `/` 会触发 |
| 文本框有多行 | 弹窗位置跟随光标所在行 |
| 命令数量超过 6 个 | 弹窗自动滚动 |
