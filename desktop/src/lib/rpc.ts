import type { BridgeStatus, StreamEvent, StreamListener } from "./types";

type RpcParams = Record<string, unknown>;

interface PendingRequest {
  resolve: (value: unknown) => void;
  reject: (error: Error) => void;
  timeoutId: number;
}

interface BridgeChild {
  write(data: string): Promise<void> | void;
  kill(): Promise<void> | void;
}

const listeners = new Set<StreamListener>();
const bridgeStatusListeners = new Set<(status: BridgeStatus) => void>();
const pendingRequests = new Map<number, PendingRequest>();

let started = false;
let startPromise: Promise<void> | null = null;
let child: BridgeChild | null = null;
let requestId = 0;
let lineBuffer = "";
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

function emit(event: StreamEvent) {
  for (const listener of listeners) {
    listener(event);
  }
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

function markBridgeConnected() {
  emitBridgeStatus({
    backendMode: "tauri",
    started: true,
    connected: true,
    reconnecting: false,
    lastError: null,
    lastAttemptAt: nowIso(),
    lastConnectedAt: nowIso(),
    fallbackReason: null,
  });
}

function markBridgeUnavailable(error: unknown) {
  emitBridgeStatus({
    backendMode: "offline",
    started: true,
    connected: false,
    reconnecting: false,
    lastError: normalizeErrorMessage(error, "Python bridge failed to start."),
    lastAttemptAt: nowIso(),
    fallbackReason: null,
  });
}

function markBridgeDisconnected(error: unknown) {
  emitBridgeStatus({
    backendMode: "offline",
    started: true,
    connected: false,
    reconnecting: false,
    lastError: normalizeErrorMessage(error, "Bridge connection dropped."),
    lastAttemptAt: nowIso(),
    fallbackReason: null,
  });
}

function clearPendingRequests(message: string) {
  for (const [id, pending] of pendingRequests) {
    globalThis.clearTimeout(pending.timeoutId);
    pending.reject(new Error(message));
    pendingRequests.delete(id);
  }
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
      emit(message.params as StreamEvent);
    }
  } catch {
    // Ignore non-JSON lines written by the bridge.
  }
}

async function rpcThroughBridge<T>(method: string, params: RpcParams): Promise<T> {
  if (!child) {
    throw new Error("Bridge process is not running");
  }

  const id = ++requestId;
  return await new Promise<T>((resolve, reject) => {
    const timeoutId = globalThis.setTimeout(() => {
      pendingRequests.delete(id);
      child = null;
      markBridgeDisconnected(`RPC timeout for ${method}`);
      reject(new Error(`RPC timeout for ${method}`));
    }, 30000);

    pendingRequests.set(id, {
      resolve: resolve as (value: unknown) => void,
      reject,
      timeoutId,
    });

    const payload = `${JSON.stringify({ jsonrpc: "2.0", method, params, id })}\n`;
    Promise.resolve(child!.write(payload)).catch((error: unknown) => {
      pendingRequests.delete(id);
      globalThis.clearTimeout(timeoutId);
      child = null;
      markBridgeDisconnected(error);
      reject(error instanceof Error ? error : new Error(String(error)));
    });
  });
}

async function launchBridge() {
  const shell = await import("@tauri-apps/plugin-shell");
  const command = shell.Command.sidecar("binaries/triad-bridge");

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
  await rpcThroughBridge("ping", {});
  markBridgeConnected();
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
  if (child) {
    return;
  }
  if (startPromise) {
    return startPromise;
  }

  started = true;
  emitBridgeStatus({
    started: true,
    reconnecting: false,
    lastError: null,
    lastAttemptAt: nowIso(),
  });

  startPromise = launchBridge().catch((error) => {
    clearPendingRequests("Bridge startup failed.");
    if (child) {
      void Promise.resolve(child.kill()).catch(() => undefined);
    }
    child = null;
    markBridgeUnavailable(error);
    throw error instanceof Error ? error : new Error(String(error));
  }).finally(() => {
    startPromise = null;
  });

  return startPromise;
}

export async function stopBridge() {
  clearPendingRequests("Bridge stopped.");
  if (child) {
    await Promise.resolve(child.kill()).catch(() => undefined);
    child = null;
  }
  started = false;
  lineBuffer = "";
  emitBridgeStatus({
    backendMode: "offline",
    started: false,
    connected: false,
    reconnecting: false,
    lastAttemptAt: bridgeStatus.lastAttemptAt,
  });
}

export async function reconnectBridge() {
  emitBridgeStatus({
    reconnecting: true,
    lastAttemptAt: nowIso(),
    lastError: null,
    fallbackReason: null,
  });
  await stopBridge();
  return startBridge();
}

export async function rpc<T = unknown>(method: string, params: RpcParams = {}) {
  if (!started || !child) {
    await startBridge();
  }

  if (!child) {
    throw new Error(bridgeStatus.lastError ?? "Python bridge is unavailable");
  }

  return rpcThroughBridge<T>(method, params);
}
