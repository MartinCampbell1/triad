import { useEffect, useRef, useState } from "react";
import { rpc } from "../../lib/rpc";
import { useProviderStore } from "../../stores/provider-store";
import { useProjectStore } from "../../stores/project-store";
import { appendUserMessage, useSessionStore } from "../../stores/session-store";
import { ModeSelector } from "./ModeSelector";
import { ModelSelector } from "./ModelSelector";

export function Composer() {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const { activeProject } = useProjectStore();
  const { activeSession, createSession, clearStreamingText } = useSessionStore();
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

    try {
      if (mode === "critic") {
        await rpc("critic.start", {
          session_id: session.id,
          prompt: content,
          project_path: session.project_path,
          writer: activeProvider,
          model: activeModel,
          max_rounds: 3,
        });
      } else if (mode === "brainstorm") {
        await rpc("brainstorm.start", {
          session_id: session.id,
          prompt: content,
          project_path: session.project_path,
          provider: activeProvider,
          model: activeModel,
        });
      } else if (mode === "delegate") {
        await rpc("delegate.start", {
          session_id: session.id,
          prompt: content,
          project_path: session.project_path,
          provider: activeProvider,
          model: activeModel,
        });
      } else {
        await rpc("session.send", {
          session_id: session.id,
          content,
          project_path: session.project_path,
          provider: activeProvider,
          model: activeModel,
          mode,
        });
      }

      appendUserMessage(session.id, content, activeProvider);
      setValue("");
    } catch (error) {
      if (typeof globalThis.alert === "function") {
        globalThis.alert(error instanceof Error ? error.message : "Failed to send message");
      }
    }
  };

  return (
    <div className="border-t border-border-light bg-[linear-gradient(180deg,transparent,rgba(0,0,0,0.18)),var(--color-bg-surface)] px-4 pb-4 pt-3">
      <div className="mx-auto flex w-full max-w-[var(--composer-width)] flex-col gap-2">
        <div className="rounded-[22px] border border-border-default bg-[linear-gradient(180deg,rgba(255,255,255,0.03),rgba(255,255,255,0.015))] p-4 shadow-glow">
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
            placeholder="Ask Codex anything, @ to add files, / for commands, # for skills"
            rows={1}
            className="min-h-[22px] w-full resize-none border-0 bg-transparent text-[13px] leading-[1.6] text-text-primary outline-none placeholder:text-text-muted"
          />

          <div className="mt-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button
                type="button"
                aria-label="Attach context"
                className="grid h-8 w-8 place-items-center rounded-full border border-border-default bg-black/20 text-[16px] text-text-secondary transition-colors hover:border-border-heavy hover:text-text-primary"
              >
                +
              </button>
              <ModelSelector />
              <label className="relative inline-flex items-center gap-1 rounded-full border border-border-default bg-black/20 px-3 py-1 text-[12px] text-text-secondary transition-colors hover:border-border-heavy">
                <span>
                  {accessMode === "local" ? "Местный" : "Удаленный"}
                </span>
                <select
                  value={accessMode}
                  onChange={(event) => {
                    const next = event.target.value === "remote" ? "remote" : "local";
                    useProviderStore.getState().setAccessMode(next);
                  }}
                  className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                  aria-label="Access mode selector"
                >
                  <option value="local">Местный</option>
                  <option value="remote">Удаленный</option>
                </select>
                <span className="text-[10px] text-text-tertiary">▾</span>
              </label>
              <label className="relative inline-flex items-center gap-1 rounded-full border border-border-default bg-black/20 px-3 py-1 text-[12px] text-text-secondary transition-colors hover:border-border-heavy">
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
                <span className="text-[10px] text-text-tertiary">▾</span>
              </label>
            </div>

            <button
              type="button"
              aria-label="Send message"
              onClick={() => void handleSend()}
              disabled={!value.trim()}
              className="grid h-9 w-9 place-items-center rounded-full bg-accent text-[15px] text-white shadow-[0_0_0_1px_rgba(51,156,255,0.25)] transition-opacity disabled:cursor-not-allowed disabled:opacity-35"
            >
              ↗
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between px-1 text-[12px] text-text-tertiary">
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-text-tertiary" />
              Местный
            </span>
            <span className="inline-flex items-center gap-1 text-text-warning">
              <span className="h-2 w-2 rounded-full bg-text-warning" />
              Полный доступ
            </span>
          </div>
          <div className="max-w-[42%] truncate text-right text-text-secondary">
            {activeProject?.path ?? "Откройте папку проекта"}
          </div>
        </div>
      </div>
    </div>
  );
}
