export type ProviderId = "claude" | "codex" | "gemini";
export type ModeId = "solo" | "critic" | "brainstorm" | "delegate";
export type ProviderSurface = "interactive" | "headless";
export type SessionStatus = "active" | "running" | "paused" | "completed" | "failed";
export type MessageRole = "user" | "assistant" | "system";
export type BridgeBackendMode = "tauri" | "offline";
export type AttachmentKind = "file" | "image";

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

export interface TerminalHostMetadata {
  terminal_id?: string | null;
  terminal_title?: string | null;
  terminal_cwd?: string | null;
  terminal_status?: "starting" | "ready" | "unavailable" | "unknown";
  live?: boolean;
  transcript_mode?: "partial" | "typed" | "live" | "full";
  linked_run_id?: string | null;
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
  diff_additions?: number;
  diff_deletions?: number;
  terminal_host?: TerminalHostMetadata | null;
}

export interface ToolCall {
  id: string;
  tool: string;
  input: Record<string, unknown> | string;
  output?: string;
  status: "running" | "completed" | "failed";
}

export interface Attachment {
  id: string;
  name: string;
  path: string;
  kind: AttachmentKind;
  size_bytes?: number;
  source?: string;
  mime_type?: string;
}

export interface AttachmentDraft {
  id: string;
  name: string;
  kind: AttachmentKind;
  path?: string;
  size_bytes?: number;
  source?: string;
  mime_type?: string;
  content_base64?: string;
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
  attachments?: Attachment[];
  terminal_host?: TerminalHostMetadata | null;
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

export interface RuntimeProviderCapability {
  mode: ProviderSurface;
  capabilities: string[];
}

export interface RuntimeProvider {
  id: ProviderId;
  label: string;
  surfaces: RuntimeProviderCapability[];
}

export interface RuntimeModel {
  id: string;
  label: string;
  provider: ProviderId;
  description?: string;
}

export interface RuntimeMode {
  id: ModeId;
  label: string;
  description?: string;
}

export interface RuntimeCapabilities {
  providers: RuntimeProvider[];
  models: RuntimeModel[];
  modes: RuntimeMode[];
  defaults: {
    provider: ProviderId;
    model: string;
    mode: ModeId;
  };
}

interface TimelineItemBase {
  id: string;
  session_id: string;
  ts: string;
  provider?: ProviderId;
  run_id?: string;
  role?: string;
  terminal_host?: TerminalHostMetadata | null;
}

export interface UserTimelineItem extends TimelineItemBase {
  kind: "user_message";
  text: string;
  attachments?: Attachment[];
}

export interface AssistantTimelineItem extends TimelineItemBase {
  kind: "assistant_message";
  text: string;
  status: "streaming" | "done" | "error";
}

export interface SystemNoticeTimelineItem extends TimelineItemBase {
  kind: "system_notice";
  level: "info" | "warning" | "error";
  title?: string;
  body: string;
}

export interface ToolCallTimelineItem extends TimelineItemBase {
  kind: "tool_call";
  tool: string;
  input: Record<string, unknown> | string | null;
  output?: unknown;
  status: "running" | "completed" | "failed";
}

export interface ReviewFindingTimelineItem extends TimelineItemBase {
  kind: "review_finding";
  severity: ReviewFinding["severity"];
  file: string;
  line?: number;
  line_range?: string;
  title: string;
  explanation: string;
}

export interface DiffSnapshotTimelineItem extends TimelineItemBase {
  kind: "diff_snapshot";
  patch: string;
  diff_stat?: string;
}

export type TimelineItem =
  | UserTimelineItem
  | AssistantTimelineItem
  | SystemNoticeTimelineItem
  | ToolCallTimelineItem
  | ReviewFindingTimelineItem
  | DiffSnapshotTimelineItem;

export interface TimelineItemSummary {
  kind: TimelineItem["kind"];
  label: string;
  excerpt?: string;
}

export interface SessionCompareRow {
  index: number;
  status: "same" | "different" | "left_only" | "right_only";
  left: TimelineItem | null;
  right: TimelineItem | null;
  left_summary: TimelineItemSummary | null;
  right_summary: TimelineItemSummary | null;
}

export interface SessionCompareOverview {
  left_total: number;
  right_total: number;
  shared_prefix_count: number;
  left_counts: Partial<Record<TimelineItem["kind"], number>>;
  right_counts: Partial<Record<TimelineItem["kind"], number>>;
}

export interface SessionCompareResult {
  left_session: Session;
  right_session: Session;
  overview: SessionCompareOverview;
  rows: SessionCompareRow[];
}

export interface SessionReplayFrame {
  index: number;
  step: number;
  ts: string;
  summary: TimelineItemSummary;
  item: TimelineItem;
  counts: Partial<Record<TimelineItem["kind"], number>>;
}

export interface SessionReplayMarker {
  index: number;
  kind: TimelineItem["kind"];
  ts: string;
  label: string;
}

export interface SessionReplay {
  session: Session;
  timeline: TimelineItem[];
  total_frames: number;
  frames: SessionReplayFrame[];
  markers: SessionReplayMarker[];
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
    | "diff_snapshot"
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
  patch?: string;
  diff_stat?: string;
  terminal_id?: string;
  linked_terminal_id?: string;
  transcript_mode?: TerminalHostMetadata["transcript_mode"];
  terminal_kind?: "shell" | "provider";
  terminal_status?: TerminalHostMetadata["terminal_status"];
  data?: string;
  status?: "running" | "completed" | "failed";
  success?: boolean;
}

export interface StreamListener {
  (event: StreamEvent): void;
}
