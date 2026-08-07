# HANDOVER — 2026-08-07

> 面向看不到此前会话的新会话的交接文档。

## 当前状态

- 分支 `main`，与 origin/main 同步（atomgit），HEAD `4da5469`
- 工作区干净，无未提交改动
- 版本：v1.9.0（`pyproject.toml` 为版本唯一事实源；本次修复**未 bump 版本号**）
- 后端测试：514 passed（`.venv/bin/python -m pytest tests/`）
- 打包产物：`dist-electron/ZLink Agent-1.9.0-arm64.dmg`（170MB，2026-08-07 构建，含本次全部修复，未签名）
- Windows 包：尚未构建，需在 Windows 机器 Git Bash 里 `bash scripts/build-electron.sh --win`（原生构建，无需 wine）

## 本次会话完成的工作（5 个 commit）

1. `fdacca7` **ERP 工具门控修复**：NC/YonSuite 内置工具注册时缺 `check_fn`，ERP 停用后工具 schema 仍发给 LLM（此前只有 system prompt 标注 ❌）。新增 `_nc_enabled()`/`_ys_enabled()`（读 `erp_clients.<name>.enabled`，fail closed），15 个 `register()` 全部挂上门控；每次 `get_definitions()` 重新读配置，开关下条消息即生效。测试 `tests/test_erp_tool_gating.py`（5 个用例）。
2. `85e2086` **思考过程/流式修复**：`backend/api/chat.py` 调 `run_conversation_async()` 没传 `stream_callback`/`reasoning_callback`，而 adapter 以回调是否非 None 决定 `stream=True` 和 MessageUpdate 事件发射 → LLM 非流式、零 token/reasoning_token 帧，前端回答整块出现且无"思考过程"。修复 = 传两个 no-op 回调解锁流式开关（WS 转发走 `_on_event` 订阅，回调本体不需要做事）。已经浏览器实测修复前后对比验证。
3. `710d24d` **前端 Drawer 组件**（用户自己的未提交改动代为提交）：新增 `web/src/components/Drawer.tsx` + global.css 样式，Memory/SkillManager/Tools 三页详情面板迁移到 Drawer。
4. `c27be3b` **冒烟测试超时 15s→60s**（`scripts/build-pyinstaller.sh`）。
5. `4da5469` 构建脚本头注释修正（Windows 打包不需要 wine）。

## 关键决策与原因

- **推翻了 2026-08-05 交接里"冒烟 15s 上限保持不动"的决策**：旧结论说"重跑即过"，但本次发现 `build-pyinstaller.sh` 每次都会删掉并重建 `dist/zlink-backend/`（`COLLECT` 阶段），产物每次都是"首次执行"→ 每次都触发 macOS 安全扫描 → 每次构建都可能在冒烟测试挂掉，不是偶发。热启动实测仅 1.2s，60s 仍保留回归保护意义。
- **版本号未 bump**：用户只要求重新打包，没要求发布。dmg 覆盖了旧 1.9.0 包。若对外发布这批修复，需按 AGENTS.md §10 走 1.9.1 流程（pyproject.toml + package.json + CHANGELOG + README + tag）。
- **ERP 门控放在工具模块内（check_fn）而非 registry**：`agent/tools/registry.py` 是 ❌ 禁改区，check_fn 是既有扩展点。

## 已知问题 / 注意事项

- **adapter 的隐式契约**（`agent/core/agent_adapter.py:851-853`）：不传 callbacks 就静默退化为非流式、无 MessageUpdate 事件。调用方只有 chat.py，已在代码注释说明；若以后加调用方（如 cronjob 需要流式）要注意。
- `agent/tools/erp_nc_tools.py`、`erp_ys_tools.py` 存在**既有** `ruff format` 偏差（多行 dict 风格），与本次改动无关，未触碰。
- AGENTS.md §3 已把 "ERP isolation" 写成既定行为，但代码是本次会话才补上的——文档描述与实现现在一致了。
- 用户的 YonSuite SKILL.md 修改在旧 commit `6e983f1`（7-20）里，早已提交推送，无遗漏。

## 新会话启动提示词

```
Read HANDOVER.md 和 AGENTS.md。当前 main 与 origin 同步（HEAD 4da5469），v1.9.0，
最新 dmg 已含 ERP 门控 + 思考过程流式修复。版本未 bump，若发布需走 1.9.1 流程。
```

第一个动作：`git log --oneline -8` 确认提交历史与上文一致。
