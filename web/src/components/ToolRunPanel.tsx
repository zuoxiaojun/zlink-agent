import { useEffect, useRef, useState } from "react";
import {
  IconChevronDown,
  IconChevronRight,
  IconCircleCheck,
  IconAlertCircle,
  IconAlertTriangle,
  IconPlayerPlay,
  IconClock,
  IconTool,
} from "@tabler/icons-react";
import type { Message, ToolCall } from "../types";

export interface ToolRunEntry {
  call: ToolCall;
  result: Message;
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
    return String(parsed.command || "").slice(0, 200) || null;
  }
  if (toolName === "execute_code") {
    return String(parsed.code || "").slice(0, 200) || null;
  }
  if (["read_file", "write_file", "patch"].includes(toolName)) {
    return String(parsed.path || parsed.file_path || "").slice(0, 200) || null;
  }
  if (["ls", "search_files", "glob"].includes(toolName)) {
    return String(parsed.path || parsed.pattern || parsed.directory || "").slice(0, 200) || null;
  }
  if (toolName === "web_search") {
    const q = String(parsed.query || parsed.search_term || "");
    return q ? `"${q.slice(0, 80)}"` : null;
  }
  if (toolName === "web_extract") {
    return String(parsed.url || "").slice(0, 200) || null;
  }
  if (toolName === "tool_search") {
    return String(parsed.query || "").slice(0, 200) || null;
  }
  if (toolName === "tool_describe" || toolName === "tool_call") {
    return String(parsed.name || "").slice(0, 200) || null;
  }
  if (toolName.startsWith("query_") || toolName.startsWith("nc_")) {
    const dateFrom = String(parsed.date_from || "");
    const dateTo = String(parsed.date_to || "");
    if (dateFrom && dateTo) return `${dateFrom} ~ ${dateTo}`;
    return null;
  }
  return null;
}

function isPendingResult(result: Message): boolean {
  const id = result.tool_call_id || "";
  return (id.startsWith("running:") || id.startsWith("pending:")) && !result._tool_done;
}

function rawTextOf(result: Message): string {
  if (typeof result.content === "string") return result.content;
  if (Array.isArray(result.content)) {
    return result.content.map(p => p.type === "text" ? p.text || "" : "").join("\n");
  }
  return "";
}

function formatSecs(ms: number): string {
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatElapsed(ms: number): string {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const mm = String(Math.floor(totalSec / 60)).padStart(2, "0");
  const ss = String(totalSec % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

interface RowInfo {
  name: string;
  displayName: string;
  args: string;
  subtitle: string | null;
  pending: boolean;
  denied: boolean;
  failed: boolean;
  raw: string;
  durationMs?: number;
}

function toRowInfo(entry: ToolRunEntry): RowInfo {
  const { call, result } = entry;
  const pending = isPendingResult(result);
  const rawText = rawTextOf(result);
  const raw = !pending && rawText.trim() ? rawText : "";
  const name = pending
    ? (result.tool_call_id || "").replace(/^(running:|pending:)/, "")
    : call.function.name;
  const args = result._tool_args ??
    (pending && typeof result.content === "string" && result.content.trim() ? result.content : call.function.arguments);
  const denied = result._denied === true;
  const failed = !pending && !denied && raw.trim() ? isErrorResult(raw) : false;
  return {
    name,
    displayName: TOOL_DISPLAY_NAMES[name] || name,
    args,
    subtitle: extractSubtitle(name, args),
    pending,
    denied,
    failed,
    raw,
    durationMs: result._tool_duration_ms,
  };
}

function RowIcon({ row }: { row: RowInfo }) {
  if (row.pending) return <span className="tool-step-spinner" />;
  if (row.denied) return <IconAlertTriangle size={14} />;
  if (row.failed) return <IconAlertCircle size={14} />;
  return <IconCircleCheck size={14} />;
}

export default function ToolRunPanel({ entries, live }: { entries: ToolRunEntry[]; live?: boolean }) {
  const rows = entries.map(toRowInfo);
  const pendingCount = rows.filter(r => r.pending).length;
  const hasPending = pendingCount > 0;
  const doneCount = rows.length - pendingCount;

  const [manualExpanded, setManualExpanded] = useState<boolean | null>(null);
  // live（本轮进行中）时保持展开累积行，否则折叠；手动操作优先
  const expanded = manualExpanded ?? (live === true);
  const [openIdx, setOpenIdx] = useState<number | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const startBase = (() => {
    let min: number | null = null;
    for (const e of entries) {
      const s = e.result._tool_started_at;
      if (s != null && (min === null || s < min)) min = s;
    }
    return min;
  })();

  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!hasPending && !live) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [hasPending, live]);

  useEffect(() => {
    if (!hasPending || !expanded) return;
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [entries.length, doneCount, hasPending, expanded]);

  const wallMs = (() => {
    let min: number | null = null;
    let max: number | null = null;
    for (const e of entries) {
      const s = e.result._tool_started_at;
      const d = e.result._tool_duration_ms;
      if (s != null && d != null) {
        if (min === null || s < min) min = s;
        if (max === null || s + d > max) max = s + d;
      }
    }
    return min !== null && max !== null && max > min ? max - min : null;
  })();

  const timeText = (live || hasPending) && startBase !== null
    ? formatElapsed(now - startBase)
    : wallMs !== null ? formatSecs(wallMs) : null;

  if (!expanded) {
    const errCount = rows.filter(r => r.failed).length;
    const deniedCount = rows.filter(r => r.denied).length;
    const okCount = rows.length - pendingCount - errCount - deniedCount;
    const statusParts: string[] = [];
    if (hasPending) statusParts.push(`${doneCount}/${rows.length} 完成`);
    if (!hasPending && errCount === 0 && deniedCount === 0) {
      statusParts.push("全部成功");
    } else {
      if (okCount > 0) statusParts.push(`${okCount} 成功`);
      if (errCount > 0) statusParts.push(`${errCount} 失败`);
      if (deniedCount > 0) statusParts.push(`${deniedCount} 已拒绝`);
    }
    const statusClass = errCount > 0 ? "tool-run-summary-status-err" : deniedCount > 0 ? "tool-run-summary-status-denied" : "";
    return (
      <div className="tool-run-summary" onClick={() => setManualExpanded(true)} title="展开工具执行详情">
        <IconTool size={13} />
        <span className="tool-run-count">{rows.length} 个工具</span>
        <span className={statusClass}>{statusParts.join(" · ")}</span>
        {timeText && <span className="tool-run-elapsed">{hasPending ? timeText : `共 ${timeText}`}</span>}
        <span className="tool-run-chevron"><IconChevronRight size={14} /></span>
      </div>
    );
  }

  return (
    <div className="tool-run-panel">
      <div className="tool-run-panel-header" onClick={() => setManualExpanded(false)} title="收起">
        {hasPending ? <span className="tool-step-spinner" /> : <IconTool size={13} />}
        <span className="tool-run-count">工具执行 · {doneCount}/{rows.length}</span>
        {timeText && <span className="tool-run-elapsed">{timeText}</span>}
        <span className="tool-run-chevron"><IconChevronDown size={14} /></span>
      </div>
      <div className="tool-run-list" ref={listRef}>
        {rows.map((row, i) => {
          const statusClass = row.pending ? "tool-run-row-running" : row.denied ? "tool-run-row-denied" : row.failed ? "tool-run-row-err" : "tool-run-row-ok";
          const clickable = !row.pending;
          return (
            <div key={i}>
              <div
                className={`tool-run-row ${statusClass}${clickable ? " tool-run-row-clickable" : ""}`}
                onClick={clickable ? () => setOpenIdx(openIdx === i ? null : i) : undefined}
              >
                <span className="tool-run-row-icon"><RowIcon row={row} /></span>
                <span className="tool-run-row-name">{row.displayName}</span>
                <span className="tool-run-row-sub">{row.subtitle || (row.pending ? "正在执行…" : row.denied ? "已拒绝" : row.failed ? "执行失败" : "")}</span>
                <span className="tool-run-row-dur">{row.durationMs != null ? formatSecs(row.durationMs) : ""}</span>
              </div>
              {openIdx === i && clickable && (
                <div className="tool-run-row-detail">
                  {row.args && row.args !== "{}" && (
                    <div>
                      <div className="tool-run-detail-title"><IconPlayerPlay size={11} /> 参数</div>
                      <pre>{formatJson(row.args)}</pre>
                    </div>
                  )}
                  {row.raw && (
                    <div>
                      <div className="tool-run-detail-title"><IconClock size={11} /> 返回</div>
                      <pre>{formatJson(row.raw)}</pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
