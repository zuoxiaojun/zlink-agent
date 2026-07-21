import { useState } from "react";
import {
  IconChevronDown,
  IconChevronRight,
  IconCircleCheck,
  IconAlertCircle,
  IconPlayerPlay,
  IconClock,
} from "@tabler/icons-react";
import type { Message, ToolCall } from "../types";

interface ToolStepCardProps {
  call: ToolCall;
  result?: Message;
  onChoiceSelect?: (text: string) => void;
}

// ── 工具名称映射 ──────────────────────────────────────

const TOOL_DISPLAY_NAMES: Record<string, string> = {
  terminal: "执行命令",
  execute_code: "执行代码",
  read_file: "读取文件",
  write_file: "写入文件",
  patch: "修改文件",
  search_files: "搜索文件",
  ls: "列出目录",
  glob: "搜索文件路径",
  web_search: "搜索网络",
  web_extract: "提取网页",
  vision_analyze: "分析图片",
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
  memory: "保存记忆",
  session_search: "搜索会话",
  clarify: "请求澄清",
  process: "管理进程",
  todo: "管理任务",
  tool_search: "搜索工具",
  tool_describe: "查看工具",
  tool_call: "调用工具",
};

// ── 工具函数 ──────────────────────────────────────────

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

function extractSubtitle(toolName: string, raw: string): string | null {
  let parsed: Record<string, unknown>;
  try { parsed = JSON.parse(raw); } catch { return null; }

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
  if (toolName.startsWith("query_") || toolName.startsWith("nc_")) {
    const dateFrom = String(parsed.date_from || "");
    const dateTo = String(parsed.date_to || "");
    if (dateFrom && dateTo) return `${dateFrom} ~ ${dateTo}`;
    return null;
  }
  return null;
}

function extractCount(raw: string): string | null {
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return `${parsed.length} 条`;
    if (parsed?.data && Array.isArray(parsed.data)) return `${parsed.data.length} 条`;
    if (parsed?.total !== undefined) return `${parsed.total} 条`;
    if (parsed?.count !== undefined) return `${parsed.count} 条`;
    if (parsed?.records && Array.isArray(parsed.records)) return `${parsed.records.length} 条`;
  } catch { /* ignore */ }
  return null;
}

// ── 主组件 ────────────────────────────────────────────

export default function ToolStepCard({ call, result, onChoiceSelect }: ToolStepCardProps) {
  const [open, setOpen] = useState(false);
  const raw = result ? resultText(result) : "";

  // clarify 工具的 choices 特判：先解析，再渲染
  if (result) {
    let parsed: { choices?: string[]; question?: string; data?: string } | null = null;
    try {
      const candidate = JSON.parse(raw) as { choices?: string[]; question?: string; data?: string };
      if (candidate && Array.isArray(candidate.choices)) parsed = candidate;
    } catch { /* 非 JSON，走普通渲染 */ }
    if (parsed) {
      return (
        <div className="clarify-prompt">
          <p className="clarify-question">{parsed.question || parsed.data || ""}</p>
          {parsed.choices && parsed.choices.length > 0 && (
            <div className="clarify-choices">
              {parsed.choices.map((choice, i) => (
                <button key={i} className="clarify-chip" onClick={() => onChoiceSelect?.(choice)}>
                  {choice}
                </button>
              ))}
            </div>
          )}
        </div>
      );
    }
  }

  const running = !result;
  const failed = result ? isErrorResult(raw) : false;
  const toolName = call.function.name;
  const displayName = TOOL_DISPLAY_NAMES[toolName] || toolName;
  const subtitle = extractSubtitle(toolName, running ? call.function.arguments : raw);
  const countLabel = result ? extractCount(raw) : null;

  return (
    <div className={`tool-step${running ? " tool-step-running" : ""}${failed ? " tool-step-error" : ""}`}>
      {/* 标题行 */}
      <button
        type="button"
        className="tool-step-header"
        onClick={running ? undefined : () => setOpen(!open)}
      >
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
          <div className="tool-step-header-text">
            <div className="tool-step-title-row">
              <span className="tool-step-name">{displayName}</span>
              {result && countLabel && (
                <span className="tool-step-count">{countLabel}</span>
              )}
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

      {/* 子标题行（文件路径 / 搜索词 / 命令等） */}
      {subtitle && (
        <div className="tool-step-subtitle">{subtitle}</div>
      )}

      {/* 展开详情 */}
      {open && result && (
        <div className="tool-step-body">
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
        </div>
      )}
    </div>
  );
}