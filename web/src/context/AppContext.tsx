import React, { createContext, useContext, useReducer, type Dispatch } from "react";
import type { Message, ConfigResponse, TokenUsage } from "../types";

export const WELCOME_MESSAGE: Message[] = [
  {
    role: "assistant",
    content:
      "你好！我是 **YS-Agent**，你的 YonSuite AI 智能助手。\n\n" +
      "我可以帮你完成以下工作：\n" +
      "- 🖥 **终端操作**：执行命令、管理文件\n" +
      "- 🔍 **数据查询**：搜索和分析数据\n" +
      "- 🌐 **网页浏览**：提取和分析网页内容\n" +
      "- 📊 **YonSuite API**：调用 YonSuite 业务接口\n" +
      "- 🛠 **技能工具**：使用已安装的技能完成特定任务\n" +
      "- 📝 **任务管理**：追踪和规划多步骤工作\n\n" +
      "请告诉我你需要什么帮助，我会调用合适的工具来完成任务。",
  },
];

export interface AppState {
  currentSessionId: string | null;
  currentSessionTitle: string;
  messages: Message[];
  agentRunning: boolean;
  streamingText: string;
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
        agentRunning: false,
      };
    case "NEW_SESSION":
      return {
        ...state,
        currentSessionId: null,
        currentSessionTitle: "",
        messages: WELCOME_MESSAGE,
        streamingText: "",
        agentRunning: false,
      };
    case "SET_MESSAGES":
      return { ...state, messages: action.messages };
    case "SET_RUNNING":
      return { ...state, agentRunning: action.running, streamingText: "", progressMessage: "" };
    case "APPEND_TOKEN":
      return { ...state, streamingText: state.streamingText + action.token };
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
        progressMessage: "",
        messages: [...state.messages, { role: "assistant", content: `❌ ${action.error}` }],
      };
    case "CLEAR_STREAMING":
      return { ...state, streamingText: "", progressMessage: "" };
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
