import { useEffect, useRef } from "react";
import { onEvent } from "../lib/rpc";
import { notifyMacOSRunOutcome, setMacOSDockBadgeLabel } from "../lib/tauri-macos";
import type { DiffSnapshot, Message, StreamEvent, ToolEventPayload } from "../lib/types";
import { useSessionStore } from "../stores/session-store";
import { useUiStore } from "../stores/ui-store";

function makeEventMessageId(prefix: string, event: StreamEvent, timestamp: string) {
  if (event.message_id) {
    return `${prefix}_${event.message_id}`;
  }
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${event.run_id ?? event.type}_${crypto.randomUUID()}`;
  }
  return `${prefix}_${event.run_id ?? event.type}_${timestamp}_${Math.random().toString(36).slice(2, 8)}`;
}

function parseToolInput(input: unknown) {
  if (input && typeof input === "object") {
    return input as Record<string, unknown>;
  }
  return {};
}

function normalizeToolInput(input: unknown): Record<string, unknown> | string {
  if (typeof input === "string") {
    return input;
  }
  return parseToolInput(input);
}

function maybeBuildDiffSnapshot(tool: string, input: unknown, fallbackOutput?: unknown): DiffSnapshot | null {
  if (tool !== "Edit" && tool !== "Write") {
    return null;
  }
  const parsedInput = parseToolInput(input);
  const path = String(parsedInput.file_path ?? parsedInput.path ?? parsedInput.target_file ?? "");
  const oldText = String(parsedInput.old_text ?? parsedInput.old_string ?? parsedInput.oldText ?? "");
  const newText = String(
    parsedInput.new_text ??
      parsedInput.new_string ??
      parsedInput.newText ??
      parsedInput.content ??
      fallbackOutput ??
      ""
  );
  if (!path || (!oldText && !newText)) {
    return null;
  }
  return {
    path,
    old_text: oldText,
    new_text: newText,
  };
}

function buildToolMessage(
  sessionId: string,
  provider: Message["provider"],
  timestamp: string,
  eventId: string,
  eventType: Message["event_type"],
  toolEvent: ToolEventPayload,
  diffSnapshot: DiffSnapshot | null
): Message {
  return {
    id: eventId,
    session_id: sessionId,
    role: "system",
    content: toolEvent.tool,
    provider,
    timestamp,
    event_type: eventType,
    tool_event: toolEvent,
    diff_snapshot: diffSnapshot,
  };
}

export function useStreamEvents() {
  const appendStreamingText = useSessionStore((state) => state.appendStreamingText);
  const updateSessionStatus = useSessionStore((state) => state.updateSessionStatus);
  const finalizeStreaming = useSessionStore((state) => state.finalizeStreaming);
  const clearStreamingText = useSessionStore((state) => state.clearStreamingText);
  const addMessage = useSessionStore((state) => state.addMessage);
  const upsertDiffFile = useUiStore((state) => state.upsertDiffFile);
  const activeRunIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    return onEvent((event: StreamEvent) => {
      const { activeSession, sessions } = useSessionStore.getState();
      const sessionTitle =
        (activeSession?.id === event.session_id
          ? activeSession.title
          : sessions.find((session) => session.id === event.session_id)?.title) ?? "Current session";
      const timestamp = new Date().toISOString();

      switch (event.type) {
        case "text_delta":
          if (event.run_id) {
            activeRunIdsRef.current.add(event.run_id);
            void setMacOSDockBadgeLabel(String(activeRunIdsRef.current.size));
          }
          updateSessionStatus(event.session_id, "running");
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          appendStreamingText(event.run_id, event.delta, event.provider, event.role);
          break;
        case "tool_use": {
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          const toolEvent: ToolEventPayload = {
            tool: event.tool,
            input: normalizeToolInput(event.input),
            output: event.output,
            status: event.status,
          };
          const diffSnapshot = maybeBuildDiffSnapshot(event.tool, event.input, event.output);
          addMessage(
            buildToolMessage(
              activeSession.id,
              event.provider,
              timestamp,
              makeEventMessageId("tool", event, timestamp),
              "tool_use",
              toolEvent,
              diffSnapshot
            ),
            { count: false }
          );
          if (diffSnapshot) {
            upsertDiffFile({
              path: diffSnapshot.path,
              oldContent: diffSnapshot.old_text,
              newContent: diffSnapshot.new_text,
            });
          }
          break;
        }
        case "tool_result": {
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          const toolEvent: ToolEventPayload = {
            tool: event.tool,
            input: normalizeToolInput(event.input),
            output: event.output,
            status: event.status,
          };
          const diffSnapshot = maybeBuildDiffSnapshot(event.tool, event.input, event.output);
          addMessage(
            buildToolMessage(
              activeSession.id,
              event.provider,
              timestamp,
              makeEventMessageId("tool", event, timestamp),
              "tool_result",
              toolEvent,
              diffSnapshot
            ),
            { count: false }
          );
          if (diffSnapshot) {
            upsertDiffFile({
              path: diffSnapshot.path,
              oldContent: diffSnapshot.old_text,
              newContent: diffSnapshot.new_text,
            });
          }
          break;
        }
        case "diff_snapshot":
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          addMessage(
            {
              id: makeEventMessageId("diff", event, timestamp),
              session_id: activeSession.id,
              role: "system",
              content: event.path,
              provider: event.provider,
              timestamp,
              event_type: "diff_snapshot",
              diff_snapshot: {
                path: event.path,
                old_text: event.old_text,
                new_text: event.new_text,
              },
            },
            { count: false }
          );
          upsertDiffFile({
            path: event.path,
            oldContent: event.old_text,
            newContent: event.new_text,
          });
          break;
        case "message_finalized":
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          if (event.authoritative || event.message_id) {
            clearStreamingText(event.run_id);
            const messageId = event.message_id
              ? `msg_assistant_${event.message_id}`
              : makeEventMessageId("assistant", event, timestamp);
            addMessage(
              {
                id: messageId,
                session_id: activeSession.id,
                role: "assistant",
                content: event.content,
                provider: event.provider,
                agent_role: event.role,
                timestamp,
                authoritative: event.authoritative,
              },
              { count: true }
            );
            break;
          }
          finalizeStreaming(event.run_id, event.content, event.provider, event.role);
          break;
        case "review_finding":
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          addMessage(
            {
              id: makeEventMessageId("finding", event, timestamp),
              session_id: activeSession.id,
              role: "system",
              content: event.title,
              provider: event.provider,
              timestamp,
              event_type: "review_finding",
              review_finding: {
                severity: event.severity,
                file: event.file,
                line: event.line,
                line_range: event.line_range,
                title: event.title,
                explanation: event.explanation,
              },
            },
            { count: false }
          );
          break;
        case "stderr":
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          addMessage(
            {
              id: makeEventMessageId("stderr", event, timestamp),
              session_id: activeSession.id,
              role: "system",
              content: event.data,
              provider: event.provider,
              timestamp,
              event_type: "stderr",
            },
            { count: false }
          );
          break;
        case "system":
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          addMessage(
            {
              id: makeEventMessageId("system", event, timestamp),
              session_id: activeSession.id,
              role: "system",
              content: event.content,
              provider: event.provider,
              timestamp,
            },
            { count: false }
          );
          break;
        case "run_completed":
          if (event.run_id) {
            activeRunIdsRef.current.delete(event.run_id);
            void setMacOSDockBadgeLabel(
              activeRunIdsRef.current.size > 0 ? String(activeRunIdsRef.current.size) : undefined
            );
          }
          updateSessionStatus(event.session_id, "completed");
          if (activeSession && event.session_id === activeSession.id) {
            finalizeStreaming(event.run_id);
          }
          void notifyMacOSRunOutcome({
            title: sessionTitle,
            outcome: "completed",
            provider: event.provider,
          });
          break;
        case "run_failed":
          if (event.run_id) {
            activeRunIdsRef.current.delete(event.run_id);
            void setMacOSDockBadgeLabel(
              activeRunIdsRef.current.size > 0 ? String(activeRunIdsRef.current.size) : undefined
            );
          }
          updateSessionStatus(event.session_id, "failed");
          void notifyMacOSRunOutcome({
            title: sessionTitle,
            outcome: "failed",
            provider: event.provider,
            error: event.error,
          });
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          finalizeStreaming(event.run_id, undefined, event.provider, event.role);
          addMessage(
            {
              id: makeEventMessageId("error", event, timestamp),
              session_id: activeSession.id,
              role: "system",
              content: event.error,
              provider: event.provider,
              timestamp,
              event_type: "run_failed",
            },
            { count: false }
          );
          break;
        default:
          break;
      }
    });
  }, [
    addMessage,
    appendStreamingText,
    clearStreamingText,
    finalizeStreaming,
    updateSessionStatus,
    upsertDiffFile,
  ]);
}
