/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useReducer, type Dispatch } from "react";
import type { Message, ConfigResponse, TokenUsage } from "../types";

export const WELCOME_MESSAGE: Message[] = [
  {
    role: "assistant",
    content:
      "你好！我是 **ZLink Agent（智链 Agent）**，你的多 ERP + 数据分析 AI 助手。\n\n" +
      "## 📋 我能做什么\n\n" +
      "### 🔌 ERP 与数据查询\n" +
      "- **YonSuite**：销售/采购/生产订单、库存、商机、待办查询\n" +
      "- **NC**：销售/采购订单、物料、客户、供应商、库存、组织架构查询\n" +
      "- **westock 金融数据**：A股/港股/美股 K线、技术指标、板块行情、期货外汇\n\n" +
      "### 📊 数据分析与调研\n" +
      "- **数据分析**：KPI 分析、报表洞察、统计分析、决策简报\n" +
      "- **深度调研**：系统性多源调研、交叉验证、结构化报告输出\n" +
      "- **Python 代码执行**：沙箱环境运行 Python 做计算和数据处理\n" +
      "- **图片分析**：用 AI 视觉能力识别和分析图片内容\n\n" +
      "### 📄 文档与内容创作\n" +
      "- **Word 文档**：生成和编辑专业 DOCX 文档\n" +
      "- **PPT 演示**：创建和编辑 PowerPoint 演示文稿\n" +
      "- **PDF 生成**：生成高质量 PDF 文件\n" +
      "- **Excel 处理**：创建、读取、分析、编辑电子表格\n" +
      "- **HTML 演示**：生成企业品牌风格 HTML 报告\n\n" +
      "### 🔥 热点与搜索\n" +
      "- **全网搜索**：搜索引擎 + 网页内容提取\n" +
      "- **热点采集**：微博/抖音/B站/百度热搜、音乐榜、票房、App Store排行\n" +
      "- **AnySearch**：通用搜索引擎聚合，覆盖多领域垂直搜索\n\n" +
      "### 💻 系统与终端\n" +
      "- **终端执行**：运行 Shell 命令、脚本\n" +
      "- **进程管理**：列出和终止系统进程\n" +
      "- **文件操作**：读写文件、搜索、补丁\n" +
      "- **浏览器**：自动化网页操作（点击、填写、截图、评估）\n\n" +
      "### ⏰ 定时任务\n" +
      "- 创建定时任务，到期自动执行并生成会话报告\n\n" +
      "### 🛠 技能系统\n" +
      "- 当前已安装 19 个内置技能，覆盖数据分析、文档处理、金融数据、天气查询等\n" +
      "- 可使用 `/skills` 查看所有技能，`/skill <名称>` 查看详情\n" +
      "- 支持从 SkillHub 平台搜索和安装更多技能\n\n" +
      "### 🔗 外部 MCP 服务器\n" +
      "- 连接图表生成、YonSuite API 等 MCP 工具\n\n" +
      "---\n" +
      "你说需要什么，我来调用对应的工具和技能帮你完成！",
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
