/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useReducer, type Dispatch } from "react";
import type { Message, ConfigResponse, TokenUsage } from "../types";

export const WELCOME_MESSAGE: Message[] = [
  {
    role: "assistant",
    content:
      "你好！我是 **ZLink Agent（智链 Agent）**，你的多 ERP AI 智能助手。\n\n" +
      "## 我能做什么\n\n" +
      "- 🔌 **ERP 取数** — YonSuite / NC 业务数据查询（订单、库存、客户等）\n" +
      "- 📊 **数据分析** — 报表洞察、KPI 分析、Python 计算、图片分析\n" +
      "- 📄 **文档生成** — Word/PPT/PDF/Excel/HTML 报告\n" +
      "- 🔥 **热点搜索** — 全网搜索 + 微博/抖音/B站热搜 + 金融行情\n" +
      "- 💻 **终端 & 文件** — 命令执行、代码运行、文件读写、浏览器自动化\n" +
      "- ⏰ **定时任务** — 创建调度任务，到点自动执行并生成报告\n" +
      "- 🛠 **技能系统** — 19 个内置技能，输入 `/` 查看所有命令\n\n" +
      "直接说你的需求，我来调用对应的工具完成！",
  },
];

export interface AppState {
  currentSessionId: string | null;
  currentSessionTitle: string;
  messages: Message[];
  agentRunning: boolean;
  streamingText: string;
  reasoningText: string;
  progressMessage: string;
  currentToolName: string;
  currentToolArgs: string;
  tokenUsage: TokenUsage | null;
  apiCalls: number;
  config: ConfigResponse | null;
}

const initialState: AppState = {
  currentSessionId: null,
  currentSessionTitle: "",
  messages: WELCOME_MESSAGE,
  agentRunning: false,
  streamingText: "",
  reasoningText: "",
  progressMessage: "",
  currentToolName: "",
  currentToolArgs: "",
  tokenUsage: null,
  apiCalls: 0,
  config: null,
};

export type AppAction =
  | { type: "SET_SESSION"; sessionId: string; title: string; messages?: Message[] }
  | { type: "NEW_SESSION" }
  | { type: "SET_MESSAGES"; messages: Message[] }
  | { type: "SET_RUNNING"; running: boolean }
  | { type: "APPEND_TOKEN"; token: string }
  | { type: "APPEND_REASONING"; token: string }
  | { type: "SET_PROGRESS"; message: string }
  | { type: "SET_CURRENT_TOOL"; toolName: string }
  | { type: "SET_CURRENT_TOOL_ARGS"; args: string }
  | { type: "ADD_PENDING_TOOL"; message: Message }
  | { type: "REPLACE_PENDING_TOOL"; name: string; result: string }
  | { type: "SET_RESULT"; final_response: string; final_reasoning?: string; tokenUsage: TokenUsage | null; apiCalls: number; error: string | null; sessionId?: string; sessionTitle?: string }
  | { type: "SET_ERROR"; error: string }
  | { type: "CLEAR_STREAMING" }
  | { type: "SET_CONFIG"; config: ConfigResponse };

function reducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case "SET_SESSION": {
      const sessionMsgs = action.messages ?? state.messages;
      // 如果消息来自后端（没有 WELCOME），自动在最前面加上 WELCOME
      const hasWelcome = sessionMsgs.length > 0
        && sessionMsgs[0].role === "assistant"
        && typeof sessionMsgs[0].content === "string"
        && (sessionMsgs[0].content as string).startsWith("你好！我是 **ZLink Agent");
      return {
        ...state,
        currentSessionId: action.sessionId,
        currentSessionTitle: action.title,
        messages: hasWelcome ? sessionMsgs : [...WELCOME_MESSAGE, ...sessionMsgs],
        streamingText: "",
        reasoningText: "",
        agentRunning: false,
      };
    }
    case "NEW_SESSION":
      return {
        ...state,
        currentSessionId: null,
        currentSessionTitle: "",
        messages: WELCOME_MESSAGE,
        streamingText: "",
        reasoningText: "",
        agentRunning: false,
      };
    case "SET_MESSAGES":
      return { ...state, messages: action.messages };
    case "SET_RUNNING":
      return {
        ...state,
        agentRunning: action.running,
        streamingText: "",
        reasoningText: "",
        progressMessage: "",
        currentToolName: "",
        currentToolArgs: "",
      };
    case "APPEND_TOKEN":
      return { ...state, streamingText: state.streamingText + action.token };
    case "APPEND_REASONING":
      return { ...state, reasoningText: state.reasoningText + action.token };
    case "SET_PROGRESS":
      return { ...state, progressMessage: action.message };
    case "SET_CURRENT_TOOL":
      return { ...state, currentToolName: action.toolName };
    case "SET_CURRENT_TOOL_ARGS":
      return { ...state, currentToolArgs: action.args };
    case "ADD_PENDING_TOOL": {
      // 避免重复插入同名的 pending tool
      const id = action.message.tool_call_id || "";
      if (state.messages.some(m => m.role === "tool" && m.tool_call_id === id)) {
        return state;
      }
      return { ...state, messages: [...state.messages, action.message] };
    }
    case "REPLACE_PENDING_TOOL": {
      const id = "pending:" + action.name;
      // 从后往前遍历，替换最新一条匹配的 pending 卡
      let targetIdx = -1;
      for (let i = state.messages.length - 1; i >= 0; i--) {
        const m = state.messages[i];
        if (m.role === "tool" && m.tool_call_id === id) {
          targetIdx = i;
          break;
        }
      }
      if (targetIdx < 0) return state;
      const msgs = [...state.messages];
      msgs[targetIdx] = { ...msgs[targetIdx], content: action.result, _tool_done: true };
      return { ...state, messages: msgs };
    }
    case "SET_RESULT": {
      // 移除尚未完成的 pending 工具消息；已完成（_tool_done: true）的保留显示
      let msgs = state.messages.filter(m => !(m.role === "tool" && m.tool_call_id && m.tool_call_id.startsWith("pending:") && !m._tool_done));

      // 用 action 传入的最终文本构建 assistant 消息（避免依赖异步的 state.streamingText）
      if (action.final_response) {
        const assistantMsg: Message = { role: "assistant", content: action.final_response };
        if (action.final_reasoning) {
          assistantMsg.reasoning_content = action.final_reasoning;
        }
        msgs = [...msgs, assistantMsg];
      }

      if (action.error) {
        msgs.push({ role: "assistant", content: `❌ ${action.error}` });
      }
      return {
        ...state,
        currentSessionId: action.sessionId ?? state.currentSessionId,
        currentSessionTitle: action.sessionTitle ?? state.currentSessionTitle,
        messages: msgs,
        agentRunning: false,
        streamingText: "",
        reasoningText: "",
        progressMessage: "",
        currentToolName: "",
        currentToolArgs: "",
        tokenUsage: action.tokenUsage,
        apiCalls: action.apiCalls,
      };
    }
    case "SET_ERROR":
      return {
        ...state,
        agentRunning: false,
        streamingText: "",
        reasoningText: "",
        progressMessage: "",
        currentToolName: "",
        currentToolArgs: "",
        messages: [...state.messages, { role: "assistant", content: `❌ ${action.error}` }],
      };
    case "CLEAR_STREAMING":
      return { ...state, streamingText: "", reasoningText: "", progressMessage: "" };
    case "SET_CONFIG":
      return { ...state, config: action.config };
    default:
      return state;
  }
}

const AppContext = createContext<{ state: AppState; dispatch: Dispatch<AppAction> } | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  return React.createElement(AppContext.Provider, { value: { state, dispatch } }, children);
}

export function useAppState() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppState must be used within AppProvider");
  return ctx;
}
