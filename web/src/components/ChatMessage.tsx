import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { IconRobot, IconUser, IconTool, IconFileText, IconBolt, IconChartBar } from "@tabler/icons-react";
import type { Message } from "../types";

function ToolResult({ msg, onChoiceSelect }: { msg: Message; onChoiceSelect?: (text: string) => void }) {
  const content = msg.content;

  // Render clarify choices as clickable chips that send the choice
  if (typeof content === "string") {
    try {
      const parsed = JSON.parse(content);
      if (parsed.choices && Array.isArray(parsed.choices)) {
        return (
          <div className="clarify-prompt">
            <p className="clarify-question">{parsed.question || parsed.data || ""}</p>
            {parsed.choices.length > 0 && (
              <div className="clarify-choices">
                {parsed.choices.map((choice: string, i: number) => (
                  <button key={i} className="clarify-chip" onClick={() => onChoiceSelect?.(choice)}>
                    {choice}
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      }
    } catch {
      /* not JSON, fall through */
    }
    return (
      <details className="tool-result-inline">
        <summary><IconFileText size={12} style={{ marginRight: "4px" }} />工具返回数据</summary>
        <pre>{content}</pre>
      </details>
    );
  }
  return (
    <details className="tool-result-inline">
      <summary><IconFileText size={12} style={{ marginRight: "4px" }} />工具返回数据</summary>
      <pre>{JSON.stringify(content, null, 2)}</pre>
    </details>
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

function AssistantGroupContent({ msgs, onChoiceSelect }: { msgs: Message[]; onChoiceSelect?: (text: string) => void }) {
  return (
    <div className="msg-body" style={{ maxWidth: "85%" }}>
      {msgs.map((msg, i) => {
        if (msg.role === "tool") {
          return <ToolResult key={i} msg={msg} onChoiceSelect={onChoiceSelect} />;
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

export default function ChatMessage({ msgs, onChoiceSelect }: { msgs: Message[]; onChoiceSelect?: (text: string) => void }) {
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
      <AssistantGroupContent msgs={msgs} onChoiceSelect={onChoiceSelect} />
    </div>
  );
}
