# 会话交接 — 2026-07-22

## 当前状态

- **分支**: `main`，已推送 atomgit
- **HEAD**: `3fe7cd7 fix: increase stream preview truncation to 500 chars, remove code block collapse`
- **测试**: `pytest tests/ -q` → 373 passed
- **前端**: `npm run build && npm run lint` → 零错误
- **dev**: 已启动，`http://localhost:8089` 后端 + `http://localhost:8088` 前端

## 改动摘要（15 commits）

### 核心功能

1. **修复 SET_RESULT 去重误杀 bug**（`fb87164`）
   - 根因：`AppContext.tsx` reducer 用 `role + content` 去重，第二轮携带 `tool_calls` 的空内容 assistant 消息被丢弃 → 工具卡名显示 "tool"
   - 修法：`SET_RESULT` 改为只跳过 `user` 消息，其余原样追加

2. **渐进式 tool_result**（`56fdd79` + `fb87164`）
   - `agent.py` 新增 `tool_result_callback`（dispatch 后调用，向后兼容 None）
   - `chat.py` 接线推 WS `{"type":"tool_result", name, result}`
   - 前端 `REPLACE_PENDING_TOOL` reducer + `_tool_done` 标记 + `ToolStepCard` 条件判断
   - 新增 2 个 pytest 用例

3. **工具卡折叠预览移除**（`c3243c3`）
   - 折叠状态下不再显示结果预览，用户点击展开后才看

4. **代码块不撑宽**（`dbb49f1` → `de789de` 多次迭代）
   - 结论：`.code-block pre`/`.msg-bubble pre` 统一 `white-space: pre-wrap; word-break: break-all`
   - `.msg-body` 加 `overflow: hidden` 强制 flex 子项收缩
   - `.code-block` 加 `max-width: 100%; min-width: 0; overflow-x: auto`

5. **流式工具结果截断 200→500 字符**（`3fe7cd7`）
   - `agent.py:686` 和 `tool_dispatcher.py:30` 的 `preview_length` 从 200 改为 500

6. **工具卡展开结果区美化**（`66d0ea0`）
   - 白底、左侧红色 accent 竖线、标题加粗

### 文档

- `docs/superpowers/specs/2026-07-22-tool-card-live-status-design.md`
- `docs/superpowers/plans/2026-07-22-tool-card-live-status.md`

## 改动文件

| 文件 | 改动 |
|------|------|
| `agent/core/agent.py` | `tool_result_callback` 参数 + 调用；截断 200→500 |
| `agent/core/tool_dispatcher.py` | 默认 `preview_length` 200→500 |
| `backend/api/chat.py` | `tool_result_callback` 接线 |
| `web/src/types/index.ts` | `Message._tool_done?`；`WsServerMessage` 加 `tool_result` |
| `web/src/context/AppContext.tsx` | 修 `SET_RESULT` 去重 + `REPLACE_PENDING_TOOL` |
| `web/src/hooks/useChat.ts` | `case "tool_result"` |
| `web/src/components/ToolStepCard.tsx` | `isPendingTool` 加 `&& !result._tool_done`；移除折叠预览 |
| `web/src/components/CodeBlock.tsx` | 还原原样（无折叠） |
| `web/src/styles/global.css` | 代码块换行约束、消息气泡溢出约束、工具卡展开区美化 |

## 当前已知问题

- 无

## 下一步（按优先级）

1. 无待办——本次会话已交付全部改动。如需开启新功能，建议先 `Read HANDOVER.md` + `git log --oneline -5`。

## 启动提示词

```bash
Read HANDOVER.md
git log --oneline -5
./start.sh --dev
pytest tests/ -q
```