# 聊天流式输出界面打磨 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-subagent-driven-development (recommended) or superpowers-executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复流式渲染每 50ms 全量重解析 Markdown 造成的闪烁，用 Agent 状态条替换 `progress-text` 小字，rAF 节流自动滚动，打磨光标/消息入场/工具卡过渡视觉细节，并清理 `global.css` 重复定义。

**Architecture:** 纯前端增量优化，后端/agent/WS 协议零改动。新增 `StreamingMarkdown` 组件把流式文本切分为"已闭合块（memo 冻结）+ 尾部实时块（每帧重解析）"；新增 `AgentStatusBar` 状态条（优先级：工具名 > progress 文本 > 思考中），并在 `useChat.ts` 接线 `SET_CURRENT_TOOL`（同步删除 `ChatMessage.tsx` 中会因此复活的死代码 `runningToolCard`）；自动滚动改 `requestAnimationFrame` 节流（并移除 `.chat-messages` 的 `scroll-behavior: smooth`，否则直赋仍触发平滑动画）；CSS 打磨全部复用 `:root` 现有变量，不新增颜色/变量/依赖。

**Tech Stack:** React 19 / TypeScript ~6.0 / Vite 8 / ReactMarkdown 10 + remark-gfm + rehype-highlight / @tabler/icons-react 3.44 / Node 26（原生 TS 执行，用于切分算法验证脚本）

---

## 全局约束（Global Constraints）

1. **后端零改动**：`backend/`、`agent/` 目录不得修改；WebSocket 消息 type 集合与字段（`web/src/types/index.ts:191-209`）不变；`web/src/api/ws.ts`、`web/src/context/AppContext.tsx` 不改（`SET_CURRENT_TOOL` action 已存在于 `AppContext.tsx:60/116-117`）。
2. **不新增 `:root` CSS 变量、不引入新颜色、不引入新依赖**；所有新样式只用 §3.3 已列出的现有变量。
3. **不改动非流式渲染路径**：`MessageContent` 对已完成消息/数组 content 的渲染行为不变；`SET_RESULT` 后最终消息仍走完整 `ReactMarkdown` 解析。
4. **前端验证**：`cd web && npm run build`（`tsc -b && vite build`）零错误；`cd web && npm run lint` 零 error/warning。`tsconfig.app.json` 已开 `noUnusedLocals`/`noUnusedParameters` —— 死代码/未用导入删除不彻底会直接构建失败。
5. **后端回归**：`.venv/bin/python -m pytest tests/ -q` 全绿（仅确认无意外牵连，不改任何后端文件）。
6. **提交约定**：每个 Task 一个 commit，message 用英文、遵循仓库 conventional commits 风格（`feat:`/`refactor:`/`style:`/`perf:`/`docs:`）；本计划文档所在 `docs/` 在 `.gitignore`，提交时需 `git add -f`（与 `8ccb72a` 提交 spec 的仓库惯例一致）。
7. **代码注释风格**：与仓库一致，JSX/TS 内中文注释。
8. **仅本计划新增文件**：`web/src/components/StreamingMarkdown.tsx`、`web/src/components/AgentStatusBar.tsx`、`web/src/utils/streamingSplit.ts`、`web/scripts/verify-streaming-split.ts`（切分算法独立成纯 TS 文件以便 Node 原生执行验证——spec §4.1 伪代码注明"实现细节以 plan 为准"，接口 `splitStreamingText(text): {closed, tail}` 与 spec 完全一致）。

---

## 任务依赖图

| Task | 内容 | 依赖 | 验证 |
|------|------|------|------|
| 1 | `MessageContent.tsx` 导出共享 memoized `Markdown` | 无 | build + lint |
| 2 | `utils/streamingSplit.ts` 切分算法 + 验证脚本 | 无 | node 验证脚本 16 断言全 PASS |
| 3 | `components/StreamingMarkdown.tsx` | Task 1, 2 | build + lint |
| 4 | `ChatMessage.tsx` 流式分支换 `StreamingMarkdown` + 删死代码 | Task 3 | build + lint |
| 5 | `components/AgentStatusBar.tsx` | 无 | build + lint |
| 6 | `useChat.ts` 接线 `SET_CURRENT_TOOL` + `ChatPage.tsx` 换状态条 | Task 4, 5（Task 4 必须先删死代码，接线后才不会重复渲染） | build + lint + 人工 |
| 7 | `ChatPage.tsx` rAF 滚动 + 移除 `.chat-messages` smooth | 无（与 Task 6 同文件，顺序执行） | build + lint + 人工 |
| 8 | `global.css` 视觉细节（光标呼吸/msg-in/工具卡过渡/状态条样式/删 `.progress-text`） | Task 3, 5（类名存在） | build + 人工截图 |
| 9 | `global.css` 删 599-613 重复定义 | Task 8 之后（同区域顺序执行） | build + lint |
| 10 | 全量回归：build + lint + pytest + 10 项人工清单 | 全部 | 见 Task 10 |

---

## Task 1: `MessageContent.tsx` — 导出共享 memoized `Markdown` 组件

> ✅ 已完成（2026-08-05，commit `b971d15`）

**目标:** 把 `MessageContent.tsx:10-17` 的 `markdownComponents` 与插件配置（`remarkGfm` + `rehypeHighlight`）抽成可导出的 memoized `Markdown` 组件（props 仅 `text: string`，`React.memo` 浅比较），供 `StreamingMarkdown` 复用；`MessageContent` 的渲染行为保持不变。

**改动文件:**
- Modify: `web/src/components/MessageContent.tsx`

**Interfaces:**
- Consumes: 现有 `CodeBlock`、`Components`、`remarkGfm`、`rehypeHighlight` 导入（已存在）
- Produces: `export const Markdown: React.MemoExoticComponent<(props: { text: string }) => ReactElement>` —— Task 3 直接消费

- [x] **Step 1.1: 修改 `MessageContent.tsx`**

**位置:** 文件全文（50 行）。当前代码（第 19-48 行）:

```tsx
function MessageContent({ content }: { content: Message["content"] }) {
  if (typeof content === "string") {
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={markdownComponents}
      >
        {content}
      </ReactMarkdown>
    );
  }
  if (Array.isArray(content)) {
    return content.map((part, i) =>
      part.type === "text" ? (
        <ReactMarkdown
          key={i}
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeHighlight]}
          components={markdownComponents}
        >
          {part.text || ""}
        </ReactMarkdown>
      ) : part.type === "image_url" ? (
        <img key={i} src={part.image_url?.url} alt="" />
      ) : null
    );
  }
  return <>{String(content)}</>;
}
```

**修改后:**

```tsx
export const Markdown = memo(function Markdown({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight]}
      components={markdownComponents}
    >
      {text}
    </ReactMarkdown>
  );
});

function MessageContent({ content }: { content: Message["content"] }) {
  if (typeof content === "string") {
    return <Markdown text={content} />;
  }
  if (Array.isArray(content)) {
    return content.map((part, i) =>
      part.type === "text" ? (
        <ReactMarkdown
          key={i}
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeHighlight]}
          components={markdownComponents}
        >
          {part.text || ""}
        </ReactMarkdown>
      ) : part.type === "image_url" ? (
        <img key={i} src={part.image_url?.url} alt="" />
      ) : null
    );
  }
  return <>{String(content)}</>;
}

export default memo(MessageContent);
```

> 说明：数组分支（`ContentPart[]`）保持原样，`markdownComponents` 仍被它引用，不会产生未用变量；该分支继续直接使用 `ReactMarkdown`，输出与修改前逐字节一致。文件头部导入无需改动（`memo`、`ReactMarkdown`、`Components`、`remarkGfm`、`rehypeHighlight`、`CodeBlock`、`Message` 全部仍被使用）。

- [x] **Step 1.2: 验证构建与 lint**

运行（工作目录 `web/`）:
```bash
npm run build
npm run lint
```
预期：`tsc -b && vite build` 零错误（出现 `built in` 输出与 `vite build` 完成信息）；`npm run lint` 输出无 error、无 warning。

- [x] **Step 1.3: 提交**（已完成：`b971d15`）

```bash
git add web/src/components/MessageContent.tsx
git commit -m "refactor: extract shared memoized Markdown component from MessageContent"
```

---

## Task 2: `utils/streamingSplit.ts` — 切分算法 + 独立验证脚本

> ✅ 已完成（2026-08-05，commit `020edcc`）

**目标:** 实现 spec §4.1 的 `splitStreamingText(text): {closed, tail}` 纯函数（`\n\n` 分段 + 反引号奇偶游标 + 缩进/列表续行合并，**最后一段永不闭合**，闭合判定依赖下一段）。独立成纯 TS 文件，配合 `web/scripts/verify-streaming-split.ts` 用 Node 26 原生 TS 执行做自动化断言（16 条边界用例，全部已在本计划编写时预跑验证通过）。

**改动文件:**
- Create: `web/src/utils/streamingSplit.ts`（目录已存在，含 `errors.ts`）
- Create: `web/scripts/verify-streaming-split.ts`（`web/scripts/` 为新目录）

**Interfaces:**
- Consumes: 无
- Produces: `splitStreamingText(text: string): StreamingSplit`，`StreamingSplit = { closed: string; tail: string }` —— Task 3 消费

- [x] **Step 2.1: 创建 `web/src/utils/streamingSplit.ts`**

```ts
export interface StreamingSplit {
  closed: string;
  tail: string;
}

export function splitStreamingText(text: string): StreamingSplit {
  const normalized = text.replace(/\r\n/g, "\n");
  const segments = normalized.split("\n\n").filter((s) => s.length > 0);
  if (segments.length === 0) return { closed: "", tail: "" };

  const isListSegment = (s: string) => /^\s*(?:[-*+]|\d+\.)\s/.test(s);

  let openFence = false;
  let lastClosable = -1;
  for (let i = 0; i < segments.length - 1; i++) {
    const seg = segments[i];
    const next = segments[i + 1];
    const backtickCount = (seg.match(/`/g) || []).length;
    openFence = openFence !== (backtickCount % 2 === 1);
    const closable =
      !openFence && !/^\s/.test(next) && !(isListSegment(seg) && isListSegment(next));
    if (closable) lastClosable = i;
  }

  const closed = lastClosable >= 0 ? segments.slice(0, lastClosable + 1).join("\n\n") : "";
  const tail = segments.slice(lastClosable + 1).join("\n\n");
  return { closed, tail };
}
```

> 算法说明（与 spec §4.1 规则逐条对应）：`lastClosable` 取**最后一个**可闭合下标而非"遇首个不可闭合即 break"——这样才能满足 spec 边界表"闭合 ``` 到来才整体冻结"（围栏段在 fence 未闭合时不可闭合但**不终止扫描**）与"列表遇到非列表段才整体冻结"（连续列表项合并为一块，扫描跳过，到块末才判定）。已冻结前缀单调增长：每个 segment 的判定只依赖它与下一段，追加新段不改旧判定，`closed` 只增不减——这是 memo 跳过的正确性前提。16 条断言已预跑全 PASS（见 Step 2.3 预期输出）。

- [x] **Step 2.2: 创建 `web/scripts/verify-streaming-split.ts`**

```ts
// splitStreamingText 独立验证脚本（项目无前端测试框架，Node >= 23.6 原生执行 .ts）
// 运行: node scripts/verify-streaming-split.ts   （工作目录 web/）
import { splitStreamingText } from "../src/utils/streamingSplit.ts";

function check(input: string, expectedClosed: string, expectedTail: string, label: string): void {
  const { closed, tail } = splitStreamingText(input);
  if (closed !== expectedClosed || tail !== expectedTail) {
    console.error(`FAIL ${label}`);
    console.error(`  input:    ${JSON.stringify(input)}`);
    console.error(`  closed:   ${JSON.stringify(closed)}   (expected ${JSON.stringify(expectedClosed)})`);
    console.error(`  tail:     ${JSON.stringify(tail)}   (expected ${JSON.stringify(expectedTail)})`);
    throw new Error(`verification failed: ${label}`);
  }
  console.log(`PASS ${label}`);
}

check("", "", "", "empty text");
check("p1\n\np2\n\np3", "p1\n\np2", "p3", "plain paragraphs freeze on next segment");
check("p1", "", "p1", "last segment never closes");
check("para\n\n", "", "para", "trailing blank line filtered, para stays in tail");
check("p1\r\n\r\np2", "p1", "p2", "CRLF normalized");
check("```python\n\ncode\n\n```", "", "```python\n\ncode\n\n```", "open fence keeps all in tail");
check("```python\n\ncode\n\n```\n\nnext", "```python\n\ncode\n\n```", "next", "fenced block freezes when following segment arrives");
check("- a\n\n- b\n\n- c", "", "- a\n\n- b\n\n- c", "consecutive list items stay in tail");
check("- a\n\n- b\n\n- c\n\npara", "- a\n\n- b\n\n- c", "para", "list run freezes when non-list segment arrives");
check("- item\n\n  continuation", "", "- item\n\n  continuation", "indented continuation keeps list item in tail");
check("- item1\n\n  continuation", "", "- item1\n\n  continuation", "blank line inside list item keeps both in tail");
check("a `b\n\nc` d", "", "a `b\n\nc` d", "inline code spanning segments stays in tail");
check("| a | b |\n|---|--|\n| 1 | 2 |", "", "| a | b |\n|---|--|\n| 1 | 2 |", "GFM table is a single segment (never split)");
check("- a\n\npara", "- a", "para", "single list item freezes when non-list follows");
check("p1\n\n```python", "p1", "```python", "paragraph freezes, open fence stays in tail");
check("p1\n\np2\n\n```python\n\ncode", "p1\n\np2", "```python\n\ncode", "paragraphs freeze up to the fence");
console.log("Done");
```

- [x] **Step 2.3: 运行验证脚本**

运行（工作目录 `web/`）:
```bash
node scripts/verify-streaming-split.ts
```
预期：16 行 `PASS ...` + 最后一行 `Done`，进程退出码 0（断言失败会抛异常，退出码非 0 并打印 `FAIL` 行）。

- [x] **Step 2.4: 验证构建与 lint**

```bash
npm run build
npm run lint
```
预期：零错误。`tsconfig.app.json` 的 `include` 仅含 `src`，`scripts/` 不参与 tsc；eslint 会检查 `scripts/verify-streaming-split.ts`，须零 error/warning（脚本未引用 `process`/`window` 等非浏览器全局，使用 throw 而非 exitCode 就是为了通过 lint）。

- [x] **Step 2.5: 提交**

```bash
git add web/src/utils/streamingSplit.ts web/scripts/verify-streaming-split.ts
git commit -m "feat: add streaming markdown split algorithm with edge-case verification"
```

---

## Task 3: `components/StreamingMarkdown.tsx`

> ✅ 已完成（2026-08-05，commit `9032568`） — 切分渲染组件

**目标:** 新增流式专用渲染组件：`useMemo` 调 `splitStreamingText` 切分为 `closed`（冻结块）+ `tail`（实时块），两个容器分别用共享 memoized `Markdown` 渲染。props 仅 `text`；`closed` 字符串不变时 React.memo 浅比较跳过整段重解析，每 50ms flush 只重解析 tail。

**改动文件:**
- Create: `web/src/components/StreamingMarkdown.tsx`

**Interfaces:**
- Consumes: `Markdown`（Task 1 导出，`{ text: string }`）；`splitStreamingText`（Task 2 导出，`(text: string) => StreamingSplit`）
- Produces: `default function StreamingMarkdown({ text }: { text: string })`，渲染 `.streaming-split > .streaming-closed + .streaming-tail` —— Task 4 消费；CSS 类名 `.streaming-split` / `.streaming-closed` / `.streaming-tail` 被 Task 8 的光标规则引用

- [x] **Step 3.1: 创建 `web/src/components/StreamingMarkdown.tsx`**

```tsx
import { useMemo } from "react";
import { Markdown } from "./MessageContent";
import { splitStreamingText } from "../utils/streamingSplit";

// 流式期间专用：已闭合块（memo 冻结，不重解析）+ 尾部实时块（每帧重解析）
// done 后 ChatMessage 的 isStreaming 变 false，本组件卸载，最终消息走 MessageContent 全量解析
export default function StreamingMarkdown({ text }: { text: string }) {
  const { closed, tail } = useMemo(() => splitStreamingText(text), [text]);
  return (
    <div className="streaming-split">
      <div className="streaming-closed">
        <Markdown text={closed} />
      </div>
      {tail !== "" && (
        <div className="streaming-tail">
          <Markdown text={tail} />
        </div>
      )}
    </div>
  );
}
```

> 说明：spec §4.1 伪代码中的 `MemoizedMarkdown` 由 Task 1 导出的 memoized `Markdown` 直接承担（`Markdown` 本身已 `React.memo` 且 props 仅 `text` 字符串，浅比较即值比较），无需在组件内再包一层——"单一导出点、共用同一实例配置"（spec §7 风险表）由 `MessageContent.tsx` 导出保证。不存在循环导入：`MessageContent` 不引用本组件。

- [x] **Step 3.2: 验证构建与 lint**

```bash
npm run build
npm run lint
```
预期：零错误。

- [x] **Step 3.3: 提交**

```bash
git add web/src/components/StreamingMarkdown.tsx
git commit -m "feat: add StreamingMarkdown split-rendering component"
```

---

## Task 4: `ChatMessage.tsx` — 流式分支换 `StreamingMarkdown` + 删除死代码 `runningToolCard`

> ✅ 已完成（2026-08-05，commit `125916b`）

**目标:** ① `isStreaming` 分支（原第 60-62 行）改渲染 `<StreamingMarkdown text={msg.content} />`（仅当 `typeof content === "string"`，满足 TS 收窄）；② 删除死代码 `runningToolCard`（原第 8-17/95/109-131/150 行相关片段）——它在 `currentToolName` 恒空时不可达，Task 6 接线 `SET_CURRENT_TOOL` 后必与 `ADD_PENDING_TOOL` 插入的 pending 卡重复渲染，故必须在本任务删干净（`noUnusedLocals` 会强制验证）。

**改动文件:**
- Modify: `web/src/components/ChatMessage.tsx`

**Interfaces:**
- Consumes: `StreamingMarkdown`（Task 3）
- Produces: 无新接口；删除 `AssistantGroupContent` 的 `runningToolCard` prop（Task 6 不依赖它）

- [x] **Step 4.1: 修改导入（原第 3-6 行）**

**当前代码:**
```tsx
import MessageContent from "./MessageContent";
import ReasoningBlock from "./ReasoningBlock";
import ToolStepCard from "./ToolStepCard";
import { useAppState } from "../context/AppContext";
```

**修改后:**
```tsx
import MessageContent from "./MessageContent";
import ReasoningBlock from "./ReasoningBlock";
import StreamingMarkdown from "./StreamingMarkdown";
import ToolStepCard from "./ToolStepCard";
```

- [x] **Step 4.2: 删除 `AssistantGroupContent` 的 `runningToolCard` prop（原第 8-17 行）**

**当前代码:**
```tsx
function AssistantGroupContent({
  msgs,
  streaming,
  runningToolCard,
  onChoiceSelect,
}: {
  msgs: Message[];
  streaming?: boolean;
  runningToolCard?: React.ReactNode;
  onChoiceSelect?: (text: string) => void;
}) {
```

**修改后:**
```tsx
function AssistantGroupContent({
  msgs,
  streaming,
  onChoiceSelect,
}: {
  msgs: Message[];
  streaming?: boolean;
  onChoiceSelect?: (text: string) => void;
}) {
```

- [x] **Step 4.3: 删除渲染尾部 `{runningToolCard}`（原第 95 行）**

**当前代码:**
```tsx
      )}
      {runningToolCard}
    </div>
  );
}
```

**修改后:**
```tsx
      )}
    </div>
  );
}
```

- [x] **Step 4.4: 流式分支换 `StreamingMarkdown`（原第 59-63 行）**

**当前代码:**
```tsx
              {hasContent ? (
                <div className={`msg-bubble${isStreaming ? " streaming-text" : ""}`}>
                  <MessageContent content={msg.content} />
                </div>
              ) : isStreaming ? (
```

**修改后:**
```tsx
              {hasContent ? (
                <div className={`msg-bubble${isStreaming ? " streaming-text" : ""}`}>
                  {isStreaming && typeof msg.content === "string" ? (
                    <StreamingMarkdown text={msg.content} />
                  ) : (
                    <MessageContent content={msg.content} />
                  )}
                </div>
              ) : isStreaming ? (
```

> `thinking-indicator` 分支与其余代码不变。`MessageContent` 仍被非流式分支与用户消息分支使用，导入保留。

- [x] **Step 4.5: 删除 `useAppState`/`showRunning`/`runningToolCard` 定义（原第 109-131 行）**

**当前代码:**
```tsx
  const { state } = useAppState();
  // 只在流式进行中且当前有工具时显示运行中卡片
  const showRunning = streaming && state.currentToolName ? true : false;

  const runningToolCard = showRunning ? (
    <div className="tool-step-group">
      <div className="tool-step tool-step-running">
        <div className="tool-step-header" style={{ cursor: 'default' }}>
          <div className="tool-step-header-left">
            <div className="tool-step-icon">
              <div className="tool-step-spinner" />
            </div>
            <div className="tool-step-header-text">
              <div className="tool-step-title-row">
                <span className="tool-step-name">{state.currentToolName}</span>
              </div>
              <div className="tool-step-desc">正在执行…</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  ) : null;

  const first = msgs[0];
```

**修改后:**
```tsx
  const first = msgs[0];
```

- [x] **Step 4.6: 删除 `runningToolCard` 透传（原第 150 行）**

**当前代码:**
```tsx
      <AssistantGroupContent msgs={msgs} streaming={streaming} runningToolCard={runningToolCard} onChoiceSelect={onChoiceSelect} />
```

**修改后:**
```tsx
      <AssistantGroupContent msgs={msgs} streaming={streaming} onChoiceSelect={onChoiceSelect} />
```

- [x] **Step 4.7: 验证构建与 lint**

```bash
npm run build
npm run lint
```
预期：零错误（`streaming` prop 仍被 `isStreaming` 使用；若残留 `state`/`runningToolCard` 等未用变量，`noUnusedLocals` 会报错）。

- [x] **Step 4.8: 提交**

```bash
git add web/src/components/ChatMessage.tsx
git commit -m "refactor: use StreamingMarkdown during streaming and drop dead runningToolCard"
```

---

## Task 5: `components/AgentStatusBar.tsx` — Agent 状态条组件

> ✅ 已完成（2026-08-05，commit `681e766`；偏差：`IconWrench`→`IconTool`（依赖版本无此图标）、effect 内 setElapsed(0) 改为派生值 displayElapsed（过 lint））

**目标:** 新增状态条组件：优先级 `currentToolName`（工具图标 + `调用工具 <名>`）> `progressMessage`（原文）> `思考中…`（脉冲点）；`useEffect` 依赖 `[state.agentRunning]` 自持已耗时（`setInterval` 每秒推进，从 `Date.now()` 起始点计算避免累加漂移；false 时清零），`mm:ss` 展示。

**改动文件:**
- Create: `web/src/components/AgentStatusBar.tsx`

**Interfaces:**
- Consumes: `useAppState()`（`AppContext.tsx:202`，返回 `{ state, dispatch }`）；`state.currentToolName` / `state.progressMessage` / `state.agentRunning`
- Produces: `default function AgentStatusBar()`，渲染 `.agent-status-bar`（`role="status"` `aria-live="polite"`）> `.agent-status-icon` + `.agent-status-label` + `.agent-status-elapsed` —— Task 6 消费；这些类名被 Task 8 样式引用

- [x] **Step 5.1: 创建 `web/src/components/AgentStatusBar.tsx`**

```tsx
import { useEffect, useState } from "react";
import { IconWrench } from "@tabler/icons-react";
import { useAppState } from "../context/AppContext";

function formatElapsed(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const mm = String(Math.floor(totalSec / 60)).padStart(2, "0");
  const ss = String(totalSec % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

export default function AgentStatusBar() {
  const { state } = useAppState();
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!state.agentRunning) {
      setElapsed(0);
      return;
    }
    const start = Date.now();
    const id = window.setInterval(() => {
      setElapsed(Date.now() - start);
    }, 1000);
    return () => window.clearInterval(id);
  }, [state.agentRunning]);

  const label = state.currentToolName
    ? `调用工具 ${state.currentToolName}`
    : state.progressMessage
      ? state.progressMessage
      : "思考中…";

  return (
    <div className="agent-status-bar" role="status" aria-live="polite">
      <span className="agent-status-icon">
        {state.currentToolName ? (
          <IconWrench size={14} />
        ) : (
          <span className="agent-status-dots">
            <span />
            <span />
            <span />
          </span>
        )}
      </span>
      <span className="agent-status-label">{label}</span>
      <span className="agent-status-elapsed">{formatElapsed(elapsed)}</span>
    </div>
  );
}
```

> 说明：样式（含 `.agent-status-dots` 脉冲动画复用现有 `think-bounce` keyframes）在 Task 8 落地，本任务先保证组件可编译。`tool_result` 到达、下一工具或 `done` 到来前 `currentToolName` 保持最近一次工具名（`SET_RESULT`/`SET_RUNNING` 才清空，见 `AppContext.tsx:107/169/182`）——spec §4.2 明确这是有意保留的行为；`done` 后随 `agentRunning=false` 整条消失。

- [x] **Step 5.2: 验证构建与 lint**

```bash
npm run build
npm run lint
```
预期：零错误。

- [x] **Step 5.3: 提交**

```bash
git add web/src/components/AgentStatusBar.tsx
git commit -m "feat: add AgentStatusBar component"
```

---

## Task 6: 接线 `SET_CURRENT_TOOL` + `ChatPage.tsx` 换用 `<AgentStatusBar />`

> ✅ 已完成（2026-08-05，commit `4fb2f2c`；顺带授权修复 useChat.ts 既存 lint 错误；Step 6.5 人工冒烟合并至 Task 10 统一执行）

**目标:** ① `useChat.ts` 的 `case "tool_call"` 新增 `dispatch({ type: "SET_CURRENT_TOOL", toolName: msg.name })`（spec §4.2 关键决策：接线而非解析 `"🔧 执行工具: "` 字符串，避免 emoji 前缀脆弱解析；`SET_RUNNING`/`SET_RESULT`/`SET_ERROR` 已有清空逻辑，无需改 reducer）；② `ChatPage.tsx` 删除 `progress-text` 区块（含第 174 行 `!includes("执行工具")` 过滤），替换为 `<AgentStatusBar />`，`StopButton` 位置不变。Task 4 已先删除会复活的 `runningToolCard` 死代码。

**改动文件:**
- Modify: `web/src/hooks/useChat.ts:73-77`
- Modify: `web/src/pages/ChatPage.tsx:171-180`（+ 第 11 行后加导入）

**Interfaces:**
- Consumes: `AgentStatusBar`（Task 5）
- Produces: 无新接口；`currentToolName` 从恒 `""` 变为工具调用期间非空

- [x] **Step 6.1: `useChat.ts` 接线 `SET_CURRENT_TOOL`**

**位置:** `web/src/hooks/useChat.ts` 第 73-77 行

**当前代码:**
```tsx
          case "tool_call":
            // 收到后端发来的 tool_call 消息，立即插入 pending 工具卡片
            dispatch({ type: "SET_PROGRESS", message: `🔧 执行工具: ${msg.name}` });
            dispatch({ type: "ADD_PENDING_TOOL", message: { role: "tool", content: msg.arguments, tool_call_id: "pending:" + msg.name } });
            break;
```

**修改后:**
```tsx
          case "tool_call":
            // 收到后端发来的 tool_call 消息，立即插入 pending 工具卡片
            dispatch({ type: "SET_PROGRESS", message: `🔧 执行工具: ${msg.name}` });
            dispatch({ type: "SET_CURRENT_TOOL", toolName: msg.name });
            dispatch({ type: "ADD_PENDING_TOOL", message: { role: "tool", content: msg.arguments, tool_call_id: "pending:" + msg.name } });
            break;
```

> `SET_PROGRESS` 仍保留（`progressMessage` 是状态条的第二优先级数据源；工具执行期间 `currentToolName` 优先显示工具名）。

- [x] **Step 6.2: `ChatPage.tsx` 添加导入（第 11 行后）**

**当前代码:**
```tsx
import StopButton from "../components/StopButton";
```

**修改后:**
```tsx
import StopButton from "../components/StopButton";
import AgentStatusBar from "../components/AgentStatusBar";
```

- [x] **Step 6.3: `ChatPage.tsx` 替换 `progress-text` 区块（第 171-180 行）**

**当前代码:**
```tsx
      {state.agentRunning && (
        <>
          <StopButton onStop={stopAgent} />
          {state.progressMessage && !state.progressMessage.includes("执行工具") && (
            <div className="progress-text" style={{ paddingBottom: "4px" }}>
              {state.progressMessage}
            </div>
          )}
        </>
      )}
```

**修改后:**
```tsx
      {state.agentRunning && (
        <>
          <StopButton onStop={stopAgent} />
          <AgentStatusBar />
        </>
      )}
```

- [x] **Step 6.4: 验证构建与 lint**

```bash
npm run build
npm run lint
```
预期：零错误。

- [x] **Step 6.5: 人工冒烟（功能验证，样式在 Task 8 落地前未打磨属预期）**

`./start.sh --dev` 起服务后（浏览器 DevTools → Network → WS 观察），发一条会调用工具的消息（如"查 YonSuite 销售订单"）。预期：
- 输入框上方出现状态条，工具调用期间显示 `调用工具 query_sale_orders` + 秒数每秒递增；
- `tool_result` 到达、整轮结束前状态条保持显示最近一次工具名（有意行为）；`done` 后随 `agentRunning=false` 整条消失；
- 无工具调用时显示 `思考中…`（脉冲点样式 Task 8 后可见）。

- [x] **Step 6.6: 提交**

```bash
git add web/src/hooks/useChat.ts web/src/pages/ChatPage.tsx
git commit -m "feat: wire current tool name and replace progress-text with AgentStatusBar"
```

---

## Task 7: `ChatPage.tsx` 自动滚动改 rAF 节流 + 移除 `.chat-messages` smooth

**目标:** 滚动 effect（原第 78-88 行）从 `setTimeout(0)` 直赋改为 `requestAnimationFrame` 节流；同时移除 `global.css:289` `.chat-messages` 的 `scroll-behavior: smooth`——若不移除，CSS 平滑会让 rAF 里的 `scrollTop` 直赋仍触发平滑动画，逐 token 动画重启恰是顿挫源，与 spec §4.3 "流式跟随滚动始终用 scrollTop 直赋（不累积 smooth 动画队列）" 直接冲突；"回到底部"按钮显式 `behavior: "smooth"`（第 150 行）不受影响，smooth 仅保留给用户触发。

**改动文件:**
- Modify: `web/src/pages/ChatPage.tsx:78-88`
- Modify: `web/src/styles/global.css:285-290`

**Interfaces:**
- Consumes: `scrollRef`（`ChatPage.tsx:22`）、`userScrolledUp`（第 23 行 ref，`handleScroll` 第 90-96 行维持不变）
- Produces: 无新接口

- [ ] **Step 7.1: `ChatPage.tsx` 滚动 effect 改 rAF**

**位置:** `web/src/pages/ChatPage.tsx` 第 78-88 行

**当前代码:**
```tsx
  useEffect(() => {
    if (!userScrolledUp.current && scrollRef.current) {
      const el = scrollRef.current;
      // 使用 setTimeout 代替 requestAnimationFrame，确保在 DOM 更新后执行
      setTimeout(() => {
        if (el) {
          el.scrollTop = el.scrollHeight;
        }
      }, 0);
    }
  }, [state.messages, state.streamingText]);
```

**修改后:**
```tsx
  useEffect(() => {
    if (userScrolledUp.current || !scrollRef.current) return;
    const el = scrollRef.current;
    const rafId = requestAnimationFrame(() => {
      if (!userScrolledUp.current) {
        el.scrollTop = el.scrollHeight;
      }
    });
    return () => cancelAnimationFrame(rafId);
  }, [state.messages, state.streamingText]);
```

> **spec 伪代码勘误**：spec §4.3 给出的外层守卫 `if (!userScrolledUp.current || ...) return;` 与现状语义（在底部才跟随滚动）及 rAF 内层二次校验（`!userScrolledUp.current` 才滚）矛盾，属笔误。本计划按意图修正为 `if (userScrolledUp.current || !scrollRef.current) return;`。rAF 合并多次 flush 的滚动到同一帧（约 60Hz 节流）；effect 在 React commit 后运行、rAF 回调在绘制前执行，DOM 已就绪；`userScrolledUp` 在 rAF 回调内二次校验（帧内用户可能上滚）。依赖数组与现状一致，不触发 eslint exhaustive-deps。

- [ ] **Step 7.2: 移除 `.chat-messages` 的 `scroll-behavior: smooth`**

**位置:** `web/src/styles/global.css` 第 285-290 行

**当前代码:**
```css
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
  scroll-behavior: smooth;
}
```

**修改后:**
```css
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
```

- [ ] **Step 7.3: 验证构建与 lint**

```bash
npm run build
npm run lint
```
预期：零错误。

- [ ] **Step 7.4: 人工冒烟（滚动行为）**

`./start.sh --dev` 下：流式输出时页面跟随滚动流畅无逐 token 顿挫（可对比改动前）；用户上滚超过 150px 后不再被抢滚，"回到底部"按钮出现，点击后 smooth 回底；继续流式输出不再劫持滚动。

- [ ] **Step 7.5: 提交**

```bash
git add web/src/pages/ChatPage.tsx web/src/styles/global.css
git commit -m "perf: throttle auto-scroll with requestAnimationFrame"
```

---

## Task 8: `global.css` 视觉细节 — 光标呼吸 / msg-in / 工具卡过渡 / 状态条样式 / 删 `.progress-text`

**目标:** 按 spec §4.4/§4.5 落地视觉细节，全部复用 `:root` 现有变量，不新增变量/颜色。

**改动文件:**
- Modify: `web/src/styles/global.css`

**Interfaces:**
- Consumes: `.streaming-split` / `.streaming-closed` / `.streaming-tail`（Task 3 输出）；`.agent-status-bar` / `.agent-status-icon` / `.agent-status-label` / `.agent-status-elapsed` / `.agent-status-dots`（Task 5 输出）
- Produces: 无新接口

- [ ] **Step 8.1: `msg-in` 微调（第 307、310-313 行）**

**当前代码:**
```css
  animation: msg-in 0.3s ease;
```
**修改后:**
```css
  animation: msg-in 0.25s ease-out;
```

**当前代码:**
```css
@keyframes msg-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
```
**修改后:**
```css
@keyframes msg-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
```

- [ ] **Step 8.2: `.tool-step` 过渡扩展（第 561-568 行，整块替换以保证 old-string 唯一——`transition: box-shadow 0.2s` 在文件中另有 1191/1490 两处出现）**

**当前代码:**
```css
.tool-step {
  margin: 8px 0;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-card);
  overflow: hidden;
  transition: box-shadow 0.2s;
}
```
**修改后:**
```css
.tool-step {
  margin: 8px 0;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-card);
  overflow: hidden;
  transition: box-shadow 0.2s, background-color 0.3s ease, border-color 0.3s ease;
}
```

- [ ] **Step 8.3: `.tool-step-icon` 新增过渡（第 614-623 行）**

**当前代码:**
```css
.tool-step-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 14px;
}
```
**修改后:**
```css
.tool-step-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 14px;
  transition: background-color 0.3s ease, color 0.3s ease;
}
```

- [ ] **Step 8.4: 光标改呼吸 + 作用域限定 tail + 冻结块段间距修复（第 784-798 行）**

**当前代码:**
```css
.streaming-text p:last-child::after {
  content: '';
  display: inline-block;
  width: 2px;
  height: 1em;
  background: var(--primary);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink-cursor 0.8s infinite;
}

@keyframes blink-cursor {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
```

**修改后:**
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

/* 已冻结块最后一段保留段间距，避免与 tail 首段粘连（原单容器由 p:last-child 规则给 0 边距，切分后需补回） */
.streaming-split .streaming-closed p:last-child {
  margin-bottom: 6px;
}
```

> 说明：原 `.streaming-text p:last-child::after` 在双容器下会出现双光标，新选择器只匹配 tail 的最后一个 `p`；tail 恒非空（最后一段永不闭合）保证光标持续存在。`.msg-bubble p` 的 `margin: 0 0 6px` 依然作用于两个容器内所有 p；但 `.msg-bubble p:last-child { margin-bottom: 0 }` 会把冻结块的末段下边距清零，导致与 tail 首段粘连，故补一条 `.streaming-closed p:last-child` 规则恢复 6px。

- [ ] **Step 8.5: 新增 `.agent-status-bar` 系列样式（追加到 Streaming indicator 分区，紧跟 Step 8.4 的光标块之后）**

```css
/* ── Agent status bar ─────────────────────────────────── */

.agent-status-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 2px 6px;
  font-size: 12px;
  color: var(--text-3);
}
.agent-status-icon {
  display: inline-flex;
  align-items: center;
  color: var(--primary);
}
.agent-status-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.agent-status-elapsed {
  font-variant-numeric: tabular-nums;
  color: var(--text-4);
}
.agent-status-dots {
  display: inline-flex;
  gap: 3px;
}
.agent-status-dots span {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--primary);
  animation: think-bounce 1.4s infinite;
}
.agent-status-dots span:nth-child(2) { animation-delay: 0.2s; }
.agent-status-dots span:nth-child(3) { animation-delay: 0.4s; }
```

> 脉冲点动画复用现有 `think-bounce` keyframes（第 817-820 行），不新增 keyframes、不新增颜色。

- [ ] **Step 8.6: 删除孤儿 `.progress-text`（第 1049-1055 行）**

**当前代码:**
```css
.progress-text {
  font-size: 12px;
  color: var(--text-3);
  display: flex;
  align-items: center;
  gap: 4px;
}

/* ── Token usage footer ──────────────────────────────── */
```

**修改后:**
```css
/* ── Token usage footer ──────────────────────────────── */
```

- [ ] **Step 8.7: 验证构建与 lint**

```bash
npm run build
npm run lint
```
预期：零错误（CSS 不参与 tsc，lint 通过即可）。

- [ ] **Step 8.8: 人工截图核验（本轮视觉验收）**

`./start.sh --dev` 下逐项截图留证：
- 流式输出最后一段文字后出现呼吸光标（1.2s ease-in-out，无硬切闪烁）；冻结块末尾无光标（单光标）；
- 冻结段落与实时段落的段间距与其他段落一致（无粘连）；
- 工具卡 running→完成切换时图标容器背景 `--primary-bg`→`--success-bg` 平滑过渡；
- 状态条图标/文字/耗时布局正常，脉冲点在"思考中"时跳动。

- [ ] **Step 8.9: 提交**

```bash
git add web/src/styles/global.css
git commit -m "style: add breathing cursor and smooth tool card transitions"
```

---

## Task 9: `global.css` 删除重复的 `.tool-step-title-row` / `.tool-step-count`（第 599-613 行）

**目标:** 删除旧定义（gap 6px / font-size 10px / radius 3px / 含 `flex-shrink: 0`），保留第 657-670 行更完整定义（gap 8px / font-size 11px / radius 4px）。`.tool-step-count` 无组件引用（grep 确认仅 CSS 内部），后者不含 `flex-shrink: 0` 无功能影响，按 spec §4.5 批准决定原样保留后者。

**改动文件:**
- Modify: `web/src/styles/global.css:599-613`

**Interfaces:**
- Consumes: 无
- Produces: 无

- [ ] **Step 9.1: 删除重复块**

**当前代码:**
```css
.tool-step-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.tool-step-count {
  font-size: 10px;
  color: var(--text-3);
  background: var(--bg-hover);
  padding: 0 5px;
  border-radius: 3px;
  line-height: 1.6;
  white-space: nowrap;
  flex-shrink: 0;
}
.tool-step-icon {
```

**修改后:**
```css
.tool-step-icon {
```

- [ ] **Step 9.2: 验证构建与 lint + 类名引用核对**

```bash
npm run build
npm run lint
rg -n "tool-step-count" web/src --glob '!**/global.css'   # 预期：无输出（无组件引用）
rg -n "tool-step-title-row" web/src --glob '!**/global.css'  # 预期：ChatMessage.tsx 已无引用（Task 4 已删），ToolStepCard.tsx:157 仍引用
```
预期：build/lint 零错误；第一条 rg 无输出；第二条 rg 只显示 `web/src/components/ToolStepCard.tsx:157`。

- [ ] **Step 9.3: 提交**

```bash
git add web/src/styles/global.css
git commit -m "style: remove duplicate tool-step title/count CSS"
```

---

## Task 10: 全量回归验证（无代码改动，不产生 commit）

**目标:** 确认全部改动无回归：前端构建 + lint、后端 pytest 冒烟、10 项人工验证清单逐项截图留证。

- [ ] **Step 10.1: 前端构建 + lint**

```bash
cd web && npm run build && npm run lint
```
预期：`tsc -b && vite build` 零错误、lint 零 error/warning。

- [ ] **Step 10.2: 切分算法回归**

```bash
cd web && node scripts/verify-streaming-split.ts
```
预期：16 行 `PASS` + `Done`，退出码 0。

- [ ] **Step 10.3: 后端回归冒烟**

```bash
.venv/bin/python -m pytest tests/ -q
```
预期：全部通过（仓库当前 371 tests，零失败）。

- [ ] **Step 10.4: 人工验证清单（`./start.sh --dev`，逐项截图留证）**

| # | 场景 | 预期 |
|---|------|------|
| 1 | 长文本流式输出（多段 + 标题 + 列表） | 已闭合段冻结不闪、不高亮跳动；光标只在正在输入的最后一段 |
| 2 | 代码块流式（``` python ...） | 围栏未闭合前整块在 tail 持续更新；闭合 + 后续段到达后整体冻结；无中途拆开 |
| 3 | 表格流式 | 整表一次成型，绝无半表渲染；与完成态样式一致 |
| 4 | 连续列表项流式 | 列表项合并渲染，遇到非列表段后整体冻结；无拆项错位 |
| 5 | 工具调用流（如"查 YonSuite 销售订单"） | 状态条显示"调用工具 query_sale_orders" + 工具图标 + 秒数递增；pending 卡 spinner 正常；`tool_result` 到达后卡片变绿且背景平滑过渡；整轮结束状态条消失 |
| 6 | 纯思考阶段（无工具） | 状态条显示"思考中…"脉冲点 + 耗时；推理内容流式期间状态条持续 |
| 7 | 自动滚动 | 流式期间平滑跟随（无逐 token 顿挫）；用户上滚后不抢滚；点"回到底部" smooth 回底；新内容不再被劫持 |
| 8 | 中途停止 | Stop 按钮可用；停止后状态条消失、光标消失、最终消息正确落定 |
| 9 | 回归 | 历史会话加载、审批流、WELCOME 消息、斜杠命令、token 用量条、文件上传附件均正常 |
| 10 | 光标视觉 | 呼吸动画（1.2s ease-in-out）平滑，无硬切闪烁；截图确认光标位于最后一段文字后 |

- [ ] **Step 10.5: 工作区检查**

```bash
git status
git log --oneline -12
```
预期：9 个功能 commit（Task 1-9）按顺序可见，工作区干净（本计划文档已在收尾提交）。

---

## 自审记录（Self-Review）

- **spec 一致性**：5 项工作逐一映射 —— 改动 1 → Task 1-4；改动 2 → Task 5-6；改动 3 → Task 7；改动 4 → Task 8；改动 5 → Task 9；测试策略 → Task 10。spec §5"不改动"清单全部遵守（types/ws/AppContext/backend/agent 零改动）。
- **spec 伪代码勘误**：§4.3 rAF 外层守卫 `!userScrolledUp.current` 为笔误，按意图修正（见 Task 7.1 说明）。
- **spec 未明示的必要实现细节**：① 移除 `.chat-messages` 的 `scroll-behavior: smooth`（否则 rAF 直赋仍平滑，顿挫不除，与 §4.3 意图冲突）；② `.streaming-closed p:last-child` 补回 6px 段间距（切分后 `p:last-child` 规则失效导致段粘连）；③ 切分算法采用"最后一个可闭合下标"而非"首个不可闭合即 break"，以满足 spec 边界表"围栏/列表遇到后续段才整体冻结"（16 条边界断言已预跑全 PASS）；④ 为可验证性将 `splitStreamingText` 独立为 `utils/streamingSplit.ts`（spec 文件清单写的是放进 StreamingMarkdown.tsx，spec §4.1 注明"实现细节以 plan 为准"，接口不变）。
- **占位符扫描**：无 TBD/TODO/省略号；每个文件创建/编辑均给出完整代码或精确 old/new。
- **类型一致性**：`splitStreamingText(text): StreamingSplit`、`Markdown({text})`、`StreamingMarkdown({text})`、`AgentStatusBar()` 在 Task 间引用一致；CSS 类名 `.streaming-split/.streaming-closed/.streaming-tail/.agent-status-*` 在 Task 3/5 产出、Task 8 消费，逐一核对。
- **task 粒度**：每任务 1 commit、2-5 分钟/步、独立可验证（build/lint 或 node 脚本或人工清单）。
