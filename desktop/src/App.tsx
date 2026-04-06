import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { Composer } from "./components/composer/Composer";
import { BridgeStatusBanner } from "./components/shared/BridgeStatusBanner";
import { TitleBar } from "./components/layout/TitleBar";
import { Sidebar } from "./components/sidebar/Sidebar";
import { TerminalDrawer } from "./components/terminal/TerminalDrawer";
import { Transcript } from "./components/transcript/Transcript";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { useStreamEvents } from "./hooks/useStreamEvents";
import { onBridgeStatus, reconnectBridge, rpc, startBridge, stopBridge } from "./lib/rpc";
import { ensureMacOSNotificationPermissionPromptOnce, setMacOSDockBadgeLabel } from "./lib/tauri-macos";
import { useBridgeStore } from "./stores/bridge-store";
import { useProjectStore } from "./stores/project-store";
import { useProviderStore } from "./stores/provider-store";
import { useSessionStore } from "./stores/session-store";
import { useUiStore } from "./stores/ui-store";

const SettingsLayout = lazy(async () => {
  const module = await import("./components/settings/SettingsLayout");
  return { default: module.SettingsLayout };
});

const DiffPanel = lazy(async () => {
  const module = await import("./components/diff/DiffPanel");
  return { default: module.DiffPanel };
});

const SessionCompareReplayPanel = lazy(async () => {
  const module = await import("./components/session/SessionCompareReplayPanel");
  return { default: module.SessionCompareReplayPanel };
});

const CommandPalette = lazy(async () => {
  const module = await import("./components/shared/CommandPalette");
  return { default: module.CommandPalette };
});

function BootState({
  title,
  detail,
  actionLabel,
  onAction,
}: {
  title: string;
  detail: string;
  actionLabel: string;
  onAction?: () => void;
}) {
  return (
    <div className="flex h-full w-full items-center justify-center bg-[var(--color-bg-surface)] px-6 text-[var(--color-text-primary)]">
      <div className="w-full max-w-[520px] rounded-[20px] border border-[var(--color-border)] bg-[rgba(255,255,255,0.02)] p-6 text-center">
        <div className="text-[14px] font-medium">{title}</div>
        <div className="mt-2 text-[13px] leading-[1.6] text-[var(--color-text-tertiary)]">{detail}</div>
        {onAction ? (
          <button
            type="button"
            onClick={onAction}
            className="mt-5 rounded-md border border-[var(--color-border)] px-3 py-1.5 text-[12px] text-[var(--color-text-secondary)] transition-colors hover:bg-[rgba(255,255,255,0.03)] hover:text-[var(--color-text-primary)]"
          >
            {actionLabel}
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function App() {
  const activeProject = useProjectStore((state) => state.activeProject);
  const setProjects = useProjectStore((state) => state.setProjects);
  const setActiveProject = useProjectStore((state) => state.setActiveProject);
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
  const compareReplayPanelOpen = useUiStore((state) => state.compareReplayPanelOpen);
  const diffFiles = useUiStore((state) => state.diffFiles);
  const toggleDrawer = useUiStore((state) => state.toggleDrawer);
  const toggleDiffPanel = useUiStore((state) => state.toggleDiffPanel);
  const setCompareReplayPanel = useUiStore((state) => state.setCompareReplayPanel);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);
  const clearDiffFiles = useUiStore((state) => state.clearDiffFiles);
  const settingsOpen = useUiStore((state) => state.settingsOpen);
  const setSettingsOpen = useUiStore((state) => state.setSettingsOpen);
  const setBridgeStatus = useBridgeStore((state) => state.setStatus);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [booting, setBooting] = useState(true);
  const [bootError, setBootError] = useState<string | null>(null);

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
      try {
        setBooting(true);
        setBootError(null);
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

        if (disposed) {
          return;
        }

        setProjects(state.projects);
        setSessions(state.sessions);

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
      } catch (error) {
        if (disposed) {
          return;
        }
        setBootError(error instanceof Error ? error.message : "Python bridge failed to start.");
      } finally {
        if (!disposed) {
          setBooting(false);
        }
      }
    })();

    return () => {
      disposed = true;
      void stopBridge();
    };
  }, [hydrateSession, setActiveProject, setProjects, setSessions]);

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
        id: "open-session-compare",
        label: "Open Session Compare",
        description: activeSession ? `Compare ${activeSession.title} with another session` : "No active session",
        keywords: ["compare", "session", "replay", "timeline"],
        action: () => {
          setCompareReplayPanel(true, { tab: "compare" });
        },
      },
      {
        id: "open-session-replay",
        label: "Open Session Replay",
        description: activeSession ? `Replay the timeline for ${activeSession.title}` : "No active session",
        keywords: ["replay", "session", "timeline", "scrub"],
        action: () => {
          setCompareReplayPanel(true, { tab: "replay" });
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
      setCompareReplayPanel,
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

  if (settingsOpen) {
    return (
      <Suspense fallback={<div className="flex h-full w-full bg-[var(--color-bg-surface)]" />}>
        <SettingsLayout onBack={() => setSettingsOpen(false)} />
      </Suspense>
    );
  }

  if (booting && !activeProject && !activeSession) {
    return (
      <BootState
        title="Starting bridge"
        detail="Launching the Python sidecar and loading the current workspace."
        actionLabel="Starting"
      />
    );
  }

  if (bootError && !activeProject && !activeSession) {
    return (
      <BootState
        title="Bridge unavailable"
        detail={bootError}
        actionLabel="Retry"
        onAction={() => {
          setBooting(true);
          setBootError(null);
          void reconnectBridge()
            .then(async () => {
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
            })
            .catch((error) => {
              setBootError(error instanceof Error ? error.message : "Python bridge failed to start.");
            })
            .finally(() => {
              setBooting(false);
            });
        }}
      />
    );
  }

  return (
    <div className="flex h-full w-full overflow-hidden bg-[var(--color-bg-surface)] text-[var(--color-text-primary)]">
      {!sidebarCollapsed ? <Sidebar /> : null}
      <div className="flex min-w-0 flex-1 flex-col">
        <TitleBar />
        <BridgeStatusBanner />
        <div className="flex min-h-0 flex-1">
          <div className="flex min-w-0 flex-1 flex-col">
            <Transcript />
            <Composer />
          </div>
          {compareReplayPanelOpen ? (
            <Suspense fallback={<div className="w-[44%] min-w-[360px] border-l border-[var(--color-border)] bg-[var(--color-bg-editor)]" />}>
              <SessionCompareReplayPanel />
            </Suspense>
          ) : diffPanelOpen ? (
            <Suspense fallback={<div className="w-[44%] min-w-[360px] border-l border-[var(--color-border)] bg-[var(--color-bg-editor)]" />}>
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
