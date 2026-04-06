import { useCallback, useEffect, useMemo, useState } from "react";
import { rpc } from "../../lib/rpc";
import { useBridgeStore } from "../../stores/bridge-store";
import { Badge } from "./Badge";

type ProviderName = "claude" | "codex" | "gemini";

interface ProviderPoolEntry {
  name: string;
  available: boolean;
  requests_made: number;
  errors: number;
  cooldown_remaining_sec: number;
}

interface ActiveSessionEntry {
  id: string;
  mode: string;
  provider: string;
  project_path: string;
  state: string;
}

interface DiagnosticsPayload {
  version: string;
  python_version: string;
  triad_home: string;
  db_path: string;
  providers: Record<ProviderName, ProviderPoolEntry[]>;
  active_claude_sessions: string[];
  active_sessions: ActiveSessionEntry[];
  active_terminals: string[];
  hooks_socket: string;
}

interface Props {
  open: boolean;
}

const PROVIDERS: ProviderName[] = ["claude", "codex", "gemini"];

function providerLabel(provider: ProviderName) {
  if (provider === "codex") return "Codex";
  if (provider === "gemini") return "Gemini";
  return "Claude";
}

function compactPath(value: string) {
  if (!value) {
    return "n/a";
  }
  return value.length > 52 ? `...${value.slice(-49)}` : value;
}

function toneForAvailability(available: boolean) {
  return available ? "accent" : "subtle";
}

function SummaryStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-[14px] border border-border-light bg-black/20 px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.12em] text-text-tertiary">{label}</div>
      <div className="mt-1 text-[14px] font-medium text-text-primary">{value}</div>
    </div>
  );
}

export function DiagnosticsPanel({ open }: Props) {
  const [data, setData] = useState<DiagnosticsPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bridgeStatus = useBridgeStore((state) => state.status);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await rpc<DiagnosticsPayload>("diagnostics");
      setData(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Diagnostics unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open && !data && !loading) {
      void load();
    }
  }, [data, load, loading, open]);

  const providerStats = useMemo(() => {
    if (!data) {
      return [];
    }

    return PROVIDERS.map((provider) => {
      const entries = data.providers[provider] ?? [];
      const available = entries.filter((entry) => entry.available).length;
      const cooling = entries.filter((entry) => entry.cooldown_remaining_sec > 0).length;
      return {
        provider,
        total: entries.length,
        available,
        cooling,
      };
    });
  }, [data]);

  if (!open) {
    return null;
  }

  return (
    <div className="codex-message-enter-subtle mb-2 rounded-[18px] border border-border-light bg-[linear-gradient(180deg,rgba(255,255,255,0.04),transparent_30%),rgba(0,0,0,0.22)] p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.12em] text-text-tertiary">Diagnostics</div>
          <div className="mt-1 text-[12px] text-text-secondary">Bridge runtime, provider pools and active sessions.</div>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-md border border-border-light px-2 py-1 text-[11px] text-text-tertiary transition-colors hover:border-border-default hover:text-text-primary"
        >
          Refresh
        </button>
      </div>

      {loading && !data ? (
        <div className="mt-3 rounded-[14px] border border-border-light bg-black/20 px-3 py-2 text-[12px] text-text-tertiary">
          Loading diagnostics...
        </div>
      ) : null}

      {error ? (
        <div className="mt-3 rounded-[14px] border border-[rgba(250,66,62,0.22)] bg-[rgba(250,66,62,0.08)] px-3 py-2 text-[12px] text-text-error">
          {error}
        </div>
      ) : null}

      {data ? (
        <>
          <div className="mt-3 grid grid-cols-3 gap-2">
            <SummaryStat label="Sessions" value={data.active_sessions.length} />
            <SummaryStat label="Claude PTY" value={data.active_claude_sessions.length} />
            <SummaryStat label="Terminals" value={data.active_terminals.length} />
          </div>

          <div className="mt-3 flex flex-wrap gap-1.5">
            <Badge tone="subtle">{`v${data.version}`}</Badge>
            <Badge tone="subtle" title={data.python_version}>
              {data.python_version.split(" ")[0]}
            </Badge>
            <Badge tone={data.active_sessions.length > 0 ? "accent" : "neutral"}>
              {data.active_sessions.length > 0 ? "Bridge live" : "Bridge idle"}
            </Badge>
            <Badge
              tone={bridgeStatus.reconnecting ? "subtle" : bridgeStatus.connected ? "accent" : "neutral"}
              title={bridgeStatus.lastError ?? bridgeStatus.fallbackReason ?? undefined}
            >
              {bridgeStatus.started
                ? bridgeStatus.reconnecting
                  ? "Bridge retrying"
                  : bridgeStatus.connected
                    ? "Bridge live"
                    : bridgeStatus.backendMode === "mock"
                      ? "Bridge mock"
                      : "Bridge offline"
                : "Bridge starting"}
            </Badge>
          </div>

          <div className="mt-3 space-y-2">
            {providerStats.map((provider) => (
              <div
                key={provider.provider}
                className="rounded-[14px] border border-border-light bg-black/20 px-3 py-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[12px] font-medium text-text-primary">{providerLabel(provider.provider)}</span>
                  <Badge tone={toneForAvailability(provider.available > 0)}>
                    {provider.total > 0 ? `${provider.available}/${provider.total} available` : "No accounts"}
                  </Badge>
                </div>
                <div className="mt-1 text-[11px] text-text-tertiary">
                  {provider.cooling > 0 ? `${provider.cooling} cooling down` : "No cooldowns"}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-3 space-y-2">
            <div className="text-[11px] uppercase tracking-[0.12em] text-text-tertiary">Active sessions</div>
            {data.active_sessions.length === 0 ? (
              <div className="rounded-[14px] border border-border-light bg-black/20 px-3 py-2 text-[12px] text-text-tertiary">
                No active sessions.
              </div>
            ) : (
              data.active_sessions.slice(0, 4).map((session) => (
                <div
                  key={session.id}
                  className="rounded-[14px] border border-border-light bg-black/20 px-3 py-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-[12px] font-medium text-text-primary">{session.id}</span>
                    <Badge tone="subtle" className="capitalize">
                      {session.state}
                    </Badge>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    <Badge tone="neutral" className="capitalize">
                      {session.mode}
                    </Badge>
                    <Badge tone="neutral">{session.provider}</Badge>
                  </div>
                  <div className="mt-1 truncate font-mono text-[11px] text-text-tertiary" title={session.project_path}>
                    {compactPath(session.project_path)}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="mt-3 space-y-2 rounded-[14px] border border-border-light bg-black/20 px-3 py-2">
            <div className="text-[11px] uppercase tracking-[0.12em] text-text-tertiary">Paths</div>
            <div className="text-[11px] text-text-tertiary">
              <span className="mr-2 text-text-secondary">DB</span>
              <span className="font-mono" title={data.db_path}>
                {compactPath(data.db_path)}
              </span>
            </div>
            <div className="text-[11px] text-text-tertiary">
              <span className="mr-2 text-text-secondary">Home</span>
              <span className="font-mono" title={data.triad_home}>
                {compactPath(data.triad_home)}
              </span>
            </div>
            <div className="text-[11px] text-text-tertiary">
              <span className="mr-2 text-text-secondary">Hooks</span>
              <span className="font-mono" title={data.hooks_socket}>
                {compactPath(data.hooks_socket)}
              </span>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
