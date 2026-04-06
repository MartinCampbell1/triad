import { lazy, Suspense, useCallback } from "react";
import { rpc } from "../../lib/rpc";
import type { Message } from "../../lib/types";
import { useSessionStore } from "../../stores/session-store";

interface Props {
  message: Message;
}

const Markdown = lazy(async () => {
  const module = await import("./Markdown");
  return { default: module.Markdown };
});

export function AssistantMessage({ message }: Props) {
  const activeSession = useSessionStore((state) => state.activeSession);

  const handleContinue = useCallback(() => {
    if (!activeSession) return;
    void rpc("session.send", {
      session_id: activeSession.id,
      content: "продолжай",
      project_path: activeSession.project_path,
    });
  }, [activeSession]);

  return (
    <div className="py-2">
      <div className="text-[14px] leading-[1.6] text-text-primary">
        <Suspense fallback={<div className="whitespace-pre-wrap">{message.content}</div>}>
          <Markdown content={message.content} />
        </Suspense>
      </div>
      {/* Action row: copy + continue */}
      <div className="mt-1.5 flex items-center justify-between">
        <button className="flex h-6 w-6 items-center justify-center rounded text-text-tertiary transition-colors hover:text-text-secondary">
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
            <rect x="5" y="5" width="9" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
            <path d="M11 5V3.5A1.5 1.5 0 009.5 2h-6A1.5 1.5 0 002 3.5v6A1.5 1.5 0 003.5 11H5" stroke="currentColor" strokeWidth="1.2" />
          </svg>
        </button>
        <button
          onClick={handleContinue}
          className="rounded-full bg-[rgba(255,255,255,0.06)] px-3.5 py-1.5 text-[12px] text-text-secondary transition-colors hover:bg-[rgba(255,255,255,0.12)] hover:text-text-primary"
        >
          продолжай
        </button>
      </div>
    </div>
  );
}
