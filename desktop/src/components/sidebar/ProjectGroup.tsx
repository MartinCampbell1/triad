import { useMemo, useState } from "react";
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
  const sessionCount = useMemo(() => sessions.length, [sessions.length]);

  return (
    <section className="mb-2">
      <button
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[11px] font-medium uppercase tracking-[0.12em] text-text-tertiary hover:text-text-secondary"
      >
        <span className={`inline-block transition-transform duration-150 ${expanded ? "rotate-90" : ""}`}>▸</span>
        <span className="truncate">{project.name}</span>
        <span className="ml-auto rounded-full border border-border-light px-1.5 py-0.5 text-[10px] text-text-muted">
          {sessionCount}
        </span>
      </button>
      {expanded ? (
        <div className="mt-0.5 space-y-0.5 pl-1.5">
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
