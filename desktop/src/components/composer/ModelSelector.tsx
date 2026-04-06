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
    <label className="relative inline-flex cursor-pointer items-center gap-1 text-[13px] text-text-secondary transition-colors hover:text-text-primary">
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
      <svg width="8" height="8" viewBox="0 0 16 16" fill="none" className="text-text-tertiary opacity-60">
        <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </label>
  );
}
