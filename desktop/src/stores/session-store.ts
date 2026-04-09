import { create } from "zustand";
import { rpc } from "../lib/rpc";
import type { DiffFile, Message, ProviderId, Session, StreamingRun } from "../lib/types";
import { useProjectStore } from "./project-store";
import { useUiStore } from "./ui-store";

interface SessionState {
  sessions: Session[];
  activeSession: Session | null;
  messages: Message[];
  streamingRuns: StreamingRun[];
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
  ) => Promise<{ session: Session; messages: Message[]; project?: { path: string; name: string; git_root: string; last_opened_at?: string }; path: string }>;
  hydrateSession: (sessionId: string) => Promise<void>;
  setActiveSession: (session: Session | null) => void;
  addMessage: (message: Message, options?: { count?: boolean }) => void;
  appendStreamingText: (runId: string | undefined, delta: string, provider?: Session["provider"], role?: string) => void;
  updateSessionStatus: (sessionId: string, status: Session["status"]) => void;
  finalizeStreaming: (
    runId?: string,
    content?: string,
    provider?: Session["provider"],
    role?: string
  ) => void;
  clearStreamingText: (runId?: string) => void;
  setSessions: (sessions: Session[]) => void;
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

function extractDiffFiles(messages: Message[]): DiffFile[] {
  const filesByPath = new Map<string, DiffFile>();
  for (const message of messages) {
    const diff = message.diff_snapshot;
    if (!diff) {
      continue;
    }
    filesByPath.set(diff.path, {
      path: diff.path,
      oldContent: diff.old_text,
      newContent: diff.new_text,
    });
  }
  return [...filesByPath.values()];
}

function normalizeRunId(runId?: string) {
  return runId?.trim() || "__default__";
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessions: [],
  activeSession: null,
  messages: [],
  streamingRuns: [],
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
        useUiStore.getState().clearDiffFiles();
        set({ activeSession: null, messages: [], streamingRuns: [] });
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
    set((state) => ({
      sessions: [session, ...state.sessions],
      activeSession: session,
      messages: [],
      streamingRuns: [],
    }));
    return session;
  },
  forkSession: async (sessionId, options) => {
    const session = await rpc<Session>("session.fork", {
      session_id: sessionId,
      title: options?.title,
    });
    set((state) => ({
      sessions: [session, ...state.sessions],
      activeSession: session,
      messages: [],
      streamingRuns: [],
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
      messages: Message[];
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
    useUiStore.getState().replaceDiffFiles(extractDiffFiles(result.messages));

    set((state) => {
      const nextSessions = state.sessions.some((session) => session.id === result.session.id)
        ? state.sessions.map((session) => (session.id === result.session.id ? result.session : session))
        : [result.session, ...state.sessions];
      return {
        sessions: nextSessions,
        activeSession: result.session,
        messages: result.messages,
        streamingRuns: [],
      };
    });
    return result;
  },
  hydrateSession: async (sessionId: string) => {
    const result = await rpc<{ session: Session; messages: Message[] }>("session.get", {
      session_id: sessionId,
    });
    useUiStore.getState().replaceDiffFiles(extractDiffFiles(result.messages));
    const existingSessions = get().sessions;
    const nextSessions = existingSessions.some((session) => session.id === result.session.id)
      ? existingSessions.map((session) => (session.id === result.session.id ? result.session : session))
      : [result.session, ...existingSessions];
    set({
      activeSession: result.session,
      messages: result.messages,
      streamingRuns: [],
      sessions: nextSessions,
    });
  },
  setActiveSession: (session) => {
    if (!session) {
      useUiStore.getState().clearDiffFiles();
      set({ activeSession: null, messages: [], streamingRuns: [] });
      return;
    }

    const cached = get().sessions.find((item) => item.id === session.id);
    set({
      activeSession: cached ?? session,
      messages: [],
      streamingRuns: [],
    });
    void get().hydrateSession(session.id);
  },
  addMessage: (message, options) => {
    const count = options?.count ?? true;
    set((state) => {
      const existingIndex = state.messages.findIndex((entry) => entry.id === message.id);
      const isNewMessage = existingIndex < 0;
      const nextMessages =
        existingIndex < 0
          ? [...state.messages, message]
          : state.messages.map((entry, index) => (index === existingIndex ? message : entry));
      const nextCountDelta = count && isNewMessage ? 1 : 0;

      return {
        messages: nextMessages,
        activeSession: state.activeSession
          ? {
              ...state.activeSession,
              updated_at: message.timestamp,
              message_count: state.activeSession.message_count + nextCountDelta,
            }
          : state.activeSession,
        sessions: state.sessions.map((session) =>
          session.id === message.session_id
            ? {
                ...session,
                updated_at: message.timestamp,
                message_count: session.message_count + nextCountDelta,
              }
            : session
        ),
      };
    });
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
  updateSessionStatus: (sessionId, status) =>
    set((state) => ({
      activeSession:
        state.activeSession?.id === sessionId
          ? {
              ...state.activeSession,
              status,
            }
          : state.activeSession,
      sessions: state.sessions.map((session) =>
        session.id === sessionId
          ? {
              ...session,
              status,
            }
          : session
      ),
    })),
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
      const messages: Message[] = [];
      if (activeSession) {
        for (const stream of streams) {
          const text = (
            content?.trim() && streams.length === 1 ? content : stream.text
          ).trim();
          if (!text) {
            continue;
          }
          messages.push({
            id: makeMessageId("msg"),
            session_id: activeSession.id,
            role: "assistant",
            content: text,
            provider: provider ?? stream.provider ?? activeSession.provider,
            agent_role: role ?? stream.role ?? undefined,
            timestamp: nowIso(),
          });
        }
      }

      const remainingRuns = normalizedRunId
        ? state.streamingRuns.filter((stream) => stream.run_id !== normalizedRunId)
        : [];

      if (!messages.length) {
        return { streamingRuns: remainingRuns };
      }

      const latestTimestamp = messages[messages.length - 1]?.timestamp ?? nowIso();
      return {
        streamingRuns: remainingRuns,
        messages: [...state.messages, ...messages],
        sessions: state.sessions.map((session) =>
          session.id === activeSession?.id
            ? {
                ...session,
                updated_at: latestTimestamp,
                message_count: session.message_count + messages.length,
              }
            : session
        ),
        activeSession: activeSession
          ? {
              ...activeSession,
              updated_at: latestTimestamp,
              message_count: activeSession.message_count + messages.length,
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
}));

export function appendUserMessage(sessionId: string, content: string, provider?: Session["provider"]) {
  const message: Message = {
    id: makeMessageId("msg"),
    session_id: sessionId,
    role: "user",
    content,
    provider,
    timestamp: new Date().toISOString(),
  };
  useSessionStore.getState().addMessage(message);
  return message;
}
