import { useProviderStore } from "../../stores/provider-store";
import type { ModeId } from "../../lib/types";

const MODES: Array<{ id: ModeId; label: string }> = [
  { id: "solo", label: "Solo" },
  { id: "critic", label: "Critic" },
  { id: "brainstorm", label: "Brainstorm" },
  { id: "delegate", label: "Delegate" },
];

export function ModeSelector() {
  const { mode, setMode } = useProviderStore();

  return (
    <label className="relative inline-flex cursor-pointer items-center gap-1 text-text-tertiary transition-colors hover:text-text-secondary">
      <svg width="11" height="11" viewBox="0 0 16 16" fill="none">
        <path d="M8 2L2 8l6 6 6-6L8 2z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
      </svg>
      <span>{MODES.find((item) => item.id === mode)?.label ?? mode}</span>
      <select
        value={mode}
        onChange={(event) => setMode(event.target.value as ModeId)}
        className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
        aria-label="Mode selector"
      >
        {MODES.map((item) => (
          <option key={item.id} value={item.id}>
            {item.label}
          </option>
        ))}
      </select>
      <svg width="8" height="8" viewBox="0 0 16 16" fill="none" className="opacity-60">
        <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </label>
  );
}
