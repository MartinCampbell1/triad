import { create } from "zustand";
import type { DiffFile } from "../lib/types";

interface UiState {
  sidebarCollapsed: boolean;
  drawerOpen: boolean;
  drawerHeight: number;
  diffPanelOpen: boolean;
  titlebarCompact: boolean;
  diffFiles: DiffFile[];
  activeDiffPath: string | null;
  toggleSidebar: () => void;
  toggleDrawer: () => void;
  setDrawerHeight: (height: number) => void;
  toggleDiffPanel: () => void;
  setTitlebarCompact: (value: boolean) => void;
  upsertDiffFile: (file: DiffFile) => void;
  replaceDiffFiles: (files: DiffFile[]) => void;
  clearDiffFiles: () => void;
  setActiveDiffPath: (path: string | null) => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: false,
  drawerOpen: true,
  drawerHeight: 210,
  diffPanelOpen: false,
  titlebarCompact: false,
  diffFiles: [],
  activeDiffPath: null,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  toggleDrawer: () => set((state) => ({ drawerOpen: !state.drawerOpen })),
  setDrawerHeight: (height) => set({ drawerHeight: height }),
  toggleDiffPanel: () => set((state) => ({ diffPanelOpen: !state.diffPanelOpen })),
  setTitlebarCompact: (value) => set({ titlebarCompact: value }),
  upsertDiffFile: (file) =>
    set((state) => {
      const existing = state.diffFiles.findIndex((entry) => entry.path === file.path);
      const diffFiles =
        existing >= 0
          ? state.diffFiles.map((entry, index) => (index === existing ? file : entry))
          : [file, ...state.diffFiles];
      return {
        diffFiles,
        diffPanelOpen: true,
        activeDiffPath: state.activeDiffPath ?? file.path,
      };
    }),
  replaceDiffFiles: (files) =>
    set({
      diffFiles: files,
      activeDiffPath: files[0]?.path ?? null,
      diffPanelOpen: files.length > 0,
    }),
  clearDiffFiles: () => set({ diffFiles: [], activeDiffPath: null, diffPanelOpen: false }),
  setActiveDiffPath: (path) => set({ activeDiffPath: path }),
}));
