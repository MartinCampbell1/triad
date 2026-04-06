import { useEffect, useRef } from "react";
import { parseStructuredDiffPatch } from "../lib/diff";
import { onEvent } from "../lib/rpc";
import { notifyMacOSRunOutcome, setMacOSDockBadgeLabel } from "../lib/tauri-macos";
import type { StreamEvent, TerminalHostMetadata } from "../lib/types";
import { useSessionStore } from "../stores/session-store";
import { useUiStore } from "../stores/ui-store";

function parseToolInput(input: unknown) {
  if (input && typeof input === "object") {
    return input as Record<string, unknown>;
  }
  return {};
}

export function useStreamEvents() {
  const activeSession = useSessionStore((state) => state.activeSession);
  const sessions = useSessionStore((state) => state.sessions);
  const appendStreamingText = useSessionStore((state) => state.appendStreamingText);
  const finalizeStreaming = useSessionStore((state) => state.finalizeStreaming);
  const addTimelineItem = useSessionStore((state) => state.addTimelineItem);
  const updateSessionTerminalHost = useSessionStore((state) => state.updateSessionTerminalHost);
  const upsertDiffFile = useUiStore((state) => state.upsertDiffFile);
  const setDiffFiles = useUiStore((state) => state.setDiffFiles);
  const activeRunIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    return onEvent((event: StreamEvent) => {
      const sessionTitle =
        (activeSession?.id === event.session_id ? activeSession.title : sessions.find((session) => session.id === event.session_id)?.title) ??
        "Current session";
      const currentSession =
        activeSession?.id === event.session_id
          ? activeSession
          : sessions.find((session) => session.id === event.session_id) ?? null;
      const currentTerminalHost = currentSession?.terminal_host ?? null;

      const syncTerminalHost = (patch: Partial<TerminalHostMetadata>) => {
        const terminalId = event.linked_terminal_id ?? event.terminal_id ?? currentTerminalHost?.terminal_id;
        if (!terminalId) {
          return;
        }
        updateSessionTerminalHost(event.session_id, {
          ...currentTerminalHost,
          ...patch,
          terminal_id: terminalId,
        });
      };

      switch (event.type) {
        case "text_delta":
          if (event.run_id) {
            activeRunIdsRef.current.add(event.run_id);
            void setMacOSDockBadgeLabel(String(activeRunIdsRef.current.size));
          }
          if (event.linked_terminal_id || currentTerminalHost?.terminal_id) {
            syncTerminalHost({
              live: true,
              linked_run_id: event.run_id ?? currentTerminalHost?.linked_run_id ?? null,
              terminal_status: "ready",
              transcript_mode: event.transcript_mode ?? currentTerminalHost?.transcript_mode ?? "partial",
            });
          }
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          appendStreamingText(event.run_id, String(event.delta ?? ""), event.provider, event.role);
          break;
        case "tool_use":
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          addTimelineItem(
            {
              id: `tool_${Date.now()}`,
              kind: "tool_call",
              session_id: activeSession.id,
              ts: new Date().toISOString(),
              provider: event.provider,
              run_id: event.run_id,
              role: event.role,
              tool: String(event.tool ?? "tool"),
              input:
                typeof event.input === "string" || (event.input && typeof event.input === "object")
                  ? (event.input as Record<string, unknown> | string)
                  : null,
              output: event.output,
              status: event.status ?? "running",
            },
            { count: false }
          );

          if (String(event.tool ?? "") === "Edit" || String(event.tool ?? "") === "Write") {
            const input = parseToolInput(event.input);
            const path = String(input.file_path ?? input.path ?? input.target_file ?? "untitled");
            const oldText = String(input.old_string ?? input.oldText ?? "");
            const newText = String(input.new_string ?? input.newText ?? input.content ?? "");
            if (path && (oldText || newText)) {
              upsertDiffFile({
                path,
                oldContent: oldText,
                newContent: newText,
              });
            }
          }
          break;
        case "tool_result":
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          addTimelineItem(
            {
              id: `tool_result_${Date.now()}`,
              kind: "tool_call",
              session_id: activeSession.id,
              ts: new Date().toISOString(),
              provider: event.provider,
              run_id: event.run_id,
              role: event.role,
              tool: String(event.tool ?? "tool"),
              input:
                typeof event.input === "string" || (event.input && typeof event.input === "object")
                  ? (event.input as Record<string, unknown> | string)
                  : null,
              output: event.output,
              status: event.status ?? (event.success === false ? "failed" : "completed"),
            },
            { count: false }
          );
          break;
        case "message_finalized":
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          finalizeStreaming(event.run_id, String(event.content ?? ""), event.provider, event.role);
          break;
        case "review_finding":
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          addTimelineItem(
            {
              id: `finding_${Date.now()}`,
              kind: "review_finding",
              session_id: activeSession.id,
              ts: new Date().toISOString(),
              provider: event.provider,
              run_id: event.run_id,
              role: event.role,
              severity: event.severity ?? "P2",
              file: String(event.file ?? ""),
              line: event.line,
              line_range: event.line_range,
              title: String(event.title ?? "Finding"),
              explanation: String(event.explanation ?? ""),
            },
            { count: false }
          );
          break;
        case "diff_snapshot": {
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          const patch = String(event.patch ?? "");
          const parsedFiles = parseStructuredDiffPatch(patch);
          setDiffFiles(parsedFiles, { open: parsedFiles.length > 0 });
          addTimelineItem(
            {
              id: `diff_${Date.now()}`,
              kind: "diff_snapshot",
              session_id: activeSession.id,
              ts: new Date().toISOString(),
              provider: event.provider,
              run_id: event.run_id,
              role: event.role,
              patch,
              diff_stat: event.diff_stat,
            },
            { count: false }
          );
          break;
        }
        case "system":
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          addTimelineItem(
            {
              id: `system_${Date.now()}`,
              kind: "system_notice",
              session_id: activeSession.id,
              ts: new Date().toISOString(),
              provider: event.provider,
              run_id: event.run_id,
              role: event.role,
              level: "info",
              title: event.title ? String(event.title) : undefined,
              body: String(event.content ?? ""),
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
          if (event.linked_terminal_id || currentTerminalHost?.terminal_id) {
            syncTerminalHost({
              live: false,
              linked_run_id: null,
              terminal_status: event.terminal_status ?? "unavailable",
              transcript_mode: event.transcript_mode ?? currentTerminalHost?.transcript_mode ?? "partial",
            });
          }
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
          if (event.linked_terminal_id || currentTerminalHost?.terminal_id) {
            syncTerminalHost({
              live: false,
              linked_run_id: null,
              terminal_status: event.terminal_status ?? "unavailable",
              transcript_mode: event.transcript_mode ?? currentTerminalHost?.transcript_mode ?? "partial",
            });
          }
          void notifyMacOSRunOutcome({
            title: sessionTitle,
            outcome: "failed",
            provider: event.provider,
            error: event.error ?? "Run failed",
          });
          if (!activeSession || event.session_id !== activeSession.id) {
            break;
          }
          finalizeStreaming(event.run_id, undefined, event.provider, event.role);
          addTimelineItem(
            {
              id: `error_${Date.now()}`,
              kind: "system_notice",
              session_id: activeSession.id,
              ts: new Date().toISOString(),
              provider: event.provider,
              run_id: event.run_id,
              role: event.role,
              level: "error",
              title: "Run failed",
              body: event.error ?? "Run failed",
            },
            { count: false }
          );
          break;
        case "terminal_output":
          if (event.terminal_kind === "provider" && event.session_id) {
            syncTerminalHost({
              live: true,
              linked_run_id: event.run_id ?? currentTerminalHost?.linked_run_id ?? null,
              terminal_status: "ready",
              transcript_mode: event.transcript_mode ?? currentTerminalHost?.transcript_mode ?? "partial",
            });
          }
          break;
        default:
          break;
      }
    });
  }, [
    activeSession,
    addTimelineItem,
    appendStreamingText,
    finalizeStreaming,
    sessions,
    setDiffFiles,
    updateSessionTerminalHost,
    upsertDiffFile,
  ]);
}
