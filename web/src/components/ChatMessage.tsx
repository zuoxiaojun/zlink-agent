import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, User, Wrench, FileText, Zap, BarChart3 } from "lucide-react";
import type { Message } from "../types";

export default function ChatMessage({ msg }: { msg: Message }) {
  const content = msg.content;

  // Tool result message
  if (msg.role === "tool") {
    return (
      <div className="msg-row tool">
        <div className="msg-avatar"><Wrench size={16} /></div>
        <div className="msg-body">
          <details className="tool-result-inline">
            <summary><FileText size={12} style={{ marginRight: "4px" }} />工具返回数据</summary>
            <pre>{typeof content === "string" ? content.substring(0, 3000) : JSON.stringify(content, null, 2).substring(0, 3000)}</pre>
          </details>
        </div>
      </div>
    );
  }

  // Assistant with tool calls
  if (msg.role === "assistant" && msg.tool_calls) {
    return (
      <div className="msg-row assistant">
        <div className="msg-avatar"><Bot size={18} /></div>
        <div className="msg-body" style={{ maxWidth: "85%" }}>
          {typeof content === "string" && content.trim() && (
            <div className="msg-bubble">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </div>
          )}
          {msg.tool_calls.map((tc, i) => (
            <details key={i} className="tool-card">
              <summary><Wrench size={12} style={{ marginRight: "4px" }} />调用工具: {tc.function.name}</summary>
              <div className="tool-card-content">
                <pre>{tc.function.arguments}</pre>
              </div>
            </details>
          ))}
        </div>
      </div>
    );
  }

  // Normal messages
  const isUser = msg.role === "user";
  return (
    <div className={`msg-row ${msg.role}`}>
      <div className="msg-avatar">
        {isUser ? <User size={18} color="#fff" /> : <Bot size={18} />}
      </div>
      <div className="msg-body">
        <div className="msg-bubble">
          {typeof content === "string" ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          ) : Array.isArray(content) ? (
            content.map((part, i) =>
              part.type === "text" ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]} key={i}>{part.text || ""}</ReactMarkdown>
              ) : part.type === "image_url" ? (
                <img key={i} src={part.image_url?.url} alt="" style={{ maxWidth: "100%", borderRadius: "8px" }} />
              ) : null
            )
          ) : (
            <>{String(content)}</>
          )}
        </div>
        {msg.role === "assistant" && msg._agent_info && (
          <div className="usage-bar" style={{ justifyContent: "flex-start", paddingTop: "6px" }}>
            <span className="usage-item"><Zap size={12} /> {msg._agent_info.api_calls} 次调用</span>
            {msg._agent_info.token_usage && (
              <span className="usage-item">
                <BarChart3 size={12} /> {msg._agent_info.token_usage.total_tokens.toLocaleString()} tokens
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
