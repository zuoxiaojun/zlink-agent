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
  tool_call_id?: string;
  reasoning_content?: string;
  _agent_info?: AgentInfo;
  _tool_done?: boolean;  // 前端临时标记：工具已执行完成
  _denied?: boolean;     // 前端临时标记：工具调用被用户拒绝
  _tool_duration_ms?: number;  // 前端临时标记：工具执行耗时（本次运行）
  _tool_started_at?: number;   // 前端临时标记：工具开始时间（epoch ms）
  _tool_args?: string;         // 前端临时标记：工具调用原始参数（本次运行，完成后 content 已被结果覆盖）
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

export interface ModelInfo {
  id: string;
  context_length: number;
  max_output?: number;
}

export interface ProviderInfo {
  name: string;
  base_url: string;
  models: ModelInfo[];
  api_key_label: string;
  api_key_placeholder: string;
}

export interface YonSuiteConfigPayload {
  app_key: string;
  app_secret: string;
  tenant_id: string;
}

export interface AgentConfigPayload {
  max_iterations: number;
  compaction_enabled: boolean;
  max_context_tokens: number;
  max_context_tokens_auto: boolean;
  reserve_tokens: number;
  keep_recent_tokens: number;
  approval_mode: string;
}

export interface ConfigResponse {
  llm: LLMConfigPayload;
  yonsuite: YonSuiteConfigPayload;
  agent: AgentConfigPayload;
  version: string;
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
  builtin?: boolean;
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
  | { type: "stop" }
  | { type: "approval_response"; payload: { approved: boolean } }
  | { type: "steering"; payload: { content: string } };

export interface ApprovalState {
  tool_name: string;
  reason: string;
  resolved: boolean;
}

// MCP types
export interface MCPServerConfig {
  name: string;
  transport: "stdio" | "http";
  command?: string;
  args?: string[];
  url?: string;
  headers?: Record<string, string>;
  env?: Record<string, string>;
  enabled?: boolean;
  timeout?: number;
}

export interface MCPServerStatus {
  name: string;
  transport: string;
  enabled: boolean;
  builtin?: boolean;
  status: "connected" | "disconnected" | "error";
  tool_count: number;
  error_message: string | null;
  command?: string;
  args?: string[];
  url?: string;
  headers?: Record<string, string>;
  env?: Record<string, string>;
  timeout?: number;
}

export interface MCPTestResult {
  success: boolean;
  tools_discovered: number;
  tool_names: string[];
  error_message: string | null;
}

// Extension types (M5+)
export interface ExtensionInfo {
  name: string;
  enabled: boolean;
  description: string;
  kind: "log" | "policy" | "transform" | "other";
}

export interface ExtensionReloadResult {
  now_active: string[];
  now_disabled: string[];
}

export type WsServerMessage =
  | { type: "token"; content: string }
  | { type: "reasoning_token"; content: string }
  | { type: "tool_call"; name: string; arguments: string }
  | { type: "tool_result"; name: string; result: string; denied?: boolean }
  | { type: "progress"; message: string }
  | {
      type: "done";
      final_response: string;
      messages: Message[];
      api_calls: number;
      token_usage: TokenUsage | null;
      completed: boolean;
      error: string | null;
      session_id: string;
      session_title: string;
    }
  | { type: "error"; message: string; session_id?: string }
  | { type: "approval_request"; payload: { tool_name: string; reason: string } };

// Slash command popup types
export interface SlashCommandInfo {
  name: string;
  description: string;
  usage: string;
  type?: "command" | "skill";
}

export interface SlashCommandsResponse {
  commands: SlashCommandInfo[];
}
