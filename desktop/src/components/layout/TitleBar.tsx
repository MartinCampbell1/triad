import { useState } from "react";
import { useProjectStore } from "../../stores/project-store";
import { useSessionStore } from "../../stores/session-store";
import { useUiStore } from "../../stores/ui-store";

function TitleBarButton({
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
      className={`flex h-7 w-7 items-center justify-center rounded-md text-text-tertiary transition-colors hover:bg-white/5 hover:text-text-secondary ${className}`}
    >
      {children}
    </button>
  );
}

export function TitleBar() {
  const sidebarCollapsed = useUiStore((state) => state.sidebarCollapsed);
  const diffPanelOpen = useUiStore((state) => state.diffPanelOpen);
  const diffFiles = useUiStore((state) => state.diffFiles);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);
  const toggleDiffPanel = useUiStore((state) => state.toggleDiffPanel);
  const activeProject = useProjectStore((state) => state.activeProject);
  const activeSession = useSessionStore((state) => state.activeSession);
  const [commitOpen, setCommitOpen] = useState(false);

  // Calculate diff stats from files
  const diffStats = diffFiles.reduce(
    (acc, file) => {
      const oldLines = file.oldContent.split("\n").length;
      const newLines = file.newContent.split("\n").length;
      return {
        additions: acc.additions + Math.max(0, newLines - oldLines),
        deletions: acc.deletions + Math.max(0, oldLines - newLines),
      };
    },
    { additions: 0, deletions: 0 }
  );

  return (
    <div
      data-tauri-drag-region
      className="flex h-[var(--titlebar-height)] items-center border-b border-[rgba(255,255,255,0.06)] bg-transparent"
    >
      {/* Left: sidebar toggle + nav arrows */}
      <div className="flex items-center gap-1 pl-[78px]">
        <TitleBarButton title="Toggle sidebar" onClick={toggleSidebar}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <rect x="1.5" y="2.5" width="13" height="11" rx="2" stroke="currentColor" strokeWidth="1.2" />
            <line x1="5.5" y1="2.5" x2="5.5" y2="13.5" stroke="currentColor" strokeWidth="1.2" />
          </svg>
        </TitleBarButton>
        <TitleBarButton title="Back">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M10 4L6 8L10 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </TitleBarButton>
        <TitleBarButton title="Forward">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M6 4L10 8L6 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </TitleBarButton>
      </div>

      {/* Center: session title + project name */}
      <div data-tauri-drag-region className="flex min-w-0 flex-1 items-center justify-center gap-2 px-4">
        <span className="truncate text-[13px] font-medium text-text-primary">
          {activeSession?.title ?? "Новая беседа"}
        </span>
        <span className="truncate text-[13px] text-text-tertiary">
          {activeProject?.name ?? ""}
        </span>
        <button className="ml-0.5 text-text-tertiary hover:text-text-secondary">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
            <circle cx="3" cy="8" r="1.5" />
            <circle cx="8" cy="8" r="1.5" />
            <circle cx="13" cy="8" r="1.5" />
          </svg>
        </button>
      </div>

      {/* Right: action buttons matching Codex */}
      <div className="flex items-center gap-1 pr-3">
        {/* Run */}
        <TitleBarButton title="Run">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
            <path d="M4 2.5L13 8L4 13.5V2.5Z" />
          </svg>
        </TitleBarButton>

        {/* Split view */}
        <TitleBarButton title="Split view" onClick={toggleDiffPanel}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <rect x="1.5" y="2.5" width="13" height="11" rx="2" stroke="currentColor" strokeWidth="1.2" />
            <line x1="8" y1="2.5" x2="8" y2="13.5" stroke="currentColor" strokeWidth="1.2" />
          </svg>
        </TitleBarButton>

        {/* Separator */}
        <div className="mx-1 h-4 w-px bg-[rgba(255,255,255,0.06)]" />

        {/* Move to worktree */}
        <button className="flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-1 text-[12px] text-text-tertiary transition-colors hover:bg-white/5 hover:text-text-secondary">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
            <path d="M3 8h10M10 5l3 3-3 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="max-w-[180px] truncate">Переместить в рабочее дерево</span>
        </button>

        {/* Commit button with gear icon */}
        {activeSession ? (
          <button
            onClick={() => setCommitOpen(!commitOpen)}
            className="flex items-center gap-1.5 rounded-md border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.04)] px-2.5 py-1 text-[12px] text-text-secondary transition-colors hover:bg-white/[0.06] hover:text-text-primary"
          >
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.2" />
              <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
            </svg>
            <span>Совершить</span>
            <svg width="8" height="8" viewBox="0 0 16 16" fill="none">
              <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        ) : null}

        {/* Separator */}
        <div className="mx-0.5 h-4 w-px bg-[rgba(255,255,255,0.06)]" />

        {/* More icons */}
        <TitleBarButton title="Open externally">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
            <path d="M6 2H3a1 1 0 00-1 1v10a1 1 0 001 1h10a1 1 0 001-1v-3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
            <path d="M9 2h5v5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M14 2L7 9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
        </TitleBarButton>

        <TitleBarButton title="Download">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
            <path d="M8 2v8M8 10L5 7M8 10L11 7" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M3 13h10" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
        </TitleBarButton>

        {/* Diff stats */}
        {(diffStats.additions > 0 || diffStats.deletions > 0) ? (
          <span className="ml-1 text-[12px]">
            <span className="text-green-300">+{diffStats.additions}</span>
            {" "}
            <span className="text-red-300">-{diffStats.deletions}</span>
          </span>
        ) : null}

        {/* Share/copy icon */}
        <TitleBarButton title="Share">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
            <rect x="3" y="3" width="10" height="10" rx="2" stroke="currentColor" strokeWidth="1.2" />
            <path d="M7 3V1h8v8h-2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </TitleBarButton>
      </div>
    </div>
  );
}
