import { useEffect, useMemo, useRef, useState } from "react";
import { onEvent, rpc } from "../../lib/rpc";
import { useProjectStore } from "../../stores/project-store";
import { useSessionStore } from "../../stores/session-store";
import { useUiStore, type TerminalSession } from "../../stores/ui-store";
import type { TerminalHostMetadata } from "../../lib/types";

type XtermTerminal = {
  open: (el: HTMLElement) => void;
  write: (data: string) => void;
  writeln: (data: string) => void;
  loadAddon?: (addon: any) => void;
  onData?: (cb: (data: string) => void) => { dispose: () => void } | void;
  onResize?: (cb: (size: { cols: number; rows: number }) => void) => { dispose: () => void } | void;
  clear?: () => void;
  dispose: () => void;
  fit?: () => void;
};

type TerminalAddon = {
  fit?: () => void;
};

type TerminalBackendSession = {
  terminal_id: string;
  title?: string | null;
  cwd?: string | null;
  kind?: "shell" | "provider";
  virtual?: boolean;
  linked_session_id?: string | null;
  linked_provider?: string | null;
  transcript_mode?: TerminalHostMetadata["transcript_mode"] | null;
  status?: "starting" | "ready" | "unavailable";
  created_at?: string | null;
  updated_at?: string | null;
  last_output_at?: string | null;
  snapshot?: string | null;
};

function safeAtob(value: string) {
  try {
    return atob(value);
  } catch {
    return "";
  }
}

function encodeInput(value: string) {
  try {
    return btoa(value);
  } catch {
    return "";
  }
}

function resolveDrawerHeights(viewportHeight: number) {
  const peek = 176;
  const half = Math.max(260, Math.min(Math.floor(viewportHeight * 0.34), 360));
  const full = Math.max(half, Math.min(Math.floor(viewportHeight * 0.62), viewportHeight - 112));
  return { peek, half, full };
}

function basename(path: string | null | undefined) {
  if (!path) {
    return "Shell";
  }
  const segments = path.split(/[\\/]+/).filter(Boolean);
  return segments.at(-1) || "Shell";
}

function describeTerminalHostTitle(
  terminalHost: TerminalHostMetadata | null | undefined
) {
  if (!terminalHost) {
    return null;
  }
  if (terminalHost.terminal_title?.trim()) {
    return terminalHost.terminal_title.trim();
  }
  if (terminalHost.terminal_cwd?.trim()) {
    return basename(terminalHost.terminal_cwd);
  }
  if (terminalHost.terminal_id?.trim()) {
    return terminalHost.terminal_id.trim();
  }
  return null;
}

function mapBackendSession(session: TerminalBackendSession): TerminalSession {
  const now = new Date().toISOString();
  return {
    id: session.terminal_id,
    title: session.title?.trim() || basename(session.cwd) || "Shell",
    cwd: session.cwd ?? null,
    terminalId: session.terminal_id,
    kind: session.kind ?? "shell",
    virtual: session.virtual ?? false,
    linkedSessionId: session.linked_session_id ?? null,
    linkedProvider: session.linked_provider ?? null,
    transcriptMode: session.transcript_mode ?? null,
    status: session.status ?? "ready",
    createdAt: session.created_at ?? now,
    updatedAt: session.updated_at ?? session.created_at ?? now,
  };
}

function makeFallbackSession(cwd: string | null, index: number): TerminalSession {
  const now = new Date().toISOString();
  const id =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? `terminal_${crypto.randomUUID().slice(0, 8)}`
      : `terminal_${Math.random().toString(36).slice(2, 10)}`;

  return {
    id,
    title: `${basename(cwd)} ${index}`,
    cwd,
    terminalId: null,
    kind: "shell",
    virtual: false,
    linkedSessionId: null,
    linkedProvider: null,
    transcriptMode: null,
    status: "unavailable",
    createdAt: now,
    updatedAt: now,
  };
}

export function TerminalDrawer() {
  const {
    drawerOpen,
    drawerHeight,
    toggleDrawer,
    setDrawerHeight,
    terminalSessions,
    activeTerminalSessionId,
    addTerminalSession,
    setTerminalSessions,
    updateTerminalSession,
    removeTerminalSession,
    setActiveTerminalSessionId,
  } = useUiStore();
  const activeProject = useProjectStore((state) => state.activeProject);
  const activeSession = useSessionStore((state) => state.activeSession);
  const mountRef = useRef<HTMLDivElement | null>(null);
  const terminalRef = useRef<XtermTerminal | null>(null);
  const fitRef = useRef<TerminalAddon | null>(null);
  const terminalIdRef = useRef<string | null>(null);
  const dataDisposableRef = useRef<{ dispose: () => void } | null>(null);
  const bufferRef = useRef<Map<string, string>>(new Map());
  const bootstrapRef = useRef(false);
  const [viewportHeight, setViewportHeight] = useState(() =>
    typeof window === "undefined" ? 900 : window.innerHeight
  );

  const activeTerminalSession = useMemo(() => {
    return terminalSessions.find((session) => session.id === activeTerminalSessionId) ?? terminalSessions[0] ?? null;
  }, [activeTerminalSessionId, terminalSessions]);
  const terminalHost = activeSession?.terminal_host ?? null;
  const linkedTerminalSession = terminalHost?.terminal_id
    ? terminalSessions.find((session) => session.id === terminalHost.terminal_id) ?? null
    : null;
  const linkedTerminalLabel =
    linkedTerminalSession?.title ?? describeTerminalHostTitle(terminalHost) ?? "linked shell";
  const liveInteractiveLabel = terminalHost?.live
    ? "Live interactive run"
    : terminalHost
      ? "Terminal-linked run"
      : null;

  const drawerHeights = useMemo(() => resolveDrawerHeights(viewportHeight), [viewportHeight]);
  const preset = useMemo(() => {
    const distances = [
      { id: "peek", value: drawerHeights.peek },
      { id: "half", value: drawerHeights.half },
      { id: "full", value: drawerHeights.full },
    ];
    return distances.reduce((closest, current) =>
      Math.abs(current.value - drawerHeight) < Math.abs(closest.value - drawerHeight) ? current : closest
    ).id as "peek" | "half" | "full";
  }, [drawerHeight, drawerHeights.full, drawerHeights.half, drawerHeights.peek]);

  const headerLabel = useMemo(() => {
    if (!drawerOpen) {
      return "Terminal";
    }
    if (!activeTerminalSession) {
      return `${activeProject?.name ?? "Project"} shell`;
    }
    if (activeTerminalSession.status === "ready") {
      return activeTerminalSession.title;
    }
    if (activeTerminalSession.status === "unavailable") {
      return `${activeTerminalSession.title} unavailable`;
    }
    return `${activeTerminalSession.title} starting`;
  }, [activeProject?.name, activeTerminalSession, drawerOpen]);

  const collapsedLabel = useMemo(() => {
    if (!activeTerminalSession) {
      return `${activeProject?.name ?? "Project"} shell`;
    }
    return activeTerminalSession.title;
  }, [activeProject?.name, activeTerminalSession]);

  const renderSnapshot = (session: TerminalSession) => {
    const terminal = terminalRef.current;
    if (!terminal) {
      return;
    }

    terminal.clear?.();
    const snapshot = bufferRef.current.get(session.id) ?? "";
    if (snapshot) {
      terminal.write(snapshot);
      return;
    }

    if (session.status === "unavailable") {
      terminal.writeln("[Triad] Terminal backend is unavailable.");
      return;
    }

    if (session.status === "starting") {
      terminal.writeln("Starting terminal...");
    }
  };

  const createSession = async () => {
    const cwd = activeProject?.path ?? null;
    const index = terminalSessions.length + 1;
    const title = `${basename(cwd)} ${index}`;

    try {
      const response = (await rpc("terminal.create", {
        cwd: cwd ?? undefined,
        title,
        cols: 120,
        rows: 24,
      })) as { session?: TerminalBackendSession };
      const backendSession = response.session;
      if (!backendSession?.terminal_id) {
        throw new Error("Terminal session metadata was not returned");
      }

      const session = mapBackendSession(backendSession);
      bufferRef.current.set(session.id, backendSession.snapshot ?? "");
      addTerminalSession(session);
      setActiveTerminalSessionId(session.id);
      bootstrapRef.current = true;
      return session;
    } catch {
      const session = makeFallbackSession(cwd, index);
      bufferRef.current.set(session.id, "");
      addTerminalSession(session);
      setActiveTerminalSessionId(session.id);
      bootstrapRef.current = true;
      return session;
    }
  };

  const closeSession = (session: TerminalSession) => {
    if (session.terminalId) {
      void rpc("terminal.close", { terminal_id: session.terminalId }).catch(() => undefined);
    }
    bufferRef.current.delete(session.id);
    removeTerminalSession(session.id);
  };

  useEffect(() => {
    if (!drawerOpen) {
      return;
    }

    let cancelled = false;

    const syncTerminalSessions = async () => {
      try {
        const response = (await rpc("terminal.list", {})) as { sessions?: TerminalBackendSession[] };
        if (cancelled) {
          return;
        }

        const backendSessions = Array.isArray(response.sessions) ? response.sessions : [];
        const snapshotById = new Map(backendSessions.map((entry) => [entry.terminal_id, entry.snapshot ?? ""]));
        const sessions = backendSessions.map(mapBackendSession);
        const sessionIds = new Set(sessions.map((session) => session.id));
        for (const session of sessions) {
          bufferRef.current.set(session.id, snapshotById.get(session.id) ?? "");
        }
        for (const terminalId of Array.from(bufferRef.current.keys())) {
          if (!sessionIds.has(terminalId)) {
            bufferRef.current.delete(terminalId);
          }
        }
        setTerminalSessions(sessions);
        const shouldCreateInitialSession = !bootstrapRef.current && sessions.length === 0;
        bootstrapRef.current = true;

        if (shouldCreateInitialSession) {
          await createSession();
        }
      } catch {
        if (cancelled) {
          return;
        }
        if (!bootstrapRef.current && terminalSessions.length === 0) {
          bootstrapRef.current = true;
          await createSession();
        }
      }
    };

    void syncTerminalSessions();

    return () => {
      cancelled = true;
    };
  }, [activeProject?.path, drawerOpen, setTerminalSessions, terminalSessions.length]);

  useEffect(() => {
    const onResize = () => setViewportHeight(window.innerHeight);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    if (drawerHeight > drawerHeights.full) {
      setDrawerHeight(drawerHeights.full);
    }
  }, [drawerHeight, drawerHeights.full, setDrawerHeight]);

  useEffect(() => {
    const unsub = onEvent((event) => {
      if (event.type !== "terminal_output") {
        return;
      }
      const terminalId = event.terminal_id;
      if (!terminalId) {
        return;
      }
      const payload = typeof event.data === "string" ? safeAtob(event.data) : "";
      if (!payload) {
        return;
      }

      const current = bufferRef.current.get(terminalId) ?? "";
      bufferRef.current.set(terminalId, `${current}${payload}`.slice(-200000));
      updateTerminalSession(terminalId, { status: "ready" });
      if (terminalId === terminalIdRef.current && terminalRef.current) {
        terminalRef.current.write(payload);
      }
    });

    return () => unsub();
  }, []);

  useEffect(() => {
    if (!drawerOpen || !mountRef.current || terminalRef.current) {
      return;
    }

    let disposed = false;
    let observer: ResizeObserver | null = null;
    let onWindowResize: (() => void) | null = null;

    const init = async () => {
      try {
        const xterm = await import("@xterm/xterm");
        const fitAddon = await import("@xterm/addon-fit");
        const webLinksAddon = await import("@xterm/addon-web-links");
        await import("@xterm/xterm/css/xterm.css");

        if (disposed || !mountRef.current) {
          return;
        }

        const terminal = new xterm.Terminal({
          cursorBlink: true,
          fontFamily: '"SF Mono", ui-monospace, Menlo, monospace',
          fontSize: 13,
          lineHeight: 1.35,
          scrollback: 10000,
          theme: {
            background: "#181818",
            foreground: "#e8e8e8",
            cursor: "#ffffff",
            selectionBackground: "rgba(51, 156, 255, 0.25)",
            black: "#0d0d0d",
            red: "#ff6764",
            green: "#40c977",
            yellow: "#ffd240",
            blue: "#339cff",
            magenta: "#ad7bf9",
            cyan: "#99ceff",
            white: "#f5f5f5",
            brightBlack: "#5d5d5d",
            brightRed: "#fa423e",
            brightGreen: "#04b84c",
            brightYellow: "#ffc300",
            brightBlue: "#0285ff",
            brightMagenta: "#924ff7",
            brightCyan: "#99ceff",
            brightWhite: "#ffffff",
          },
        });
        const fitAddonInstance = new fitAddon.FitAddon();
        terminal.loadAddon(fitAddonInstance);
        terminal.loadAddon(new webLinksAddon.WebLinksAddon());
        terminal.open(mountRef.current);
        fitAddonInstance.fit();

        terminalRef.current = terminal as unknown as XtermTerminal;
        fitRef.current = fitAddonInstance as unknown as TerminalAddon;

        dataDisposableRef.current = null;
        const dataDisposable = terminal.onData?.((data) => {
          const terminalId = terminalIdRef.current;
          if (!terminalId) {
            return;
          }
          void rpc("terminal.input", {
            terminal_id: terminalId,
            data: encodeInput(data),
          }).catch(() => undefined);
        });
        dataDisposableRef.current = dataDisposable && typeof dataDisposable === "object" ? dataDisposable : null;

        observer = new ResizeObserver(() => {
          fitAddonInstance.fit();
          const terminalId = terminalIdRef.current;
          if (terminalId) {
            const sizedTerminal = terminal as unknown as { cols?: number; rows?: number };
            void rpc("terminal.resize", {
              terminal_id: terminalId,
              cols: sizedTerminal.cols ?? 120,
              rows: sizedTerminal.rows ?? 24,
            }).catch(() => undefined);
          }
        });
        observer.observe(mountRef.current);

        onWindowResize = () => fitAddonInstance.fit();
        window.addEventListener("resize", onWindowResize);

      } catch {
        if (!disposed) {
          terminalRef.current = null;
          fitRef.current = null;
        }
      }
    };

    void init();

    return () => {
      disposed = true;
      observer?.disconnect();
      if (onWindowResize) {
        window.removeEventListener("resize", onWindowResize);
      }
      dataDisposableRef.current?.dispose?.();
      dataDisposableRef.current = null;
      terminalRef.current?.dispose();
      terminalRef.current = null;
      fitRef.current = null;
      terminalIdRef.current = null;
    };
  }, [drawerOpen]);

  useEffect(() => {
    if (!drawerOpen || !terminalRef.current || !activeTerminalSession) {
      return;
    }

    terminalIdRef.current = activeTerminalSession.terminalId;
    renderSnapshot(activeTerminalSession);

    if (activeTerminalSession.status !== "ready" || !activeTerminalSession.terminalId) {
      return;
    }

    const terminal = terminalRef.current as unknown as { cols?: number; rows?: number };
    void rpc("terminal.resize", {
      terminal_id: activeTerminalSession.terminalId,
      cols: terminal.cols ?? 120,
      rows: terminal.rows ?? 24,
    }).catch(() => undefined);
  }, [activeTerminalSession, drawerOpen]);

  useEffect(() => {
    if (!terminalHost?.terminal_id) {
      return;
    }
    if (!terminalSessions.some((session) => session.id === terminalHost.terminal_id)) {
      return;
    }
    if (activeTerminalSessionId === terminalHost.terminal_id) {
      return;
    }
    setActiveTerminalSessionId(terminalHost.terminal_id);
  }, [activeTerminalSessionId, setActiveTerminalSessionId, terminalHost?.terminal_id, terminalSessions]);

  useEffect(() => {
    if (!drawerOpen || !fitRef.current) {
      return;
    }
    fitRef.current.fit?.();
  }, [drawerHeight, drawerOpen]);

  if (!drawerOpen) {
    return (
      <button
        type="button"
        onClick={toggleDrawer}
        className="flex h-8 w-full items-center gap-2 border-t border-[rgba(255,255,255,0.06)] bg-[var(--color-bg-surface)] px-4 text-left text-[12px] text-text-secondary transition-colors hover:text-text-primary"
      >
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none" className="text-text-tertiary">
          <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span>{collapsedLabel}</span>
        <span className="ml-auto text-[11px] text-text-tertiary">
          {terminalSessions.length > 1 ? `${terminalSessions.length} shells` : "Peek"}
        </span>
      </button>
    );
  }

  return (
    <section
      className="flex flex-col border-t border-[rgba(255,255,255,0.06)] bg-[var(--color-bg-surface)]"
      style={{ height: drawerHeight }}
    >
      <div className="flex h-8 items-center justify-between border-b border-[rgba(255,255,255,0.06)] px-4">
        <div className="flex min-w-0 items-center gap-2">
          <svg width="10" height="10" viewBox="0 0 16 16" fill="none" className="text-text-tertiary">
            <path d="M4 10L8 6L12 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="truncate text-[12px] text-text-secondary">{headerLabel}</span>
          <span className="text-[11px] text-text-tertiary">{preset}</span>
          {terminalHost ? (
            <span className="truncate text-[11px] text-text-tertiary">
              {liveInteractiveLabel} · {linkedTerminalLabel}
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-1.5">
          {(["peek", "half", "full"] as const).map((size) => (
            <button
              key={size}
              type="button"
              onClick={() => setDrawerHeight(drawerHeights[size])}
              className={[
                "rounded-md border px-2 py-0.5 text-[11px] transition-colors",
                preset === size
                  ? "border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.04)] text-text-primary"
                  : "border-transparent text-text-tertiary hover:border-[rgba(255,255,255,0.05)] hover:text-text-secondary",
              ].join(" ")}
            >
              {size}
            </button>
          ))}
          <button
            type="button"
            onClick={() => {
              void createSession();
            }}
            className="rounded-md border border-transparent px-2 py-0.5 text-[11px] text-text-tertiary transition-colors hover:border-[rgba(255,255,255,0.05)] hover:text-text-secondary"
          >
            new
          </button>
          <button
            type="button"
            onClick={() => {
              if (activeTerminalSession?.terminalId) {
                void rpc("terminal.clear", { terminal_id: activeTerminalSession.terminalId }).catch(() => undefined);
              }
              if (activeTerminalSession) {
                bufferRef.current.set(activeTerminalSession.id, "");
              }
              terminalRef.current?.clear?.();
            }}
            className="rounded-md border border-transparent px-2 py-0.5 text-[11px] text-text-tertiary transition-colors hover:border-[rgba(255,255,255,0.05)] hover:text-text-secondary"
          >
            clear
          </button>
          <button
            type="button"
            onClick={toggleDrawer}
            className="flex h-5 w-5 items-center justify-center rounded text-text-tertiary hover:text-text-secondary"
          >
            <svg width="10" height="10" viewBox="0 0 16 16" fill="none">
              <path d="M4 4L12 12M12 4L4 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      {terminalSessions.length > 0 ? (
        <div className="flex gap-1 border-b border-[rgba(255,255,255,0.06)] px-3 py-2">
          {terminalSessions.map((session) => {
            const active = session.id === activeTerminalSession?.id;
            return (
              <div key={session.id} className="flex min-w-0 items-center">
                <button
                  type="button"
                  onClick={() => setActiveTerminalSessionId(session.id)}
                  className={[
                    "flex min-w-0 items-center gap-2 rounded-l-md border px-3 py-1 text-[11px] transition-colors",
                    active
                      ? "border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.04)] text-text-primary"
                      : "border-transparent text-text-tertiary hover:border-[rgba(255,255,255,0.05)] hover:text-text-secondary",
                  ].join(" ")}
                >
                  <span className="truncate">{session.title}</span>
                  {session.kind === "provider" ? (
                    <span className="rounded-full border border-[rgba(255,255,255,0.08)] px-1.5 py-0.5 text-[9px] uppercase tracking-[0.08em] text-text-tertiary">
                      linked
                    </span>
                  ) : null}
                  <span className="rounded-full border border-[rgba(255,255,255,0.08)] px-1.5 py-0.5 text-[10px] uppercase tracking-[0.08em]">
                    {session.status === "ready" ? "live" : session.status}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => closeSession(session)}
                  className={[
                    "flex h-[26px] items-center justify-center rounded-r-md border border-l-0 px-2 text-text-tertiary transition-colors",
                    active
                      ? "border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.04)] hover:text-text-primary"
                      : "border-transparent hover:border-[rgba(255,255,255,0.05)] hover:text-text-secondary",
                  ].join(" ")}
                >
                  <svg width="8" height="8" viewBox="0 0 16 16" fill="none">
                    <path d="M4 4L12 12M12 4L4 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                </button>
              </div>
            );
          })}
        </div>
      ) : null}

      {terminalHost ? (
        <div className="border-b border-[rgba(255,255,255,0.06)] px-4 py-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-[rgba(255,255,255,0.08)] px-2 py-0.5 text-[10px] uppercase tracking-[0.1em] text-text-tertiary">
              {terminalHost.live ? "Live interactive" : "Terminal-linked"}
            </span>
            <span className="truncate text-[11px] text-text-secondary">
              {linkedTerminalLabel}
            </span>
          </div>
          <div className="mt-1 text-[11px] leading-[1.45] text-text-tertiary">
            {terminalHost.live
              ? "Terminal is the source of truth; transcript capture may be partial."
              : "This session is linked to a shell, but it is not marked as live interactive."}
          </div>
        </div>
      ) : null}

      <div className="flex-1 overflow-hidden p-1">
        <div ref={mountRef} className="h-full w-full" />
      </div>
    </section>
  );
}
