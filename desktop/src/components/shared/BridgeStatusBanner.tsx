import { useState } from "react";
import { reconnectBridge } from "../../lib/rpc";
import { useBridgeStore } from "../../stores/bridge-store";

export function BridgeStatusBanner() {
  const status = useBridgeStore((state) => state.status);
  const [retrying, setRetrying] = useState(false);

  const visible = status.started && (!status.connected || Boolean(status.lastError) || status.reconnecting);
  if (!visible) {
    return null;
  }

  const headline = status.reconnecting ? "Reconnecting bridge" : "Bridge unavailable";
  const detail = status.lastError ?? status.fallbackReason ?? "Retry to reconnect to the live sidecar.";

  const handleRetry = async () => {
    setRetrying(true);
    try {
      await reconnectBridge();
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div className="mx-4 mb-1 rounded-md border border-[var(--color-border)] bg-[rgba(255,255,255,0.015)] px-3 py-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[12px] text-[var(--color-text-primary)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-text-warning)]" />
            <span>{headline}</span>
          </div>
          <div className="mt-0.5 line-clamp-2 text-[11px] leading-[1.45] text-[var(--color-text-tertiary)]">{detail}</div>
        </div>
        <button
          type="button"
          onClick={() => void handleRetry()}
          disabled={retrying || status.reconnecting}
          className="shrink-0 rounded-md border border-[var(--color-border)] px-2.5 py-1 text-[11px] text-[var(--color-text-secondary)] transition-colors duration-150 hover:bg-[rgba(255,255,255,0.03)] hover:text-[var(--color-text-primary)] disabled:opacity-50"
        >
          {retrying || status.reconnecting ? "Retrying..." : "Retry"}
        </button>
      </div>
    </div>
  );
}
