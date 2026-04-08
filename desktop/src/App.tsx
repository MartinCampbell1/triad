import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { Composer } from "./components/composer/Composer";
import { BridgeStatusBanner } from "./components/shared/BridgeStatusBanner";
import { RecoveryScreen, type RecoveryState } from "./components/shared/RecoveryScreen";
import { TitleBar } from "./components/layout/TitleBar";
import { Sidebar } from "./components/sidebar/Sidebar";
import { TerminalDrawer } from "./components/terminal/TerminalDrawer";
import { Transcript } from "./components/transcript/Transcript";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { useStreamEvents } from "./hooks/useStreamEvents";
import { onBridgeStatus, rpc, startBridge, stopBridge } from "./lib/rpc";
import { ensureMacOSNotificationPermissionPromptOnce, setMacOSDockBadgeLabel } from "./lib/tauri-macos";
import { useBridgeStore } from "./stores/bridge-store";
import { useProjectStore } from "./stores/project-store";
import { useProviderStore } from "./stores/provider-store";
import { useSessionStore } from "./stores/session-store";
import { useUiStore } from "./stores/ui-store";

const DiffPanel = lazy(async () => {
  const module = await import("./components/diff/DiffPanel");
  return { default: module.DiffPanel };
});

const CommandPalette = lazy(async () => {
  const module = await import("./components/shared/CommandPalette");
  return { default: module.CommandPalette };
});

export function App() {
  const openProject = useProjectStore((state) => state.openProject);
  const activeProject = useProjectStore((state) => state.activeProject);
  const setProjects = useProjectStore((state) => state.setProjects);
  const setActiveProject = useProjectStore((state) => state.setActiveProject);
  const loadSessions = useSessionStore((state) => state.loadSessions);
  const activeSession = useSessionStore((state) => state.activeSession);
  const createSession = useSessionStore((state) => state.createSession);
  const forkSession = useSessionStore((state) => state.forkSession);
  const exportSession = useSessionStore((state) => state.exportSession);
  const importSession = useSessionStore((state) => state.importSession);
  const hydrateSession = useSessionStore((state) => state.hydrateSession);
  const setSessions = useSessionStore((state) => state.setSessions);
  const setMode = useProviderStore((state) => state.setMode);
  const setActiveProvider = useProviderStore((state) => state.setActiveProvider);
  const sidebarCollapsed = useUiStore((state) => state.sidebarCollapsed);
  const diffPanelOpen = useUiStore((state) => state.diffPanelOpen);
  const diffFiles = useUiStore((state) => state.diffFiles);
  const toggleDrawer = useUiStore((state) => state.toggleDrawer);
  const toggleDiffPanel = useUiStore((state) => state.toggleDiffPanel);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);
  const clearDiffFiles = useUiStore((state) => state.clearDiffFiles);
  const setBridgeStatus = useBridgeStore((state) => state.setStatus);
  const bridgeStatus = useBridgeStore((state) => state.status);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [bootstrapState, setBootstrapState] = useState<RecoveryState | "ready">("booting");
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);

  useStreamEvents();

  const notifyAction = useCallback((message: string) => {
    if (typeof globalThis.alert === "function") {
      globalThis.alert(message);
      return;
    }
    console.info(message);
  }, []);

  const forkCurrentSession = useCallback(() => {
    if (!activeSession) {
      return;
    }
    void forkSession(activeSession.id);
  }, [activeSession, forkSession]);

  const exportCurrentSession = useCallback(
    async (format: "archive" | "markdown") => {
      if (!activeSession) {
        return;
      }
      try {
        const result = await exportSession(activeSession.id, { format });
        notifyAction(`Exported "${activeSession.title}" to ${result.path}`);
      } catch (error) {
        notifyAction(error instanceof Error ? error.message : "Failed to export session");
      }
    },
    [activeSession, exportSession, notifyAction]
  );

  const importSessionFromPrompt = useCallback(async () => {
    if (typeof globalThis.prompt !== "function") {
      notifyAction("Session import prompt is unavailable in this environment.");
      return;
    }
    const path = globalThis.prompt("Enter the absolute path to a session archive");
    if (!path?.trim()) {
      return;
    }
    try {
      const result = await importSession(path.trim());
      notifyAction(`Imported "${result.session.title}" from ${result.path}`);
    } catch (error) {
      notifyAction(error instanceof Error ? error.message : "Failed to import session");
    }
  }, [importSession, notifyAction]);

  const stopCurrentRun = useCallback(() => {
    if (!activeSession) {
      return;
    }
    void rpc("session.stop", { session_id: activeSession.id });
  }, [activeSession]);

  const bootstrapApp = useCallback(async (forceRestart = false) => {
    setBootstrapState("booting");
    setBootstrapError(null);
    try {
      if (forceRestart) {
        await stopBridge();
      }
      await startBridge();
      const state = await rpc<{
        projects: Array<{
          path: string;
          name: string;
          git_root: string;
          last_opened_at?: string;
        }>;
        sessions: Array<{
          id: string;
          project_path: string;
          title: string;
          mode: "solo" | "critic" | "brainstorm" | "delegate";
          status: "active" | "running" | "paused" | "completed" | "failed";
          created_at: string;
          updated_at: string;
          message_count: number;
          provider?: "claude" | "codex" | "gemini";
        }>;
        last_project: string | null;
        last_session_id: string | null;
      }>("app.get_state");

      setProjects(state.projects);
      setSessions(state.sessions);

      if (!state.projects.length) {
        setActiveProject(null);
        setBootstrapState("project_unavailable");
        return;
      }

      const targetProject =
        state.projects.find((project) => project.path === state.last_project) ?? state.projects[0] ?? null;
      setActiveProject(targetProject);

      const targetSession =
        state.sessions.find((session) => session.id === state.last_session_id) ??
        state.sessions.find((session) => session.project_path === targetProject?.path) ??
        state.sessions[0];

      if (targetSession) {
        await hydrateSession(targetSession.id);
      }
      setBootstrapState("ready");
    } catch (error) {
      setBootstrapState("bridge_unavailable");
      setBootstrapError(error instanceof Error ? error.message : "Bridge startup failed");
    }
  }, [hydrateSession, setActiveProject, setProjects, setSessions]);

  const chooseProjectFromPrompt = useCallback(async () => {
    if (typeof globalThis.prompt !== "function") {
      notifyAction("Project picker is unavailable in this environment.");
      return;
    }
    const path = globalThis.prompt("Enter the absolute project path");
    if (!path?.trim()) {
      return;
    }
    try {
      const project = await openProject(path.trim());
      setActiveProject(project);
      await loadSessions(project.path);
      setBootstrapState("ready");
      setBootstrapError(null);
    } catch (error) {
      setBootstrapError(error instanceof Error ? error.message : "Failed to open project");
    }
  }, [loadSessions, notifyAction, openProject, setActiveProject]);

  const exportRecoveryDiagnostics = useCallback(async () => {
    const payload: Record<string, unknown> = {
      exported_at: new Date().toISOString(),
      recovery_state: bootstrapState,
      bridge_status: bridgeStatus,
      bootstrap_error: bootstrapError,
    };

    try {
      payload.backend = await rpc("diagnostics");
    } catch (error) {
      payload.diagnostics_error = error instanceof Error ? error.message : "Diagnostics unavailable";
    }

    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `triad-diagnostics-${Date.now()}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }, [bootstrapError, bootstrapState, bridgeStatus]);

  useKeyboardShortcuts({
    openCommandPalette: () => setPaletteOpen(true),
    stopCurrentRun,
  });

  useEffect(() => {
    return onBridgeStatus(setBridgeStatus);
  }, [setBridgeStatus]);

  useEffect(() => {
    void ensureMacOSNotificationPermissionPromptOnce();
    void setMacOSDockBadgeLabel(undefined);
    return () => {
      void setMacOSDockBadgeLabel(undefined);
    };
  }, []);

  useEffect(() => {
    let disposed = false;

    void (async () => {
      await bootstrapApp();
      if (disposed) {
        return;
      }
    })();

    return () => {
      disposed = true;
      void stopBridge();
    };
  }, [bootstrapApp]);

  useEffect(() => {
    if (
      bootstrapState === "ready" &&
      bridgeStatus.started &&
      !bridgeStatus.connected &&
      (bridgeStatus.lastError || bridgeStatus.fallbackReason)
    ) {
      setBootstrapState("bridge_unavailable");
      setBootstrapError(bridgeStatus.lastError ?? bridgeStatus.fallbackReason ?? "Bridge unavailable");
    }
  }, [
    bootstrapState,
    bridgeStatus.connected,
    bridgeStatus.fallbackReason,
    bridgeStatus.lastError,
    bridgeStatus.started,
  ]);

  useEffect(() => {
    if (!activeSession) {
      return;
    }
    setMode(activeSession.mode);
    if (activeSession.provider) {
      setActiveProvider(activeSession.provider);
    }
  }, [activeSession?.id, activeSession?.mode, activeSession?.provider, setActiveProvider, setMode]);

  const commands = useMemo(
    () => [
      {
        id: "new-session",
        label: "New Session",
        description: "Start a fresh session in the active project",
        shortcut: "⌘N",
        keywords: ["new", "session", "chat"],
        action: () => {
          if (!activeProject) {
            return;
          }
          void createSession(activeProject.path, "solo");
        },
      },
      {
        id: "toggle-terminal",
        label: "Toggle Terminal Drawer",
        description: "Show or hide the embedded terminal",
        shortcut: "⌘`",
        keywords: ["terminal", "drawer", "shell"],
        action: toggleDrawer,
      },
      {
        id: "toggle-diff",
        label: "Toggle Diff Panel",
        description: diffFiles.length ? "Open the current diff preview" : "Open or close the diff side panel",
        shortcut: "⌘⇧D",
        keywords: ["diff", "changes", "patch"],
        action: toggleDiffPanel,
      },
      {
        id: "clear-diff",
        label: "Clear Diff Preview",
        description: "Remove collected diff files from the side panel",
        keywords: ["clear", "diff", "reset"],
        action: clearDiffFiles,
      },
      {
        id: "toggle-sidebar",
        label: "Toggle Sidebar",
        description: "Collapse or expand the projects sidebar",
        shortcut: "⌘B",
        keywords: ["sidebar", "projects", "navigation"],
        action: toggleSidebar,
      },
      {
        id: "focus-session",
        label: "Focus Active Session",
        description: activeSession ? activeSession.title : "No active session",
        keywords: ["active", "session"],
        action: () => setPaletteOpen(false),
      },
      {
        id: "stop-run",
        label: "Stop Current Run",
        description: "Send a stop signal to the active session",
        shortcut: "⌘.",
        keywords: ["stop", "cancel", "run"],
        action: stopCurrentRun,
      },
      {
        id: "fork-session",
        label: "Fork Current Session",
        description: activeSession ? `Create a fork of ${activeSession.title}` : "No active session",
        shortcut: "⌘⇧F",
        keywords: ["fork", "clone", "branch", "duplicate"],
        action: forkCurrentSession,
      },
      {
        id: "export-session-archive",
        label: "Export Current Session Archive",
        description: activeSession ? `Save ${activeSession.title} as a portable archive` : "No active session",
        keywords: ["export", "archive", "session", "json"],
        action: () => {
          void exportCurrentSession("archive");
        },
      },
      {
        id: "export-session-markdown",
        label: "Export Current Session Markdown",
        description: activeSession ? `Save ${activeSession.title} as markdown` : "No active session",
        keywords: ["export", "markdown", "md", "session"],
        action: () => {
          void exportCurrentSession("markdown");
        },
      },
      {
        id: "import-session",
        label: "Import Session From Path",
        description: "Load a previously exported session archive",
        keywords: ["import", "session", "archive", "restore"],
        action: () => {
          void importSessionFromPrompt();
        },
      },
    ],
    [
      activeProject,
      activeSession,
      clearDiffFiles,
      createSession,
      diffFiles.length,
      exportCurrentSession,
      forkCurrentSession,
      importSessionFromPrompt,
      stopCurrentRun,
      toggleDiffPanel,
      toggleDrawer,
      toggleSidebar,
    ]
  );

  if (bootstrapState !== "ready") {
    return (
      <RecoveryScreen
        state={bootstrapState}
        error={bootstrapError}
        onRetry={() => bootstrapApp(true)}
        onChooseProject={bootstrapState === "project_unavailable" ? chooseProjectFromPrompt : undefined}
        onExportDiagnostics={exportRecoveryDiagnostics}
      />
    );
  }

  return (
    <div className="flex h-full w-full overflow-hidden bg-surface text-text-primary">
      {!sidebarCollapsed ? <Sidebar /> : null}
      <div className="flex min-w-0 flex-1 flex-col">
        <BridgeStatusBanner />
        <TitleBar />
        <div className="flex min-h-0 flex-1">
          <div className="flex min-w-0 flex-1 flex-col">
            <Transcript />
            <Composer />
          </div>
          {diffPanelOpen ? (
            <Suspense fallback={<div className="w-[44%] min-w-[360px] border-l border-border-light bg-[var(--color-bg-editor)]" />}>
              <DiffPanel files={diffFiles} />
            </Suspense>
          ) : null}
        </div>
        <TerminalDrawer />
      </div>
      {paletteOpen ? (
        <Suspense fallback={null}>
          <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} commands={commands} />
        </Suspense>
      ) : null}
    </div>
  );
}
