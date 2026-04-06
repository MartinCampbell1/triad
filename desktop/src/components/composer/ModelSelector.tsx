import { useProviderStore } from "../../stores/provider-store";

export function ModelSelector() {
  const { activeModel, models, setActiveModel, loadingRuntimeOptions } = useProviderStore();
  const currentModel = models.find((model) => model.id === activeModel) ?? models[0] ?? null;

  if (loadingRuntimeOptions && models.length === 0) {
    return (
      <div className="inline-flex items-center gap-1 rounded-full border border-[var(--color-border)] px-2 py-1 text-[11px] text-[var(--color-text-tertiary)]">
        <span>Loading models...</span>
      </div>
    );
  }

  if (!loadingRuntimeOptions && models.length === 0) {
    return (
      <div className="inline-flex items-center gap-1 rounded-full border border-[var(--color-border)] px-2 py-1 text-[11px] text-[var(--color-text-tertiary)]">
        <span>Models unavailable</span>
      </div>
    );
  }

  return (
    <label className="relative inline-flex cursor-pointer items-center gap-1 rounded-full border border-[var(--color-border)] px-2 py-1 text-[11px] text-[var(--color-text-secondary)] transition-colors duration-150 hover:bg-[rgba(255,255,255,0.03)] hover:text-[var(--color-text-primary)]">
      <span>{currentModel?.label ?? "Model"}</span>
      <select
        value={currentModel?.id ?? activeModel}
        onChange={(event) => {
          setActiveModel(event.target.value);
        }}
        className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
        aria-label="Model selector"
      >
        {models.map((model) => (
          <option key={model.id} value={model.id}>
            {model.label}
          </option>
        ))}
      </select>
      <svg width="8" height="8" viewBox="0 0 16 16" fill="none" className="text-[var(--color-text-tertiary)] opacity-60">
        <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </label>
  );
}
