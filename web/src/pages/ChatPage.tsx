import { useRef, useEffect, useState, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { IconBolt, IconChartBar } from "@tabler/icons-react";
import { useAppState } from "../context/AppContext";
import { useChat } from "../hooks/useChat";
import { api } from "../api/http";
import ChatMessage from "../components/ChatMessage";
import ChatInput from "../components/ChatInput";
import ApprovalCard from "../components/ApprovalCard";
import type { Message, SessionDetail, ApprovalState } from "../types";
import StopButton from "../components/StopButton";

export default function ChatPage() {
  const { state, dispatch } = useAppState();
  const [approval, setApproval] = useState<ApprovalState | null>(null);
  const autoSentRef = useRef(false);
  const { sendMessage, stopAgent, sendApproval } = useChat({
    onApprovalRequest: (payload) => {
      setApproval({ ...payload, resolved: false });
    },
  });
  const scrollRef = useRef<HTMLDivElement>(null);
  const userScrolledUp = useRef(false);
  const [searchParams, setSearchParams] = useSearchParams();

  // Derive active approval from state — no setState in effects
  const activeApproval: ApprovalState | null = useMemo(
    () => (state.agentRunning ? approval : null),
    [approval, state.agentRunning],
  );

  // Restore session from URL param ?s=
  useEffect(() => {
    const sid = searchParams.get("s");
    if (!sid) return;
    if (state.currentSessionId === sid) return; // already loaded
    api.get<SessionDetail>(`/sessions/${sid}`)
      .then((s) => {
        const msgs = s.messages || [];
        dispatch({
          type: "SET_SESSION",
          sessionId: s.id,
          title: s.title || "",
          messages: msgs.length > 0 ? msgs : undefined,
        });
      })
      .catch(() => {
        setSearchParams({}, { replace: true });
      });
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-send prompt from cronjob (param ?auto=)
  useEffect(() => {
    const autoPrompt = searchParams.get("auto");
    const sid = searchParams.get("s");
    if (!autoPrompt || autoSentRef.current || !sid) return;

    // Clean URL first to prevent re-trigger
    const newParams = new URLSearchParams(searchParams);
    newParams.delete("auto");
    setSearchParams(newParams, { replace: true });

    autoSentRef.current = true;
    // Pass session_id from URL directly to avoid using stale state.currentSessionId
    sendMessage(autoPrompt, sid);
  }, [searchParams, sendMessage, setSearchParams]);

  // Sync URL when session changes (e.g. after first message creates session)
  useEffect(() => {
    if (!state.currentSessionId) return;
    const current = searchParams.get("s");
    if (current !== state.currentSessionId) {
      setSearchParams({ s: state.currentSessionId }, { replace: true });
    }
  }, [state.currentSessionId, searchParams, setSearchParams]);

  useEffect(() => {
    if (!userScrolledUp.current && scrollRef.current) {
      requestAnimationFrame(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
      });
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
{(() => {
          const groups: typeof state.messages[] = [];
          for (const msg of state.messages) {
            if (msg.role === "user") {
              groups.push([msg]);
            } else {
              if (groups.length > 0 && groups[groups.length - 1][0].role !== "user") {
                groups[groups.length - 1].push(msg);
              } else {
                groups.push([msg]);
              }
            }
          }
          if (state.agentRunning) {
            const streamingMsg: Message = { role: "assistant", content: state.streamingText || "" };
            if (state.reasoningText) {
              streamingMsg.reasoning_content = state.reasoningText;
            }
            if (groups.length > 0 && groups[groups.length - 1][0].role !== "user") {
              groups[groups.length - 1].push(streamingMsg);
            } else {
              groups.push([streamingMsg]);
            }
          }
          return groups.map((g, i) => (
            <ChatMessage
              key={i}
              msgs={g}
            />
          ));
        })()}


      </div>

      {activeApproval && (
        <ApprovalCard
          approval={activeApproval}
          onApprove={() => {
            setApproval(null);
            sendApproval(true);
          }}
          onDeny={() => {
            setApproval(null);
            sendApproval(false);
          }}
        />
      )}

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
          <span className="usage-item"><IconBolt size={12} /> 共 {state.apiCalls} 次 API 调用</span>
          {state.tokenUsage.total_tokens > 0 && (
            <span className="usage-item">
              <IconChartBar size={12} /> 输入 {state.tokenUsage.prompt_tokens.toLocaleString()} · 输出 {state.tokenUsage.completion_tokens.toLocaleString()} · 总计 {state.tokenUsage.total_tokens.toLocaleString()} tokens
            </span>
          )}
        </div>
      )}

      <ChatInput
        onSubmit={(c) => {
          setApproval(null);
          userScrolledUp.current = false;
          sendMessage(c);
        }}
        disabled={state.agentRunning}
        placeholder={state.agentRunning ? "AI 正在思考中，请稍候..." : "输入你的问题，Enter 发送..."}
      />
    </div>
  );
}
