import { IconRobot, IconUser, IconTool, IconFileText, IconBolt, IconChartBar } from "@tabler/icons-react";
import MessageContent from "./MessageContent";
import type { Message } from "../types";

function ToolResult({ msg, onChoiceSelect }: { msg: Message; onChoiceSelect?: (text: string) => void }) {
  const content = msg.content;

  // Render clarify choices as clickable chips that send the choice
  if (typeof content === "string") {
    let parsed: { choices?: string[]; question?: string; data?: string } | null = null;
    try {
      const candidate = JSON.parse(content);
      if (candidate.choices && Array.isArray(candidate.choices)) {
        parsed = candidate;
      }
    } catch {
      /* not JSON, fall through */
    }

    if (parsed) {
      return (
        <div className="clarify-prompt">
          <p className="clarify-question">{parsed.question || parsed.data || ""}</p>
          {parsed.choices && parsed.choices.length > 0 && (
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
