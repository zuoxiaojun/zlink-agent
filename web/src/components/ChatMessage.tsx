import { IconRobot, IconUser, IconBolt, IconChartBar } from "@tabler/icons-react";
import type { Message, ToolCall } from "../types";
import MessageContent from "./MessageContent";
import ReasoningBlock from "./ReasoningBlock";
import ToolStepCard from "./ToolStepCard";
import { useAppState } from "../context/AppContext";

function AssistantGroupContent({
  msgs,
  streaming,
  runningToolCard,
  onChoiceSelect,
}: {
  msgs: Message[];
  streaming?: boolean;
  runningToolCard?: React.ReactNode;
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
            call = { id: msg.tool_call_id || "", type: "function", function: { name: "tool", arguments: "{}" } };
          }
          return <ToolStepCard key={i} call={call} result={msg} onChoiceSelect={onChoiceSelect} />;
        }
        if (msg.role === "assistant") {
          if (msg.tool_calls) pending.push(...msg.tool_calls);
          const isStreaming = streaming === true && i === lastAssistantIdx;
          const hasContent =
            (typeof msg.content === "string" && msg.content.trim().length > 0) ||
            (Array.isArray(msg.content) && msg.content.length > 0);
          return (
            <div key={i}>
              {msg.reasoning_content && (
                <ReasoningBlock text={msg.reasoning_content} streaming={isStreaming} />
              )}
              {hasContent ? (
                <div className={`msg-bubble${isStreaming ? " streaming-text" : ""}`}>
                  <MessageContent content={msg.content} />
                </div>
              ) : isStreaming ? (
                <div className="msg-bubble">
                  <div className="thinking-indicator">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              ) : null}
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
      {runningToolCard}
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
  const { state } = useAppState();
  // 显示运行中卡片：currentToolName 有值且在流式进行中
  const showRunning = (streaming || state.currentToolName) && state.currentToolName ? true : false;

  const runningToolCard = showRunning ? (
    <div className="tool-step-group">
      <div className="tool-step tool-step-running">
        <div className="tool-step-header" style={{ cursor: 'default' }}>
          <div className="tool-step-header-left">
            <div className="tool-step-icon">
              <div className="tool-step-spinner" />
            </div>
            <div className="tool-step-header-text">
              <div className="tool-step-title-row">
                <span className="tool-step-name">{state.currentToolName}</span>
              </div>
              <div className="tool-step-desc">正在执行…</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  ) : null;

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
      <AssistantGroupContent msgs={msgs} streaming={streaming} runningToolCard={runningToolCard} onChoiceSelect={onChoiceSelect} />
    </div>
  );
}