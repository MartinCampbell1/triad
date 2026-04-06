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

  const headline = status.reconnecting
    ? "Reconnecting to Python bridge..."
    : status.connected
      ? status.backendMode === "tauri"
        ? "Python bridge is connected"
        : "Running on mock backend"
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
    <div className="mx-4 mb-1 rounded-lg border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)] px-3 py-2">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[12px] text-text-primary">{headline}</div>
          <div className="mt-0.5 text-[11px] text-text-tertiary">{detail}</div>
        </div>
        <button
          type="button"
          onClick={() => void handleRetry()}
          disabled={retrying || status.reconnecting}
          className="flex-shrink-0 rounded-md px-2.5 py-1 text-[12px] text-text-secondary transition-colors hover:bg-white/[0.04] hover:text-text-primary disabled:opacity-50"
        >
          {retrying || status.reconnecting ? "Retrying..." : "Retry"}
        </button>
      </div>
    </div>
  );
}
