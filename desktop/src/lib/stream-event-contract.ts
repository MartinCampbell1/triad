// Generated from schemas/stream-event.schema.json by scripts/generate_stream_event_contract.py
export const STREAM_SCHEMA_VERSION = 1 as const;

export const STREAM_EVENT_ALIASES = {
  "message_delta": "text_delta",
  "message_completed": "message_finalized",
  "tool_started": "tool_use",
  "tool_finished": "tool_result",
  "completed": "run_completed",
  "error": "run_failed",
  "status": "system"
} as const;

export const STREAM_EVENT_TYPES = [
  "text_delta",
  "message_finalized",
  "tool_use",
  "tool_result",
  "review_finding",
  "diff_snapshot",
  "stderr",
  "run_completed",
  "run_failed",
  "terminal_output",
  "system"
] as const;
export type CanonicalStreamEventType = typeof STREAM_EVENT_TYPES[number];

export const MESSAGE_EVENT_TYPES = [
  "message_finalized"
] as const;
export const TOOL_EVENT_TYPES = [
  "tool_use",
  "tool_result"
] as const;
export const SYSTEM_NOTICE_EVENT_TYPES = [
  "system",
  "stderr",
  "run_failed",
  "review_finding",
  "diff_snapshot"
] as const;
export const TERMINAL_COMPLETION_EVENT_TYPES = [
  "run_completed",
  "run_failed"
] as const;
