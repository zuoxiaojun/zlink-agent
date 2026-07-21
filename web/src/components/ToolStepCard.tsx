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

export default function ToolStepCard({ call, result, onChoiceSelect }: ToolStepCardProps) {
  const [open, setOpen] = useState(true);
  const raw = result ? resultText(result) : "";

  // clarify 工具的 choices 特判：渲染为可点 chips（行为与原 ToolResult 一致）
  let parsed: { choices?: string[]; question?: string; data?: string } | null = null;
  if (result) {
    try {
      const candidate = JSON.parse(raw) as { choices?: string[]; question?: string; data?: string };
      if (candidate && Array.isArray(candidate.choices)) parsed = candidate;
    } catch {
      /* 非 JSON，走普通渲染 */
    }
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

  return (
    <div className={`tool-step${running ? " tool-step-running" : ""}${failed ? " tool-step-error" : ""}`}>
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
          <div>
            <div className="tool-step-name">{call.function.name}</div>
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
      {running && (
        <div className="tool-step-body">
          <div className="tool-step-section">
            <div className="tool-step-section-title">
              <IconPlayerPlay size={11} /> 参数
            </div>
            <pre>{formatJson(call.function.arguments)}</pre>
          </div>
        </div>
      )}
      {open && result && (
        <div className="tool-step-body">
          <div className="tool-step-section">
            <div className="tool-step-section-title">
              <IconPlayerPlay size={11} /> 参数
            </div>
            <pre>{formatJson(call.function.arguments)}</pre>
          </div>
          <div className="tool-step-section">
            <div className="tool-step-section-title">
              <IconClock size={11} /> 返回
            </div>
            <pre>{formatJson(raw)}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
