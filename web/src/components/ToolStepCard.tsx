import { useState } from "react";
import {
  IconTool,
  IconChevronDown,
  IconChevronRight,
  IconCircleCheck,
  IconAlertCircle,
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
  const [open, setOpen] = useState(false);
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

  const failed = result ? isErrorResult(raw) : false;

  return (
    <div className="tool-step">
      <button type="button" className="tool-step-header" onClick={() => setOpen(!open)}>
        {open ? <IconChevronDown size={13} /> : <IconChevronRight size={13} />}
        <IconTool size={13} />
        <span className="tool-step-name">{call.function.name}</span>
        {result &&
          (failed ? (
            <span className="tool-step-status error">
              <IconAlertCircle size={13} /> 失败
            </span>
          ) : (
            <span className="tool-step-status ok">
              <IconCircleCheck size={13} /> 完成
            </span>
          ))}
      </button>
      {open && (
        <div className="tool-step-body">
          <div className="tool-step-label">参数</div>
          <pre>{formatJson(call.function.arguments)}</pre>
          {result && (
            <>
              <div className="tool-step-label">返回</div>
              <pre>{formatJson(raw)}</pre>
            </>
          )}
        </div>
      )}
    </div>
  );
}
