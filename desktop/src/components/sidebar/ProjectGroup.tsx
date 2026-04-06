import type { Project, Session } from "../../lib/types";
import { SessionItem } from "./SessionItem";

interface Props {
  project: Project;
  sessions: Session[];
  activeSessionId: string | null;
  onSessionClick: (session: Session) => void;
}

export function ProjectGroup({ project, sessions, activeSessionId, onSessionClick }: Props) {
  return (
    <section className="mb-1">
      <div className="flex w-full items-center gap-2 px-3 py-[6px] text-[13px] text-text-secondary">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="flex-shrink-0 text-text-tertiary">
          <path d="M2 4.5h4l1.5 2H14v7H2V4.5z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
        </svg>
        <span className="min-w-0 flex-1 truncate">{project.name}</span>
      </div>
      <div className="mt-px">
        {sessions.map((session) => (
          <SessionItem
            key={session.id}
            session={session}
            active={session.id === activeSessionId}
            onClick={() => onSessionClick(session)}
          />
        ))}
      </div>
    </section>
  );
}
