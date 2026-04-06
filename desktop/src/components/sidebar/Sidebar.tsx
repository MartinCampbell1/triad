import { useMemo } from "react";
import { useProjectStore } from "../../stores/project-store";
import { useSessionStore } from "../../stores/session-store";
import { ProjectGroup } from "./ProjectGroup";
import { SearchPanel } from "./SearchPanel";
import { SidebarFooter } from "./SidebarFooter";

export function Sidebar() {
  const { projects, activeProject, setActiveProject, loadProjects, loading, openProject } = useProjectStore();
  const { sessions, activeSession, setActiveSession, createSession, loadSessions } = useSessionStore();

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
    const project = await openProject("/Users/martin/triad");
    setActiveProject(project);
    await loadSessions("");
  };

  return (
    <aside className="flex h-full w-[var(--sidebar-width)] flex-col border-r border-[rgba(255,255,255,0.06)] bg-[var(--color-bg-surface)]">
      {/* Top nav items */}
      <div className="px-3 pb-1 pt-[52px]">
        <button
          onClick={handleNewSession}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-[7px] text-left text-[13px] text-text-secondary transition-colors hover:bg-white/[0.04] hover:text-text-primary"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="flex-shrink-0 text-text-tertiary">
            <path d="M11.5 1.5L14.5 4.5L5 14H2V11L11.5 1.5Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
          </svg>
          <span>Новая беседа</span>
        </button>
        <button className="flex w-full items-center gap-3 rounded-lg px-3 py-[7px] text-left text-[13px] text-text-secondary transition-colors hover:bg-white/[0.04] hover:text-text-primary">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="flex-shrink-0 text-text-tertiary">
            <rect x="1" y="1" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.2" />
            <rect x="9.5" y="1" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.2" />
            <rect x="1" y="9.5" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.2" />
            <rect x="9.5" y="9.5" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.2" />
          </svg>
          <span>Навыки и приложения</span>
        </button>
        <button className="flex w-full items-center gap-3 rounded-lg px-3 py-[7px] text-left text-[13px] text-text-secondary transition-colors hover:bg-white/[0.04] hover:text-text-primary">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="flex-shrink-0 text-text-tertiary">
            <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.2" />
            <path d="M8 4V8L10.5 10.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
          <span>Автоматизации</span>
        </button>
      </div>

      {/* Separator */}
      <div className="mx-3 my-1 border-t border-[rgba(255,255,255,0.06)]" />

      {/* Conversations header */}
      <div className="flex items-center justify-between px-4 pb-1 pt-1">
        <span className="text-[12px] text-text-tertiary">Беседы</span>
        <div className="flex items-center gap-0.5">
          {/* Collapse-diagonal arrows (matches Codex ↙↗) */}
          <button
            className="flex h-6 w-6 items-center justify-center rounded text-text-tertiary hover:text-text-secondary"
            title="Collapse all"
          >
            <svg width="11" height="11" viewBox="0 0 16 16" fill="none">
              <path d="M10 2L6 6M6 6V2M6 6H2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M6 14L10 10M10 10V14M10 10H14" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          {/* Filter lines (matches Codex ≡) */}
          <button
            className="flex h-6 w-6 items-center justify-center rounded text-text-tertiary hover:text-text-secondary"
            title="Filter"
          >
            <svg width="11" height="11" viewBox="0 0 16 16" fill="none">
              <path d="M2 4h12M4 8h8M6 12h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
            </svg>
          </button>
          {/* Add folder (matches Codex 📁+) */}
          <button
            onClick={handleOpenProject}
            className="flex h-6 w-6 items-center justify-center rounded text-text-tertiary hover:text-text-secondary"
            title="Add project"
          >
            <svg width="11" height="11" viewBox="0 0 16 16" fill="none">
              <path d="M2 4.5h4l1.5 2H14v7H2V4.5z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
              <path d="M10 9.5v-3M8.5 8h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {loading && projects.length === 0 ? (
          <div className="px-3 py-6 text-center text-[13px] text-text-tertiary">Загрузка проектов...</div>
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
          <div className="px-3 py-6 text-center text-[13px] text-text-tertiary">
            Откройте проект, чтобы начать.
          </div>
        ) : null}
      </div>

      <SidebarFooter />
    </aside>
  );
}
