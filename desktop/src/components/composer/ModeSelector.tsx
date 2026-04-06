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
    <label className="relative inline-flex items-center gap-1 rounded-full border border-border-default bg-black/20 px-3 py-1 text-[12px] text-text-secondary transition-colors hover:border-border-heavy">
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
      <span className="text-[10px] text-text-tertiary">▾</span>
    </label>
  );
}
