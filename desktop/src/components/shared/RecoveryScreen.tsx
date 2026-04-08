import { useMemo, useState } from "react";
import { useBridgeStore } from "../../stores/bridge-store";
import { DiagnosticsPanel } from "./DiagnosticsPanel";

export type RecoveryState = "booting" | "bridge_unavailable" | "project_unavailable";

interface Props {
  state: RecoveryState;
  error?: string | null;
  onRetry: () => Promise<void> | void;
  onChooseProject?: () => Promise<void> | void;
  onExportDiagnostics: () => Promise<void> | void;
}

export function RecoveryScreen({ state, error, onRetry, onChooseProject, onExportDiagnostics }: Props) {
  const bridgeStatus = useBridgeStore((store) => store.status);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [exporting, setExporting] = useState(false);

  const copy = useMemo(() => {
    if (state === "booting") {
      return {
        eyebrow: "Starting bridge",
        title: "Triad is starting the Python sidecar",
        detail: "The desktop shell is waiting for the bridge to become healthy before it loads projects and sessions.",
      };
    }
    if (state === "project_unavailable") {
      return {
        eyebrow: "Project unavailable",
        title: "Choose a project before you start a session",
        detail: "The bridge is live, but Triad could not recover an active project from the session ledger.",
      };
    }
    return {
      eyebrow: "Bridge unavailable",
      title: "Triad cannot talk to the Python bridge",
      detail: "The UI is fail-closed: retry the sidecar, inspect diagnostics, then recover the project once the bridge is healthy.",
    };
  }, [state]);

  const handleRetry = async () => {
    setRetrying(true);
    try {
      await onRetry();
    } finally {
      setRetrying(false);
    }
  };

  const handleExportDiagnostics = async () => {
    setExporting(true);
    try {
      await onExportDiagnostics();
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex h-full w-full items-center justify-center bg-[radial-gradient(circle_at_top,rgba(38,86,151,0.16),transparent_34%),var(--color-bg-surface)] px-6 py-8 text-text-primary">
      <div className="w-full max-w-[720px] rounded-[28px] border border-border-default bg-[rgba(11,15,22,0.82)] p-6 shadow-[0_28px_80px_rgba(0,0,0,0.34)] backdrop-blur-[18px]">
        <div className="rounded-full border border-[rgba(107,167,255,0.18)] bg-[rgba(39,94,178,0.16)] px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-[rgba(178,212,255,0.9)]">
          {copy.eyebrow}
        </div>
        <h1 className="mt-4 text-[30px] font-medium tracking-[-0.03em] text-text-primary">{copy.title}</h1>
        <p className="mt-3 max-w-[640px] text-[14px] leading-[1.7] text-text-secondary">{copy.detail}</p>

        <div className="mt-5 grid gap-3 rounded-[22px] border border-border-light bg-[rgba(255,255,255,0.025)] p-4 text-[13px] text-text-secondary">
          <div className="flex items-center justify-between gap-3">
            <span>Bridge mode</span>
            <span className="rounded-full border border-border-light px-2 py-0.5 text-[11px] uppercase tracking-[0.12em] text-text-primary">
              {bridgeStatus.backendMode}
            </span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span>Connected</span>
            <span>{bridgeStatus.connected ? "Yes" : "No"}</span>
          </div>
          <div className="rounded-[16px] border border-[rgba(250,66,62,0.16)] bg-[rgba(250,66,62,0.07)] px-3 py-2 text-[12px] text-text-secondary">
            {error ?? bridgeStatus.lastError ?? bridgeStatus.fallbackReason ?? "No bridge details were recorded."}
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          {state !== "booting" ? (
            <button
              type="button"
              onClick={() => void handleRetry()}
              disabled={retrying}
              className="rounded-xl border border-[rgba(72,154,255,0.28)] bg-[rgba(40,111,214,0.16)] px-4 py-2 text-[13px] font-medium text-[rgba(177,220,255,0.95)] transition-colors hover:bg-[rgba(40,111,214,0.22)] disabled:opacity-60"
            >
              {retrying ? "Retrying bridge..." : "Retry bridge"}
            </button>
          ) : null}
          {state === "project_unavailable" && onChooseProject ? (
            <button
              type="button"
              onClick={() => void onChooseProject()}
              className="rounded-xl border border-border-light px-4 py-2 text-[13px] font-medium text-text-primary transition-colors hover:border-border-default hover:bg-white/5"
            >
              Choose project
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => setShowDiagnostics((current) => !current)}
            className="rounded-xl border border-border-light px-4 py-2 text-[13px] text-text-secondary transition-colors hover:border-border-default hover:bg-white/5 hover:text-text-primary"
          >
            {showDiagnostics ? "Hide diagnostics" : "Show diagnostics"}
          </button>
          <button
            type="button"
            onClick={() => void handleExportDiagnostics()}
            disabled={exporting}
            className="rounded-xl border border-border-light px-4 py-2 text-[13px] text-text-secondary transition-colors hover:border-border-default hover:bg-white/5 hover:text-text-primary disabled:opacity-60"
          >
            {exporting ? "Exporting diagnostics..." : "Export diagnostics"}
          </button>
        </div>

        <div className="mt-4">
          <DiagnosticsPanel open={showDiagnostics} />
        </div>
      </div>
    </div>
  );
}
