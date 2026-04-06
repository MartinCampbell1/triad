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
  return (
    <button
      onClick={onClick}
      className={[
        "group flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-[13px] transition-colors",
        active
          ? "bg-elevated text-text-primary shadow-[inset_0_0_0_1px_rgba(255,255,255,0.04)]"
          : "text-text-secondary hover:bg-elevated-secondary hover:text-text-primary",
      ].join(" ")}
      >
      <span className="min-w-0 flex-1 truncate">{session.title}</span>
      <span className="flex-shrink-0 text-[11px] text-text-tertiary group-hover:text-text-secondary">
        {formatRelative(session.updated_at)}
      </span>
    </button>
  );
}
