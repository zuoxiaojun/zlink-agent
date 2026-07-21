import { IconRobot, IconUser, IconBolt, IconChartBar } from "@tabler/icons-react";
import type { Message, ToolCall } from "../types";
import MessageContent from "./MessageContent";
import ReasoningBlock from "./ReasoningBlock";
import ToolStepCard from "./ToolStepCard";

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

  return (
    <div className="msg-body">
      {msgs.map((msg, i) => {
        if (msg.role === "tool") {
          let call: ToolCall | undefined;
          if (msg.tool_call_id) {
            const idx = pending.findIndex((c) => c.id === msg.tool_call_id);
            if (idx >= 0) call = pending.splice(idx, 1)[0];
          }
          if (!call) call = pending.shift();
          if (!call) {
            // 无配对的历史 tool 消息：用兜底 call，保证 clarify chips 等仍能渲染
            call = { id: msg.tool_call_id || "", type: "function", function: { name: "tool", arguments: "{}" } };
          }
          return <ToolStepCard key={i} call={call} result={msg} onChoiceSelect={onChoiceSelect} />;
        }
        if (msg.role === "assistant") {
          if (msg.tool_calls) pending.push(...msg.tool_calls);
          const isStreaming = streaming === true && i === lastAssistantIdx;
          return (
            <div key={i}>
              {msg.reasoning_content && (
                <ReasoningBlock text={msg.reasoning_content} streaming={isStreaming} />
              )}
              {typeof msg.content === "string" && msg.content.trim() ? (
                <div className={`msg-bubble${isStreaming ? " streaming-text" : ""}`}>
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
            </div>
          );
        }
        return null;
      })}
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
