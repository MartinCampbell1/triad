import type { Session } from "../../lib/types";

interface Props {
  session: Session;
  active: boolean;
  onClick: () => void;
}

function formatRelative(updatedAt: string) {
  const updated = new Date(updatedAt).getTime();
  const deltaMinutes = Math.max(0, Math.round((Date.now() - updated) / 60000));

  if (deltaMinutes < 60) {
    return `${Math.max(1, deltaMinutes)}m`;
  }

  const deltaHours = Math.round(deltaMinutes / 60);
  if (deltaHours < 24) {
    return `${deltaHours}h`;
  }

  const deltaDays = Math.round(deltaHours / 24);
  return `${deltaDays}d`;
}

export function SessionItem({ session, active, onClick }: Props) {
  const isRunning = session.status === "running";
  const hasDiff = (session.diff_additions ?? 0) > 0 || (session.diff_deletions ?? 0) > 0;

  return (
    <button
      onClick={onClick}
      className={[
        "flex w-full items-center gap-2 rounded-lg px-2 py-[4px] text-left text-[12px] transition-colors duration-150",
        active
          ? "bg-[rgba(255,255,255,0.05)] text-[var(--color-text-primary)]"
          : "text-[var(--color-text-secondary)] hover:bg-[rgba(255,255,255,0.03)] hover:text-[var(--color-text-primary)]",
      ].join(" ")}
    >
      {/* Running spinner or diff dot */}
      {isRunning ? (
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="shrink-0 animate-spin text-[var(--blue-300)]">
          <path d="M8 2a6 6 0 014.9 9.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      ) : hasDiff ? (
        <span className="shrink-0 h-[6px] w-[6px] rounded-full bg-[var(--blue-300)]" />
      ) : null}

      <span className="min-w-0 flex-1 truncate">{session.title}</span>

      {hasDiff ? (
        <span className="shrink-0 text-[10px]">
          <span className="text-[var(--color-text-success)]">+{session.diff_additions}</span>
          {" "}
          <span className="text-[var(--color-text-error)]">-{session.diff_deletions}</span>
        </span>
      ) : null}

      <span className="shrink-0 text-[11px] text-[var(--color-text-tertiary)]">
        {formatRelative(session.updated_at)}
      </span>
    </button>
  );
}
