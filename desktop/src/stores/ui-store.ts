import { create } from "zustand";
import { buildStructuredDiffFile, type RawDiffFile, type StructuredDiffFile } from "../lib/diff";

export interface TerminalSession {
  id: string;
  title: string;
  cwd: string | null;
  terminalId: string | null;
  kind?: "shell" | "provider";
  virtual?: boolean;
  linkedSessionId?: string | null;
  linkedProvider?: string | null;
  transcriptMode?: "partial" | "typed" | "live" | "full" | null;
  status: "starting" | "ready" | "unavailable";
  createdAt: string;
  updatedAt: string;
}

interface UiState {
  sidebarCollapsed: boolean;
  drawerOpen: boolean;
  drawerHeight: number;
  diffPanelOpen: boolean;
  compareReplayPanelOpen: boolean;
  compareReplayPanelTab: "compare" | "replay";
  titlebarCompact: boolean;
  settingsOpen: boolean;
  diffFiles: StructuredDiffFile[];
  activeDiffPath: string | null;
  terminalSessions: TerminalSession[];
  activeTerminalSessionId: string | null;
  toggleSidebar: () => void;
  toggleDrawer: () => void;
  setDrawerHeight: (height: number) => void;
  toggleDiffPanel: () => void;
  setDiffPanelOpen: (value: boolean) => void;
  toggleCompareReplayPanel: (tab?: "compare" | "replay") => void;
  setCompareReplayPanel: (value: boolean, options?: { tab?: "compare" | "replay" }) => void;
  setTitlebarCompact: (value: boolean) => void;
  setSettingsOpen: (value: boolean) => void;
  setDiffFiles: (files: StructuredDiffFile[], options?: { open?: boolean }) => void;
  upsertDiffFile: (file: RawDiffFile) => void;
  clearDiffFiles: () => void;
  setActiveDiffPath: (path: string | null) => void;
  addTerminalSession: (session: TerminalSession) => void;
  setTerminalSessions: (sessions: TerminalSession[]) => void;
  updateTerminalSession: (sessionId: string, patch: Partial<Omit<TerminalSession, "id" | "createdAt">>) => void;
  removeTerminalSession: (sessionId: string) => void;
  setActiveTerminalSessionId: (sessionId: string | null) => void;
  clearTerminalSessions: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: false,
  drawerOpen: true,
  drawerHeight: 210,
  diffPanelOpen: false,
  compareReplayPanelOpen: false,
  compareReplayPanelTab: "compare",
  titlebarCompact: false,
  settingsOpen: false,
  diffFiles: [],
  activeDiffPath: null,
  terminalSessions: [],
  activeTerminalSessionId: null,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  toggleDrawer: () => set((state) => ({ drawerOpen: !state.drawerOpen })),
  setDrawerHeight: (height) => set({ drawerHeight: height }),
  toggleDiffPanel: () =>
    set((state) => ({
      diffPanelOpen: !state.diffPanelOpen,
      compareReplayPanelOpen: !state.diffPanelOpen ? false : state.compareReplayPanelOpen,
    })),
  setDiffPanelOpen: (value) =>
    set((state) => ({
      diffPanelOpen: value,
      compareReplayPanelOpen: value ? false : state.compareReplayPanelOpen,
    })),
  toggleCompareReplayPanel: (tab) =>
    set((state) => {
      const shouldOpen = tab ? true : !state.compareReplayPanelOpen;
      return {
        compareReplayPanelOpen: shouldOpen,
        compareReplayPanelTab: tab ?? state.compareReplayPanelTab,
        diffPanelOpen: shouldOpen ? false : state.diffPanelOpen,
      };
    }),
  setCompareReplayPanel: (value, options) =>
    set((state) => ({
      compareReplayPanelOpen: value,
      compareReplayPanelTab: options?.tab ?? state.compareReplayPanelTab,
      diffPanelOpen: value ? false : state.diffPanelOpen,
    })),
  setTitlebarCompact: (value) => set({ titlebarCompact: value }),
  setSettingsOpen: (value) => set({ settingsOpen: value }),
  setDiffFiles: (files, options) =>
    set((state) => ({
      diffFiles: files,
      diffPanelOpen: options?.open ?? state.diffPanelOpen,
      activeDiffPath:
        files.length === 0 ? null : files.some((file) => file.path === state.activeDiffPath) ? state.activeDiffPath : files[0].path,
    })),
  upsertDiffFile: (file) =>
    set((state) => {
      const nextFile = buildStructuredDiffFile(file);
      const existing = state.diffFiles.findIndex((entry) => entry.path === nextFile.path);
      const diffFiles =
        existing >= 0
          ? state.diffFiles.map((entry, index) => (index === existing ? nextFile : entry))
          : [nextFile, ...state.diffFiles];
      return {
        diffFiles,
        diffPanelOpen: true,
        compareReplayPanelOpen: false,
        activeDiffPath: state.activeDiffPath ?? nextFile.path,
      };
    }),
  clearDiffFiles: () => set({ diffFiles: [], activeDiffPath: null, diffPanelOpen: false }),
  setActiveDiffPath: (path) => set({ activeDiffPath: path }),
  addTerminalSession: (session) =>
    set((state) => {
      if (state.terminalSessions.some((entry) => entry.id === session.id)) {
        return {
          terminalSessions: state.terminalSessions.map((entry) => (entry.id === session.id ? { ...entry, ...session } : entry)),
          activeTerminalSessionId: state.activeTerminalSessionId ?? session.id,
        };
      }
      return {
        terminalSessions: [...state.terminalSessions, session],
        activeTerminalSessionId: state.activeTerminalSessionId ?? session.id,
      };
    }),
  setTerminalSessions: (sessions) =>
    set((state) => {
      const activeTerminalSessionId =
        state.activeTerminalSessionId && sessions.some((session) => session.id === state.activeTerminalSessionId)
          ? state.activeTerminalSessionId
          : sessions[0]?.id ?? null;
      return {
        terminalSessions: sessions,
        activeTerminalSessionId,
      };
    }),
  updateTerminalSession: (sessionId, patch) =>
    set((state) => ({
      terminalSessions: state.terminalSessions.map((entry) =>
        entry.id === sessionId ? { ...entry, ...patch, updatedAt: new Date().toISOString() } : entry
      ),
    })),
  removeTerminalSession: (sessionId) =>
    set((state) => {
      const terminalSessions = state.terminalSessions.filter((entry) => entry.id !== sessionId);
      return {
        terminalSessions,
        activeTerminalSessionId:
          state.activeTerminalSessionId === sessionId
            ? terminalSessions[0]?.id ?? null
            : state.activeTerminalSessionId,
      };
    }),
  setActiveTerminalSessionId: (sessionId) => set({ activeTerminalSessionId: sessionId }),
  clearTerminalSessions: () => set({ terminalSessions: [], activeTerminalSessionId: null }),
}));
