# HANDOVER

> 2026-08-24 会话交接。状态：**全部完成，无遗留开发任务**。

## 当前状态

- 分支 main @ v1.10.0，tag v1.10.0 已推送
- 最新 DMG：`dist-electron/ZLink Agent-1.10.0-arm64.dmg`（174MB）
- 测试：526 passed / ruff check + format 全干净 / 构建冒烟测试通过（61 工具）
- 服务已停止（8088/8089 端口已释放）

## 本会话产出

### 主线：U8 ERP 连接配置 + 内置查询工具

**commit** `f2cb618` — `feat: 新增 U8 ERP 连接配置和内置查询工具`

### 新增文件

| 文件 | 说明 |
|------|------|
| `agent/tools/erp_u8_tools.py` | 4 个内置工具（u8_query / u8_list_tables / u8_describe_table / u8_raw_sql） |
| `agent/skills/u8/SKILL.md` | U8 技能文档（含数据分析 HTML 报告规范） |

### 修改文件

| 文件 | 改动 |
| ------ | ------ |
| `web/src/pages/SettingsERPPage.tsx` | 新增 U8 页签（Host/Port/Database/User/Password/Max Rows） |
| `backend/api/erp_clients_api.py` | SECRET_FIELDS、ERPPutRequest、_apply_erp_env、get_erp_client、test_erp_client 加 u8 分支 |
| `backend/main.py` | lifespan 注入 U8 环境变量 |
| `agent/core/agent_adapter.py` | _ERP_LABELS 加 u8、_build_erp_context 加 U8 表清单注入 |
| `agent/tools/registry.py` | PyInstaller 冻结模式加 erp_u8_tools |
| `pyproject.toml` | 新增 pymssql>=2.2.0 依赖 |

### 归类修复 / 改进

| 修复 | 原因 |
|------|------|
| `execute_code` 长耗时工具心跳 | 每 5 秒发 ToolExecutionUpdate 事件，避免前端 spinner 卡死感 |
| `chat.py` 支持 tool_execution_update | 推送给前端显示"⏳ 执行中"提示 |
| 系统提示词路径规则 | 不硬编码用户名，提示用 `ls`/`find` 确认真实路径 |
| 技能路径说明 | 同时覆盖内置技能和用户安装技能 |

### 归类修复

| 修复 | 原因 |
| ------ | ------ |
| `_map_event_to_bus` 类型缩小假阳性 | isinstance 替代字符串匹配，补全 import |
| `_token`/`_llm_stop_event` 类型标注假阳性 | 加 `# type: ignore[assignment]` |
| `test_resolves_bare_command_via_path` | 文件缺执行权限 |
| `test_parse_empty_html` | `_pending` 属性名与 Python 3.14 HTMLParser 冲突 |
| `web_tools.py` limit 参数 | 加 `or 5` 兜底 |
| `toggle_mcp_server` json.loads | 加 try/except 兜底 |

### 真实数据验证

U8 数据库（62.234.158.154:1433/UFDATA_999_2014）12 个查询全部验证通过 ✅

## 已知事项

- 旧版 `HANDOFF.md` 已删除（内容被 `HANDOVER.md` 覆盖）
- 旧版 DMG（v1.9.4）已清理，仅保留 `dist-electron/ZLink Agent-1.10.0-arm64.dmg`
- U8 数据字典 `.chm` 文件在桌面，CHM 解析出的 HTML 在 `/tmp/u8_dict/`（如需解析完整字典建 JSON 文件，参考 NC 的 `scripts/parse_nc_dict_chm.py` 模式）
- Inventory（供应链用）和 bas_part（生产制造用）通过 `Inventory.cInvCode = bas_part.InvCode` 关联
- 主子表关联键：销售订单 `SO_SOMain.ID = SO_SODetails.ID`；采购订单 `PO_Pomain.POID = PO_Podetails.POID`；生产订单 `mom_order.MoId` 串联 `mom_orderdetail.MoId`

## 新会话入口

`git log --oneline -5` → `CHANGELOG.md` 顶部 v1.10.0 条目即本会话全部内容。
