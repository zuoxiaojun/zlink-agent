import { useRef, useCallback } from "react";
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
  const onApprovalRequestRef = useRef(options?.onApprovalRequest);
  onApprovalRequestRef.current = options?.onApprovalRequest;

  const sendMessage = useCallback(
    (content: string | import("../types").ContentPart[], sessionOverride?: string) => {
      const sessionId = sessionOverride || state.currentSessionId || "_new";

      dispatch({ type: "SET_RUNNING", running: true });
      runningRef.current = true;
      stopRequestedRef.current = false;

      // Add user message to display immediately
      dispatch({
        type: "SET_MESSAGES",
        messages: [...state.messages, { role: "user", content }],
      });

      const ws = new ChatWebSocket();
      wsRef.current = ws;

      ws.onMessage((msg: WsServerMessage) => {
        switch (msg.type) {
          case "token":
            dispatch({ type: "APPEND_TOKEN", token: msg.content });
            break;
          case "reasoning_token":
            dispatch({ type: "APPEND_REASONING", token: msg.content });
            break;
          case "progress":
            dispatch({ type: "SET_PROGRESS", message: msg.message });
            break;
          case "done":
            runningRef.current = false;
            dispatch({
              type: "SET_RESULT",
              messages: msg.messages.length > 0
                ? msg.messages
                : msg.final_response
                  ? [{ role: "assistant" as const, content: msg.final_response }]
                  : [],
              tokenUsage: msg.token_usage,
              apiCalls: msg.api_calls,
              error: msg.error,
            });
            // Ensure running state is off (SET_RESULT also does this, but double-safety)
            dispatch({ type: "SET_RUNNING", running: false });
            if (msg.session_id && msg.session_id !== "_new") {
              sessionStorage.setItem("zlink_agent_last_session", msg.session_id);
              dispatch({
                type: "SET_SESSION",
                sessionId: msg.session_id,
                title: msg.session_title,
              });
            }
            ws.close();
            wsRef.current = null;
            break;
          case "approval_request":
            onApprovalRequestRef.current?.(msg.payload);
            break;
          case "error":
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

  return { sendMessage, stopAgent, sendApproval };
}
