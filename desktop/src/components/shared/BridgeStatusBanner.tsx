import { useState } from "react";
import { reconnectBridge } from "../../lib/rpc";
import { useBridgeStore } from "../../stores/bridge-store";
import { Badge } from "./Badge";

function statusTone(connected: boolean, reconnecting: boolean) {
  if (reconnecting) {
    return "subtle";
  }
  return connected ? "accent" : "neutral";
}

export function BridgeStatusBanner() {
  const status = useBridgeStore((state) => state.status);
  const [retrying, setRetrying] = useState(false);

  const visible = status.started && (!status.connected || Boolean(status.lastError) || status.reconnecting);
  if (!visible) {
    return null;
  }

  const headline = status.reconnecting
    ? "Reconnecting to Python bridge..."
    : status.connected
      ? status.backendMode === "tauri"
        ? "Python bridge is connected"
        : "Python bridge is degraded"
      : "Python bridge is unavailable";

  const detail = status.lastError
    ? status.lastError
    : status.fallbackReason ?? "Retry to reconnect to the live sidecar.";

  const handleRetry = async () => {
    setRetrying(true);
    try {
      await reconnectBridge();
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div className="codex-message-enter-subtle mx-4 mb-2 rounded-[16px] border border-[rgba(51,156,255,0.18)] bg-[linear-gradient(180deg,rgba(51,156,255,0.12),rgba(255,255,255,0.02))] px-4 py-3 shadow-[0_10px_30px_rgba(0,0,0,0.18)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-[12px] font-medium text-text-primary">{headline}</div>
            <Badge tone={statusTone(status.connected, status.reconnecting)}>
              {status.backendMode === "tauri" ? "live" : "offline"}
            </Badge>
            {status.reconnecting ? <Badge tone="subtle">reconnecting</Badge> : null}
          </div>
          <div className="mt-1 text-[12px] leading-[1.5] text-text-secondary">{detail}</div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void handleRetry()}
            disabled={retrying || status.reconnecting}
            className="rounded-md border border-[rgba(51,156,255,0.24)] bg-[rgba(51,156,255,0.12)] px-3 py-1.5 text-[12px] font-medium text-[#8cc7ff] transition-colors hover:border-[rgba(51,156,255,0.36)] hover:bg-[rgba(51,156,255,0.16)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {retrying || status.reconnecting ? "Retrying..." : "Retry bridge"}
          </button>
        </div>
      </div>
    </div>
  );
}
