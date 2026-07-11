import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { IconRobot, IconUser, IconTool, IconFileText, IconBolt, IconChartBar, IconCircleCheck, IconCircleX } from "@tabler/icons-react";
import type { Message } from "../types";

/** Check if a tool result content is an approval_hook block message. */
function _isApprovalBlock(content: Message["content"]): boolean {
  return typeof content === "string" && content.includes("需要你的确认");
}

function ToolResult({ msg, onApprove, disabled }: { msg: Message; onApprove?: (approved: boolean) => void; disabled?: boolean }) {
  const content = msg.content;
  const isApproval = _isApprovalBlock(content);
  const [resolved, setResolved] = useState(false);

  return (
    <div>
      <details className="tool-result-inline">
        <summary><IconFileText size={12} style={{ marginRight: "4px" }} />工具返回数据</summary>
        <pre>{typeof content === "string" ? content : JSON.stringify(content, null, 2)}</pre>
      </details>
      {isApproval && onApprove && !disabled && !resolved && (
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button
            className="btn btn-primary"
            style={{ height: 32, fontSize: 13 }}
            onClick={() => { setResolved(true); onApprove(true); }}
          >
            <IconCircleCheck size={14} /> 批准
          </button>
          <button
            className="btn btn-secondary"
            style={{ height: 32, fontSize: 13 }}
            onClick={() => { setResolved(true); onApprove(false); }}
          >
            <IconCircleX size={14} /> 拒绝
          </button>
        </div>
      )}
      {resolved && (
        <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 6 }}>
          {onApprove ? "已操作" : ""}
        </div>
      )}
    </div>
  );
}

function ToolCallCard({ tc }: { tc: NonNullable<Message["tool_calls"]>[number] }) {
  return (
    <details className="tool-card">
      <summary><IconTool size={12} style={{ marginRight: "4px" }} />调用工具: {tc.function.name}</summary>
      <div className="tool-card-content">
        <pre>{tc.function.arguments}</pre>
      </div>
    </details>
  );
}

function MessageContent({ content }: { content: Message["content"] }) {
  if (typeof content === "string") {
    return <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>;
  }
  if (Array.isArray(content)) {
    return content.map((part, i) =>
      part.type === "text" ? (
        <ReactMarkdown remarkPlugins={[remarkGfm]} key={i}>{part.text || ""}</ReactMarkdown>
      ) : part.type === "image_url" ? (
        <img key={i} src={part.image_url?.url} alt="" style={{ maxWidth: "100%", borderRadius: "8px" }} />
      ) : null
    );
  }
  return <>{String(content)}</>;
}

function AssistantGroupContent({ msgs, onApprove, disabled }: { msgs: Message[]; onApprove?: (approved: boolean) => void; disabled?: boolean }) {
  return (
    <div className="msg-body" style={{ maxWidth: "85%" }}>
      {msgs.map((msg, i) => {
        if (msg.role === "tool") {
          return <ToolResult key={i} msg={msg} onApprove={onApprove} disabled={disabled} />;
        }
        if (msg.role === "assistant") {
          return (
            <div key={i}>
              {msg.reasoning_content && (
                <div className="reasoning-content">
                  {msg.reasoning_content}
                </div>
              )}
              {typeof msg.content === "string" && msg.content.trim() ? (
                <div className="msg-bubble">
                  <MessageContent content={msg.content} />
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
              {msg.tool_calls?.map((tc, j) => (
                <ToolCallCard key={j} tc={tc} />
              ))}
            </div>
          );
        }
        return null;
      })}
      {msgs.some(m => m._agent_info) && (
        <div className="usage-bar" style={{ justifyContent: "flex-start", paddingTop: "6px" }}>
          {msgs.filter(m => m._agent_info).map((m, i) => (
            <span key={i} style={{ display: "inline-flex", gap: "12px" }}>
              <span className="usage-item"><IconBolt size={12} /> {m._agent_info!.api_calls} 次调用</span>
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

export default function ChatMessage({ msgs, onApprove, disabled }: { msgs: Message[]; onApprove?: (approved: boolean) => void; disabled?: boolean }) {
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
      <AssistantGroupContent msgs={msgs} onApprove={onApprove} disabled={disabled} />
    </div>
  );
}
