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

/**
 * 一条活着的 run。除了连接，还留一份「本轮往视图写过什么」的账：
 * recorded 里只放改 messages 的动作（ADD_MESSAGE / ADD_PENDING_TOOL /
 * REPLACE_PENDING_TOOL）—— 它们在 reducer 里都是相对动作（追加 / 按 id 替换），
 * 所以可以在「刚从磁盘读回来的历史」上原样重放，切回会话时不必重新拉一遍。
 */
interface LiveRun {
  ws: ChatWebSocket;
  recorded: AppAction[];
  tokenAll: string;
  reasoningAll: string;
  flushedTokens: number;
  flushedReasoning: number;
  progress: string;
  toolName: string;
  /** 切回本会话时把视图接回来（运行中状态 + 本轮气泡 + 已流出的文本 + 进度） */
  attach: () => void;
}

/** 视图写入只有"sid 对得上当前会话"才生效 —— 裁决在 reducer，不在闭包 */
function scoped(sid: string, action: AppAction): AppAction {
  return { type: "SCOPED", sid, action };
}

/**
 * 单会话视图 + 按 sid 绑定的 run。
 *
 * 两件事：
 * 1. 不串台。一条 run 的 WS 帧只允许写它自己那条会话的视图；改前所有回调都无条件
 *    dispatch，从历史页切进别的会话后，后台 run 的工具卡会插进正在显示的会话、
 *    SET_RESULT 还会把 currentSessionId 改回旧会话。后端从来不受影响（照常跑完按 sid 落盘）。
 * 2. 切回来接得上。run 活着时它记着账，切回该会话即重放，进度条 / 停止按钮 /
 *    本轮气泡 / 置灰一起回来，不用等跑完或刷新。
 *
 * 连接按 sid 存进 runsRef —— stop / 审批 / steering 因此总回到正确的连接。
 */
export function useChat(options?: UseChatOptions) {
  const { state, dispatch } = useAppState();
  const runsRef = useRef<Map<string, LiveRun>>(new Map());
  const [pending, setPending] = useState<PendingApproval | null>(null);
  // pending 的同步镜像：sendApproval 要在发帧那一刻读到 sid，不能靠 state updater
  // （StrictMode 会重复调用 updater，审批响应就会发两次）
  const pendingRef = useRef<PendingApproval | null>(null);

  const activeSidRef = useRef<string | null>(state.currentSessionId);
  // 只用来决定"这 50ms 的 token 现在渲染还是先攒着"，正确性在 reducer，不在这里。
  // 必须声明在下面的重放 effect 之前：同一次 commit 里 effect 按声明顺序跑。
  useEffect(() => {
    activeSidRef.current = state.currentSessionId;
  });

  const onToolActivityRef = useRef(options?.onToolActivity);
  useEffect(() => {
    onToolActivityRef.current = options?.onToolActivity;
  }, [options?.onToolActivity]);

  const setPendingBoth = useCallback((next: PendingApproval | null) => {
    pendingRef.current = next;
    setPending(next);
  }, []);
  const clearPendingFor = useCallback(
    (sid: string) => {
      if (pendingRef.current?.sid === sid) setPendingBoth(null);
    },
    [setPendingBoth]
  );

  // 切到一个「还在跑」的会话 → 把它的视图接回来。只依赖 sid：磁盘历史已随
  // SET_SESSION 一起落地，这一步是在它之后追加本轮的增量。
  useEffect(() => {
    if (state.currentSessionId) runsRef.current.get(state.currentSessionId)?.attach();
  }, [state.currentSessionId]);

  const sendOn = useCallback((sid: string | null, msg: WsClientMessage) => {
    runsRef.current.get(sid ?? "_new")?.ws.send(msg);
  }, []);

  const sendMessage = useCallback(
    (content: string | ContentPart[], sessionOverride?: string) => {
      let bound = sessionOverride || state.currentSessionId || "_new";
      const isShown = () => {
        const cur = activeSidRef.current;
        return cur === bound || (cur === null && bound === "_new");
      };
      const write = (action: AppAction) => dispatch(scoped(bound, action));

      const ws = new ChatWebSocket();
      const run: LiveRun = {
        ws,
        recorded: [],
        tokenAll: "",
        reasoningAll: "",
        flushedTokens: 0,
        flushedReasoning: 0,
        progress: "",
        toolName: "",
        attach: () => {},
      };
      runsRef.current.set(bound, run);

      /** 改 messages 的动作：先记账，再写视图（视图不归本会话时 reducer 会丢掉） */
      const writeMsg = (action: AppAction) => {
        run.recorded.push(action);
        write(action);
      };

      let running = true;
      const toolStarts = new Map<string, number[]>();
      let flushTimer: number | null = null;

      const stopFlush = () => {
        if (flushTimer !== null) {
          clearTimeout(flushTimer);
          flushTimer = null;
        }
      };

      const flush = () => {
        stopFlush();
        if (!isShown()) return; // 切走时不渲染，文本继续在 run.tokenAll 里攒着
        if (run.tokenAll.length > run.flushedTokens) {
          write({ type: "APPEND_TOKEN", token: run.tokenAll.slice(run.flushedTokens) });
          run.flushedTokens = run.tokenAll.length;
        }
        if (run.reasoningAll.length > run.flushedReasoning) {
          write({ type: "APPEND_REASONING", token: run.reasoningAll.slice(run.flushedReasoning) });
          run.flushedReasoning = run.reasoningAll.length;
        }
      };

      const scheduleFlush = () => {
        if (flushTimer === null) flushTimer = window.setTimeout(flush, 50);
      };

      run.attach = () => {
        // SET_RUNNING 会清 streaming / progress，所以必须排在最前
        dispatch({ type: "SET_RUNNING", running: true });
        for (const action of run.recorded) dispatch(action);
        run.flushedTokens = 0;
        run.flushedReasoning = 0;
        flush();
        if (run.progress) dispatch({ type: "SET_PROGRESS", message: run.progress });
        if (run.toolName) dispatch({ type: "SET_CURRENT_TOOL", toolName: run.toolName });
      };

      const forget = () => {
        running = false;
        stopFlush();
        if (runsRef.current.get(bound) === run) runsRef.current.delete(bound);
        clearPendingFor(bound);
      };

      write({ type: "SET_RUNNING", running: true });
      writeMsg({ type: "ADD_MESSAGE", message: { role: "user", content } });

      ws.onMessage((msg: WsServerMessage) => {
        switch (msg.type) {
          case "token":
            run.tokenAll += msg.content;
            scheduleFlush();
            break;

          case "reasoning_token":
            run.reasoningAll += msg.content;
            scheduleFlush();
            break;

          case "tool_call": {
            const startedAt = Date.now();
            const queue = toolStarts.get(msg.name) ?? [];
            queue.push(startedAt);
            toolStarts.set(msg.name, queue);
            run.progress = `🔧 执行工具: ${msg.name}`;
            run.toolName = msg.name;
            write({ type: "SET_PROGRESS", message: run.progress });
            write({ type: "SET_CURRENT_TOOL", toolName: msg.name });
            writeMsg({
              type: "ADD_PENDING_TOOL",
              message: {
                role: "tool",
                content: msg.arguments,
                tool_call_id: "pending:" + msg.name,
                _tool_args: msg.arguments,
              },
              startedAt,
            });
            break;
          }

          case "progress":
            run.progress = msg.message;
            write({ type: "SET_PROGRESS", message: msg.message });
            break;

          case "tool_result": {
            const queue = toolStarts.get(msg.name);
            const startedAt = queue && queue.length > 0 ? queue.shift() : undefined;
            writeMsg({
              type: "REPLACE_PENDING_TOOL",
              name: msg.name,
              result: msg.result,
              denied: msg.denied,
              ...(startedAt != null ? { durationMs: Date.now() - startedAt } : {}),
            });
            // 产物面板跟着「正在看的那个会话」刷，所以只在正看着它时通知
            if (isShown()) onToolActivityRef.current?.(msg.name);
            break;
          }

          case "done": {
            stopFlush();
            const finalContent = msg.final_response || run.tokenAll;
            const finalReasoning = run.reasoningAll;
            // 必须在改绑之前判归属并记下归属 sid：新会话这条 run 此刻还挂在 "_new"，
            // SET_RESULT 正是靠这个 sid 才被 reducer 放行并采纳真实 id
            const shouldRender = isShown();
            const ownerSid = bound;
            const real = msg.session_id && msg.session_id !== "_new" ? msg.session_id : undefined;
            if (real && real !== bound) {
              if (runsRef.current.get(bound) === run) runsRef.current.delete(bound);
              runsRef.current.set(real, run);
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
              onToolActivityRef.current?.("__turn_end__");
            }
            if (runsRef.current.get(bound) === run) runsRef.current.delete(bound);
            clearPendingFor(bound);
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
            write({ type: "SET_ERROR", error: msg.message });
            forget();
            ws.close();
            break;
        }
      });

      ws.onClose(() => {
        if (running) {
          running = false;
          write({ type: "SET_RUNNING", running: false });
        }
        forget();
      });

      ws.connect(bound);
      ws.send({ type: "send_message", content });
    },
    [state.currentSessionId, dispatch, setPendingBoth, clearPendingFor]
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
      setPendingBoth(null);
      sendOn(sid, { type: "approval_response", payload: { approved } });
    },
    [sendOn, setPendingBoth, state.currentSessionId]
  );

  /** 丢掉审批卡片（用户改主见直接发消息时）；不回复给后端 */
  const dismissApproval = useCallback(() => setPendingBoth(null), [setPendingBoth]);

  /** Steering：本会话的 run 在跑时，新消息注入下一轮而不是另起一次 run */
  const steerMessage = useCallback(
    (content: string) => {
      const run = runsRef.current.get(state.currentSessionId ?? "_new");
      if (!run) return;
      const action: AppAction = { type: "ADD_MESSAGE", message: { role: "user", content } };
      run.recorded.push(action);
      dispatch(action);
      run.ws.send({ type: "steering", payload: { content } });
    },
    [state.currentSessionId, dispatch]
  );

  return { sendMessage, stopAgent, sendApproval, steerMessage, dismissApproval, pendingApproval: pending };
}
