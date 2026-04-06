import { create } from "zustand";
import { parseStructuredDiffPatch } from "../lib/diff";
import { rpc } from "../lib/rpc";
import type {
  Attachment,
  DiffSnapshotTimelineItem,
  Message,
  ProviderId,
  Session,
  SessionCompareResult,
  SessionReplay,
  StreamingRun,
  TerminalHostMetadata,
  TimelineItem,
} from "../lib/types";
import { useProjectStore } from "./project-store";
import { useUiStore } from "./ui-store";

interface SessionState {
  sessions: Session[];
  activeSession: Session | null;
  timeline: TimelineItem[];
  streamingRuns: StreamingRun[];
  compareResult: SessionCompareResult | null;
  replay: SessionReplay | null;
  loading: boolean;
  loadSessions: (projectPath: string) => Promise<void>;
  createSession: (
    projectPath: string,
    mode: Session["mode"],
    options?: { provider?: ProviderId; title?: string }
  ) => Promise<Session>;
  forkSession: (sessionId: string, options?: { title?: string }) => Promise<Session>;
  exportSession: (
    sessionId: string,
    options?: { format?: "archive" | "markdown"; path?: string }
  ) => Promise<{ status: string; session_id: string; format: string; path: string }>;
  importSession: (
    path: string
  ) => Promise<{ session: Session; timeline: TimelineItem[]; project?: { path: string; name: string; git_root: string; last_opened_at?: string }; path: string }>;
  hydrateSession: (sessionId: string) => Promise<void>;
  loadCompare: (leftSessionId: string, rightSessionId: string) => Promise<SessionCompareResult>;
  loadReplay: (sessionId: string) => Promise<SessionReplay>;
  clearCompareReplay: () => void;
  setActiveSession: (session: Session | null) => void;
  addTimelineItem: (item: TimelineItem, options?: { count?: boolean }) => void;
  appendStreamingText: (runId: string | undefined, delta: string, provider?: Session["provider"], role?: string) => void;
  finalizeStreaming: (
    runId?: string,
    content?: string,
    provider?: Session["provider"],
    role?: string
  ) => void;
  clearStreamingText: (runId?: string) => void;
  setSessions: (sessions: Session[]) => void;
  updateSessionTerminalHost: (sessionId: string, terminalHost: TerminalHostMetadata | null) => void;
}

function makeMessageId(prefix: string) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID().slice(0, 8)}`;
  }
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function nowIso() {
  return new Date().toISOString();
}

function normalizeRunId(runId?: string) {
  return runId?.trim() || "__default__";
}

function shouldCountTimelineItem(item: TimelineItem) {
  return item.kind === "user_message" || item.kind === "assistant_message";
}

function attachTerminalHost<T extends TimelineItem | Message>(item: T, terminalHost?: TerminalHostMetadata | null): T {
  if (item.terminal_host || !terminalHost) {
    return item;
  }
  return {
    ...item,
    terminal_host: terminalHost,
  };
}

function messageToTimelineItem(message: Message, terminalHost?: TerminalHostMetadata | null): TimelineItem {
  if (message.role === "user") {
    return attachTerminalHost({
      id: message.id,
      kind: "user_message",
      session_id: message.session_id,
      ts: message.timestamp,
      provider: message.provider,
      text: message.content,
      attachments: message.attachments,
      terminal_host: message.terminal_host ?? terminalHost ?? undefined,
    }, message.terminal_host ?? terminalHost ?? undefined);
  }

  if (message.role === "assistant") {
    return attachTerminalHost({
      id: message.id,
      kind: "assistant_message",
      session_id: message.session_id,
      ts: message.timestamp,
      provider: message.provider,
      run_id: message.streaming ? message.id : undefined,
      role: message.agent_role,
      text: message.content,
      status: message.streaming ? "streaming" : "done",
      terminal_host: message.terminal_host ?? terminalHost ?? undefined,
    }, message.terminal_host ?? terminalHost ?? undefined);
  }

  return attachTerminalHost({
    id: message.id,
    kind: "system_notice",
    session_id: message.session_id,
    ts: message.timestamp,
    provider: message.provider,
    level: "info",
    body: message.content,
    terminal_host: message.terminal_host ?? terminalHost ?? undefined,
  }, message.terminal_host ?? terminalHost ?? undefined);
}

function resolveTimeline(
  payload: { timeline?: TimelineItem[]; messages?: Message[] },
  session?: Pick<Session, "terminal_host"> | null
) {
  const terminalHost = session?.terminal_host ?? null;
  if (Array.isArray(payload.timeline)) {
    return payload.timeline.map((item) => attachTerminalHost(item, item.terminal_host ?? terminalHost ?? undefined));
  }
  return Array.isArray(payload.messages)
    ? payload.messages.map((message) => messageToTimelineItem(message, terminalHost))
    : [];
}

function syncDiffPreview(timeline: TimelineItem[]) {
  const latestSnapshot = [...timeline]
    .reverse()
    .find((item): item is DiffSnapshotTimelineItem => item.kind === "diff_snapshot" && Boolean(item.patch.trim()));

  if (!latestSnapshot) {
    useUiStore.getState().clearDiffFiles();
    return;
  }

  useUiStore.getState().setDiffFiles(parseStructuredDiffPatch(latestSnapshot.patch), { open: false });
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessions: [],
  activeSession: null,
  timeline: [],
  streamingRuns: [],
  compareResult: null,
  replay: null,
  loading: false,
  loadSessions: async (projectPath: string) => {
    set({ loading: true });
    try {
      const result = await rpc<{ sessions: Session[] }>("session.list", { project_path: projectPath });
      set({ sessions: result.sessions, loading: false });
      const current = get().activeSession;
      const shouldSwitch = !current || (!!projectPath && current.project_path !== projectPath);
      if (shouldSwitch && result.sessions.length > 0) {
        await get().hydrateSession(result.sessions[0].id);
      } else if (shouldSwitch) {
        set({ activeSession: null, timeline: [], streamingRuns: [], compareResult: null, replay: null });
      }
    } catch {
      set({ loading: false });
    }
  },
  createSession: async (projectPath: string, mode: Session["mode"], options) => {
    const session = await rpc<Session>("session.create", {
      project_path: projectPath,
      mode,
      provider: options?.provider,
      title: options?.title,
    });
    useUiStore.getState().clearDiffFiles();
    set((state) => ({
      sessions: [session, ...state.sessions],
      activeSession: session,
      timeline: [],
      streamingRuns: [],
      compareResult: null,
      replay: null,
    }));
    return session;
  },
  forkSession: async (sessionId, options) => {
    const session = await rpc<Session>("session.fork", {
      session_id: sessionId,
      title: options?.title,
    });
    useUiStore.getState().clearDiffFiles();
    set((state) => ({
      sessions: [session, ...state.sessions],
      activeSession: session,
      timeline: [],
      streamingRuns: [],
      compareResult: null,
      replay: null,
    }));
    await get().hydrateSession(session.id);
    return session;
  },
  exportSession: async (sessionId, options) =>
    rpc<{ status: string; session_id: string; format: string; path: string }>("session.export", {
      session_id: sessionId,
      format: options?.format ?? "archive",
      path: options?.path,
    }),
  importSession: async (path) => {
    const result = await rpc<{
      session: Session;
      timeline?: TimelineItem[];
      messages?: Message[];
      project?: { path: string; name: string; git_root: string; last_opened_at?: string };
      path: string;
    }>("session.import", {
      path,
    });

    if (result.project) {
      const projectStore = useProjectStore.getState();
      projectStore.upsertProject(result.project);
      projectStore.setActiveProject(result.project);
    }

    set((state) => {
      const nextSessions = state.sessions.some((session) => session.id === result.session.id)
        ? state.sessions.map((session) => (session.id === result.session.id ? result.session : session))
        : [result.session, ...state.sessions];
      const timeline = resolveTimeline(result, result.session);
      syncDiffPreview(timeline);
      return {
        sessions: nextSessions,
        activeSession: result.session,
        timeline,
        streamingRuns: [],
        compareResult: null,
        replay: null,
      };
    });
    return { ...result, timeline: resolveTimeline(result, result.session) };
  },
  hydrateSession: async (sessionId: string) => {
    const result = await rpc<{ session: Session; timeline?: TimelineItem[]; messages?: Message[] }>("session.get", {
      session_id: sessionId,
    });
    const existingSessions = get().sessions;
    const nextSessions = existingSessions.some((session) => session.id === result.session.id)
      ? existingSessions.map((session) => (session.id === result.session.id ? result.session : session))
      : [result.session, ...existingSessions];
    const timeline = resolveTimeline(result, result.session);
    syncDiffPreview(timeline);
    set({
      activeSession: result.session,
      timeline,
      streamingRuns: [],
      compareResult: null,
      replay: null,
      sessions: nextSessions,
    });
  },
  loadCompare: async (leftSessionId, rightSessionId) => {
    const result = await rpc<SessionCompareResult>("session.compare", {
      left_session_id: leftSessionId,
      right_session_id: rightSessionId,
    });
    set({ compareResult: result });
    return result;
  },
  loadReplay: async (sessionId) => {
    const result = await rpc<SessionReplay>("session.replay", {
      session_id: sessionId,
    });
    set({ replay: result });
    return result;
  },
  clearCompareReplay: () => set({ compareResult: null, replay: null }),
  setActiveSession: (session) => {
    if (!session) {
      useUiStore.getState().clearDiffFiles();
      set({ activeSession: null, timeline: [], streamingRuns: [], compareResult: null, replay: null });
      return;
    }

    const cached = get().sessions.find((item) => item.id === session.id);
    useUiStore.getState().clearDiffFiles();
    set({
      activeSession: cached ?? session,
      timeline: [],
      streamingRuns: [],
      compareResult: null,
      replay: null,
    });
    void get().hydrateSession(session.id);
  },
  addTimelineItem: (item, options) => {
    const count = options?.count ?? shouldCountTimelineItem(item);
    set((state) => ({
      timeline: [...state.timeline, item],
      activeSession: state.activeSession
        ? {
            ...state.activeSession,
            updated_at: item.ts,
            message_count: count ? state.activeSession.message_count + 1 : state.activeSession.message_count,
          }
        : state.activeSession,
      sessions: state.sessions.map((session) =>
        session.id === item.session_id
          ? {
              ...session,
              updated_at: item.ts,
              message_count: count ? session.message_count + 1 : session.message_count,
            }
          : session
      ),
    }));
  },
  appendStreamingText: (runId, delta, provider, role) => {
    const normalizedRunId = normalizeRunId(runId);
    const timestamp = nowIso();
    set((state) => ({
      streamingRuns: state.streamingRuns.some((stream) => stream.run_id === normalizedRunId)
        ? state.streamingRuns.map((stream) =>
            stream.run_id === normalizedRunId
              ? {
                  ...stream,
                  text: `${stream.text}${delta}`,
                  provider: provider ?? stream.provider,
                  role: role ?? stream.role,
                  updated_at: timestamp,
                }
              : stream
          )
        : [
            ...state.streamingRuns,
            {
              run_id: normalizedRunId,
              text: delta,
              provider: provider ?? state.activeSession?.provider,
              role: role ?? undefined,
              started_at: timestamp,
              updated_at: timestamp,
            },
          ],
    }));
  },
  finalizeStreaming: (runId, content, provider, role) => {
    const activeSession = get().activeSession;
    const normalizedRunId = runId ? normalizeRunId(runId) : null;

    set((state) => {
      const targets = normalizedRunId
        ? state.streamingRuns.filter((stream) => stream.run_id === normalizedRunId)
        : state.streamingRuns;
      const fallbackTarget =
        !targets.length && content?.trim()
          ? [
              {
                run_id: normalizedRunId ?? normalizeRunId(undefined),
                text: "",
                provider: provider ?? state.activeSession?.provider,
                role: role ?? undefined,
                started_at: nowIso(),
                updated_at: nowIso(),
              } satisfies StreamingRun,
            ]
          : [];
      const streams = targets.length > 0 ? targets : fallbackTarget;
      const items: TimelineItem[] = [];
      if (activeSession) {
        for (const stream of streams) {
          const text = (
            content?.trim() && streams.length === 1 ? content : stream.text
          ).trim();
          if (!text) {
            continue;
          }
          items.push({
            id: makeMessageId("msg"),
            kind: "assistant_message",
            session_id: activeSession.id,
            ts: nowIso(),
            provider: provider ?? stream.provider ?? activeSession.provider,
            role: role ?? stream.role ?? undefined,
            text,
            status: "done",
          });
        }
      }

      const remainingRuns = normalizedRunId
        ? state.streamingRuns.filter((stream) => stream.run_id !== normalizedRunId)
        : [];

      if (!items.length) {
        return { streamingRuns: remainingRuns };
      }

      const latestTimestamp = items[items.length - 1]?.ts ?? nowIso();
      return {
        streamingRuns: remainingRuns,
        timeline: [...state.timeline, ...items],
        sessions: state.sessions.map((session) =>
          session.id === activeSession?.id
            ? {
                ...session,
                updated_at: latestTimestamp,
                message_count: session.message_count + items.length,
              }
            : session
        ),
        activeSession: activeSession
          ? {
              ...activeSession,
              updated_at: latestTimestamp,
              message_count: activeSession.message_count + items.length,
            }
          : activeSession,
      };
    });
  },
  clearStreamingText: (runId) =>
    set((state) => ({
      streamingRuns: runId
        ? state.streamingRuns.filter((stream) => stream.run_id !== normalizeRunId(runId))
        : [],
    })),
  setSessions: (sessions) => set({ sessions }),
  updateSessionTerminalHost: (sessionId, terminalHost) =>
    set((state) => ({
      activeSession:
        state.activeSession?.id === sessionId
          ? {
              ...state.activeSession,
              terminal_host: terminalHost,
            }
          : state.activeSession,
      sessions: state.sessions.map((session) =>
        session.id === sessionId
          ? {
              ...session,
              terminal_host: terminalHost,
            }
          : session
      ),
    })),
}));

export function appendUserMessage(
  sessionId: string,
  content: string,
  provider?: Session["provider"],
  attachments?: Attachment[]
) {
  const item: TimelineItem = {
    id: makeMessageId("msg"),
    kind: "user_message",
    session_id: sessionId,
    ts: new Date().toISOString(),
    provider,
    text: content,
    attachments,
  };
  useSessionStore.getState().addTimelineItem(item);
  return item;
}
