import { useState } from "react";
import type { Project, Session } from "../../lib/types";
import { SessionItem } from "./SessionItem";

interface Props {
  project: Project;
  sessions: Session[];
  activeSessionId: string | null;
  onSessionClick: (session: Session) => void;
}

export function ProjectGroup({ project, sessions, activeSessionId, onSessionClick }: Props) {
  const [expanded, setExpanded] = useState(true);

  return (
    <section className="mb-0.5">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-1.5 rounded-md px-2 py-[4px] text-left text-[12px] text-[var(--color-text-tertiary)] transition-colors duration-150 hover:bg-[rgba(255,255,255,0.025)] hover:text-[var(--color-text-secondary)]"
      >
        <svg
          width="8"
          height="8"
          viewBox="0 0 16 16"
          fill="currentColor"
          className={`shrink-0 text-[var(--color-text-tertiary)] transition-transform duration-150 ${expanded ? "rotate-90" : ""}`}
        >
          <path d="M6 3L12 8L6 13V3Z" />
        </svg>
        <svg width="13" height="13" viewBox="0 0 16 16" fill="none" className="shrink-0 text-[var(--color-text-tertiary)]">
          <path d="M2 4.5h4l1.5 2H14v7H2V4.5z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
        </svg>
        <span className="min-w-0 flex-1 truncate">{project.name}</span>
      </button>
      {expanded ? (
        <div className="pl-2">
          {sessions.map((session) => (
            <SessionItem
              key={session.id}
              session={session}
              active={session.id === activeSessionId}
              onClick={() => onSessionClick(session)}
            />
          ))}
        </div>
      ) : null}
    </section>
  );
}
