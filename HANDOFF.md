# HANDOFF — 对话界面工具执行面板完成（2026-08-07）

> 供新 opencode 会话快速接续。所有工作已提交并推送，无未保存改动。

## 当前状态

- 分支：`main`，与 `origin/main`（atomgit）同步，HEAD = `6f03b3a`
- 版本：v1.9.0（用户拍板：本次不发新版本，DMG 名义 1.9.0 但已含面板特性）
- 测试：509 passed / ruff clean / `npm run build` + `npm run lint` 全绿
- 打包产物：`dist-electron/ZLink Agent-1.9.0-arm64.dmg`（170M，arm64，未签名如常，构建冒烟测试通过）
- 测试服务已停（8088/8089 端口已释放）

## 本次会话完成的事

**主线：对话界面工具执行面板（ToolRunPanel）**，spec：`docs/superpowers/specs/2026-08-06-tool-run-panel-design.md`（docs/ 被 gitignore，仅本地）。两个代码 commit：

1. `fde3abc` feat：同回合连续 tool 消息收进固定高度（220px）内嵌面板，紧凑日志行（图标+名称+参数摘要+耗时），内部自动滚动；全部完成自动折叠成摘要行「N 个工具 · 全部成功 · 共 Xs」；点击展开/行内详情（参数+返回，pre 限高 240px）；耗时前端采集（WS 零改动）
2. `5b3e09b` fix：折叠触发器从"全部完成即折"改为 live 语义（本轮进行中保持展开累积行，回合结束才折叠）——消除 LLM 批次间隙的折叠/展开抖动

**联调中修复的存量/衍生 bug（均已随上述 commit 入库）：**
- `ADD_PENDING_TOOL` 去重吞卡：已完成消息保留 `pending:xxx` id 导致同会话同名工具第二次调用的 pending 卡被吞、旧消息内容被新结果覆盖 → 去重条件加 `!m._tool_done`
- 实况中工具详情「参数」误显结果 JSON → `message._tool_args` stash 原始参数
- `extractSubtitle` 补 ls/glob/search_files case

**其他决策：**
- **暗色主题永远不做**（用户拍板，已记入 `AGENTS.md` §13，commit `6f03b3a`）
- 单工具回合统一走面板；clarify 工具不进面板（交互按钮留消息流）
- 版本不 bump：DMG 叫 1.9.0，用户原话"先就叫 1.9 吧"

## 改动文件（均已入库）

- `web/src/components/ToolRunPanel.tsx`（新建：面板/行/摘要/详情 + 迁移来的 helpers）
- `web/src/components/ChatMessage.tsx`（run 分组渲染 + live 传递）
- `web/src/components/ToolStepCard.tsx`（收缩为仅 clarify-prompt）
- `web/src/hooks/useChat.ts`（toolStartRef 计时 + `_tool_args`）
- `web/src/context/AppContext.tsx`（计时字段 + dedup 修复）
- `web/src/types/index.ts`（`_tool_duration_ms`/`_tool_started_at`/`_tool_args`）
- `web/src/styles/global.css`（`tool-run-*` 系列类）
- 后端零改动，四个冻结契约零破坏

## 验证命令与结果（实测）

```bash
.venv/bin/python -m pytest tests/ -q   # 509 passed
cd web && npm run build && npm run lint # 全绿
bash scripts/build-electron.sh          # 冒烟测试通过（57 工具），dmg 产出
```

**浏览器实机 E2E（dev + 真实 LLM，全部通过）**：历史回放折叠摘要；实况 spinner 行+参数副标题+耗时 tick；自动折叠（总耗时 8.0s/20.4s/30.1s 精确）；12 工具累积 325px 自动滚底（scrollTop=105）；clarify 选项点击续聊；执行中停止无悬挂状态；审批拒绝（橙色「已拒绝」行+摘要）；行详情限高。

## 已知问题 / 注意事项

- **审批拒绝测试前置坑**：运行时后端若是 v1.9.0 发布前启动的旧进程，无 M-1 denied 传播，拒绝会显示「失败」——重启后端即可，代码本身无问题
- **打包版未人工 E2E**：dmg 只跑了构建内冒烟测试；含上一会话遗留的 Tavily `web_search` 打包档验证（key 在 `~/.zlink-agent/.env`，打包版启动即读）
- 暗色主题截图未验证（已拍板永不做，无需验）
- 测试用 dev 会话产生了一些测试 session 数据（cd31b691、4a314c7b、bf83f979 等），可在历史页删除

## 遗留事项（不阻塞，按优先级）

1. 打包版人工验证：安装 dmg → 跑一轮多工具对话确认面板 + `web_search` 走 Tavily
2. 可选：根 `package-lock.json` version 仍 1.7.0（过时，不影响构建）
3. 下次发版时把面板特性写进 CHANGELOG/README

## 新会话启动提示词

```
Read HANDOFF.md 和 AGENTS.md。当前 main 与 origin 同步（HEAD 6f03b3a），
上次会话完成对话界面工具执行面板（ToolRunPanel，2 commits + 全量浏览器 E2E），
已打包 dist-electron/ZLink Agent-1.9.0-arm64.dmg（含面板特性，版本未 bump）。
暗色主题是禁区（AGENTS.md §13）。本次任务：<在这里填你的任务>
```

第一个动作：`git log --oneline -5` 确认提交历史与上文一致。
