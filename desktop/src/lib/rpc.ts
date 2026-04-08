import type { BridgeStatus, ProviderId, StreamEvent, StreamListener } from "./types";

type RpcParams = Record<string, unknown>;
type BackendMode = "tauri" | "offline";

interface PendingRequest {
  resolve: (value: unknown) => void;
  reject: (error: Error) => void;
  timeoutId: number;
}

interface BridgeChild {
  write(data: string): Promise<void> | void;
  kill(): Promise<void> | void;
}

interface TestBridge {
  start: () => Promise<void> | void;
  stop?: () => Promise<void> | void;
  request: <T>(method: string, params: RpcParams) => Promise<T>;
  subscribe: (listener: StreamListener) => () => void;
}

declare global {
  interface Window {
    __TRIAD_E2E__?: boolean;
    __TRIAD_TEST_BRIDGE__?: TestBridge;
  }
}

const EVENT_TYPE_ALIASES: Record<string, StreamEvent["type"]> = {
  message_delta: "text_delta",
  message_completed: "message_finalized",
  tool_started: "tool_use",
  tool_finished: "tool_result",
  completed: "run_completed",
  error: "run_failed",
  status: "system",
};

const listeners = new Set<StreamListener>();
const bridgeStatusListeners = new Set<(status: BridgeStatus) => void>();
const pendingRequests = new Map<number, PendingRequest>();

let started = false;
let backendMode: BackendMode = "offline";
let child: BridgeChild | null = null;
let requestId = 0;
let lineBuffer = "";
let testBridgeUnsubscribe: (() => void) | null = null;
let bridgeStatus: BridgeStatus = {
  backendMode: "offline",
  started: false,
  connected: false,
  reconnecting: false,
  lastError: null,
  lastAttemptAt: null,
  lastConnectedAt: null,
  fallbackReason: null,
};

function nowIso() {
  return new Date().toISOString();
}

function cloneBridgeStatus(): BridgeStatus {
  return { ...bridgeStatus };
}

function emitBridgeStatus(next: Partial<BridgeStatus>) {
  bridgeStatus = { ...bridgeStatus, ...next };
  for (const listener of bridgeStatusListeners) {
    listener(cloneBridgeStatus());
  }
}

function normalizeErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  if (typeof error === "string" && error.trim()) {
    return error;
  }
  return fallback;
}

function markBridgeConnected(mode: BackendMode) {
  emitBridgeStatus({
    backendMode: mode,
    started: true,
    connected: true,
    reconnecting: false,
    lastError: null,
    lastAttemptAt: nowIso(),
    lastConnectedAt: nowIso(),
    fallbackReason: null,
  });
}

function markBridgeOffline(error: unknown, fallbackReason: string) {
  emitBridgeStatus({
    backendMode: "offline",
    started: true,
    connected: false,
    reconnecting: false,
    lastError: normalizeErrorMessage(error, fallbackReason),
    lastAttemptAt: nowIso(),
    fallbackReason,
  });
}

function emit(event: StreamEvent) {
  for (const listener of listeners) {
    listener(event);
  }
}

function rejectPendingRequests(reason: string) {
  for (const [id, pending] of pendingRequests.entries()) {
    pendingRequests.delete(id);
    globalThis.clearTimeout(pending.timeoutId);
    pending.reject(new Error(reason));
  }
}

function normalizeProvider(value: unknown): ProviderId | undefined {
  if (value === "claude" || value === "codex" || value === "gemini") {
    return value;
  }
  return undefined;
}

function normalizeChunk(data: unknown): string {
  if (typeof data === "string") {
    return data;
  }
  if (data instanceof Uint8Array) {
    return new TextDecoder().decode(data);
  }
  return String(data ?? "");
}

function normalizeEventType(value: unknown): StreamEvent["type"] | null {
  const raw = String(value ?? "system").trim() || "system";
  const canonical = EVENT_TYPE_ALIASES[raw] ?? raw;
  switch (canonical) {
    case "text_delta":
    case "message_finalized":
    case "tool_use":
    case "tool_result":
    case "review_finding":
    case "diff_snapshot":
    case "stderr":
    case "run_completed":
    case "run_failed":
    case "terminal_output":
    case "system":
      return canonical;
    default:
      return null;
  }
}

function normalizeEvent(raw: unknown): StreamEvent | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const event = raw as Record<string, unknown>;
  const type = normalizeEventType(event.type);
  const sessionId = String(event.session_id ?? event.sessionId ?? "").trim();
  if (!type || !sessionId) {
    return null;
  }

  const base = {
    schema_version: 1 as const,
    session_id: sessionId,
    run_id: event.run_id ? String(event.run_id) : undefined,
    provider: normalizeProvider(event.provider),
    role: event.role ? String(event.role) : undefined,
    source: event.source ? String(event.source) : undefined,
    timestamp: event.timestamp ? String(event.timestamp) : undefined,
    authoritative: event.authoritative === true,
    message_id: event.message_id ? String(event.message_id) : undefined,
  };

  switch (type) {
    case "text_delta":
      return { ...base, type, delta: String(event.delta ?? event.content ?? "") };
    case "message_finalized":
      return { ...base, type, content: String(event.content ?? "") };
    case "tool_use":
      return {
        ...base,
        type,
        tool: String(event.tool ?? "tool"),
        input: event.input,
        output: event.output,
        status: event.status === "completed" || event.status === "failed" ? event.status : "running",
      };
    case "tool_result":
      return {
        ...base,
        type,
        tool: String(event.tool ?? "tool"),
        input: event.input,
        output: event.output,
        status: event.status === "running" || event.status === "failed" ? event.status : "completed",
        success: typeof event.success === "boolean" ? event.success : undefined,
      };
    case "review_finding":
      return {
        ...base,
        type,
        severity:
          event.severity === "P0" || event.severity === "P1" || event.severity === "P3" ? event.severity : "P2",
        file: String(event.file ?? ""),
        title: String(event.title ?? "Finding"),
        explanation: String(event.explanation ?? event.content ?? ""),
        line: typeof event.line === "number" ? event.line : undefined,
        line_range: event.line_range ? String(event.line_range) : undefined,
      };
    case "diff_snapshot":
      return {
        ...base,
        type,
        path: String(event.path ?? event.file_path ?? ""),
        old_text: String(event.old_text ?? event.old_string ?? event.oldText ?? ""),
        new_text: String(event.new_text ?? event.new_string ?? event.newText ?? event.content ?? ""),
      };
    case "stderr":
      return { ...base, type, data: String(event.data ?? event.error ?? "") };
    case "run_completed":
      return { ...base, type };
    case "run_failed":
      return { ...base, type, error: String(event.error ?? event.content ?? "Run failed") };
    case "terminal_output":
      return {
        ...base,
        type,
        terminal_id: String(event.terminal_id ?? ""),
        data: String(event.data ?? ""),
      };
    case "system":
      return { ...base, type, content: String(event.content ?? event.message ?? "") };
  }
}

function handleBridgeLine(line: string) {
  if (!line.trim()) {
    return;
  }

  try {
    const message = JSON.parse(line) as Record<string, unknown>;
    if ("id" in message && message.id != null) {
      const id = Number(message.id);
      const pending = pendingRequests.get(id);
      if (!pending) {
        return;
      }
      pendingRequests.delete(id);
      globalThis.clearTimeout(pending.timeoutId);
      if (message.error && typeof message.error === "object") {
        const payload = message.error as { message?: string };
        pending.reject(new Error(payload.message ?? "RPC error"));
        return;
      }
      pending.resolve(message.result);
      return;
    }

    if (typeof message.method === "string" && message.params && typeof message.params === "object") {
      const event = normalizeEvent(message.params);
      if (event) {
        emit(event);
      }
    }
  } catch {
    // Ignore non-JSON lines written by the bridge.
  }
}

function getTestBridge(): TestBridge | undefined {
  if (typeof window === "undefined" || window.__TRIAD_E2E__ !== true) {
    return undefined;
  }
  return window.__TRIAD_TEST_BRIDGE__;
}

async function tryStartInjectedBridge(): Promise<boolean> {
  const testBridge = getTestBridge();
  if (!testBridge) {
    return false;
  }
  await Promise.resolve(testBridge.start());
  testBridgeUnsubscribe?.();
  testBridgeUnsubscribe = testBridge.subscribe((event) => {
    const normalized = normalizeEvent(event);
    if (normalized) {
      emit(normalized);
    }
  });
  backendMode = "tauri";
  markBridgeConnected("tauri");
  return true;
}

async function tryStartTauriBridge(): Promise<boolean> {
  try {
    const shell = await import("@tauri-apps/plugin-shell");
    const command = shell.Command.sidecar("binaries/triad-bridge");

    command.on("close", ({ code, signal }) => {
      rejectPendingRequests(`Bridge exited (code=${String(code)}, signal=${String(signal)})`);
      child = null;
      backendMode = "offline";
      markBridgeOffline(
        `Bridge exited (code=${String(code)}, signal=${String(signal)})`,
        "The Python bridge exited and the desktop returned to recovery mode."
      );
    });

    command.on("error", (error) => {
      rejectPendingRequests(normalizeErrorMessage(error, "The Python bridge reported a process-level error."));
      child = null;
      backendMode = "offline";
      markBridgeOffline(error, "The Python bridge reported a process-level error.");
    });

    command.stdout.on("data", (chunk: unknown) => {
      lineBuffer += normalizeChunk(chunk);
      const lines = lineBuffer.split("\n");
      lineBuffer = lines.pop() ?? "";
      for (const line of lines) {
        handleBridgeLine(line);
      }
    });

    command.stderr.on("data", (chunk: unknown) => {
      console.warn("[triad-bridge]", normalizeChunk(chunk));
    });

    child = (await command.spawn()) as unknown as BridgeChild;
    backendMode = "tauri";
    markBridgeConnected("tauri");
    return true;
  } catch (error) {
    markBridgeOffline(error, "Desktop bridge is unavailable until the sidecar can be started again.");
    return false;
  }
}

async function rpcThroughBridge<T>(method: string, params: RpcParams): Promise<T> {
  if (!child) {
    throw new Error("Bridge process is not running");
  }

  const id = ++requestId;
  return await new Promise<T>((resolve, reject) => {
    const bridgeChild = child;
    if (!bridgeChild) {
      reject(new Error("Bridge process is not running"));
      return;
    }
    const timeoutId = globalThis.setTimeout(() => {
      pendingRequests.delete(id);
      void Promise.resolve(bridgeChild.kill()).catch(() => undefined);
      child = null;
      backendMode = "offline";
      started = true;
      markBridgeOffline(`RPC timeout for ${method}`, "The bridge stopped responding to JSON-RPC requests.");
      reject(new Error(`RPC timeout for ${method}`));
    }, 30000);

    pendingRequests.set(id, {
      resolve: resolve as (value: unknown) => void,
      reject,
      timeoutId,
    });
    const payload = `${JSON.stringify({ jsonrpc: "2.0", method, params, id })}\n`;

    Promise.resolve(bridgeChild.write(payload)).catch((error: unknown) => {
      pendingRequests.delete(id);
      globalThis.clearTimeout(timeoutId);
      void Promise.resolve(bridgeChild.kill()).catch(() => undefined);
      child = null;
      backendMode = "offline";
      started = true;
      markBridgeOffline(error, "The bridge write channel failed.");
      reject(error instanceof Error ? error : new Error(String(error)));
    });
  });
}

export function onEvent(listener: StreamListener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function onBridgeStatus(listener: (status: BridgeStatus) => void) {
  bridgeStatusListeners.add(listener);
  listener(cloneBridgeStatus());
  return () => {
    bridgeStatusListeners.delete(listener);
  };
}

export function getBridgeStatus() {
  return cloneBridgeStatus();
}

export async function startBridge() {
  if (started) {
    return;
  }

  started = true;
  emitBridgeStatus({
    started: true,
    reconnecting: false,
    lastAttemptAt: nowIso(),
  });

  const testReady = await tryStartInjectedBridge();
  if (testReady) {
    return;
  }

  const tauriReady = await tryStartTauriBridge();
  if (!tauriReady) {
    backendMode = "offline";
  }
}

export async function stopBridge() {
  testBridgeUnsubscribe?.();
  testBridgeUnsubscribe = null;

  const testBridge = getTestBridge();
  if (testBridge?.stop) {
    await Promise.resolve(testBridge.stop()).catch(() => undefined);
  }

  if (child) {
    await Promise.resolve(child.kill()).catch(() => undefined);
    child = null;
  }

  for (const pending of pendingRequests.values()) {
    globalThis.clearTimeout(pending.timeoutId);
    pending.reject(new Error("Bridge stopped"));
  }
  pendingRequests.clear();
  backendMode = "offline";
  started = false;
}

export async function reconnectBridge() {
  emitBridgeStatus({
    reconnecting: true,
    lastAttemptAt: nowIso(),
    lastError: null,
    fallbackReason: null,
  });
  await stopBridge();
  await startBridge();
}

export async function rpc<T = unknown>(method: string, params: RpcParams = {}) {
  if (!started) {
    await startBridge();
  }

  const testBridge = getTestBridge();
  if (testBridge) {
    return await testBridge.request<T>(method, params);
  }

  if (backendMode !== "tauri") {
    throw new Error(bridgeStatus.lastError ?? "Bridge is unavailable");
  }

  return await rpcThroughBridge<T>(method, params);
}
