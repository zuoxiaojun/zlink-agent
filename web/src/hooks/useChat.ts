import { useRef, useCallback, useEffect } from "react";
import { useAppState } from "../context/AppContext";
import { ChatWebSocket } from "../api/ws";
import type { WsServerMessage } from "../types";

interface UseChatOptions {
  onApprovalRequest?: (payload: { tool_name: string; reason: string }) => void;
}

export function useChat(options?: UseChatOptions) {
  const { state, dispatch } = useAppState();
  const wsRef = useRef<ChatWebSocket | null>(null);
  const stopRequestedRef = useRef(false);
  const runningRef = useRef(false);
  const toolStartRef = useRef<Map<string, number[]>>(new Map());
  const onApprovalRequestRef = useRef(options?.onApprovalRequest);
  useEffect(() => {
    onApprovalRequestRef.current = options?.onApprovalRequest;
  }, [options?.onApprovalRequest]);

  const sendMessage = useCallback(
    (content: string | import("../types").ContentPart[], sessionOverride?: string) => {
      const sessionId = sessionOverride || state.currentSessionId || "_new";

      dispatch({ type: "SET_RUNNING", running: true });
      runningRef.current = true;
      stopRequestedRef.current = false;
      toolStartRef.current.clear();

      dispatch({
        type: "SET_MESSAGES",
        messages: [...state.messages, { role: "user", content }],
      });

      const ws = new ChatWebSocket();
      wsRef.current = ws;

      let tokenBuf = "";
      let reasoningBuf = "";
      let reasoningAll = "";
      let flushTimer: number | null = null;

      const flush = () => {
        if (flushTimer !== null) {
          clearTimeout(flushTimer);
          flushTimer = null;
        }
        if (tokenBuf) {
          dispatch({ type: "APPEND_TOKEN", token: tokenBuf });
          tokenBuf = "";
        }
        if (reasoningBuf) {
          dispatch({ type: "APPEND_REASONING", token: reasoningBuf });
          reasoningBuf = "";
        }
      };

      const scheduleFlush = () => {
        if (flushTimer === null) {
          flushTimer = window.setTimeout(flush, 50);
        }
      };

      ws.onMessage((msg: WsServerMessage) => {
        switch (msg.type) {
          case "token":
            tokenBuf += msg.content;
            scheduleFlush();
            break;
          case "reasoning_token":
            reasoningBuf += msg.content;
            reasoningAll += msg.content;
            scheduleFlush();
            break;
          case "tool_call": {
            // 收到后端发来的 tool_call 消息，立即插入 pending 工具卡片
            const startedAt = Date.now();
            const queue = toolStartRef.current.get(msg.name) ?? [];
            queue.push(startedAt);
            toolStartRef.current.set(msg.name, queue);
            dispatch({ type: "SET_PROGRESS", message: `🔧 执行工具: ${msg.name}` });
            dispatch({ type: "SET_CURRENT_TOOL", toolName: msg.name });
            dispatch({ type: "ADD_PENDING_TOOL", message: { role: "tool", content: msg.arguments, tool_call_id: "pending:" + msg.name, _tool_args: msg.arguments }, startedAt });
            break;
          }
          case "progress":
            dispatch({ type: "SET_PROGRESS", message: msg.message });
            break;
          case "tool_result": {
            const queue = toolStartRef.current.get(msg.name);
            const startedAt = queue && queue.length > 0 ? queue.shift() : undefined;
            dispatch({
              type: "REPLACE_PENDING_TOOL",
              name: msg.name,
              result: msg.result,
              denied: msg.denied,
              ...(startedAt != null ? { durationMs: Date.now() - startedAt } : {}),
            });
            break;
          }
          case "done": {
            // 内联 flush：直接构建最终文本，避免 React 状态异步造成 streamingText 为空
            if (flushTimer !== null) {
              clearTimeout(flushTimer);
              flushTimer = null;
            }
            const finalContent = msg.final_response || tokenBuf || "";
            const finalReasoning = reasoningAll || reasoningBuf || "";
            tokenBuf = "";
            reasoningBuf = "";
            runningRef.current = false;
            dispatch({
              type: "SET_RESULT",
              final_response: finalContent,
              final_reasoning: finalReasoning,
              tokenUsage: msg.token_usage,
              apiCalls: msg.api_calls,
              error: msg.error,
              sessionId: msg.session_id && msg.session_id !== "_new" ? msg.session_id : undefined,
              sessionTitle: msg.session_title || undefined,
            });
            if (msg.session_id && msg.session_id !== "_new") {
              sessionStorage.setItem("zlink_agent_last_session", msg.session_id);
            }
            ws.close();
            wsRef.current = null;
            break;
          }
          case "approval_request":
            onApprovalRequestRef.current?.(msg.payload);
            break;
          case "error":
            flush();
            runningRef.current = false;
            dispatch({ type: "SET_ERROR", error: msg.message });
            ws.close();
            wsRef.current = null;
            break;
        }
      });

      ws.onClose(() => {
        if (runningRef.current) {
          runningRef.current = false;
          dispatch({ type: "SET_RUNNING", running: false });
        }
      });

      ws.connect(sessionId);
      ws.send({ type: "send_message", content });
    },
    [state.currentSessionId, state.messages, dispatch]
  );

  const stopAgent = useCallback(() => {
    stopRequestedRef.current = true;
    wsRef.current?.send({ type: "stop" });
  }, []);

  const sendApproval = useCallback((approved: boolean) => {
    wsRef.current?.send({ type: "approval_response", payload: { approved } });
  }, []);

  // Steering: while the agent is running, a new user message is injected
  // into the next turn on the SAME connection instead of starting a new run.
  const steerMessage = useCallback(
    (content: string) => {
      if (!wsRef.current) return;
      dispatch({
        type: "SET_MESSAGES",
        messages: [...state.messages, { role: "user", content }],
      });
      wsRef.current.send({ type: "steering", payload: { content } });
    },
    [state.messages, dispatch]
  );

  return { sendMessage, stopAgent, sendApproval, steerMessage };
}