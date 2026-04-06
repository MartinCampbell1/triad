import { create } from "zustand";
import type { BridgeStatus } from "../lib/types";

interface BridgeState {
  status: BridgeStatus;
  setStatus: (status: BridgeStatus) => void;
  clearError: () => void;
}

const initialStatus: BridgeStatus = {
  backendMode: "offline",
  started: false,
  connected: false,
  reconnecting: false,
  lastError: null,
  lastAttemptAt: null,
  lastConnectedAt: null,
  fallbackReason: null,
};

export const useBridgeStore = create<BridgeState>((set) => ({
  status: initialStatus,
  setStatus: (status) => set({ status }),
  clearError: () =>
    set((state) => ({
      status: {
        ...state.status,
        lastError: null,
        fallbackReason: null,
      },
    })),
}));
