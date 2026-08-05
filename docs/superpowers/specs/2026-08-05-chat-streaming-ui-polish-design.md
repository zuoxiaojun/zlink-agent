# 聊天流式输出界面打磨设计（Chat Streaming UI Polish）

> 纯前端增量优化：修复流式渲染闪烁、新增 Agent 状态条、平滑化自动滚动、视觉细节打磨、清理重复 CSS。后端/agent/WS 协议零改动。

## 1. 目标

提升 ZLink Agent 对话页（`web/src/pages/ChatPage.tsx`）流式输出体验，共 5 项改动：(1) 流式期间不再每 50ms 对整段 `streamingText` 全量重解析 Markdown，改为"已闭合块缓存 + 尾部实时块"切分渲染，消除闪烁与高亮跳动；(2) 用紧凑的 Agent 状态条（阶段图标 + 文字 + 已耗时 + 呼吸动画）替换输入框上方现存的灰色 `progress-text` 小字，并正确展示工具名（当前该信息被 `ChatPage.tsx:174` 的 `includes("执行工具")` 过滤逻辑丢弃）；(3) 自动跟随滚动改为 requestAnimationFrame 节流，消除逐 token 滚动顿挫，smooth 行为仅保留给"回到底部"按钮；(4) 流式光标改为渐隐呼吸效果、微调 `msg-in` 动画、为工具卡 running→完成状态切换补 transition；(5) 合并 `global.css` 中重复定义的 `.tool-step-title-row` / `.tool-step-count`。所有样式沿用 `:root` 现有 CSS 变量体系，不引入新颜色。

## 2. 非目标（Non-Goals）

- **不做暗色模式**，不引入任何新颜色体系或新增 `:root` 变量。
- **不修改后端**：`backend/`、`agent/` 目录零改动，WebSocket 协议（消息 type 集合与字段）不变。
- **不在前端接入 phase**：已核实 `web/src/api/ws.ts`、`web/src/types/index.ts`、`web/src/context/AppContext.tsx` 均无 phase 字段（详见 §3.2）。状态条只基于现有 `progressMessage` / `currentToolName` / `agentRunning` 渲染；若需显示 phase 必须改 WS 协议与后端，属范围外。
- **不引入新依赖**：不采用 `2026-07-22-frontend-chat-rendering-redesign.md` 中 @assistant-ui/streamdown/Tailwind 的整体替换方案（该方案未实施，代码库仍为 ReactMarkdown 自建链路），本次在现有架构内增量优化。
- **不改动非流式渲染路径**：`MessageContent.tsx` 对已完成消息的渲染行为不变；`SET_RESULT` 后最终消息仍走完整 `ReactMarkdown` 解析。
- **不做虚拟滚动 / 长文本整体性能重构**，不做前端测试框架搭建（项目无单测体系，验证以构建 + 人工清单为准，见 §6）。

## 3. 现状与上下文（Context）

### 3.1 流式渲染链路（已核实）

```
useChat.ts:56-60   flush：50ms setTimeout 批量 dispatch APPEND_TOKEN
AppContext.tsx:110-111  streamingText += token
ChatPage.tsx:114-124  把 state.streamingText 组装为 streamingMsg 并入消息分组
ChatPage.tsx:125-136  <ChatMessage streaming={...} />
ChatMessage.tsx:50-71 isStreaming → div.msg-bubble.streaming-text → MessageContent
MessageContent.tsx:22-28  ReactMarkdown + remarkGfm + rehypeHighlight 对整段 content 全量重解析
```

- `MessageContent.tsx:1` 已 `memo()` 包裹，但 props（`content` 字符串）每 50ms 变化，memo 失效，每次 flush 都会对**整段**已累积文本重新解析 + 重新语法高亮，token 一多即闪烁/跳动。
- 每次 flush 也会触发 `ChatPage.tsx:78-88` 的滚动 effect（`setTimeout(0)` 直接设 `scrollTop`），逐帧顿挫。

### 3.2 状态与数据源（已核实，含两处"名存实亡"）

- `progressMessage`：来源两处——`useChat.ts:75`（`tool_call` 消息 → `"🔧 执行工具: ${msg.name}"`）、`useChat.ts:79`（`progress` 消息原文）。展示处 `ChatPage.tsx:174-178` 用 `!state.progressMessage.includes("执行工具")` 把工具执行状态过滤掉，导致工具执行阶段状态区空白。
- `currentToolName`：`AppState` 字段存在（`AppContext.tsx:30/45`，reducer 的 `SET_CURRENT_TOOL` 定义于 60/116-117，`SET_RUNNING`/`SET_RESULT` 会清空它），但**全仓库没有任何 dispatch `SET_CURRENT_TOOL` 的调用方**（grep 确认仅 AppContext 内部 4 处定义）。因此 `currentToolName` 恒为 `""`，`ChatMessage.tsx:111-131` 的 `runningToolCard`（"正在执行…"卡片）是**死代码**。
- **phase 未接入前端**：`web/src/api/ws.ts:23-30` 直接 `JSON.parse` 为 `WsServerMessage`；`types/index.ts:191-209` 的联合类型无 phase 字段；`backend/api/chat.py:305-333` 下发的是扁平 `{type: "token"|"progress"|"tool_call"|...}`。结论：前端当前**不接收、不保存** Envelope 的 phase。故状态条按已批准方案只显示 progress 文本，不显示 phase。
- `agentRunning`：由 `SET_RUNNING` / `SET_RESULT` / `SET_ERROR` / `onClose` 维护，状态条挂载条件可直接复用 `ChatPage.tsx:171` 的判断。

### 3.3 CSS 现状（已核实）

- 变量体系 `global.css:5-47`：`--primary/-bg`、`--success/-bg`、`--danger/-bg`、`--warning/-bg`、`--bg-page/card/hover`、`--text-1..4`、`--border/-light`、`--radius/-sm/-lg`、`--shadow/-sm/-lg`、`--font-mono/sans`。
- 流式光标：`.streaming-text p:last-child::after`（`global.css:784-793`）+ `blink-cursor` 硬切闪烁（795-798）。
- `msg-in` 动画：`.msg-row`（303-308）`animation: msg-in 0.3s ease`，位移 8px（310-313）。
- 工具卡：`.tool-step` 仅 `transition: box-shadow 0.2s`（567）；`.tool-step-icon` 无 transition（614-623）；running 用 `.tool-step-spinner`（636-643），完成后切 `IconCircleCheck`（`ToolStepCard.tsx:154`），背景/颜色瞬间跳变。
- **重复定义确认**：`.tool-step-title-row` + `.tool-step-count` 出现两处——`global.css:599-613`（旧）与 `657-670`（新）。`.tool-step-title-row` 被 `ChatMessage.tsx:122`、`ToolStepCard.tsx:157` 使用；`.tool-step-count` 无任何组件引用（grep 确认仅 CSS 内部）。
- `.progress-text`（1049-1055）仅被 `ChatPage.tsx:175` 使用，替换状态条后将成为孤儿样式。

## 4. 架构设计（Proposed Architecture）

### 4.1 改动 1：流式渲染防闪烁（StreamingMarkdown 切分渲染）

**新组件 `web/src/components/StreamingMarkdown.tsx`**，仅流式期间使用。输入完整 `streamingText`（字符串），内部 `useMemo` 切分为 `closed`（已闭合块）+ `tail`（尾部未闭合块），渲染为两个容器：

```tsx
// 伪代码，实现细节以 plan 为准
function StreamingMarkdown({ text }: { text: string }) {
  const { closed, tail } = useMemo(() => splitStreamingText(text), [text]);
  return (
    <div className="streaming-split">
      <div className="streaming-closed">
        <MemoizedMarkdown text={closed} />
      </div>
      {tail && (
        <div className="streaming-tail">
          <Markdown text={tail} />
        </div>
      )}
    </div>
  );
}

const MemoizedMarkdown = React.memo(
  ({ text }: { text: string }) => <Markdown text={text} />,
);
```

- **`Markdown` 为共享渲染组件**：把 `MessageContent.tsx:10-17` 的 `markdownComponents`（`pre → CodeBlock`、`table → table-wrap`）与插件配置（`remarkGfm` + `rehypeHighlight`）抽成可从 `MessageContent.tsx` 导出的 `Markdown` 组件，`StreamingMarkdown` 复用，保证两个容器（尤其表格/代码块）样式一致，避免配置漂移。
- **`MemoizedMarkdown` 的 memo 机制**：props 只有 `text` 字符串，`React.memo` 浅比较。`closed` 一旦冻结不再变化 → 跳过 re-render → `ReactMarkdown` 不再对该段重解析/重高亮。每 50ms flush 只重解析 **tail**（通常为进行中的单个段落，体量小）。

#### 切分策略 `splitStreamingText(text): { closed, tail }`

1. 规范化：`text.replace(/\r\n/g, "\n")`（后端可能带 `\r\n`）。
2. `segments = text.split("\n\n").filter(s => s.length > 0)`（**过滤空段，含尾随空段**）。过滤后"文本以 `\n\n` 结尾"时最后一段真实内容留在 tail、光标不中断；连续空行（`\n\n\n\n`）与单个空行在 Markdown 中等价，过滤不改变渲染。
3. 从左到右维护**反引号奇偶游标** `openFence`：对每个 segment 统计 `` ` `` 字符数，`openFence = openFence XOR (count % 2)`（三反引号围栏 `` ``` `` 计 3 为奇、行内 `` `code` `` 计 2 为偶，统一用奇偶翻转处理）。
4. segment[i]（`i < n-1`，即非最后一段）判定为**可闭合**，当且仅当同时满足：
   - 处理完该段后 `openFence == false`（反引号已配对，无未闭合代码围栏/行内代码）；
   - 下一段 `segments[i+1]` 不以空白开头（`!/^\s/`，防止"列表项缩进续行"或"缩进代码块"被拆开）；
   - 不是"本段与下一段均为列表项"（`/^\s*(?:[-*+]|\d+\.)\s/`，连续列表项合并为一个块，直到遇到非列表段才整体冻结）。
5. **最后一段永不闭合**：永远留在 tail。因此流式期间 tail 恒非空（文本非空时），光标只挂在 tail 上（见 §4.4 光标作用域）。
6. `closed = segments[0..k].join("\n\n")`，`k` 为第一个不可闭合段的前一个下标（一旦某段不可闭合，其后全部归 tail，closed 是连续前缀）；`tail = segments[k+1..].join("\n\n")`。

设计要点：闭合判定**依赖下一段是否存在及内容**，即"已闭合块一经冻结就不可变"是成立的前提——只有当下一段被证明不可能续写当前段时才冻结当前段（保守边界）。流式结束（`done`）后 `ChatMessage` 的 `isStreaming` 变为 false，最终消息走原有 `MessageContent` 完整解析，`StreamingMarkdown` 卸载，天然兜底。

#### 边界情况表

| 场景 | 行为 |
|------|------|
| 普通多段文本 `"p1\n\np2\n\np3"` | `p1`、`p2` 随各自下一段出现依次冻结；`p3` 保持 tail 实时更新 |
| 代码围栏跨段：`` ``` `` 开头的段落 | 反引号奇偶 → `openFence=true` → 该段及围栏内所有段（即使含 `\n\n`）全部留在 tail，直到闭合 `` ``` `` 到来才整体冻结 |
| 行内代码跨段（奇数 `` ` ``） | 同上，奇偶游标保持 open，后续段并入 tail 直至配对 |
| GFM 表格（表头/分隔行/数据行用单 `\n` 相连） | 整表是**一个** segment（内部无 `\n\n`），原子渲染，绝不会从表格中间切开 |
| 连续列表 `- a\n\n- b\n\n- c` | 三段合并为一个块，全留在 tail；遇到非列表段（或流结束）才整体冻结。代价：长列表期间 tail 较大、每帧重解析该列表——与现状持平，不劣化 |
| 列表项缩进续行 `- item\n\n  continuation` | 下一段以空白开头 → 前段不可闭合，续行与列表项同处 tail，渲染正确 |
| 段落后空行 `"para\n\n"`（尾随空段被过滤） | `para` 成为最后一段 → 留在 tail，光标不中断；下一 token 到达后按新段冻结判断 |
| 空行插在列表项内 `- item1\n\n  continuation` | 尾随空段被过滤，`- item1` 仍是最后一段、不冻结；`  continuation`（空白开头）到达后前段判定不可闭合，整项同处 tail，宽松列表渲染正确 |
| `done` 后 | `StreamingMarkdown` 卸载，`SET_RESULT` 的消息走 `MessageContent` 全量解析，显示与历史行为一致 |

### 4.2 改动 2：Agent 状态条

**新组件 `web/src/components/AgentStatusBar.tsx`**，替换 `ChatPage.tsx:174-178` 的 `progress-text` 区块（`StopButton` 位置保持 `ChatPage.tsx:173` 不变）。直接使用 `useAppState()`（与 `ChatMessage.tsx:109` 先例一致），内部自持已耗时状态：

- **状态优先级**：`state.currentToolName` 非空 → 显示 `调用工具 <工具名>`（工具图标）；否则 `state.progressMessage` 非空 → 原文显示（思考中/压缩中/其他 progress 消息）；否则 → `思考中…`（脉冲点）。
- **工具名数据源（关键决策）**：接线 `SET_CURRENT_TOOL`——在 `useChat.ts:73-77` 的 `case "tool_call"` 中新增一行 `dispatch({ type: "SET_CURRENT_TOOL", toolName: msg.name })`。选择接线而非解析 `"🔧 执行工具: "` 字符串，避免依赖 emoji 前缀的脆弱解析。`SET_RUNNING(true)`/`SET_RESULT`/`SET_ERROR` 已有清空逻辑（`AppContext.tsx:107/169/182`），无需改 reducer。
- **同步删除死代码**：`ChatMessage.tsx:111-131` 的 `runningToolCard`（含 `showRunning` 及 `AssistantGroupContent` 的 `runningToolCard` prop 透传，8-17/95/150 行）当前因 `currentToolName` 恒空而从不出现在 UI。一旦接线 `SET_CURRENT_TOOL`，它会复活并与 `ADD_PENDING_TOOL`（`AppContext.tsx:120-127`）插入的 pending 工具卡**重复渲染**。因此本改动一并删除该死代码——职责由"消息流内 pending 卡（spinner）+ 状态条（工具名）"完整承接。
- **已耗时**：`useEffect` 依赖 `[state.agentRunning]`——`true` 时 `setInterval` 每秒推进（从 `Date.now()` 起始点计算，避免累加漂移），`false` 时清零并清理 interval。耗时以纯文本 `mm:ss` 展示（如 `01:23`），`font-variant-numeric: tabular-nums` 防跳动，不引入 emoji 字符。
- **DOM**：`<div className="agent-status-bar" role="status" aria-live="polite">`，内含 `.agent-status-icon`（有工具名 → Tabler 工具图标如 `IconWrench`，否则三个脉冲点）、`.agent-status-label`（单行省略）、`.agent-status-elapsed`。
- **已知的瞬时显示**：`tool_result` 到达、下一工具或 `done` 到来前的间隙，状态条仍显示最近一次工具名（`currentToolName` 在 `SET_RESULT`/`SET_RUNNING` 时才清空）——这是有意保留的行为（"最后一个工具已执行完，agent 处理中"），不是缺陷；`done` 后随 `agentRunning=false` 整条消失。
- 旧逻辑 `ChatPage.tsx:174` 的 `!state.progressMessage.includes("执行工具")` 过滤随 `progress-text` 区块一并删除；`global.css` 的 `.progress-text`（1049-1055）成为孤儿样式，一并移除（本改动造成的孤儿，符合清理规范）。

### 4.3 改动 3：滚动平滑化

`ChatPage.tsx:78-88` 的 effect 改为 rAF 节流：

```tsx
useEffect(() => {
  if (!userScrolledUp.current || !scrollRef.current) return;
  const el = scrollRef.current;
  const rafId = requestAnimationFrame(() => {
    if (!userScrolledUp.current) el.scrollTop = el.scrollHeight;
  });
  return () => cancelAnimationFrame(rafId);
}, [state.messages, state.streamingText]);
```

- **rAF 合并**：多次 flush 驱动的 state 变化在同一帧内只执行一次滚动，天然以显示刷新率（约 60Hz）节流，消除逐 token `scrollTop` 设置造成的顿挫。effect 在 React commit 之后运行、rAF 回调在绘制前执行，DOM 已就绪。
- **保留 `userScrolledUp` 逻辑**：`ChatPage.tsx:90-96` `handleScroll`（距底 >150px 判定）与 23 行 ref 不动；rAF 回调内二次校验 `userScrolledUp.current`（帧内用户可能滚动）。
- **smooth 仅用户触发**：`ChatPage.tsx:142-155` "回到底部"按钮保留 `behavior: "smooth"` 不变，流式跟随滚动始终用 `scrollTop` 直赋（不累积 smooth 动画队列）。
- effect 依赖数组与现状一致（`[state.messages, state.streamingText]`），不触发 eslint exhaustive-deps。

### 4.4 改动 4：视觉细节（global.css）

全部沿用现有 `:root` 变量（§3.3），不新增变量、不新增内联 style。

1. **流式光标**：删除 `global.css:784-793` 的 `.streaming-text p:last-child::after` 与 795-798 的 `blink-cursor`（硬切闪烁），替换为作用域限定在 tail 容器的呼吸效果：

```css
.streaming-split .streaming-tail p:last-child::after {
  content: '';
  display: inline-block;
  width: 2px;
  height: 1em;
  border-radius: 1px;
  background: var(--primary);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: cursor-breathe 1.2s ease-in-out infinite;
}
@keyframes cursor-breathe {
  0%, 100% { opacity: 0.25; }
  50%      { opacity: 1; box-shadow: 0 0 4px var(--primary); }
}
```

  作用域说明：`streaming-split` 内两个容器（`.streaming-closed` / `.streaming-tail`），若沿用旧选择器会出现双光标。新选择器只匹配 tail 的最后一个 `p`；tail 恒非空（§4.1 第 5 条）保证光标持续存在，无需为 closed 兜底规则。

2. **`msg-in` 微调**：`global.css:307` `animation: msg-in 0.3s ease` → `0.25s ease-out`；`:310-313` 位移 8px → 6px。流式期间最后一条 `.msg-row` 保持挂载（`ChatPage.tsx:126` key 稳定），动画不重复触发，无副作用。

3. **工具卡状态过渡**：`.tool-step`（567 行）`transition: box-shadow 0.2s` → `transition: box-shadow 0.2s, background-color 0.3s ease, border-color 0.3s ease`；`.tool-step-icon`（614-623 定义处）新增 `transition: background-color 0.3s ease, color 0.3s ease`。spinner → `IconCircleCheck` 的元素替换是即时的，但图标容器背景/颜色（`--primary-bg` → `--success-bg`，624-635 行）平滑过渡，消除 running→完成的跳变感。

### 4.5 改动 5：重复 CSS 清理

删除 `global.css:599-613` 的旧 `.tool-step-title-row` / `.tool-step-count`，保留 `657-670` 的更完整定义（gap 8px、font-size 11px、radius 4px）。保留后者的 `.tool-step-count` 不含旧定义的 `flex-shrink: 0`——因该 class 无组件引用（§3.3），无功能影响，按批准决定原样保留后者。

## 5. 文件改动清单（Files To Change）

| 文件 | 类型 | 改动说明 |
|------|------|----------|
| `web/src/components/StreamingMarkdown.tsx` | 新增 | 切分渲染组件：`splitStreamingText` + `MemoizedMarkdown`（closed）+ 实时 tail |
| `web/src/components/AgentStatusBar.tsx` | 新增 | 状态条：图标/文字/耗时/脉冲动画，`useAppState()` + interval |
| `web/src/components/MessageContent.tsx` | 修改 | 导出共享 `Markdown` 渲染组件（plugins + markdownComponents 从现有 10-17/22-28 行抽出）；`MessageContent` 保持 memo 行为不变 |
| `web/src/components/ChatMessage.tsx` | 修改 | `isStreaming` 分支（60-62 行）改渲染 `<StreamingMarkdown text={stringContent} />`（仅当 `typeof content === "string"`）；删除死代码 `runningToolCard`（8-17/95/110-131/150 行相关片段） |
| `web/src/hooks/useChat.ts` | 修改 | `case "tool_call"`（73-77）新增 `dispatch({ type: "SET_CURRENT_TOOL", toolName: msg.name })` |
| `web/src/pages/ChatPage.tsx` | 修改 | 78-88 行滚动 effect 改 rAF；171-180 行 `progress-text` 区块替换为 `<AgentStatusBar />`（删 174 行过滤逻辑） |
| `web/src/styles/global.css` | 修改 | 删 599-613 重复定义；光标改呼吸 + 作用域 `.streaming-tail`；`msg-in` 微调；`.tool-step`/`.tool-step-icon` 加 transition；新增 `.agent-status-bar` 系列与 `cursor-breathe` 动画（放 Streaming indicator 分区）；删除孤儿 `.progress-text` |

**不改动**：`web/src/types/index.ts`（无新 WS 类型）、`web/src/api/ws.ts`、`web/src/context/AppContext.tsx`（`SET_CURRENT_TOOL` action 已存在）、`backend/`、`agent/`。

## 6. 测试策略（Testing Strategy）

项目前端无单测框架（`web/package.json` 仅 build/lint），验证 = 构建 + 静态检查 + 人工清单。

1. **构建与 lint**：`cd web && npm run build`（`tsc -b && vite build`）零错误；`cd web && npm run lint` 零 error/warning。
2. **后端回归冒烟**：`.venv/bin/python -m pytest tests/ -q` 全绿（后端零改动，仅确认无意外牵连）。
3. **人工验证清单**（`./start.sh --dev` 起服务，逐项截图留证）：

| # | 场景 | 预期 |
|---|------|------|
| 1 | 长文本流式输出（多段 + 标题 + 列表） | 已闭合段冻结不闪、不高亮跳动；光标只在正在输入的最后一段 |
| 2 | 代码块流式（` ``` python ... `） | 围栏未闭合前整块在 tail 持续更新；闭合瞬间整体冻结；无中途拆开 |
| 3 | 表格流式 | 整表一次成型，绝无半表渲染；与完成态样式一致 |
| 4 | 连续列表项流式 | 列表项合并渲染，遇到非列表段后整体冻结；无拆项错位 |
| 5 | 工具调用流（如 "查 YonSuite 销售订单"） | 状态条显示"调用工具 query_sale_orders"+ 工具图标 + 秒数递增；pending 卡 spinner 正常；`tool_result` 到达后卡片变绿且背景平滑过渡；整轮结束状态条消失 |
| 6 | 纯思考阶段（无工具） | 状态条显示"思考中…"脉冲点 + 耗时；推理内容流式期间状态条持续 |
| 7 | 自动滚动 | 流式期间平滑跟随（无逐 token 顿挫）；用户上滚后不抢滚；点"回到底部" smooth 回底；新内容不再被劫持 |
| 8 | 中途停止 | Stop 按钮可用；停止后状态条消失、光标消失、最终消息正确落定 |
| 9 | 回归 | 历史会话加载、审批流、WELCOME 消息、斜杠命令、token 用量条、文件上传附件均正常 |
| 10 | 光标视觉 | 呼吸动画（1.2s ease-in-out）平滑，无硬切闪烁；截图确认光标位于最后一段文字后 |

## 7. 风险与缓解（Risks And Mitigations）

| 风险 | 缓解 |
|------|------|
| 切分边界误判导致已冻结块渲染错误（列表缩进续行、空行插入列表项等） | 保守边界规则：仅当下一段被证明不可能续写当前段时才冻结（下一段以空白开头/列表项合并/奇偶游标未闭合均不冻结）；且 `StreamingMarkdown` 仅流式期使用，`done` 后最终消息走 `MessageContent` 全量解析兜底，错误最长只存在到流结束 |
| 双容器引入双光标或光标缺失 | 光标选择器限定 `.streaming-split .streaming-tail p:last-child::after`，且 tail 恒非空（最后一段永不闭合）保证单光标；实现后按 §6 清单 #10 截图核验 |
| 接线 `SET_CURRENT_TOOL` 后 ChatMessage 运行中卡片复活导致与 pending 卡重复 | 本改动同步删除死代码 `runningToolCard`（§4.2），职责由 pending 卡 + 状态条承接；删除前该代码本就不可达，删除无功能回归面 |
| rAF 滚动时序（绘制前执行时 DOM 未含最新内容） | effect 在 React commit 后运行，rAF 回调同帧绘制前执行时 DOM 已就绪；即便个别帧漏滚，下一 flush 的 effect 立即补偿；`userScrolledUp` 在 rAF 内二次校验 |
| 状态条 interval 泄漏 / 不归零 | `useEffect` 依赖 `[state.agentRunning]` 的 cleanup 负责清除；`false` 时清零 elapsed；`SET_RESULT`/`SET_ERROR`/WS 关闭均已重置 `agentRunning` |
| `Markdown` 配置抽离导致表格/代码块样式漂移 | 单一导出点（`MessageContent.tsx` 导出 `Markdown`），`StreamingMarkdown` 与 `MessageContent` 共用同一实例配置，杜绝两份配置；清单 #3 核验表格一致性 |

## 8. 决策总结（Decision Summary）

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 防闪烁方案 | 自建 `StreamingMarkdown` 切分（已批准方案 1） | 不动后端协议，不引入新依赖，ReactMarkdown 生态复用 |
| 切分粒度与闭合规则 | `\n\n` 段落 + 反引号奇偶游标 + 缩进/列表续行合并；**最后一段永不闭合**；闭合判定依赖下一段 | 冻结块不可变是 memo 正确性的前提；保守边界 + done 全量兜底 |
| closed 块缓存方式 | 整段 closed 文本 join 后由单个 `React.memo` 组件渲染 | 单实例 props 浅比较即可跳过重解析，无需逐块管理 |
| 光标归属 | 仅 `.streaming-tail`，呼吸动画 | tail 恒非空 ⇒ 光标不缺失；双容器杜绝双光标 |
| 工具名数据源 | 接线 `SET_CURRENT_TOOL`（`useChat.ts` 一行 dispatch） | 比解析 `"🔧 执行工具: "` 字符串健壮；`SET_RUNNING`/`SET_RESULT` 已有清空逻辑 |
| ChatMessage 运行中卡片 | 删除死代码 `runningToolCard` | 接线后必与 pending 卡重复；该代码当前不可达，删除零风险 |
| phase 显示 | 不显示（前端未接入，改协议超范围） | 已核实 ws.ts / types.ts / AppContext 无 phase 字段 |
| 滚动节流 | `requestAnimationFrame` 替代 `setTimeout(0)`；smooth 仅"回到底部"按钮 | rAF 以帧为节流粒度；smooth 流式期间堆积会产生动画队列 |
| 视觉细节 | 光标呼吸、`msg-in` 0.25s ease-out / 6px、工具卡背景/图标 transition | 全部复用 `:root` 变量，不引新色 |
| CSS 去重 | 保 `global.css:657-670` 后者，删 `599-613` 前者 | 已批准决定；`.tool-step-count` 无组件引用，无功能影响 |
| 验证 | `npm run build` + `npm run lint` + 后端 pytest 冒烟 + 10 项人工清单截图 | 项目无前端测试框架，人工清单为唯一 UI 正确性依据 |
