import { useProviderStore } from "../../stores/provider-store";
import type { ModeId } from "../../lib/types";

export function ModeSelector() {
  const { mode, modes, setMode, loadingRuntimeOptions } = useProviderStore();
  const currentMode = modes.find((item) => item.id === mode) ?? modes[0] ?? null;

  if (loadingRuntimeOptions && modes.length === 0) {
    return (
      <div className="inline-flex items-center gap-1 rounded-full border border-[var(--color-border)] px-2 py-1 text-[11px] text-[var(--color-text-tertiary)]">
        <span>Loading modes...</span>
      </div>
    );
  }

  if (!loadingRuntimeOptions && modes.length === 0) {
    return (
      <div className="inline-flex items-center gap-1 rounded-full border border-[var(--color-border)] px-2 py-1 text-[11px] text-[var(--color-text-tertiary)]">
        <span>Modes unavailable</span>
      </div>
    );
  }

  return (
    <label className="relative inline-flex cursor-pointer items-center gap-1 rounded-full border border-[var(--color-border)] px-2 py-1 text-[11px] text-[var(--color-text-tertiary)] transition-colors duration-150 hover:bg-[rgba(255,255,255,0.03)] hover:text-[var(--color-text-secondary)]">
      <svg width="11" height="11" viewBox="0 0 16 16" fill="none">
        <path d="M8 2L2 8l6 6 6-6L8 2z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
      </svg>
      <span>{currentMode?.label ?? "Mode"}</span>
      <select
        value={currentMode?.id ?? mode}
        onChange={(event) => setMode(event.target.value as ModeId)}
        className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
        aria-label="Mode selector"
      >
        {modes.map((item) => (
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
