import { useEffect, useRef, useState } from "react";
import { rpc } from "../../lib/rpc";
import { useProviderStore } from "../../stores/provider-store";
import { useProjectStore } from "../../stores/project-store";
import { appendUserMessage, useSessionStore } from "../../stores/session-store";
import { ModelSelector } from "./ModelSelector";
import { ModeSelector } from "./ModeSelector";

export function Composer() {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const { activeProject } = useProjectStore();
  const { activeSession, createSession, clearStreamingText, streamingRuns } = useSessionStore();
  const { mode, accessMode, activeProvider, activeModel } = useProviderStore();

  useEffect(() => {
    const node = textareaRef.current;
    if (!node) {
      return;
    }
    node.style.height = "0px";
    node.style.height = `${Math.min(node.scrollHeight, 144)}px`;
  }, [value]);

  const handleSend = async () => {
    const content = value.trim();
    if (!content) {
      return;
    }

    let session = activeSession;
    if (!session) {
      const project = activeProject ?? (await rpc<{ projects: { path: string }[] }>("project.list")).projects[0];
      if (!project) {
        return;
      }
      session = await createSession(project.path, mode, {
        provider: activeProvider,
        title: content.slice(0, 60),
      });
    }

    clearStreamingText();
    appendUserMessage(session.id, content, activeProvider);
    setValue("");

    if (mode === "critic") {
      await rpc("critic.start", {
        session_id: session.id,
        prompt: content,
        project_path: session.project_path,
        writer: activeProvider,
        model: activeModel,
        max_rounds: 3,
      });
      return;
    }

    if (mode === "brainstorm") {
      await rpc("brainstorm.start", {
        session_id: session.id,
        prompt: content,
        project_path: session.project_path,
        provider: activeProvider,
        model: activeModel,
      });
      return;
    }

    if (mode === "delegate") {
      await rpc("delegate.start", {
        session_id: session.id,
        prompt: content,
        project_path: session.project_path,
        provider: activeProvider,
        model: activeModel,
      });
      return;
    }

    await rpc("session.send", {
      session_id: session.id,
      content,
      project_path: session.project_path,
      provider: activeProvider,
      model: activeModel,
      mode,
    });
  };

  return (
    <div className="px-4 pb-3 pt-2">
      <div className="mx-auto w-full max-w-[var(--composer-width)]">
        {/* Main composer container */}
        <div className="rounded-[18px] border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.03)] px-4 pb-3 pt-3">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                event.preventDefault();
                void handleSend();
              }
            }}
            placeholder="Запросите внесение дополнительных изменений"
            rows={1}
            className="min-h-[22px] w-full resize-none border-0 bg-transparent text-[13px] leading-[1.5] text-text-primary outline-none placeholder:text-text-muted"
          />

          {/* Controls row */}
          <div className="mt-2.5 flex items-center justify-between">
            <div className="flex items-center gap-2">
              {/* Attach button */}
              <button
                type="button"
                className="flex h-7 w-7 items-center justify-center rounded-full text-[15px] text-text-tertiary transition-colors hover:bg-white/[0.06] hover:text-text-secondary"
              >
                +
              </button>
              {/* Model selector */}
              <ModelSelector />
              {/* Reasoning effort */}
              <label className="relative inline-flex cursor-pointer items-center gap-1 text-[13px] text-text-secondary transition-colors hover:text-text-primary">
                <span>Очень высокий</span>
                <select
                  value="very-high"
                  onChange={(event) => {
                    const value = event.target.value as "very-high" | "high" | "medium";
                    useProviderStore.getState().setReasoningEffort(value);
                  }}
                  className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                  aria-label="Reasoning effort selector"
                >
                  <option value="very-high">Очень высокий</option>
                  <option value="high">Высокий</option>
                  <option value="medium">Средний</option>
                </select>
                <svg width="8" height="8" viewBox="0 0 16 16" fill="none" className="text-text-tertiary opacity-60">
                  <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </label>
            </div>

            <div className="flex items-center gap-2">
              {/* Mic button */}
              <button
                type="button"
                className="flex h-7 w-7 items-center justify-center rounded-full text-text-tertiary transition-colors hover:text-text-secondary"
              >
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                  <rect x="5.5" y="1" width="5" height="9" rx="2.5" stroke="currentColor" strokeWidth="1.2" />
                  <path d="M3 7.5a5 5 0 0010 0" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                  <path d="M8 13v2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                </svg>
              </button>
              {/* Send / Stop button */}
              {activeSession?.status === "running" || streamingRuns.length > 0 ? (
                <button
                  type="button"
                  onClick={() => {
                    if (activeSession) {
                      void rpc("session.stop", { session_id: activeSession.id });
                    }
                  }}
                  className="flex h-8 w-8 items-center justify-center rounded-full bg-white/90 text-[#181818] transition-opacity"
                >
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
                    <rect x="0" y="0" width="10" height="10" rx="1.5" />
                  </svg>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => void handleSend()}
                  disabled={!value.trim()}
                  className="flex h-8 w-8 items-center justify-center rounded-full bg-white/90 text-[#181818] transition-opacity disabled:opacity-30"
                >
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                    <path d="M8 12V4M8 4L4 8M8 4L12 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Bottom status bar */}
        <div className="mt-1.5 flex items-center justify-between px-1 text-[12px]">
          <div className="flex items-center gap-3">
            <button className="inline-flex items-center gap-1.5 text-text-tertiary transition-colors hover:text-text-secondary">
              <svg width="11" height="11" viewBox="0 0 16 16" fill="none">
                <rect x="2" y="2" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.3" />
                <path d="M6 6h4v4H6z" stroke="currentColor" strokeWidth="1.3" />
              </svg>
              <span>{accessMode === "local" ? "Местный" : "Удаленный"}</span>
              <svg width="8" height="8" viewBox="0 0 16 16" fill="none" className="opacity-60">
                <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <button className="inline-flex items-center gap-1.5 text-text-warning transition-colors hover:text-orange-300">
              <svg width="11" height="11" viewBox="0 0 16 16" fill="none">
                <path d="M8 1.5L2 4.5V8c0 3.5 2.5 6 6 7 3.5-1 6-3.5 6-7V4.5L8 1.5z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" fill="currentColor" fillOpacity="0.15" />
              </svg>
              <span>Полный доступ</span>
              <svg width="8" height="8" viewBox="0 0 16 16" fill="none" className="opacity-60">
                <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <ModeSelector />
          </div>
          <div className="flex items-center gap-2 text-text-tertiary">
            {activeProject?.path ? (
              <button className="inline-flex items-center gap-1.5 transition-colors hover:text-text-secondary">
                <svg width="11" height="11" viewBox="0 0 16 16" fill="none">
                  <circle cx="4" cy="4" r="1.5" stroke="currentColor" strokeWidth="1" />
                  <circle cx="4" cy="12" r="1.5" stroke="currentColor" strokeWidth="1" />
                  <circle cx="12" cy="8" r="1.5" stroke="currentColor" strokeWidth="1" />
                  <path d="M4 5.5V10.5M4 8h6.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
                </svg>
                <span className="max-w-[200px] truncate text-[12px]">
                  {activeProject.path.split("/").pop() ?? activeProject.path}
                </span>
                <svg width="8" height="8" viewBox="0 0 16 16" fill="none" className="opacity-60">
                  <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            ) : null}
            <button
              className="flex h-5 w-5 items-center justify-center rounded text-text-tertiary transition-colors hover:text-text-secondary"
              title="Refresh"
            >
              <svg width="11" height="11" viewBox="0 0 16 16" fill="none">
                <path d="M2 8a6 6 0 1011.5-2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                <path d="M14 2v4h-4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
