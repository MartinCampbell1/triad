import { STREAM_SCHEMA_VERSION } from "./stream-event-contract";
import type { CanonicalStreamEventType } from "./stream-event-contract";

export type ProviderId = "claude" | "codex" | "gemini";
export type ModeId = "solo" | "critic" | "brainstorm" | "delegate";
export type SessionStatus = "active" | "running" | "paused" | "completed" | "failed";
export type MessageRole = "user" | "assistant" | "system";
export type BridgeBackendMode = "tauri" | "offline";

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

export interface ReviewFinding {
  severity: "P0" | "P1" | "P2" | "P3";
  file: string;
  line?: number;
  line_range?: string;
  title: string;
  explanation: string;
}

export interface DiffSnapshot {
  path: string;
  old_text: string;
  new_text: string;
}

export interface ToolEventPayload {
  tool: string;
  input: Record<string, unknown> | string;
  output?: unknown;
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
  event_type?: "tool_use" | "tool_result" | "review_finding" | "diff_snapshot" | "run_failed" | "stderr";
  tool_event?: ToolEventPayload;
  review_finding?: ReviewFinding;
  diff_snapshot?: DiffSnapshot | null;
  authoritative?: boolean;
}

export interface StreamingRun {
  run_id: string;
  text: string;
  provider?: ProviderId;
  role?: string;
  started_at: string;
  updated_at: string;
}

export interface DiffFile {
  path: string;
  oldContent: string;
  newContent: string;
}

interface StreamBaseEvent {
  schema_version?: typeof STREAM_SCHEMA_VERSION;
  session_id: string;
  run_id?: string;
  provider?: ProviderId;
  role?: string;
  source?: string;
  timestamp?: string;
  authoritative?: boolean;
  message_id?: string;
}

export type TextDeltaEvent = StreamBaseEvent & {
  type: Extract<CanonicalStreamEventType, "text_delta">;
  delta: string;
};

export type MessageFinalizedEvent = StreamBaseEvent & {
  type: Extract<CanonicalStreamEventType, "message_finalized">;
  content: string;
};

export type ToolUseEvent = StreamBaseEvent & {
  type: Extract<CanonicalStreamEventType, "tool_use">;
  tool: string;
  input?: unknown;
  output?: unknown;
  status: "running" | "completed" | "failed";
};

export type ToolResultEvent = StreamBaseEvent & {
  type: Extract<CanonicalStreamEventType, "tool_result">;
  tool: string;
  input?: unknown;
  output?: unknown;
  status: "running" | "completed" | "failed";
  success?: boolean;
};

export type ReviewFindingEvent = StreamBaseEvent & {
  type: Extract<CanonicalStreamEventType, "review_finding">;
  severity: ReviewFinding["severity"];
  file: string;
  title: string;
  explanation: string;
  line?: number;
  line_range?: string;
};

export type DiffSnapshotEvent = StreamBaseEvent & {
  type: Extract<CanonicalStreamEventType, "diff_snapshot">;
  path: string;
  old_text: string;
  new_text: string;
};

export type StderrEvent = StreamBaseEvent & {
  type: Extract<CanonicalStreamEventType, "stderr">;
  data: string;
};

export type RunCompletedEvent = StreamBaseEvent & {
  type: Extract<CanonicalStreamEventType, "run_completed">;
};

export type RunFailedEvent = StreamBaseEvent & {
  type: Extract<CanonicalStreamEventType, "run_failed">;
  error: string;
};

export type TerminalOutputEvent = StreamBaseEvent & {
  type: Extract<CanonicalStreamEventType, "terminal_output">;
  terminal_id: string;
  data: string;
};

export type SystemEvent = StreamBaseEvent & {
  type: Extract<CanonicalStreamEventType, "system">;
  content: string;
};

export type StreamEvent =
  | TextDeltaEvent
  | MessageFinalizedEvent
  | ToolUseEvent
  | ToolResultEvent
  | ReviewFindingEvent
  | DiffSnapshotEvent
  | StderrEvent
  | RunCompletedEvent
  | RunFailedEvent
  | TerminalOutputEvent
  | SystemEvent;

export interface StreamListener {
  (event: StreamEvent): void;
}
