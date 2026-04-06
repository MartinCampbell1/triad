import { create } from "zustand";
import type { ModeId, ProviderId } from "../lib/types";

interface ProviderState {
  activeProvider: ProviderId;
  activeModel: string;
  mode: ModeId;
  reasoningEffort: "very-high" | "high" | "medium";
  accessMode: "local" | "remote";
  setActiveProvider: (provider: ProviderId) => void;
  setActiveModel: (model: string) => void;
  setMode: (mode: ModeId) => void;
  setReasoningEffort: (effort: "very-high" | "high" | "medium") => void;
  setAccessMode: (mode: "local" | "remote") => void;
}

export const useProviderStore = create<ProviderState>((set) => ({
  activeProvider: "claude",
  activeModel: "claude-opus-4-6",
  mode: "solo",
  reasoningEffort: "very-high",
  accessMode: "local",
  setActiveProvider: (provider) => set({ activeProvider: provider }),
  setActiveModel: (model) => set({ activeModel: model }),
  setMode: (mode) => set({ mode }),
  setReasoningEffort: (reasoningEffort) => set({ reasoningEffort }),
  setAccessMode: (accessMode) => set({ accessMode }),
}));
