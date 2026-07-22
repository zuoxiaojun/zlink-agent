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

function formatJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
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
  if (toolName === "terminal") {
    return String(parsed.command || "").slice(0, 60) || null;
  }
  if (toolName === "execute_code") {
    return String(parsed.code || "").slice(0, 60) || null;
  }
  if (["read_file", "write_file", "patch"].includes(toolName)) {
    return String(parsed.path || parsed.file_path || "").slice(0, 60) || null;
  }
  if (toolName === "web_search") {
    const q = String(parsed.query || parsed.search_term || "");
    return q ? `"${q.slice(0, 40)}"` : null;
  }
  if (toolName === "web_extract") {
    return String(parsed.url || "").slice(0, 60) || null;
  }
  if (toolName.startsWith("query_") || toolName.startsWith("nc_")) {
    const dateFrom = String(parsed.date_from || "");
    const dateTo = String(parsed.date_to || "");
    if (dateFrom && dateTo) return `${dateFrom} ~ ${dateTo}`;
    return null;
  }
  return null;
}

export default function ToolStepCard({ call, result, onChoiceSelect }: ToolStepCardProps) {
  const [open, setOpen] = useState(false);
  const isPendingTool = result && result.tool_call_id && (result.tool_call_id.startsWith("running:") || result.tool_call_id.startsWith("pending:")) && !result._tool_done;
  // 直接从 result.content 提取文本内容
  const rawText = (() => {
    if (!result) return "";
    if (typeof result.content === "string") return result.content;
    if (Array.isArray(result.content)) {
      return result.content.map(p => p.type === "text" ? p.text || "" : "").join("\n");
    }
    return "";
  })();
  const raw = result && !isPendingTool && rawText.trim() ? rawText : "";
  const running = !result || isPendingTool;
  const failed = !running && raw.trim() ? isErrorResult(raw) : false;
  // 如果是 pending 工具，从 tool_call_id 提取工具名，从 content 提取参数
  const effectiveCallName = isPendingTool && result ? (result.tool_call_id || "").replace(/^(running:|pending:)/, "") : call.function.name;
  const effectiveArgs = isPendingTool && result ? (typeof result.content === "string" ? result.content : "") : call.function.arguments;
  const toolName = effectiveCallName;
  const displayName = TOOL_DISPLAY_NAMES[toolName] || toolName;
  const subtitle = extractSubtitle(toolName, effectiveArgs);

  // 提前解析 clarify 结果，避免 JSX 在 try/catch 内
  let clarifyParsed: { choices?: string[]; question?: string; data?: string } | null = null;
  if (result && raw.trim()) {
    try {
      const candidate = JSON.parse(raw) as { choices?: string[]; question?: string; data?: string };
      if (candidate && Array.isArray(candidate.choices)) clarifyParsed = candidate;
    } catch { /* ignore */ }
  }
  if (clarifyParsed) {
    return (
      <div className="clarify-prompt">
        <p className="clarify-question">{clarifyParsed.question || clarifyParsed.data || ""}</p>
        {clarifyParsed.choices && clarifyParsed.choices.length > 0 && (
          <div className="clarify-choices">
            {clarifyParsed.choices.map((choice, i) => (
              <button key={i} className="clarify-chip" onClick={() => onChoiceSelect?.(choice)}>
                {choice}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={`tool-step${running ? " tool-step-running" : ""}${failed ? " tool-step-error" : ""}`}>
      <button type="button" className="tool-step-header" onClick={running ? undefined : () => setOpen(!open)}>
        <div className="tool-step-header-left">
          <div className="tool-step-icon">
            {running ? <div className="tool-step-spinner" /> : failed ? <IconAlertCircle size={16} /> : <IconCircleCheck size={16} />}
          </div>
          <div className="tool-step-header-text">
            <div className="tool-step-title-row">
              <span className="tool-step-name">{displayName}</span>
            </div>
            <div className="tool-step-desc">{running ? "正在执行…" : failed ? "执行失败" : "执行完成"}</div>
          </div>
        </div>
        {result && <div className="tool-step-header-right">{open ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}</div>}
      </button>
      {subtitle && <div className="tool-step-subtitle">{subtitle}</div>}
      {open && result && (
        <div className="tool-step-body">
          {call.function.arguments && call.function.arguments !== "{}" && (
            <div className="tool-step-section">
              <div className="tool-step-section-title"><IconPlayerPlay size={11} /> 参数</div>
              <pre>{formatJson(call.function.arguments)}</pre>
            </div>
          )}
          {raw && (
            <div className="tool-step-section">
              <div className="tool-step-section-title"><IconClock size={11} /> 返回</div>
              <pre>{formatJson(raw)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}