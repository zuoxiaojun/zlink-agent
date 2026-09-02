import { useCallback, useEffect, useRef, useState } from "react";
import { useAppState } from "../context/AppContext";
import type { AppAction } from "../context/AppContext";
import { ChatWebSocket } from "../api/ws";
import type { ApprovalState, ContentPart, WsClientMessage, WsServerMessage } from "../types";

interface UseChatOptions {
  /** 工具执行完成 / 回合结束（name === "__turn_end__"）—— 供产物面板刷新 */
  onToolActivity?: (name: string) => void;
}

/** 挂起的审批：连同它所属会话一起存，显示与否由渲染侧按 sid 裁决 */
export interface PendingApproval {
  sid: string;
  payload: ApprovalState;
}

/** 一条 run 的视图写入只有"sid 对得上"才生效 —— 裁决在 reducer，不在闭包 */
function scoped(sid: string, action: AppAction): AppAction {
  return { type: "SCOPED", sid, action };
}

/**
 * 单会话视图 + 按 sid 绑定的 run。
 *
 * 改前 useChat 的所有 WS 回调都无条件 dispatch，所以从历史页切进另一个会话后，
 * 后台那条 run 后续的 tool 卡片会插进正在显示的会话、SET_RESULT 还会把
 * currentSessionId 改回旧会话（串台）。后端从来不受影响：run 照常跑完并按 sid 落盘。
 *
 * 现在每条 run 绑死自己的 sid，视图写入一律包成 SCOPED 交给 reducer 比对；
 * 连接也按 sid 存进 socksRef —— stop / 审批 / steering 因此回到正确的连接。
 */
export function useChat(options?: UseChatOptions) {
  const { state, dispatch } = useAppState();
  const socksRef = useRef<Map<string, ChatWebSocket>>(new Map());
  const [pending, setPending] = useState<PendingApproval | null>(null);
  // pending 的同步镜像：sendApproval 要在发帧那一刻读到 sid，
  // 不能靠 state updater（StrictMode 会重复调用 updater，审批响应就会发两次）。
  const pendingRef = useRef<PendingApproval | null>(null);
  const setPendingBoth = useCallback((next: PendingApproval | null) => {
    pendingRef.current = next;
    setPending(next);
  }, []);
  const clearPendingFor = useCallback((sid: string) => {
    if (pendingRef.current?.sid === sid) setPendingBoth(null);
  }, [setPendingBoth]);

  // 只用来决定"这 50ms 的 token 现在渲染还是先攒着"，不承担正确性（正确性在 reducer）。
  const activeSidRef = useRef<string | null>(state.currentSessionId);
  useEffect(() => {
    activeSidRef.current = state.currentSessionId;
  });

  const onToolActivityRef = useRef(options?.onToolActivity);
  useEffect(() => {
    onToolActivityRef.current = options?.onToolActivity;
  }, [options?.onToolActivity]);

  const sendOn = useCallback((sid: string | null, msg: WsClientMessage) => {
    socksRef.current.get(sid ?? "_new")?.send(msg);
  }, []);

  const sendMessage = useCallback(
    (content: string | ContentPart[], sessionOverride?: string) => {
      let bound = sessionOverride || state.currentSessionId || "_new";
      /** 当前是否正看着这条 run 的会话（仅影响 token 缓冲，见上） */
      const isShown = () => {
        const cur = activeSidRef.current;
        return cur === bound || (cur === null && bound === "_new");
      };

      dispatch(scoped(bound, { type: "SET_RUNNING", running: true }));
      dispatch(scoped(bound, { type: "SET_MESSAGES", messages: [...state.messages, { role: "user", content }] }));

      const ws = new ChatWebSocket();
      socksRef.current.set(bound, ws);

      let running = true;
      const toolStarts = new Map<string, number[]>();
      let tokenBuf = "";
      let reasoningBuf = "";
      let reasoningAll = "";
      let flushTimer: number | null = null;

      const stopFlush = () => {
        if (flushTimer !== null) {
          clearTimeout(flushTimer);
          flushTimer = null;
        }
      };

      const flush = () => {
        stopFlush();
        // 切走时继续攒着（切回来能立刻补上尾巴），只停渲染
        if (!isShown()) return;
        if (tokenBuf) {
          dispatch(scoped(bound, { type: "APPEND_TOKEN", token: tokenBuf }));
          tokenBuf = "";
        }
        if (reasoningBuf) {
          dispatch(scoped(bound, { type: "APPEND_REASONING", token: reasoningBuf }));
          reasoningBuf = "";
        }
      };

      const scheduleFlush = () => {
        if (flushTimer === null) flushTimer = window.setTimeout(flush, 50);
      };

      const forget = () => {
        running = false;
        stopFlush();
        if (socksRef.current.get(bound) === ws) socksRef.current.delete(bound);
        clearPendingFor(bound);
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
            const startedAt = Date.now();
            const queue = toolStarts.get(msg.name) ?? [];
            queue.push(startedAt);
            toolStarts.set(msg.name, queue);
            dispatch(scoped(bound, { type: "SET_PROGRESS", message: `🔧 执行工具: ${msg.name}` }));
            dispatch(scoped(bound, { type: "SET_CURRENT_TOOL", toolName: msg.name }));
            dispatch(
              scoped(bound, {
                type: "ADD_PENDING_TOOL",
                message: {
                  role: "tool",
                  content: msg.arguments,
                  tool_call_id: "pending:" + msg.name,
                  _tool_args: msg.arguments,
                },
                startedAt,
              }),
            );
            break;
          }

          case "progress":
            dispatch(scoped(bound, { type: "SET_PROGRESS", message: msg.message }));
            break;

          case "tool_result": {
            const queue = toolStarts.get(msg.name);
            const startedAt = queue && queue.length > 0 ? queue.shift() : undefined;
            dispatch(
              scoped(bound, {
                type: "REPLACE_PENDING_TOOL",
                name: msg.name,
                result: msg.result,
                denied: msg.denied,
                ...(startedAt != null ? { durationMs: Date.now() - startedAt } : {}),
              }),
            );
            // 产物面板属于"正在看的那个会话"，所以只有正看着它时才刷
            if (isShown()) onToolActivityRef.current?.(msg.name);
            break;
          }

          case "done": {
            stopFlush();
            const finalContent = msg.final_response || tokenBuf || "";
            const finalReasoning = reasoningAll || reasoningBuf || "";
            tokenBuf = "";
            reasoningBuf = "";
            // 必须在改绑之前判归属、并记下归属 sid：新会话这条 run 此刻还挂在 "_new"，
            // SET_RESULT 正是靠这个 sid 才被 reducer 放行并采纳真实 id。
            const shouldRender = isShown();
            const ownerSid = bound;
            const real = msg.session_id && msg.session_id !== "_new" ? msg.session_id : undefined;
            if (real && real !== bound) {
              if (socksRef.current.get(bound) === ws) socksRef.current.delete(bound);
              socksRef.current.set(real, ws);
              if (pendingRef.current?.sid === bound) {
                setPendingBoth({ ...pendingRef.current, sid: real });
              }
              bound = real;
            }
            running = false;
            if (shouldRender) {
              dispatch(
                scoped(ownerSid, {
                  type: "SET_RESULT",
                  final_response: finalContent,
                  final_reasoning: finalReasoning,
                  tokenUsage: msg.token_usage,
                  apiCalls: msg.api_calls,
                  error: msg.error,
                  sessionId: real,
                  sessionTitle: msg.session_title || undefined,
                }),
              );
              if (real) sessionStorage.setItem("zlink_agent_last_session", real);
            }
            if (shouldRender) onToolActivityRef.current?.("__turn_end__");
            forget();
            ws.close();
            break;
          }

          case "approval_request":
            // 只登记"哪个会话在等什么"，显示与否交给渲染侧按 sid 裁决
            setPendingBoth({ sid: bound, payload: { ...msg.payload, resolved: false } });
            break;

          case "error":
            flush();
            running = false;
            dispatch(scoped(bound, { type: "SET_ERROR", error: msg.message }));
            forget();
            ws.close();
            break;
        }
      });

      ws.onClose(() => {
        if (running) {
          running = false;
          dispatch(scoped(bound, { type: "SET_RUNNING", running: false }));
        }
        forget();
      });

      ws.connect(bound);
      ws.send({ type: "send_message", content });
    },
    // setPendingBoth / clearPendingFor 是稳定 useCallback，列进来只为满足 exhaustive-deps
    [state.currentSessionId, state.messages, dispatch, setPendingBoth, clearPendingFor]
  );

  /** 停止「当前显示会话」的 run；没有它的连接就什么都不做（绝不碰别的会话） */
  const stopAgent = useCallback(() => {
    sendOn(state.currentSessionId, { type: "stop" });
  }, [sendOn, state.currentSessionId]);

  /** 审批按它自己的 sid 回到原连接，与「现在显示哪个会话」无关 */
  const sendApproval = useCallback(
    (approved: boolean) => {
      const cur = pendingRef.current;
      const sid = cur ? cur.sid : state.currentSessionId;
      clearPendingFor(sid ?? "");
      setPendingBoth(null);
      sendOn(sid, { type: "approval_response", payload: { approved } });
    },
    [clearPendingFor, sendOn, setPendingBoth, state.currentSessionId]
  );

  /** 丢掉审批卡片（用户改主见直接发消息时）；不回复给后端 */
  const dismissApproval = useCallback(() => setPendingBoth(null), [setPendingBoth]);

  /** Steering：本会话的 run 在跑时，新消息注入下一轮而不是另起一次 run */
  const steerMessage = useCallback(
    (content: string) => {
      const key = state.currentSessionId ?? "_new";
      if (!socksRef.current.has(key)) return;
      dispatch({
        type: "SET_MESSAGES",
        messages: [...state.messages, { role: "user", content }],
      });
      sendOn(state.currentSessionId, { type: "steering", payload: { content } });
    },
    [sendOn, state.currentSessionId, state.messages, dispatch]
  );

  return { sendMessage, stopAgent, sendApproval, steerMessage, dismissApproval, pendingApproval: pending };
}
