/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useReducer, type Dispatch } from "react";
import type { Message, ConfigResponse, TokenUsage } from "../types";

export const WELCOME_MESSAGE: Message[] = [
  {
    role: "assistant",
    content:
      "你好！我是 **ZLink Agent（智链 Agent）**，你的多 ERP + 数据智能助手。\n\n" +
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
  | { type: "SET_RESULT"; messages: Message[]; tokenUsage: TokenUsage | null; apiCalls: number; error: string | null }
  | { type: "SET_ERROR"; error: string }
  | { type: "CLEAR_STREAMING" }
  | { type: "SET_CONFIG"; config: ConfigResponse };

function reducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case "SET_SESSION":
      return {
        ...state,
        currentSessionId: action.sessionId,
        currentSessionTitle: action.title,
        messages: action.messages ?? state.messages,
        streamingText: "",
        reasoningText: "",
        agentRunning: false,
      };
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
      return { ...state, agentRunning: action.running, streamingText: "", reasoningText: "", progressMessage: "" };
    case "APPEND_TOKEN":
      return { ...state, streamingText: state.streamingText + action.token };
    case "APPEND_REASONING":
      return { ...state, reasoningText: state.reasoningText + action.token };
    case "SET_PROGRESS":
      return { ...state, progressMessage: action.message };
    case "SET_RESULT": {
      const msgs = [...state.messages];
      for (const m of action.messages) {
        const key = m.role + (typeof m.content === "string" ? m.content : "");
        if (!msgs.some(existing => existing.role + (typeof existing.content === "string" ? existing.content : "") === key)) {
          msgs.push(m);
        }
      }
      if (action.error) {
        msgs.push({ role: "assistant", content: `❌ ${action.error}` });
      }
      return {
        ...state,
        messages: msgs,
        agentRunning: false,
        streamingText: "",
        reasoningText: "",
        progressMessage: "",
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
