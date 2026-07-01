import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, User, Wrench, FileText, Zap, BarChart3 } from "lucide-react";
import type { Message } from "../types";

function ToolResult({ msg }: { msg: Message }) {
  const content = msg.content;
  return (
    <details className="tool-result-inline">
      <summary><FileText size={12} style={{ marginRight: "4px" }} />工具返回数据</summary>
      <pre>{typeof content === "string" ? content : JSON.stringify(content, null, 2)}</pre>
    </details>
  );
}

function ToolCallCard({ tc }: { tc: NonNullable<Message["tool_calls"]>[number] }) {
  return (
    <details className="tool-card">
      <summary><Wrench size={12} style={{ marginRight: "4px" }} />调用工具: {tc.function.name}</summary>
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

function AssistantGroupContent({ msgs }: { msgs: Message[] }) {
  return (
    <div className="msg-body" style={{ maxWidth: "85%" }}>
      {msgs.map((msg, i) => {
        if (msg.role === "tool") {
          return <ToolResult key={i} msg={msg} />;
        }
        if (msg.role === "assistant") {
          return (
            <div key={i}>
              {typeof msg.content === "string" && msg.content.trim() && (
                <div className="msg-bubble">
                  <MessageContent content={msg.content} />
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
              <span className="usage-item"><Zap size={12} /> {m._agent_info!.api_calls} 次调用</span>
              {m._agent_info!.token_usage && (
                <span className="usage-item">
                  <BarChart3 size={12} /> {m._agent_info!.token_usage.total_tokens.toLocaleString()} tokens
                </span>
              )}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ChatMessage({ msgs }: { msgs: Message[] }) {
  const first = msgs[0];
  if (first.role === "user") {
    return (
      <div className="msg-row user">
        <div className="msg-avatar"><User size={18} color="#fff" /></div>
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
      <div className="msg-avatar"><Bot size={18} /></div>
      <AssistantGroupContent msgs={msgs} />
    </div>
  );
}
