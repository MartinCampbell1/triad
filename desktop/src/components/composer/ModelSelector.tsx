import { useProviderStore } from "../../stores/provider-store";
import type { ProviderId } from "../../lib/types";

const MODELS: Array<{ id: string; label: string; provider: ProviderId }> = [
  { id: "gpt-5.4", label: "GPT-5.4", provider: "codex" },
  { id: "claude-opus-4-6", label: "Claude Opus 4.6", provider: "claude" },
  { id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6", provider: "claude" },
  { id: "gemini-2.5-pro", label: "Gemini 2.5 Pro", provider: "gemini" },
];

export function ModelSelector() {
  const { activeModel, setActiveModel, setActiveProvider } = useProviderStore();

  return (
    <label className="relative inline-flex items-center gap-1 rounded-full border border-border-default bg-black/20 px-3 py-1 text-[12px] text-text-secondary transition-colors hover:border-border-heavy">
      <span>{MODELS.find((model) => model.id === activeModel)?.label ?? activeModel}</span>
      <select
        value={activeModel}
        onChange={(event) => {
          const model = MODELS.find((item) => item.id === event.target.value);
          if (model) {
            setActiveModel(model.id);
            setActiveProvider(model.provider);
          }
        }}
        className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
        aria-label="Model selector"
      >
        {MODELS.map((model) => (
          <option key={model.id} value={model.id}>
            {model.label}
          </option>
        ))}
      </select>
      <span className="text-[10px] text-text-tertiary">▾</span>
    </label>
  );
}
