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
    if (typeof globalThis.prompt !== "function") {
      return;
    }
    const path = globalThis.prompt("Enter the absolute project path");
    if (!path?.trim()) {
      return;
    }
    try {
      const project = await openProject(path.trim());
      setActiveProject(project);
      await loadSessions(project.path);
    } catch (error) {
      if (typeof globalThis.alert === "function") {
        globalThis.alert(error instanceof Error ? error.message : "Failed to open project");
      }
    }
  };

  return (
    <aside className="flex h-full w-[var(--sidebar-width)] flex-col border-r border-border-light bg-[linear-gradient(180deg,rgba(255,255,255,0.02),transparent_20%),var(--color-bg-surface)]">
      <div className="px-4 pb-3 pt-4">
        <button
          onClick={handleNewSession}
          className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-[13px] text-text-secondary transition-colors hover:bg-elevated-secondary hover:text-text-primary"
        >
          <span className="grid h-4 w-4 place-items-center rounded-full border border-border-light text-[11px]">
            +
          </span>
          <span>Новая беседа</span>
        </button>
      </div>

      <div className="px-4 pb-2">
        <button className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-[13px] text-text-secondary transition-colors hover:bg-elevated-secondary hover:text-text-primary">
          <span className="grid h-4 w-4 place-items-center rounded-full border border-border-light text-[10px]">
            ◌
          </span>
          <span>Навыки и приложения</span>
        </button>
        <button className="mt-0.5 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-[13px] text-text-secondary transition-colors hover:bg-elevated-secondary hover:text-text-primary">
          <span className="grid h-4 w-4 place-items-center rounded-full border border-border-light text-[10px]">
            ◌
          </span>
          <span>Автоматизации</span>
        </button>
      </div>

      <div className="mx-4 my-2 border-t border-border-light" />

      <SearchPanel />

      <div className="flex items-center justify-between px-4 pb-2 pt-1">
        <span className="text-[11px] uppercase tracking-[0.12em] text-text-tertiary">Беседы</span>
        <div className="flex items-center gap-1 text-text-tertiary">
          <button
            onClick={() => {
              void loadProjects();
              void loadSessions("");
            }}
            className="rounded px-1.5 py-1 text-[12px] hover:text-text-secondary"
          >
            ↻
          </button>
          <button onClick={handleOpenProject} className="rounded px-1.5 py-1 text-[12px] hover:text-text-secondary">
            ⊞
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {loading && projects.length === 0 ? (
          <div className="px-3 py-6 text-center text-[13px] text-text-tertiary">Загрузка проектов…</div>
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
            Откройте проект, чтобы начать новую беседу.
          </div>
        ) : null}
      </div>

      <SidebarFooter />
    </aside>
  );
}
