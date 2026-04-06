import { useProjectStore } from "../../stores/project-store";
import { useSessionStore } from "../../stores/session-store";
import { useUiStore } from "../../stores/ui-store";

function IconButton({
  title,
  onClick,
  children,
  className = "",
}: {
  title: string;
  onClick?: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={`flex h-7 w-7 items-center justify-center rounded-md text-[var(--color-text-tertiary)] transition-colors duration-150 hover:bg-[rgba(255,255,255,0.06)] hover:text-[var(--color-text-secondary)] ${className}`}
    >
      {children}
    </button>
  );
}

export function TitleBar() {
  const sidebarCollapsed = useUiStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);
  const toggleDiffPanel = useUiStore((state) => state.toggleDiffPanel);
  const toggleCompareReplayPanel = useUiStore((state) => state.toggleCompareReplayPanel);
  const terminalSessions = useUiStore((state) => state.terminalSessions);
  const activeProject = useProjectStore((state) => state.activeProject);
  const activeSession = useSessionStore((state) => state.activeSession);
  const terminalHost = activeSession?.terminal_host ?? null;
  const linkedTerminal = terminalHost?.terminal_id
    ? terminalSessions.find((session) => session.id === terminalHost.terminal_id) ?? null
    : null;
  const linkedShellLabel = terminalHost
    ? linkedTerminal?.title ?? terminalHost.terminal_title ?? terminalHost.terminal_cwd ?? "Linked shell"
    : null;
  const interactiveLabel = terminalHost
    ? terminalHost.live
      ? "Live terminal run"
      : "Terminal-linked run"
    : null;

  return (
    <div
      data-tauri-drag-region
      className="flex h-[var(--titlebar-height)] shrink-0 items-center border-b border-[var(--color-border)] bg-transparent"
    >
      {sidebarCollapsed ? (
        <div className="flex items-center gap-0.5 pl-[78px]">
          <IconButton title="Toggle sidebar" onClick={toggleSidebar}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="1.5" y="2.5" width="13" height="11" rx="2" stroke="currentColor" strokeWidth="1.2" />
              <line x1="5.5" y1="2.5" x2="5.5" y2="13.5" stroke="currentColor" strokeWidth="1.2" />
            </svg>
          </IconButton>
        </div>
      ) : null}

      <div data-tauri-drag-region className="flex min-w-0 flex-1 flex-col items-center justify-center px-4">
        <span className="truncate text-[13px] font-medium text-[var(--color-text-primary)]">
          {activeSession?.title ?? "New session"}
        </span>
        {terminalHost ? (
          <div className="flex min-w-0 items-center gap-2">
            <span className="rounded-full border border-[rgba(255,255,255,0.08)] px-2 py-0.5 text-[10px] uppercase tracking-[0.1em] text-[var(--color-text-tertiary)]">
              {interactiveLabel}
            </span>
            <span className="truncate text-[11px] text-[var(--color-text-tertiary)]">
              {linkedShellLabel}
            </span>
          </div>
        ) : activeProject ? (
          <span className="truncate text-[11px] text-[var(--color-text-tertiary)]">{activeProject.name}</span>
        ) : null}
      </div>

      <div className="flex items-center gap-0.5 pr-3">
        <IconButton title="Session compare and replay" onClick={() => toggleCompareReplayPanel("compare")}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2.5 4.5H13.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
            <path d="M2.5 8H9.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
            <path d="M2.5 11.5H13.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
            <path d="M11 6L13.5 8L11 10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </IconButton>
        <IconButton title="Split view" onClick={toggleDiffPanel}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <rect x="1.5" y="2.5" width="13" height="11" rx="2" stroke="currentColor" strokeWidth="1.2" />
            <line x1="8" y1="2.5" x2="8" y2="13.5" stroke="currentColor" strokeWidth="1.2" />
          </svg>
        </IconButton>
      </div>
    </div>
  );
}
