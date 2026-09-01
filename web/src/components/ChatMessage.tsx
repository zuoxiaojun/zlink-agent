import type { ReactNode } from "react";
import { IconRobot, IconUser, IconBolt, IconChartBar } from "@tabler/icons-react";
import type { Message, ToolCall } from "../types";
import MessageContent from "./MessageContent";
import ReasoningBlock from "./ReasoningBlock";
import StreamingMarkdown from "./StreamingMarkdown";
import ToolStepCard from "./ToolStepCard";
import ToolRunPanel, { type ToolRunEntry } from "./ToolRunPanel";

function isClarifyMessage(msg: Message): boolean {
  const id = msg.tool_call_id || "";
  if (id.replace(/^(running:|pending:)/, "") === "clarify") return true;
  const text = typeof msg.content === "string" ? msg.content : "";
  if (!text.trim()) return false;
  try {
    const candidate = JSON.parse(text) as { choices?: unknown };
    return !!(candidate && Array.isArray(candidate.choices));
  } catch {
    return false;
  }
}

function AssistantGroupContent({
  msgs,
  streaming,
  onChoiceSelect,
}: {
  msgs: Message[];
  streaming?: boolean;
  onChoiceSelect?: (text: string) => void;
}) {
  const pending: ToolCall[] = [];
  const lastAssistantIdx = msgs.reduce((acc, m, i) => (m.role === "assistant" ? i : acc), -1);
  const nodes: ReactNode[] = [];
  let run: ToolRunEntry[] = [];

  const flushRun = (key: string) => {
    if (run.length > 0) {
      nodes.push(<ToolRunPanel key={key} entries={run} live={streaming === true} />);
      run = [];
    }
  };

  msgs.forEach((msg, i) => {
    if (msg.role === "tool") {
      let call: ToolCall | undefined;
      if (msg.tool_call_id) {
        const idx = pending.findIndex((c) => c.id === msg.tool_call_id);
        if (idx >= 0) call = pending.splice(idx, 1)[0];
      }
      if (!call) call = pending.shift();
      if (!call) {
        // 从 tool_call_id 提取工具名（pending:xx 格式）
        const toolName = msg.tool_call_id?.startsWith("pending:")
          ? msg.tool_call_id.replace("pending:", "")
          : "tool";
        call = {
          id: msg.tool_call_id || "",
          type: "function" as const,
          function: {
            name: toolName,
            arguments: typeof msg.content === "string" ? msg.content : "{}",
          },
        };
      }
      if (isClarifyMessage(msg)) {
        flushRun(`run-${i}`);
        nodes.push(<ToolStepCard key={i} call={call} result={msg} onChoiceSelect={onChoiceSelect} />);
      } else {
        run.push({ call, result: msg });
      }
      return;
    }
    if (msg.role === "assistant") {
      if (msg.tool_calls) pending.push(...msg.tool_calls);
      const isStreaming = streaming === true && i === lastAssistantIdx;
      const hasContent =
        (typeof msg.content === "string" && msg.content.trim().length > 0) ||
        (Array.isArray(msg.content) && msg.content.length > 0);
      if (!hasContent && !isStreaming) return;
      flushRun(`run-${i}`);
      nodes.push(
        <div key={i}>
          {msg.reasoning_content && (
            /* key 随 isStreaming 翻转→重挂载，从而把展开态重置为 defaultOpen */
            <ReasoningBlock
              key={isStreaming ? "open" : "closed"}
              text={msg.reasoning_content}
              defaultOpen={isStreaming}
            />
          )}
          {hasContent ? (
            <div className={`msg-bubble${isStreaming ? " streaming-text" : ""}`}>
              {isStreaming && typeof msg.content === "string" ? (
                <StreamingMarkdown text={msg.content} />
              ) : (
                <MessageContent content={msg.content} />
              )}
            </div>
          ) : (
            <div className="msg-bubble">
              <div className="thinking-indicator">
                <span />
                <span />
                <span />
              </div>
            </div>
          )}
        </div>
      );
    }
  });
  flushRun("run-end");

  return (
    <div className="msg-body">
      {nodes}
      {msgs.some((m) => m._agent_info) && (
        <div className="usage-bar usage-bar-inline">
          {msgs
            .filter((m) => m._agent_info)
            .map((m, i) => (
              <span key={i} style={{ display: "inline-flex", gap: "12px" }}>
                <span className="usage-item">
                  <IconBolt size={12} /> {m._agent_info!.api_calls} 次调用
                </span>
                {m._agent_info!.token_usage && (
                  <span className="usage-item">
                    <IconChartBar size={12} /> {m._agent_info!.token_usage.total_tokens.toLocaleString()} tokens
                  </span>
                )}
              </span>
            ))}
        </div>
      )}
    </div>
  );
}

export default function ChatMessage({
  msgs,
  streaming,
  onChoiceSelect,
}: {
  msgs: Message[];
  streaming?: boolean;
  onChoiceSelect?: (text: string) => void;
}) {
  const first = msgs[0];
  if (first.role === "user") {
    return (
      <div className="msg-row user">
        <div className="msg-avatar"><IconUser size={18} color="#fff" /></div>
        <div className="msg-body">
          <div className="msg-bubble">
            <MessageContent content={first.content} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="msg-row assistant">
      <div className="msg-avatar"><IconRobot size={18} /></div>
      <AssistantGroupContent msgs={msgs} streaming={streaming} onChoiceSelect={onChoiceSelect} />
    </div>
  );
}
