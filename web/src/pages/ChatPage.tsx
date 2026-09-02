import { useRef, useEffect, useState } from "react";
import { useSearchParams, useOutletContext } from "react-router-dom";
import { IconBolt, IconChartBar, IconArrowDown } from "@tabler/icons-react";
import { useAppState } from "../context/AppContext";
import { useChat } from "../hooks/useChat";
import { api } from "../api/http";
import ChatMessage from "../components/ChatMessage";
import ChatInput from "../components/ChatInput";
import ApprovalCard from "../components/ApprovalCard";
import type { LayoutOutlet } from "../components/Layout";
import type { Message, SessionDetail } from "../types";
import StopButton from "../components/StopButton";
import AgentStatusBar from "../components/AgentStatusBar";

// 会改变会话产物的工具；__turn_end__ 是回合结束兜底（terminal 里的 shell 也能写文件）
const MUTATING_TOOLS = new Set(["write_file", "patch", "terminal", "__turn_end__"]);

export default function ChatPage() {
  const { state, dispatch } = useAppState();
  const { bumpArtifacts } = useOutletContext<LayoutOutlet>();
  const autoSentRef = useRef(false);
  const {
    sendMessage,
    stopAgent,
    sendApproval,
    steerMessage,
    dismissApproval,
    pendingApproval,
  } = useChat({
    onToolActivity: (name) => {
      if (MUTATING_TOOLS.has(name)) bumpArtifacts();
    },
  });

  // 审批卡片按 sid 归属：后台 run 在等审批时不在别的会话脸上弹卡片，
  // 但请求留着 —— 切回那条会话就重新出现，批准走它自己的连接。
  const activeApproval =
    pendingApproval && pendingApproval.sid === (state.currentSessionId ?? "_new")
      ? pendingApproval.payload
      : null;
  const scrollRef = useRef<HTMLDivElement>(null);
  const userScrolledUp = useRef(false);
  const [showBackToBottom, setShowBackToBottom] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();

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
    if (userScrolledUp.current || !scrollRef.current) return;
    const el = scrollRef.current;
    const rafId = requestAnimationFrame(() => {
      if (!userScrolledUp.current) {
        el.scrollTop = el.scrollHeight;
      }
    });
    return () => cancelAnimationFrame(rafId);
  }, [state.messages, state.streamingText]);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const up = el.scrollHeight - el.scrollTop - el.clientHeight > 150;
    userScrolledUp.current = up;
    setShowBackToBottom(up);
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
              streaming={state.agentRunning && i === groups.length - 1}
              onChoiceSelect={(text) => {
                dismissApproval();
                userScrolledUp.current = false;
                sendMessage(text);
              }}
            />
          ));
        })()}


      </div>

      {showBackToBottom && (
        <button
          type="button"
          className="back-to-bottom"
          title="回到底部"
          onClick={() => {
            userScrolledUp.current = false;
            setShowBackToBottom(false);
            scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
          }}
        >
          <IconArrowDown size={16} />
        </button>
      )}

      {activeApproval && (
        <ApprovalCard
          approval={activeApproval}
          onApprove={() => sendApproval(true)}
          onDeny={() => sendApproval(false)}
        />
      )}

      {state.agentRunning && (
        <>
          <StopButton onStop={stopAgent} />
          <AgentStatusBar />
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
          dismissApproval();
          userScrolledUp.current = false;
          if (state.agentRunning && typeof c === "string") {
            steerMessage(c);
          } else {
            sendMessage(c);
          }
        }}
        disabled={false}
        attachDisabled={state.agentRunning}
        placeholder="输入你的问题，Enter 发送..."
      />
    </div>
  );
}
