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
    return `${Math.max(1, deltaMinutes)}м`;
  }

  const deltaHours = Math.round(deltaMinutes / 60);
  if (deltaHours < 24) {
    return `${deltaHours}ч`;
  }

  const deltaDays = Math.round(deltaHours / 24);
  return `${deltaDays}д`;
}

export function SessionItem({ session, active, onClick }: Props) {
  const isRunning = session.status === "running";
  const hasDiff = (session.diff_additions ?? 0) > 0 || (session.diff_deletions ?? 0) > 0;

  return (
    <button
      onClick={onClick}
      className={[
        "flex w-full items-center gap-2 rounded-lg px-3 py-[7px] text-left text-[13px] transition-colors",
        active
          ? "bg-white/[0.06] text-text-primary"
          : "text-text-secondary hover:bg-white/[0.04] hover:text-text-primary",
      ].join(" ")}
    >
      {/* Blue dot for running, or spinner */}
      {isRunning ? (
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="flex-shrink-0 animate-spin text-[#339cff]">
          <path d="M8 2a6 6 0 014.9 9.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      ) : hasDiff ? (
        <span className="flex-shrink-0 h-[6px] w-[6px] rounded-full bg-[#339cff]" />
      ) : null}

      <span className="min-w-0 flex-1 truncate">{session.title}</span>

      {/* Colored diff stats like Codex */}
      {hasDiff ? (
        <span className="flex-shrink-0 text-[11px]">
          <span className="text-green-300">+{session.diff_additions}</span>
          {" "}
          <span className="text-red-300">-{session.diff_deletions}</span>
        </span>
      ) : null}

      <span className="flex-shrink-0 text-[12px] text-text-tertiary">
        {formatRelative(session.updated_at)}
      </span>
    </button>
  );
}
