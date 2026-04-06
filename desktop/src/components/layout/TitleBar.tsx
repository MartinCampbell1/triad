import { Badge } from "../shared/Badge";
import { useBridgeStore } from "../../stores/bridge-store";
import { useProjectStore } from "../../stores/project-store";
import { useProviderStore } from "../../stores/provider-store";
import { useSessionStore } from "../../stores/session-store";
import { useUiStore } from "../../stores/ui-store";

function TrafficLight({ tone }: { tone: "red" | "yellow" | "green" }) {
  const colors: Record<typeof tone, string> = {
    red: "bg-[#ff5f57]",
    yellow: "bg-[#febc2e]",
    green: "bg-[#28c840]",
  };

  return <span className={`h-3 w-3 rounded-full ${colors[tone]} shadow-[inset_0_0_0_1px_rgba(0,0,0,0.2)]`} />;
}

function statusBadgeClass(status?: string) {
  switch (status) {
    case "running":
      return "border-[rgba(51,156,255,0.24)] bg-[rgba(51,156,255,0.12)] text-[#8cc7ff]";
    case "completed":
      return "border-[rgba(64,201,119,0.24)] bg-[rgba(64,201,119,0.12)] text-[#8fdfae]";
    case "failed":
      return "border-[rgba(255,103,100,0.24)] bg-[rgba(255,103,100,0.12)] text-[#ff9b99]";
    case "paused":
      return "border-[rgba(255,210,64,0.24)] bg-[rgba(255,210,64,0.12)] text-[#ffd96f]";
    default:
      return "border-border-light bg-black/20 text-text-secondary";
  }
}

function providerTone(provider?: string): "neutral" | "subtle" | "accent" {
  if (provider === "codex") return "accent";
  if (provider === "gemini") return "subtle";
  return "neutral";
}

function providerLabel(provider?: string) {
  if (provider === "claude") return "Claude";
  if (provider === "codex") return "Codex";
  if (provider === "gemini") return "Gemini";
  return provider ?? "Provider";
}

function modeLabel(mode?: string) {
  if (!mode) return "Solo";
  return mode.charAt(0).toUpperCase() + mode.slice(1);
}

function bridgeTone(connected: boolean, reconnecting: boolean): "neutral" | "subtle" | "accent" {
  if (reconnecting) return "subtle";
  return connected ? "accent" : "neutral";
}

function bridgeLabel(connected: boolean, reconnecting: boolean, started: boolean, backendMode: string) {
  if (!started) return "Bridge starting";
  if (reconnecting) return "Bridge retrying";
  if (connected) return "Bridge live";
  return backendMode === "mock" ? "Bridge mock" : "Bridge offline";
}

function ShellButton({
  active = false,
  disabled = false,
  title,
  onClick,
  children,
}: {
  active?: boolean;
  disabled?: boolean;
  title: string;
  onClick?: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={[
        "rounded-md border px-2.5 py-1 text-[11px] transition-colors",
        disabled ? "cursor-not-allowed opacity-40" : "",
        active
          ? "border-[rgba(51,156,255,0.24)] bg-[rgba(51,156,255,0.12)] text-text-primary"
          : "border-border-light bg-black/10 text-text-tertiary hover:border-border-default hover:text-text-secondary",
      ].join(" ")}
    >
      {children}
    </button>
  );
}

export function TitleBar() {
  const titlebarCompact = useUiStore((state) => state.titlebarCompact);
  const sidebarCollapsed = useUiStore((state) => state.sidebarCollapsed);
  const drawerOpen = useUiStore((state) => state.drawerOpen);
  const diffPanelOpen = useUiStore((state) => state.diffPanelOpen);
  const diffFiles = useUiStore((state) => state.diffFiles);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);
  const toggleDrawer = useUiStore((state) => state.toggleDrawer);
  const toggleDiffPanel = useUiStore((state) => state.toggleDiffPanel);
  const setTitlebarCompact = useUiStore((state) => state.setTitlebarCompact);
  const activeProject = useProjectStore((state) => state.activeProject);
  const activeSession = useSessionStore((state) => state.activeSession);
  const forkSession = useSessionStore((state) => state.forkSession);
  const fallbackMode = useProviderStore((state) => state.mode);
  const fallbackProvider = useProviderStore((state) => state.activeProvider);
  const bridgeStatus = useBridgeStore((state) => state.status);

  const forkCurrentSession = () => {
    if (!activeSession) {
      return;
    }
    void forkSession(activeSession.id);
  };

  const mode = activeSession?.mode ?? fallbackMode;
  const provider = activeSession?.provider ?? fallbackProvider;
  const status = activeSession?.status ?? "active";

  return (
    <div
      className={[
        "flex items-center gap-3 border-b border-border-light bg-[linear-gradient(180deg,rgba(255,255,255,0.03),rgba(255,255,255,0.01))] px-4 backdrop-blur-xl",
        titlebarCompact ? "h-11" : "h-12",
      ].join(" ")}
    >
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2.5">
          <TrafficLight tone="red" />
          <TrafficLight tone="yellow" />
          <TrafficLight tone="green" />
        </div>

        <div className="flex items-center gap-1">
          <ShellButton title="Toggle sidebar" onClick={toggleSidebar} active={!sidebarCollapsed}>
            ≡
          </ShellButton>
          <ShellButton title="Toggle terminal" onClick={toggleDrawer} active={drawerOpen}>
            ⌁
          </ShellButton>
          <ShellButton title="Toggle diff panel" onClick={toggleDiffPanel} active={diffPanelOpen}>
            {`Δ${diffFiles.length > 0 ? ` ${diffFiles.length}` : ""}`}
          </ShellButton>
          <ShellButton
            title="Fork current session"
            onClick={forkCurrentSession}
            active={Boolean(activeSession)}
            disabled={!activeSession}
          >
            Fork
          </ShellButton>
        </div>
      </div>

      <div data-tauri-drag-region className="min-w-0 flex-1 px-3">
        <div className="truncate text-center text-[13px] font-medium tracking-[-0.01em] text-text-primary">
          {activeSession?.title ?? "Новая беседа"}
        </div>
        <div className="truncate text-center text-[11px] text-text-tertiary">
          {activeProject?.name ?? "Triad Desktop"}
          {activeProject?.path ? <span className="ml-2 text-text-muted">{activeProject.path}</span> : null}
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        <Badge
          tone={bridgeTone(bridgeStatus.connected, bridgeStatus.reconnecting)}
          title={bridgeStatus.lastError ?? bridgeStatus.fallbackReason ?? undefined}
        >
          {bridgeLabel(
            bridgeStatus.connected,
            bridgeStatus.reconnecting,
            bridgeStatus.started,
            bridgeStatus.backendMode
          )}
        </Badge>
        <Badge tone="subtle">{modeLabel(mode)}</Badge>
        <Badge tone={providerTone(provider)}>{providerLabel(provider)}</Badge>
        <Badge className={statusBadgeClass(status)}>{status}</Badge>
        <ShellButton
          title={titlebarCompact ? "Expand title bar" : "Compact title bar"}
          onClick={() => setTitlebarCompact(!titlebarCompact)}
          active={titlebarCompact}
        >
          {titlebarCompact ? "▣" : "▢"}
        </ShellButton>
      </div>
    </div>
  );
}
