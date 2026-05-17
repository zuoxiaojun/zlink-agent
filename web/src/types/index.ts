export interface SessionSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface SessionDetail {
  id: string;
  title: string;
  messages: Message[];
}

export interface Message {
  role: "user" | "assistant" | "tool";
  content: string | ContentPart[];
  tool_calls?: ToolCall[];
  reasoning_content?: string;
  _agent_info?: AgentInfo;
}

export interface ContentPart {
  type: "text" | "image_url";
  text?: string;
  image_url?: { url: string };
}

export interface ToolCall {
  id: string;
  type: "function";
  function: {
    name: string;
    arguments: string;
  };
}

export interface AgentInfo {
  api_calls: number;
  token_usage?: TokenUsage;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface LLMConfigPayload {
  api_key: string;
  base_url: string;
  model: string;
  provider: string;
}

export interface YonSuiteConfigPayload {
  app_key: string;
  app_secret: string;
  tenant_id: string;
  gateway_url: string;
}

export interface AgentConfigPayload {
  max_iterations: number;
}

export interface ConfigResponse {
  llm: LLMConfigPayload;
  yonsuite: YonSuiteConfigPayload;
  agent: AgentConfigPayload;
}

export interface ProviderInfo {
  name: string;
  base_url: string;
  models: string[];
  api_key_label: string;
  api_key_placeholder: string;
}

export interface ToolInfo {
  name: string;
  toolset: string;
  description: string;
  emoji: string;
}

export interface SkillInfo {
  name: string;
  description: string;
  version: string;
  tags: string[];
  active: boolean;
}

export interface SkillDetail {
  name: string;
  content: string;
}

export interface MemoryFacts {
  memory: string[];
  user: string[];
}

export interface MemorySummary {
  session_id: string;
  title: string;
  summary: string;
  key_facts?: string[];
}

// WebSocket message types
export type WsClientMessage =
  | { type: "send_message"; content: string | ContentPart[] }
  | { type: "stop" };

export type WsServerMessage =
  | { type: "token"; content: string }
  | { type: "tool_call"; tool_name: string; arguments_preview: string }
  | { type: "tool_result"; result_preview: string }
  | { type: "tool_done" }
  | { type: "progress"; message: string }
  | { type: "done"; final_response: string; messages: Message[]; api_calls: number; token_usage: TokenUsage | null; completed: boolean; error: string | null; session_id: string; session_title: string }
  | { type: "error"; message: string; session_id?: string };
