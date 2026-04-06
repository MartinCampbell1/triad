import { useMemo } from "react";
import { useProjectStore } from "../../stores/project-store";
import { useSessionStore } from "../../stores/session-store";
import { useUiStore } from "../../stores/ui-store";
import { ProjectGroup } from "./ProjectGroup";
import { SidebarFooter } from "./SidebarFooter";

export function Sidebar() {
  const { projects, activeProject, setActiveProject, loading, openProject } = useProjectStore();
  const { sessions, activeSession, setActiveSession, createSession, loadSessions } = useSessionStore();
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);

  const groupedSessions = useMemo(() => {
    return projects.map((project) => ({
      project,
      sessions: sessions.filter((session) => session.project_path === project.path),
    }));
  }, [projects, sessions]);

  const handleNewSession = async () => {
    const project = activeProject ?? projects[0];
    if (!project) {
      return;
    }
    const session = await createSession(project.path, "solo");
    setActiveProject(project);
    setActiveSession(session);
  };

  const handleOpenProject = async () => {
    const defaultPath = activeProject?.path ?? projects[0]?.path ?? "";
    const path = globalThis.prompt("Enter the absolute path to the project", defaultPath);
    if (!path?.trim()) {
      return;
    }
    const project = await openProject(path.trim());
    setActiveProject(project);
    await loadSessions("");
  };

  return (
    <aside className="flex h-full w-[var(--sidebar-width)] flex-col border-r border-[var(--color-border)] bg-[var(--color-bg-sidebar)]">
      <div className="flex h-[var(--titlebar-height)] shrink-0 items-center gap-0.5 pl-[78px] pr-2" data-tauri-drag-region>
        <button
          type="button"
          title="Toggle sidebar"
          onClick={toggleSidebar}
          className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--color-text-tertiary)] transition-colors duration-150 hover:bg-[rgba(255,255,255,0.06)] hover:text-[var(--color-text-secondary)]"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <rect x="1.5" y="2.5" width="13" height="11" rx="2" stroke="currentColor" strokeWidth="1.2" />
            <line x1="5.5" y1="2.5" x2="5.5" y2="13.5" stroke="currentColor" strokeWidth="1.2" />
          </svg>
        </button>
      </div>

      <div className="px-2">
        <button
          onClick={handleNewSession}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-[6px] text-left text-[13px] text-[var(--color-text-secondary)] transition-colors duration-150 hover:bg-[rgba(255,255,255,0.04)] hover:text-[var(--color-text-primary)]"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 text-[var(--color-text-tertiary)]">
            <path d="M11.5 1.5L14.5 4.5L5 14H2V11L11.5 1.5Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
          </svg>
          <span>New session</span>
        </button>
        <button
          onClick={handleOpenProject}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-[6px] text-left text-[13px] text-[var(--color-text-secondary)] transition-colors duration-150 hover:bg-[rgba(255,255,255,0.04)] hover:text-[var(--color-text-primary)]"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 text-[var(--color-text-tertiary)]">
            <rect x="1" y="1" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.2" />
            <rect x="9.5" y="1" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.2" />
            <rect x="1" y="9.5" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.2" />
            <rect x="9.5" y="9.5" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.2" />
          </svg>
          <span>Open project</span>
        </button>
      </div>

      <div className="mx-3 my-1.5 border-t border-[var(--color-border)]" />

      <div className="flex items-center justify-between px-3 pb-1 pt-0.5">
        <span className="text-[12px] text-[var(--color-text-tertiary)]">Sessions</span>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {loading && projects.length === 0 ? (
          <div className="px-3 py-6 text-center text-[13px] text-[var(--color-text-tertiary)]">Loading projects...</div>
        ) : null}
        {groupedSessions.map(({ project, sessions: projectSessions }) => (
          <ProjectGroup
            key={project.path}
            project={project}
            sessions={projectSessions}
            activeSessionId={activeSession?.id ?? null}
            onSessionClick={(session) => {
              setActiveProject(project);
              setActiveSession(session);
            }}
          />
        ))}
        {projects.length === 0 ? (
          <div className="px-3 py-6 text-center text-[13px] text-[var(--color-text-tertiary)]">
            Open a project to begin.
          </div>
        ) : null}
      </div>

      <SidebarFooter />
    </aside>
  );
}
