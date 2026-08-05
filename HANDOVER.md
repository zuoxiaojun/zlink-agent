# HANDOVER — 2026-08-05

> 面向看不到此前会话的新 opencode 会话的交接文档。

## 当前状态

- 分支 `main`，与 origin/main 同步（atomgit），tag `v1.8.1` 已推送
- 工作区干净，无未提交改动
- 版本：v1.8.1（`pyproject.toml` 为版本唯一事实源）
- 后端测试：378 passed（`.venv/bin/python -m pytest tests/ -q`）
- 前端：`npm run build` + `npm run lint` 全绿
- 打包产物：`dist-electron/ZLink Agent-1.8.1-arm64.dmg`（170MB，未分发，本地留存）

## 本次会话完成的工作

主题：**对话流式输出界面优化 + CSS 去重**，随后发布 v1.8.1。

流程产物（均已提交，docs/ 在 .gitignore 中，用 `git add -f` 提交）：
- Spec：`docs/superpowers/specs/2026-08-05-chat-streaming-ui-polish-design.md`（commit `8ccb72a`）
- Plan：`docs/superpowers/plans/2026-08-05-chat-streaming-ui-polish-plan.md`（10/10 task 全部勾选完成）

落地的 5 项改动（详见 `CHANGELOG.md` v1.8.1 条目）：
1. 流式渲染防闪烁：`web/src/components/StreamingMarkdown.tsx` + `web/src/utils/streamingSplit.ts`（闭合块 memo 冻结，仅尾部重解析）；验证脚本 `web/scripts/verify-streaming-split.ts`（16 条断言，`node` 直接跑）
2. Agent 状态条：`web/src/components/AgentStatusBar.tsx`（工具名 > progress > 思考中，mm:ss 耗时）；接线了此前从未 dispatch 的 `SET_CURRENT_TOOL`；删除 `ChatMessage.tsx` 死代码 `runningToolCard`
3. 滚动 rAF 节流（`ChatPage.tsx`），移除 `.chat-messages` 的 `scroll-behavior: smooth`（smooth 仅留"回到底部"按钮）
4. 视觉细节：呼吸光标（`.streaming-tail` 作用域）、msg-in 微调、工具卡过渡（均在 `web/src/styles/global.css`）
5. 清理 `global.css` 重复的 `.tool-step-title-row` / `.tool-step-count` 定义

关键 commit（功能 9 个）：`b971d15` → `020edcc` → `9032568` → `125916b` → `681e766` → `4fb2f2c` → `e5fd587` → `a97a67e` → `d0ee644`；版本 bump `408e305`。

## 关键决策与原因

- **不做暗色模式**：用户明确说非必须
- **不改后端/WS 协议**：后端 Envelope 的 `phase` 字段前端未接入（ws.ts/types/AppContext 均无），状态条只用已有 progress 消息；要显示实时 token 数需改后端，判定不划算
- **`IconWrench` → `IconTool`**：固定版本 `@tabler/icons-react@^3.44.0` 无 `IconWrench` 导出
- **冒烟 15s 上限保持不动**：首次运行未签名 onedir 后端时 macOS Gatekeeper 校验 `_internal/` dylib 会超 15s（已知现象，见 AGENTS.md §13），重跑即过，不要为了它调大上限

## 遗留待办（前端评审中确认过但未做的项）

按此前评审报告的优先级，下次可继续：
1. 宽屏布局：`.page-container` max-width 1040 在宽屏右侧大片空白；列表页可放宽/多列，配置页可左右两栏
2. 内联样式收敛：TSX 共 ~175 处 `style={{}}`（McpPage.tsx 51 处最多），应收敛为 CSS 类
3. TSX 硬编码颜色：`SettingsERPPage.tsx:395`（#B7EB8F/#FFA39E）等，绕过 CSS 变量体系
4. 历史对话页：右上角红色 hash 徽章无语义且占用主红色；删除按钮无二次确认
5. MCP 页操作图标（▶/↻/开关）无 tooltip
6. （大项，未承诺）暗色模式：颜色已全走 `:root` CSS 变量，加 `[data-theme="dark"]` 一套变量即可

## 已知问题 / 注意事项

- `docs/` 被 .gitignore 忽略，spec/plan 用 `git add -f` 提交（仓库惯例）
- implementer 子代理环境无再派生子代理能力，code review 均为会话内自审（结果均零 findings）
- 旧产物 `ZLink Agent-1.8.0-arm64.dmg` 已删除

## 新会话启动提示词

```
Read HANDOVER.md 和 AGENTS.md。当前 main 与 origin 同步，v1.8.1 已发布。
上次遗留的前端优化候选在 HANDOVER.md "遗留待办" 一节，先和我确认做哪项再开工。
```

第一个动作：`git log --oneline -15` 确认提交历史与上文一致。
