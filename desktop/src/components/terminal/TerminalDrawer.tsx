import { useEffect, useMemo, useRef, useState } from "react";
import { onEvent, rpc } from "../../lib/rpc";
import { useProjectStore } from "../../stores/project-store";
import { useUiStore } from "../../stores/ui-store";

type XtermTerminal = {
  open: (el: HTMLElement) => void;
  write: (data: string) => void;
  writeln: (data: string) => void;
  loadAddon?: (addon: any) => void;
  onData?: (cb: (data: string) => void) => { dispose: () => void } | void;
  onResize?: (cb: (size: { cols: number; rows: number }) => void) => { dispose: () => void } | void;
  dispose: () => void;
  fit?: () => void;
};

type TerminalAddon = {
  fit?: () => void;
  activate?: (terminal: any) => void;
};

const DEFAULT_CWD = "/";

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

export function TerminalDrawer() {
  const { drawerOpen, drawerHeight, toggleDrawer, setDrawerHeight } = useUiStore();
  const activeProject = useProjectStore((state) => state.activeProject);
  const mountRef = useRef<HTMLDivElement | null>(null);
  const terminalRef = useRef<XtermTerminal | null>(null);
  const fitRef = useRef<TerminalAddon | null>(null);
  const terminalIdRef = useRef<string | null>(null);
  const resizeRef = useRef<{ dispose: () => void } | null>(null);
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState<string>("starting");

  const headerLabel = useMemo(() => {
    if (!drawerOpen) {
      return "Terminal";
    }
    if (status === "ready") {
      return "Загружен 1 терминал";
    }
    if (status === "unavailable") {
      return "Terminal unavailable";
    }
    return "Загрузка терминала...";
  }, [drawerOpen, status]);

  useEffect(() => {
    if (!drawerOpen || !mountRef.current || terminalRef.current) {
      return;
    }

    let disposed = false;

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

        const terminalCreate = await rpc<{ terminal_id: string }>("terminal.create", {
          cwd: activeProject?.path ?? DEFAULT_CWD,
        }).catch(() => null);

        if (terminalCreate?.terminal_id) {
          terminalIdRef.current = terminalCreate.terminal_id;
          setStatus("ready");
          void rpc("terminal.resize", {
            terminal_id: terminalCreate.terminal_id,
            cols: (terminal as unknown as { cols?: number }).cols ?? 120,
            rows: (terminal as unknown as { rows?: number }).rows ?? 24,
          }).catch(() => undefined);
        } else {
          setStatus("unavailable");
          terminal.writeln("[Triad] Terminal backend is unavailable.");
        }

        const dataDisposable = terminal.onData?.((data) => {
          const terminalId = terminalIdRef.current;
          if (!terminalId) {
            return;
          }
          void rpc("terminal.input", {
            terminal_id: terminalId,
            data: encodeInput(data),
          }).catch(() => {
            // Keep the terminal usable even if backend input drops.
          });
        });

        resizeRef.current = dataDisposable && typeof dataDisposable === "object" ? dataDisposable : null;

        const unsub = onEvent((event) => {
          if (event.type !== "terminal_output") {
            return;
          }
          if (event.terminal_id !== terminalIdRef.current) {
            return;
          }
          const payload = typeof event.data === "string" ? safeAtob(event.data) : "";
          if (payload) {
            terminal.write(payload);
          }
        });

        const observer = new ResizeObserver(() => {
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

        const onWindowResize = () => fitAddonInstance.fit();
        window.addEventListener("resize", onWindowResize);

        const cleanup = () => {
          disposed = true;
          const terminalId = terminalIdRef.current;
          if (terminalId) {
            void rpc("terminal.close", { terminal_id: terminalId }).catch(() => undefined);
          }
          unsub();
          observer.disconnect();
          window.removeEventListener("resize", onWindowResize);
          dataDisposable && dataDisposable.dispose?.();
          terminal.dispose();
          terminalRef.current = null;
          fitRef.current = null;
          terminalIdRef.current = null;
          resizeRef.current = null;
        };

        return cleanup;
      } catch {
        if (!disposed) {
          setStatus("unavailable");
        }
      } finally {
        if (!disposed) {
          setReady(true);
        }
      }
    };

    let cleanupFn: (() => void) | undefined;

    void init().then((cleanup) => {
      cleanupFn = cleanup;
    });

    return () => {
      disposed = true;
      cleanupFn?.();
      resizeRef.current?.dispose?.();
      resizeRef.current = null;
      setReady(false);
    };
  }, [activeProject?.path, drawerOpen]);

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
        className="flex h-9 w-full items-center gap-2 border-t border-border-light bg-[rgba(24,24,24,0.96)] px-4 text-left text-[12px] text-text-secondary transition-colors hover:text-text-primary"
      >
        <span className="h-2 w-2 rounded-full bg-[#339cff]" />
        <span>Terminal</span>
      </button>
    );
  }

  return (
    <section
      className="codex-terminal-shell relative flex flex-col overflow-hidden border-t border-border-light bg-[linear-gradient(180deg,rgba(255,255,255,0.02),transparent_35%),var(--color-bg-surface)]"
      style={{ height: drawerHeight }}
    >
      <div className="codex-terminal-ambient pointer-events-none absolute inset-0 opacity-100" />
      <div className="relative z-10 flex h-9 items-center justify-between border-b border-border-light bg-[rgba(24,24,24,0.92)] px-4 backdrop-blur-[10px]">
        <div className="flex items-center gap-3">
          <span className="text-[12px] font-medium text-text-primary">{headerLabel}</span>
          <span className="text-[11px] text-text-tertiary">{ready ? "interactive" : "loading"}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              void rpc("terminal.close", { terminal_id: terminalIdRef.current ?? "" }).catch(() => undefined);
              toggleDrawer();
            }}
            className="rounded-md border border-border-light px-2 py-1 text-[11px] text-text-tertiary transition-[transform,border-color,background-color,color] duration-200 ease-out hover:-translate-y-0.5 hover:border-border-default hover:bg-white/5 hover:text-text-primary"
          >
            Close
          </button>
        </div>
      </div>

      <div className="relative z-10 flex-1 overflow-hidden px-2 py-2">
        <div
          ref={mountRef}
          className="h-full w-full rounded-[18px] border border-border-default bg-[rgba(0,0,0,0.25)] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-[border-color,box-shadow,transform] duration-200 ease-out hover:border-border-heavy hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.04),0_0_0_1px_rgba(255,255,255,0.02)]"
        />
        {!ready ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="codex-glow-loop rounded-full border border-border-light bg-black/50 px-3 py-1 text-[11px] text-text-tertiary">
              Preparing terminal...
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
