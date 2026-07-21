import { useState } from "react";
import {
  IconChevronDown,
  IconChevronRight,
  IconCircleCheck,
  IconAlertCircle,
  IconPlayerPlay,
  IconClock,
  IconTerminal2,
  IconSearch,
  IconFileText,
} from "@tabler/icons-react";
import type { Message, ToolCall } from "../types";

interface ToolStepCardProps {
  call: ToolCall;
  result?: Message;
  onChoiceSelect?: (text: string) => void;
}

// ── 工具名称 → 显示名映射 ──────────────────────────────

const TOOL_DISPLAY_NAMES: Record<string, string> = {
  // 终端/代码
  terminal: "执行命令",
  execute_code: "执行代码",
  read_terminal: "查看终端历史",
  close_terminal: "关闭终端",
  // 文件
  read_file: "读取文件",
  write_file: "写入文件",
  patch: "修改文件",
  search_files: "搜索文件",
  ls: "列出目录",
  glob: "搜索文件路径",
  // 网络
  web_search: "搜索网络",
  web_extract: "提取网页",
  // 视觉
  vision_analyze: "分析图片",
  // ERP
  ys_api: "YonSuite API",
  query_sale_orders: "查询销售订单",
  query_purchase_orders: "查询采购订单",
  query_production_orders: "查询生产订单",
  query_stock: "查询库存",
  query_customers: "查询客户",
  query_vendors: "查询供应商",
  query_products: "查询物料",
  query_opportunities: "查询商机",
  query_vouchers: "查询凭证",
  query_user_todos: "查询待办",
  nc_query: "NC 查询",
  nc_list_tables: "NC 列出表",
  nc_describe_table: "NC 表结构",
  nc_raw_sql: "NC 原始 SQL",
  // 定时任务
  cronjob_list: "列出定时任务",
  cronjob_create: "创建定时任务",
  cronjob_delete: "删除定时任务",
  cronjob_run: "执行定时任务",
  cronjob_update: "更新定时任务",
  cronjob_toggle: "开关定时任务",
  // 技能
  skill_list: "列出技能",
  skill_view: "查看技能",
  skill_activate: "启用技能",
  skill_deactivate: "停用技能",
  skill_install: "安装技能",
  skill_export: "导出技能",
  // MCP
  mcp_list_servers: "列出 MCP 服务器",
  mcp_add_server: "添加 MCP 服务器",
  mcp_delete_server: "删除 MCP 服务器",
  mcp_toggle_server: "开关 MCP 服务器",
  mcp_test_server: "测试 MCP 连接",
  mcp_reload_servers: "重载 MCP 服务器",
  // 项目
  project_list: "列出项目",
  project_create: "创建项目",
  project_switch: "切换项目",
  // 记忆/搜索
  memory: "保存记忆",
  session_search: "搜索会话",
  // 其他
  clarify: "请求澄清",
  process: "管理进程",
  todo: "管理任务",
  delegate_task: "委托子任务",
  tool_search: "搜索工具",
  tool_describe: "查看工具",
  tool_call: "调用工具",
};



// ── 工具函数 ───────────────────────────────────────────

function formatJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

function resultText(msg: Message): string {
  return typeof msg.content === "string" ? msg.content : JSON.stringify(msg.content, null, 2);
}

function isErrorResult(text: string): boolean {
  const t = text.slice(0, 300).toLowerCase();
  return (
    t.includes('"error"') ||
    t.includes("error:") ||
    t.includes("exception") ||
    t.includes("traceback") ||
    t.includes("错误")
  );
}

function extractSubtitle(toolName: string, args: string): string | null {
  let parsed: Record<string, unknown>;
  try { parsed = JSON.parse(args); } catch { return null; }

  if (["read_file", "write_file", "patch"].includes(toolName)) {
    const path = String(parsed.path || parsed.file_path || "");
    return path || null;
  }
  if (toolName === "terminal") {
    return String(parsed.command || "").slice(0, 60);
  }
  if (toolName === "execute_code") {
    return String(parsed.code || "").slice(0, 60);
  }
  if (toolName === "web_search") {
    const q = String(parsed.query || parsed.search_term || "");
    return q ? `"${q.slice(0, 40)}"` : null;
  }
  if (toolName === "web_extract") {
    return String(parsed.url || "").slice(0, 60);
  }
  if (toolName === "vision_analyze") {
    return String(parsed.question || parsed.prompt || "").slice(0, 60) || null;
  }
  if (toolName === "memory") {
    return String(parsed.text || "").slice(0, 60) || null;
  }
  if (toolName === "process") {
    return String(parsed.action || "");
  }
  if (toolName.startsWith("query_") || toolName.startsWith("nc_")) {
    const dateFrom = String(parsed.date_from || "");
    const dateTo = String(parsed.date_to || "");
    if (dateFrom && dateTo) return `${dateFrom} ~ ${dateTo}`;
    if (dateFrom) return `从 ${dateFrom}`;
    return null;
  }
  if (toolName.startsWith("cronjob_")) {
    return String(parsed.name || parsed.schedule || "");
  }
  if (toolName === "todo") {
    return Array.isArray(parsed.todos) ? `${parsed.todos.length} 项` : null;
  }
  return null;
}

function extractCount(result: string): string | null {
  try {
    const parsed = JSON.parse(result);
    if (Array.isArray(parsed)) return `${parsed.length} 条`;
    if (parsed?.data && Array.isArray(parsed.data)) return `${parsed.data.length} 条`;
    if (parsed?.total !== undefined) return `${parsed.total} 条`;
    if (parsed?.count !== undefined) return `${parsed.count} 条`;
    if (parsed?.records && Array.isArray(parsed.records)) return `${parsed.records.length} 条`;
  } catch { /* ignore */ }
  return null;
}

function extractStdoutStderr(text: string): { stdout: string; stderr: string } | null {
  try {
    const parsed = JSON.parse(text);
    if (typeof parsed === "object" && parsed !== null) {
      const out = parsed.stdout || parsed.output || parsed.result || "";
      const err = parsed.stderr || parsed.error_detail || "";
      if (out || err) return { stdout: String(out), stderr: String(err) };
    }
  } catch { /* ignore */ }
  return null;
}

function extractSearchHits(text: string): { url: string; title: string }[] | null {
  try {
    const parsed = JSON.parse(text);
    let items: unknown[] | null = null;
    if (Array.isArray(parsed)) items = parsed;
    else if (Array.isArray(parsed?.results)) items = parsed.results;
    else if (Array.isArray(parsed?.hits)) items = parsed.hits;
    else if (Array.isArray(parsed?.items)) items = parsed.items;

    if (items && items.length > 0) {
      return items.slice(0, 5).map((item) => {
        const r = item as Record<string, unknown>;
        return {
          url: String(r.url || r.link || ""),
          title: String(r.title || r.name || ""),
        };
      });
    }
  } catch { /* ignore */ }
  return null;
}

// ── 主组件 ─────────────────────────────────────────────

export default function ToolStepCard({ call, result, onChoiceSelect }: ToolStepCardProps) {
  const [open, setOpen] = useState(true);
  const raw = result ? resultText(result) : "";

  // clarify 工具的 choices 特判
  let parsed: { choices?: string[]; question?: string; data?: string } | null = null;
  if (result) {
    try {
      const candidate = JSON.parse(raw) as { choices?: string[]; question?: string; data?: string };
      if (candidate && Array.isArray(candidate.choices)) parsed = candidate;
    } catch { /* 非 JSON，走普通渲染 */ }
  }

  if (parsed) {
    const choices = parsed.choices ?? [];
    return (
      <div className="clarify-prompt">
        <p className="clarify-question">{parsed.question || parsed.data || ""}</p>
        {choices.length > 0 && (
          <div className="clarify-choices">
            {choices.map((choice, i) => (
              <button key={i} className="clarify-chip" onClick={() => onChoiceSelect?.(choice)}>
                {choice}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  const running = !result;
  const failed = result ? isErrorResult(raw) : false;
  const toolName = call.function.name;
  const displayName = TOOL_DISPLAY_NAMES[toolName] || toolName;
  const subtitle = running ? extractSubtitle(toolName, call.function.arguments) : null;
  const resultSubtitle = result ? extractSubtitle(toolName, raw) : null;
  const countLabel = result ? extractCount(raw) : null;
  const terminalOutput = result ? extractStdoutStderr(raw) : null;
  const searchHits = result ? extractSearchHits(raw) : null;
  return (
    <div className={`tool-step${running ? " tool-step-running" : ""}${failed ? " tool-step-error" : ""}`}>
      {/* 标题行 */}
      <button type="button" className="tool-step-header" onClick={running ? undefined : () => setOpen(!open)}>
        <div className="tool-step-header-left">
          <div className="tool-step-icon">
            {running ? (
              <div className="tool-step-spinner" />
            ) : failed ? (
              <IconAlertCircle size={16} />
            ) : (
              <IconCircleCheck size={16} />
            )}
          </div>
          <div className="tool-step-title-col">
            <div className="tool-step-title-row">
              <span className="tool-step-name">{displayName}</span>
              {countLabel && <span className="tool-step-count">{countLabel}</span>}
            </div>
            <div className="tool-step-desc">
              {running ? "正在执行…" : failed ? "执行失败" : "执行完成"}
            </div>
          </div>
        </div>
        {result && (
          <div className="tool-step-header-right">
            {open ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
          </div>
        )}
      </button>

      {/* 子标题 - 文件路径/搜索词/命令等 */}
      {subtitle && running && (
        <div className="tool-step-subtitle">
          <span className="tool-step-subtitle-text">{subtitle}</span>
        </div>
      )}

      {/* 展开内容 */}
      {open && result && (
        <div className="tool-step-body">
          {/* 子标题 */}
          {resultSubtitle && (
            <div className="tool-step-subtitle">
              <span className="tool-step-subtitle-text">{resultSubtitle}</span>
            </div>
          )}

          {/* 终端专属输出 */}
          {terminalOutput && (
            <>
              {terminalOutput.stdout && (
                <div className="tool-step-section">
                  <div className="tool-step-section-title">
                    <IconTerminal2 size={11} /> 输出
                  </div>
                  <pre className="tool-step-terminal">{terminalOutput.stdout}</pre>
                </div>
              )}
              {terminalOutput.stderr && (
                <div className="tool-step-section">
                  <div className="tool-step-section-title">
                    <IconAlertCircle size={11} /> 错误
                  </div>
                  <pre className="tool-step-terminal tool-step-terminal-err">{terminalOutput.stderr}</pre>
                </div>
              )}
            </>
          )}

          {/* 搜索专属结果 */}
          {searchHits && !terminalOutput && (
            <div className="tool-step-section">
              <div className="tool-step-section-title">
                <IconSearch size={11} /> 搜索结果
              </div>
              <div className="tool-step-search-results">
                {searchHits.map((hit, i) => (
                  <div key={i} className="tool-step-search-result">
                    <span className="tool-step-search-result-title">{hit.title}</span>
                    {hit.url && <span className="tool-step-search-result-url">{hit.url}</span>}
                  </div>
                ))}
              </div>
              <div className="tool-step-section">
                <div className="tool-step-section-title">
                  <IconFileText size={11} /> 原始结果
                </div>
                <pre>{formatJson(raw)}</pre>
              </div>
            </div>
          )}

          {/* 默认 JSON 展示 */}
          {!terminalOutput && !searchHits && (
            <>
              {call.function.arguments && call.function.arguments !== "{}" && (
                <div className="tool-step-section">
                  <div className="tool-step-section-title">
                    <IconPlayerPlay size={11} /> 参数
                  </div>
                  <pre>{formatJson(call.function.arguments)}</pre>
                </div>
              )}
              {raw && (
                <div className="tool-step-section">
                  <div className="tool-step-section-title">
                    <IconClock size={11} /> 返回
                  </div>
                  <pre>{formatJson(raw)}</pre>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}