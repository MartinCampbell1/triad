export type ProviderId = "claude" | "codex" | "gemini";
export type ModeId = "solo" | "critic" | "brainstorm" | "delegate";
export type SessionStatus = "active" | "running" | "paused" | "completed" | "failed";
export type MessageRole = "user" | "assistant" | "system";
export type BridgeBackendMode = "tauri" | "mock";

export interface BridgeStatus {
  backendMode: BridgeBackendMode;
  started: boolean;
  connected: boolean;
  reconnecting: boolean;
  lastError: string | null;
  lastAttemptAt: string | null;
  lastConnectedAt: string | null;
  fallbackReason: string | null;
}

export interface Project {
  path: string;
  name: string;
  git_root: string;
  last_opened_at?: string;
}

export interface Session {
  id: string;
  project_path: string;
  title: string;
  mode: ModeId;
  status: SessionStatus;
  created_at: string;
  updated_at: string;
  message_count: number;
  provider?: ProviderId;
}

export interface ToolCall {
  id: string;
  tool: string;
  input: Record<string, unknown> | string;
  output?: string;
  status: "running" | "completed" | "failed";
}

export interface Message {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  provider?: ProviderId;
  agent_role?: string;
  timestamp: string;
  streaming?: boolean;
  tool_calls?: ToolCall[];
}

export interface StreamingRun {
  run_id: string;
  text: string;
  provider?: ProviderId;
  role?: string;
  started_at: string;
  updated_at: string;
}

export interface ReviewFinding {
  severity: "P0" | "P1" | "P2" | "P3";
  file: string;
  line_range?: string;
  title: string;
  explanation: string;
}

export interface DiffFile {
  path: string;
  oldContent: string;
  newContent: string;
}

export interface StreamEvent {
  session_id: string;
  run_id?: string;
  type:
    | "text_delta"
    | "tool_use"
    | "tool_result"
    | "run_completed"
    | "run_failed"
    | "review_finding"
    | "message_finalized"
    | "terminal_output"
    | "system";
  provider?: ProviderId;
  role?: string;
  title?: string;
  tool?: string;
  input?: unknown;
  output?: unknown;
  delta?: string;
  content?: string;
  error?: string;
  severity?: ReviewFinding["severity"];
  file?: string;
  line?: number;
  line_range?: string;
  explanation?: string;
  terminal_id?: string;
  data?: string;
  status?: "running" | "completed" | "failed";
  success?: boolean;
}

export interface StreamListener {
  (event: StreamEvent): void;
}
