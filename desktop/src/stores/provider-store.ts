import { create } from "zustand";
import { rpc } from "../lib/rpc";
import type {
  ModeId,
  ProviderId,
  RuntimeCapabilities,
  RuntimeModel,
  RuntimeMode,
  RuntimeProvider,
} from "../lib/types";

interface ProviderState {
  activeProvider: ProviderId;
  activeModel: string;
  mode: ModeId;
  reasoningEffort: "very-high" | "high" | "medium";
  accessMode: "local" | "remote";
  providers: RuntimeProvider[];
  models: RuntimeModel[];
  modes: RuntimeMode[];
  loadingRuntimeOptions: boolean;
  runtimeLoaded: boolean;
  loadRuntimeOptions: () => Promise<void>;
  setActiveProvider: (provider: ProviderId) => void;
  setActiveModel: (model: string) => void;
  setMode: (mode: ModeId) => void;
  setReasoningEffort: (effort: "very-high" | "high" | "medium") => void;
  setAccessMode: (mode: "local" | "remote") => void;
}

const FALLBACK_MODELS: RuntimeModel[] = [];
const FALLBACK_MODES: RuntimeMode[] = [];
const FALLBACK_PROVIDERS: RuntimeProvider[] = [];

function firstModelForProvider(models: RuntimeModel[], provider: ProviderId) {
  return models.find((model) => model.provider === provider) ?? null;
}

export const useProviderStore = create<ProviderState>((set, get) => ({
  activeProvider: "claude",
  activeModel: "claude-opus-4-6",
  mode: "solo",
  reasoningEffort: "very-high",
  accessMode: "local",
  providers: FALLBACK_PROVIDERS,
  models: FALLBACK_MODELS,
  modes: FALLBACK_MODES,
  loadingRuntimeOptions: false,
  runtimeLoaded: false,
  loadRuntimeOptions: async () => {
    const state = get();
    if (state.loadingRuntimeOptions || state.runtimeLoaded) {
      return;
    }

    set({ loadingRuntimeOptions: true });
    try {
      const [capabilities, modelsResponse, modesResponse] = await Promise.all([
        rpc<RuntimeCapabilities>("capabilities.list"),
        rpc<{ models: RuntimeModel[] }>("models.list"),
        rpc<{ modes: RuntimeMode[] }>("modes.list"),
      ]);

      const providers = capabilities.providers ?? [];
      const models = modelsResponse.models?.length ? modelsResponse.models : capabilities.models ?? [];
      const modes = modesResponse.modes?.length ? modesResponse.modes : capabilities.modes ?? [];
      const defaults = capabilities.defaults;

      const currentModel =
        models.find((model) => model.id === get().activeModel) ??
        (defaults?.model ? models.find((model) => model.id === defaults.model) : null) ??
        (defaults?.provider ? firstModelForProvider(models, defaults.provider) : null) ??
        firstModelForProvider(models, get().activeProvider) ??
        models[0] ??
        null;
      const currentMode =
        modes.find((item) => item.id === get().mode) ??
        (defaults?.mode ? modes.find((item) => item.id === defaults.mode) : null) ??
        modes[0] ??
        null;

      set({
        providers,
        models,
        modes,
        runtimeLoaded: true,
        loadingRuntimeOptions: false,
        activeProvider: currentModel?.provider ?? defaults?.provider ?? get().activeProvider,
        activeModel: currentModel?.id ?? defaults?.model ?? get().activeModel,
        mode: currentMode?.id ?? defaults?.mode ?? get().mode,
      });
    } catch {
      set({ loadingRuntimeOptions: false });
    }
  },
  setActiveProvider: (provider) =>
    set((state) => {
      const nextModel = firstModelForProvider(state.models, provider);
      return {
        activeProvider: provider,
        ...(nextModel ? { activeModel: nextModel.id } : {}),
      };
    }),
  setActiveModel: (model) =>
    set((state) => {
      const selected = state.models.find((item) => item.id === model);
      return {
        activeModel: model,
        ...(selected ? { activeProvider: selected.provider } : {}),
      };
    }),
  setMode: (mode) => set({ mode }),
  setReasoningEffort: (reasoningEffort) => set({ reasoningEffort }),
  setAccessMode: (accessMode) => set({ accessMode }),
}));
