import { useRef, useEffect } from "react";
import { Bot, Zap, BarChart3 } from "lucide-react";
import { useAppState } from "../context/AppContext";
import { useChat } from "../hooks/useChat";
import ChatMessage from "../components/ChatMessage";
import ChatInput from "../components/ChatInput";
import StreamingText from "../components/StreamingText";
import StopButton from "../components/StopButton";

export default function ChatPage() {
  const { state } = useAppState();
  const { sendMessage, stopAgent } = useChat();
  const scrollRef = useRef<HTMLDivElement>(null);
  const userScrolledUp = useRef(false);

  useEffect(() => {
    if (!userScrolledUp.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [state.messages, state.streamingText]);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    userScrolledUp.current = el.scrollHeight - el.scrollTop - el.clientHeight > 150;
  };

  return (
    <div className="chat-container">
      <div className="chat-messages" ref={scrollRef} onScroll={handleScroll}>
        {state.messages.map((msg, i) => (
          <ChatMessage key={i} msg={msg} />
        ))}

        {state.agentRunning && (
          <div className="msg-row assistant">
            <div className="msg-avatar"><Bot size={18} /></div>
            <div className="msg-body" style={{ maxWidth: "85%" }}>
              <StreamingText text={state.streamingText} />
            </div>
          </div>
        )}
      </div>

      {state.agentRunning && (
        <>
          <StopButton onStop={stopAgent} />
          {state.progressMessage && (
            <div className="progress-text" style={{ paddingBottom: "4px" }}>
              <span className="thinking-indicator" style={{ display: "inline-flex", gap: "3px" }}>
                <span style={{ width: "4px", height: "4px" }} />
                <span style={{ width: "4px", height: "4px" }} />
                <span style={{ width: "4px", height: "4px" }} />
              </span>
              {state.progressMessage}
            </div>
          )}
        </>
      )}

      {state.tokenUsage && !state.agentRunning && (
        <div className="usage-bar">
          <span className="usage-item"><Zap size={12} /> 共 {state.apiCalls} 次 API 调用</span>
          {state.tokenUsage.total_tokens > 0 && (
            <span className="usage-item">
              <BarChart3 size={12} /> 输入 {state.tokenUsage.prompt_tokens.toLocaleString()} · 输出 {state.tokenUsage.completion_tokens.toLocaleString()} · 总计 {state.tokenUsage.total_tokens.toLocaleString()} tokens
            </span>
          )}
        </div>
      )}

      <ChatInput
        onSubmit={(c) => { userScrolledUp.current = false; sendMessage(c); }}
        disabled={state.agentRunning}
        placeholder={state.agentRunning ? "AI 正在思考中，请稍候..." : "输入你的问题，Enter 发送..."}
      />
    </div>
  );
}
