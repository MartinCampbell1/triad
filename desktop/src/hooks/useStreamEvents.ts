import { useEffect, useRef } from "react";
import { onEvent } from "../lib/rpc";
import { notifyMacOSRunOutcome, setMacOSDockBadgeLabel } from "../lib/tauri-macos";
import type { StreamEvent } from "../lib/types";
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
  const addMessage = useSessionStore((state) => state.addMessage);
  const upsertDiffFile = useUiStore((state) => state.upsertDiffFile);
  const activeRunIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    return onEvent((event: StreamEvent) => {
      const sessionTitle =
        (activeSession?.id === event.session_id ? activeSession.title : sessions.find((session) => session.id === event.session_id)?.title) ??
        "Current session";

      switch (event.type) {
        case "text_delta":
          if (event.run_id) {
            activeRunIdsRef.current.add(event.run_id);
            void setMacOSDockBadgeLabel(String(activeRunIdsRef.current.size));
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
          addMessage(
            {
              id: `tool_${Date.now()}`,
              session_id: activeSession.id,
              role: "system",
              content: `!tool:${JSON.stringify({
                tool: event.tool ?? "tool",
                input: event.input ?? {},
                output: event.output,
                status: event.status ?? "running",
                provider: event.provider,
              })}`,
              provider: event.provider,
              timestamp: new Date().toISOString(),
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
          addMessage(
            {
              id: `tool_result_${Date.now()}`,
              session_id: activeSession.id,
              role: "system",
              content: `!tool:${JSON.stringify({
                tool: event.tool ?? "tool",
                input: event.input ?? {},
                output: event.output,
                status: event.status ?? (event.success === false ? "failed" : "completed"),
                provider: event.provider,
              })}`,
              provider: event.provider,
              timestamp: new Date().toISOString(),
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
          addMessage(
            {
              id: `finding_${Date.now()}`,
              session_id: activeSession.id,
              role: "system",
              content: `!finding:${String(event.severity ?? "P2")}|${String(event.file ?? "src/App.tsx")}|${String(event.title ?? "Finding")}|${String(event.explanation ?? "")}`,
              provider: event.provider,
              timestamp: new Date().toISOString(),
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
              id: `system_${Date.now()}`,
              session_id: activeSession.id,
              role: "system",
              content: String(event.content ?? ""),
              provider: event.provider,
              timestamp: new Date().toISOString(),
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
          addMessage(
            {
              id: `error_${Date.now()}`,
              session_id: activeSession.id,
              role: "system",
              content: event.error ?? "Run failed",
              provider: event.provider,
              timestamp: new Date().toISOString(),
            },
            { count: false }
          );
          break;
        default:
          break;
      }
    });
  }, [activeSession?.id, activeSession?.title, addMessage, appendStreamingText, finalizeStreaming, sessions, upsertDiffFile]);
}
