# HANDOVER

> 2026-08-12 会话交接。状态：**全部完成，无遗留开发任务**。

## 当前状态

- 分支 main @ v1.9.3，tag v1.9.1 / v1.9.2 / v1.9.3 均已推送 gitcode
- 最新 DMG：`dist-electron/ZLink Agent-1.9.3-arm64.dmg`
- dev 服务可能仍在跑（`./start.sh stop` 停止；日志 /tmp/zlink-dev.log）
- CHM 解包临时目录 `/tmp/nc_dict`（重跑解析器还要用，系统清理后重新 `7z x` 即可）

## 本会话产出（2 个 commit）

0. **v1.9.3**（下午追加）：terminal 危险命令检测误杀修正——pipe to shell 只拦 `curl|wget … | bash/sh`，write to block device 只拦磁盘设备节点（原规则把 `2>/dev/null`、`curl | head` 全误杀）。起因：排查客户端会话「调一次工具就停」发现主因是弱模型口播代替 tool call，安全钩子误拦是加重因素

1. **v1.9.1** `c0918ff`：NC 扩展数据字典体系（CHM 解析脚本 + 548 表随包分发）+ `nc_list_tables` keyword 搜索 + `nc_describe_table` 枚举渲染/ALL_TAB_COLUMNS 兜底 + prompt 精选表注入 + 打包版 cryptography 修复（DPY-3016）
2. **v1.9.2** `60fab4d`：`nc_query` 新增 `gl_voucher`/`gl_balance` 预制查询（9→11 种）+ 解析器同名表取字段最丰富修正 + nc_query 参数白名单

## 关键决策

- 字典三层架构：精选层（6 表进 prompt）→ 扩展层（CHM 解析 548 表，含枚举）→ 实时层（ALL_TAB_COLUMNS 兜底）
- 字典随 git + PyInstaller 分发（客户端开箱即用），DATA_DIR 副本为本地覆盖层优先
- 模块范围 = so,pu,ic,gl,arap,cmp + 零散补表；**uapbd（基础档案 409 表）未选**，以后想要客户/供应商完整字段只需 `--modules` 加 uapbd 重跑解析器并覆盖两处 JSON
- NC 公网直连维持现状（用户家 IP 被服务端白名单拦，调试用手机热点）

## 已知事项

- 客户 NC 是医疗行业版；GL_BALANCE 空是因为凭证未记账（数据问题非 bug）
- 单轮深查对话 token 偏高（~13 万）：describe 全量渲染所致，如成问题可做字段分页
- `zlink-backend.spec` 被 .gitignore 拦截（构建实际走 build-pyinstaller.sh 的 --add-data，spec 仅参考）

## 新会话入口

`git log --oneline -3` → CHANGELOG.md 顶部两个版本条目即本会话全部内容。
