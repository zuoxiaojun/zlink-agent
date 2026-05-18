import { useRef, useCallback } from "react";
import { useAppState } from "../context/AppContext";
import { ChatWebSocket } from "../api/ws";
import type { WsServerMessage } from "../types";

export function useChat() {
  const { state, dispatch } = useAppState();
  const wsRef = useRef<ChatWebSocket | null>(null);
  const stopRequestedRef = useRef(false);

  const sendMessage = useCallback(
    (content: string | import("../types").ContentPart[]) => {
      const sessionId = state.currentSessionId || "_new";

      dispatch({ type: "SET_RUNNING", running: true });
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
          case "progress":
            dispatch({ type: "SET_PROGRESS", message: msg.message });
            break;
          case "done":
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
            if (msg.session_id && msg.session_id !== "_new") {
              sessionStorage.setItem("ys_agent_last_session", msg.session_id);
              dispatch({
                type: "SET_SESSION",
                sessionId: msg.session_id,
                title: msg.session_title,
              });
            }
            ws.close();
            wsRef.current = null;
            break;
          case "error":
            dispatch({ type: "SET_ERROR", error: msg.message });
            ws.close();
            wsRef.current = null;
            break;
        }
      });

      ws.onClose(() => {
        if (state.agentRunning) {
          dispatch({ type: "SET_RUNNING", running: false });
        }
      });

      ws.connect(sessionId);
      ws.send({ type: "send_message", content });
    },
    [state.currentSessionId, state.messages, state.agentRunning, dispatch]
  );

  const stopAgent = useCallback(() => {
    stopRequestedRef.current = true;
    wsRef.current?.send({ type: "stop" });
  }, []);

  return { sendMessage, stopAgent };
}
