import type {
  BridgeStatus,
  Message,
  ModeId,
  Project,
  ProviderId,
  Session,
  StreamEvent,
  StreamListener,
} from "./types";

type RpcParams = Record<string, unknown>;
type BackendMode = "tauri" | "mock";

interface BackendState {
  projects: Project[];
  sessions: Session[];
  messagesBySession: Record<string, Message[]>;
  exportsByPath: Record<string, string>;
}

interface PendingRequest {
  resolve: (value: unknown) => void;
  reject: (error: Error) => void;
  timeoutId: number;
}

interface BridgeChild {
  write(data: string): Promise<void> | void;
  kill(): Promise<void> | void;
}

const STORAGE_KEY = "triad.desktop.mock-state.v1";
const listeners = new Set<StreamListener>();
const bridgeStatusListeners = new Set<(status: BridgeStatus) => void>();
const pendingRequests = new Map<number, PendingRequest>();

let started = false;
let backendMode: BackendMode = "mock";
let child: BridgeChild | null = null;
let requestId = 0;
let lineBuffer = "";
let state: BackendState = createSeedState();
let bridgeStatus: BridgeStatus = {
  backendMode: "mock",
  started: false,
  connected: false,
  reconnecting: false,
  lastError: null,
  lastAttemptAt: null,
  lastConnectedAt: null,
  fallbackReason: null,
};
const mockTerminals = new Set<string>();

function nowIso() {
  return new Date().toISOString();
}

function uid(prefix: string) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID().slice(0, 8)}`;
  }
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function seededMessage(sessionId: string, role: Message["role"], content: string, provider?: ProviderId): Message {
  return {
    id: uid("msg"),
    session_id: sessionId,
    role,
    content,
    provider,
    timestamp: nowIso(),
  };
}

function hoursAgo(hours: number) {
  return new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
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

function markBridgeFallback(error: unknown, fallbackReason: string) {
  emitBridgeStatus({
    backendMode: "mock",
    started: true,
    connected: false,
    reconnecting: false,
    lastError: normalizeErrorMessage(error, fallbackReason),
    lastAttemptAt: nowIso(),
    fallbackReason,
  });
}

function markBridgeDisconnected(error: unknown) {
  emitBridgeStatus({
    backendMode: "mock",
    connected: false,
    reconnecting: false,
    lastError: normalizeErrorMessage(error, "Bridge connection dropped."),
    lastAttemptAt: nowIso(),
    fallbackReason: "Using mock backend until you retry.",
  });
}

function createSeedState(): BackendState {
  const projects: Project[] = [
    { path: "/Users/martin/FounderOS", name: "FounderOS", git_root: "/Users/martin/FounderOS", last_opened_at: nowIso() },
    { path: "/Users/martin/mymacagent", name: "mymacagent", git_root: "/Users/martin/mymacagent", last_opened_at: nowIso() },
    { path: "/Users/martin/autopilot", name: "autopilot", git_root: "/Users/martin/autopilot", last_opened_at: nowIso() },
    { path: "/Users/martin/multi-agent", name: "multi-agent", git_root: "/Users/martin/multi-agent", last_opened_at: nowIso() },
  ];

  const sessions: Session[] = [
    {
      id: "s_founder_fix",
      project_path: projects[0].path,
      title: "Исправить замечания Advisor",
      mode: "critic",
      status: "active",
      created_at: hoursAgo(8),
      updated_at: hoursAgo(1),
      message_count: 18,
      provider: "claude",
    },
    {
      id: "s_founder_rebuild",
      project_path: projects[0].path,
      title: "Исправить ошибки перед релизом",
      mode: "solo",
      status: "paused",
      created_at: hoursAgo(24),
      updated_at: hoursAgo(3),
      message_count: 11,
      provider: "claude",
    },
    {
      id: "s_myagent_audit",
      project_path: projects[1].path,
      title: "Слушай, я эксперименты провожу",
      mode: "critic",
      status: "active",
      created_at: hoursAgo(10),
      updated_at: hoursAgo(2),
      message_count: 7,
      provider: "codex",
    },
    {
      id: "s_autopilot_fast",
      project_path: projects[2].path,
      title: "Привет! Мы тут работаем над...",
      mode: "delegate",
      status: "completed",
      created_at: hoursAgo(30),
      updated_at: hoursAgo(5),
      message_count: 4,
      provider: "gemini",
    },
    {
      id: "s_multi_agent_help",
      project_path: projects[3].path,
      title: "Привет. Мы работаем над...",
      mode: "brainstorm",
      status: "active",
      created_at: hoursAgo(6),
      updated_at: hoursAgo(1),
      message_count: 6,
      provider: "claude",
    },
  ];

  const messagesBySession: Record<string, Message[]> = {
    s_founder_fix: [
      seededMessage("s_founder_fix", "user", "Проверь, почему меню не появляется в status item."),
      seededMessage(
        "s_founder_fix",
        "assistant",
        "Я сначала проверю UI-слой и рутинг окна. Потом сузим причину до AppKit / menu bar integration и уберём лишние зависимости.",
        "claude"
      ),
    ],
    s_myagent_audit: [
      seededMessage("s_myagent_audit", "user", "Покажи мне безопасный план исправления."),
      seededMessage(
        "s_myagent_audit",
        "assistant",
        "Сначала сниму точку входа, затем проверю состояние окна, после этого сверю точки привязки меню и окно поповера.",
        "codex"
      ),
    ],
    s_multi_agent_help: [
      seededMessage("s_multi_agent_help", "user", "Сделай красивый desktop shell в стиле Codex."),
      seededMessage(
        "s_multi_agent_help",
        "assistant",
        "Соберу темную структуру, шапку, сайдбар, транскрипт и composer, а потом доведу детализацию до референса.",
        "claude"
      ),
    ],
  };

  return { projects, sessions, messagesBySession, exportsByPath: {} };
}

function persistState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Browser-only convenience fallback.
  }
}

function hydrateState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      persistState();
      return;
    }
    const parsed = JSON.parse(raw) as BackendState;
    if (parsed && Array.isArray(parsed.projects) && Array.isArray(parsed.sessions) && parsed.messagesBySession) {
      state = {
        ...parsed,
        exportsByPath: parsed.exportsByPath && typeof parsed.exportsByPath === "object" ? parsed.exportsByPath : {},
      };
      return;
    }
  } catch {
    // Fall back to the seeded mock state.
  }
  persistState();
}

function cloneSession(session: Session): Session {
  return { ...session };
}

function cloneProject(project: Project): Project {
  return { ...project };
}

function cloneMessages(messages: Message[]): Message[] {
  return messages.map((message) => ({
    ...message,
    tool_calls: message.tool_calls?.map((tool) => ({ ...tool })),
  }));
}

function forkSessionInMock(sessionId: string, title?: string) {
  const source = ensureSession(sessionId);
  if (!source) {
    throw new Error(`Unknown session: ${sessionId}`);
  }

  const sourceMessages = cloneMessages(state.messagesBySession[sessionId] ?? []);
  const forkedSession: Session = {
    ...cloneSession(source),
    id: uid("session"),
    title: title || (source.title ? `Fork of ${source.title}` : "Forked session"),
    status: "active",
    created_at: nowIso(),
    updated_at: nowIso(),
    message_count: sourceMessages.length,
  };

  state.sessions = [forkedSession, ...state.sessions];
  state.messagesBySession[forkedSession.id] = sourceMessages.map((message) => ({
    ...message,
    id: uid("msg"),
    session_id: forkedSession.id,
    streaming: false,
    tool_calls: message.tool_calls?.map((tool) => ({ ...tool })),
  }));
  persistState();
  return forkedSession;
}

function slugify(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
}

function buildMockExportPath(session: Session, format: "archive" | "markdown") {
  const stamp = nowIso().replace(/[:.]/g, "-");
  const extension = format === "archive" ? "json" : "md";
  const slug = slugify(session.title) || session.id;
  return `/mock-exports/${stamp}-${slug}-${session.id}.${extension}`;
}

function buildMockProject(projectPath: string): Project {
  const existing = state.projects.find((project) => project.path === projectPath);
  if (existing) {
    return cloneProject(existing);
  }
  return {
    path: projectPath,
    name: projectPath.split("/").filter(Boolean).at(-1) ?? "Project",
    git_root: projectPath,
    last_opened_at: nowIso(),
  };
}

function messagesToMockEvents(messages: Message[]) {
  return messages.map((message, index) => {
    const eventType =
      message.role === "user" ? "user.message" : message.role === "assistant" ? "message_finalized" : "system";
    return {
      id: index + 1,
      seq: index + 1,
      type: eventType,
      provider: message.provider,
      role: message.role === "assistant" ? message.agent_role : message.role === "user" ? "user" : undefined,
      agent: message.provider,
      run_id: undefined,
      content: message.content,
      artifact_id: undefined,
      timestamp: message.timestamp,
      ts: message.timestamp,
      data: { content: message.content },
    };
  });
}

function buildMockArchive(sessionId: string) {
  const session = ensureSession(sessionId);
  if (!session) {
    throw new Error(`Unknown session: ${sessionId}`);
  }
  const messages = cloneMessages(state.messagesBySession[sessionId] ?? []);
  const project = buildMockProject(session.project_path);
  return {
    type: "triad_desktop_session_archive",
    version: 1,
    exported_at: nowIso(),
    session: {
      ...cloneSession(session),
      source_session_id: session.id,
      task: session.title,
      config: {
        project_path: session.project_path,
        provider: session.provider ?? "claude",
        title: session.title,
      },
    },
    project,
    messages,
    events: messagesToMockEvents(messages),
  };
}

function buildMockMarkdown(sessionId: string) {
  const archive = buildMockArchive(sessionId);
  const lines = [
    `# ${archive.session.title}`,
    "",
    `- Session ID: ${archive.session.source_session_id}`,
    `- Mode: ${archive.session.mode}`,
    `- Provider: ${archive.session.provider ?? "claude"}`,
    `- Status: ${archive.session.status}`,
    `- Project: ${archive.session.project_path}`,
    `- Exported At: ${archive.exported_at}`,
    "",
    "## Transcript",
    "",
  ];

  for (const message of archive.messages) {
    const badges = [message.provider, message.agent_role].filter(Boolean).join(", ");
    const heading = badges ? `${message.role} (${badges})` : message.role;
    lines.push(`### ${heading}`);
    lines.push("");
    lines.push(message.content || "_Empty message_");
    lines.push("");
  }

  return `${lines.join("\n")}\n`;
}

function messagesFromArchivePayload(archive: Record<string, unknown>, sessionId: string): Message[] {
  const rawMessages = Array.isArray(archive.messages) ? archive.messages : [];
  if (rawMessages.length > 0) {
    return rawMessages
      .filter((item): item is Record<string, unknown> => !!item && typeof item === "object")
      .map((message) => ({
        id: uid("msg"),
        session_id: sessionId,
        role: String(message.role ?? "system") as Message["role"],
        content: String(message.content ?? ""),
        provider: message.provider ? (String(message.provider) as ProviderId) : undefined,
        agent_role: message.agent_role ? String(message.agent_role) : undefined,
        timestamp: String(message.timestamp ?? nowIso()),
        streaming: false,
      }));
  }

  const rawEvents = Array.isArray(archive.events) ? archive.events : [];
  const messages: Message[] = [];
  for (const event of rawEvents.filter((item): item is Record<string, unknown> => !!item && typeof item === "object")) {
    const eventType = String(event.type ?? "");
    const data = event.data && typeof event.data === "object" ? (event.data as Record<string, unknown>) : {};
    const content = String(data.content ?? event.content ?? "");
    if (!content) {
      continue;
    }

    if (eventType === "user.message") {
      messages.push({
        id: uid("msg"),
        session_id: sessionId,
        role: "user",
        content,
        provider: event.provider ? (String(event.provider) as ProviderId) : undefined,
        timestamp: String(event.timestamp ?? nowIso()),
      });
      continue;
    }

    if (eventType === "message_finalized") {
      messages.push({
        id: uid("msg"),
        session_id: sessionId,
        role: "assistant",
        content,
        provider: event.provider ? (String(event.provider) as ProviderId) : undefined,
        agent_role: event.role ? String(event.role) : undefined,
        timestamp: String(event.timestamp ?? nowIso()),
      });
      continue;
    }

    if (eventType === "system" || eventType === "run_failed") {
      messages.push({
        id: uid("msg"),
        session_id: sessionId,
        role: "system",
        content,
        provider: event.provider ? (String(event.provider) as ProviderId) : undefined,
        timestamp: String(event.timestamp ?? nowIso()),
      });
    }
  }
  return messages;
}

function importSessionInMock(path: string, archive: Record<string, unknown>) {
  const sessionPayload =
    archive.session && typeof archive.session === "object" ? (archive.session as Record<string, unknown>) : null;
  if (!sessionPayload) {
    throw new Error("Invalid session archive: missing session payload");
  }

  const projectPayload =
    archive.project && typeof archive.project === "object" ? (archive.project as Record<string, unknown>) : {};
  const projectPath = String(projectPayload.path ?? sessionPayload.project_path ?? "/mock-import");
  const provider = (String(sessionPayload.provider ?? "claude") as ProviderId) || "claude";
  const mode = (String(sessionPayload.mode ?? "solo") as ModeId) || "solo";
  const originalStatus = String(sessionPayload.status ?? "completed");
  const importedStatus =
    originalStatus === "active" || originalStatus === "running"
      ? "paused"
      : ((originalStatus as Session["status"]) ?? "completed");
  const project: Project = {
    path: projectPath,
    name: String(projectPayload.name ?? projectPath.split("/").filter(Boolean).at(-1) ?? "Imported Project"),
    git_root: String(projectPayload.git_root ?? projectPath),
    last_opened_at: nowIso(),
  };

  const sessionId = uid("session");
  const messages = messagesFromArchivePayload(archive, sessionId);
  const session: Session = {
    id: sessionId,
    project_path: project.path,
    title: String(sessionPayload.title ?? sessionPayload.task ?? "Imported session"),
    mode,
    status: importedStatus,
    created_at: String(sessionPayload.created_at ?? nowIso()),
    updated_at: String(sessionPayload.updated_at ?? nowIso()),
    message_count: messages.filter((message) => message.role === "user" || message.role === "assistant").length,
    provider,
  };

  const existingProjectIndex = state.projects.findIndex((item) => item.path === project.path);
  if (existingProjectIndex >= 0) {
    state.projects[existingProjectIndex] = project;
  } else {
    state.projects = [project, ...state.projects];
  }
  state.sessions = [session, ...state.sessions];
  state.messagesBySession[session.id] = messages;
  persistState();
  return {
    session: cloneSession(session),
    messages: cloneMessages(messages),
    project: cloneProject(project),
    path,
  };
}

function emit(event: StreamEvent) {
  for (const listener of listeners) {
    listener(event);
  }
}

function updateSession(sessionId: string, updater: (session: Session) => Session) {
  const index = state.sessions.findIndex((session) => session.id === sessionId);
  if (index < 0) return;
  state.sessions[index] = updater(state.sessions[index]);
}

function persistMockMessage(message: Message, options: { count?: boolean } = {}) {
  const count = options.count ?? true;
  state.messagesBySession[message.session_id] = [...(state.messagesBySession[message.session_id] ?? []), message];
  updateSession(message.session_id, (current) => ({
    ...current,
    updated_at: message.timestamp,
    message_count: count ? current.message_count + 1 : current.message_count,
  }));
  persistState();
}

function buildAssistantReply(prompt: string): string {
  const normalized = prompt.trim();
  if (!normalized) {
    return "Готов продолжать. Уточни задачу, и я разложу ее по шагам.";
  }

  if (normalized.length < 120) {
    return [
      "Сделаю это в три шага:",
      "1. Сниму текущий контекст и точки входа.",
      "2. Проверю зависимые места и визуальные несоответствия.",
      "3. Внесу правку и сверю результат с референсом.",
    ].join("\n");
  }

  return [
    "Принял. Сначала проверю структуру, потом выровняю визуальные поверхности, и в конце сверю поведение с текущим сценарием.",
    "",
    "Если нужно, следующим сообщением зафиксирую конкретный план правок и список файлов.",
  ].join("\n");
}

function simulateToolEvent(sessionId: string, text: string) {
  const lower = text.toLowerCase();
  if (lower.includes("file") || lower.includes("файл")) {
    emit({
      session_id: sessionId,
      type: "tool_use",
      provider: "claude",
      tool: "Read",
      input: { path: "src/App.tsx" },
    });
  }
}

function sendAssistantStream(sessionId: string, reply: string) {
  const words = reply.split(/(\s+)/);
  let index = 0;
  const runId = uid("run");

  const tick = () => {
    if (index === 0) {
      emit({
        session_id: sessionId,
        run_id: runId,
        type: "system",
        provider: "claude",
        content: "Claude is responding",
      });
    }

    if (index < words.length) {
      const chunk = words[index++];
      emit({
        session_id: sessionId,
        run_id: runId,
        type: "text_delta",
        provider: "claude",
        delta: chunk,
      });
      globalThis.setTimeout(tick, chunk.trim() ? 18 : 8);
      return;
    }

    emit({
      session_id: sessionId,
      run_id: runId,
      type: "message_finalized",
      provider: "claude",
      content: reply,
    });
    emit({
      session_id: sessionId,
      run_id: runId,
      type: "run_completed",
      provider: "claude",
    });
  };

  globalThis.setTimeout(tick, 32);
}

function ensureSession(sessionId: string): Session | undefined {
  return state.sessions.find((session) => session.id === sessionId);
}

async function handleSessionSend(params: RpcParams) {
  const sessionId = String(params.session_id ?? "");
  const content = String(params.content ?? "");
  const session = ensureSession(sessionId);
  if (!session) {
    throw new Error(`Unknown session: ${sessionId}`);
  }

  const userMessage = seededMessage(sessionId, "user", content);
  persistMockMessage(userMessage);

  simulateToolEvent(sessionId, content);
  const reply = buildAssistantReply(content);

  const assistantMessage: Message = {
    id: uid("msg"),
    session_id: sessionId,
    role: "assistant",
    content: reply,
    provider: session.provider ?? "claude",
    agent_role: session.mode === "critic" ? "writer" : undefined,
    timestamp: nowIso(),
    streaming: false,
  };

  persistMockMessage(assistantMessage);

  sendAssistantStream(sessionId, reply);

  return { status: "sent", session_id: sessionId, message_id: assistantMessage.id };
}

function sendMockCriticRun(
  sessionId: string,
  prompt: string,
  writerProvider: ProviderId,
  criticProvider: ProviderId
) {
  const writerReply = [
    "Сначала соберу critic-loop поверх существующего bridge runtime.",
    "Потом проведу role через streaming store и transcript, чтобы writer и critic были визуально разделены.",
  ].join("\n");
  const criticReply = [
    "{\"status\":\"needs_work\",\"lgtm\":false,\"issues\":[",
    "{\"id\":\"critic-1\",\"severity\":\"high\",\"kind\":\"correctness\",\"file\":\"desktop/src/hooks/useStreamEvents.ts\",\"summary\":\"System events are not added to the transcript during live streaming.\",\"suggested_fix\":\"Handle the existing system event type and persist it as a system message in the session store.\"}",
    "]}",
  ].join("");
  const writerMessage: Message = {
    id: uid("msg"),
    session_id: sessionId,
    role: "assistant",
    content: writerReply,
    provider: writerProvider,
    agent_role: "writer",
    timestamp: nowIso(),
  };
  const criticMessage: Message = {
    id: uid("msg"),
    session_id: sessionId,
    role: "assistant",
    content: criticReply,
    provider: criticProvider,
    agent_role: "critic",
    timestamp: nowIso(),
  };

  persistMockMessage(writerMessage);
  persistMockMessage(criticMessage);

  const runId = uid("critic");
  window.setTimeout(() => {
    emit({
      session_id: sessionId,
      run_id: `${runId}:round:1`,
      type: "system",
      provider: writerProvider,
      content: "Critic round 1/3",
    });
  }, 24);
  window.setTimeout(() => {
    emit({
      session_id: sessionId,
      run_id: `${runId}:writer`,
      type: "text_delta",
      provider: writerProvider,
      role: "writer",
      delta: writerReply,
    });
  }, 72);
  window.setTimeout(() => {
    emit({
      session_id: sessionId,
      run_id: `${runId}:writer`,
      type: "message_finalized",
      provider: writerProvider,
      role: "writer",
      content: writerReply,
    });
  }, 140);
  window.setTimeout(() => {
    emit({
      session_id: sessionId,
      run_id: `${runId}:critic`,
      type: "text_delta",
      provider: criticProvider,
      role: "critic",
      delta: criticReply,
    });
  }, 220);
  window.setTimeout(() => {
    emit({
      session_id: sessionId,
      run_id: `${runId}:critic`,
      type: "message_finalized",
      provider: criticProvider,
      role: "critic",
      content: criticReply,
    });
  }, 280);
  window.setTimeout(() => {
    emit({
      session_id: sessionId,
      run_id: `${runId}:critic`,
      type: "review_finding",
      provider: criticProvider,
      role: "critic",
      severity: "P1",
      file: "desktop/src/hooks/useStreamEvents.ts",
      title: "System events are not streamed into the transcript",
      explanation: "Critic mode round banners disappear live because system events are ignored in the stream hook.",
    });
  }, 320);
  window.setTimeout(() => {
    emit({
      session_id: sessionId,
      run_id: runId,
      type: "run_completed",
      provider: criticProvider,
    });
  }, 380);
}

function sendMockBrainstormRun(
  sessionId: string,
  prompt: string,
  ideators: ProviderId[],
  moderator: ProviderId
) {
  const ideaReplies = ideators.map((provider, index) => ({
    provider,
    role: "ideator",
    content: [
      `Идея ${index + 1}: ${provider} предлагает отдельный путь для задачи.`,
      `Фокус: ${prompt.slice(0, 90) || "зафиксировать план"} и разложить решение на этапы с рисками.`,
    ].join("\n"),
  }));
  const summaryReply = [
    "Сводка brainstorm:",
    "1. Выбираем наиболее реалистичный путь с минимальным риском интеграции.",
    "2. Сразу отделяем foundation от polish.",
    "3. Дальше идём небольшими верифицируемыми слоями.",
  ].join("\n");

  for (const idea of ideaReplies) {
    persistMockMessage({
      id: uid("msg"),
      session_id: sessionId,
      role: "assistant",
      content: idea.content,
      provider: idea.provider,
      agent_role: idea.role,
      timestamp: nowIso(),
    });
  }
  persistMockMessage({
    id: uid("msg"),
    session_id: sessionId,
    role: "assistant",
    content: summaryReply,
    provider: moderator,
    agent_role: "moderator",
    timestamp: nowIso(),
  });

  const runId = uid("brainstorm");
  let delay = 24;
  for (const [index, idea] of ideaReplies.entries()) {
    window.setTimeout(() => {
      emit({
        session_id: sessionId,
        run_id: `${runId}:idea:${index + 1}`,
        type: "system",
        provider: idea.provider,
        content: `Ideation pass ${index + 1}/${ideaReplies.length}`,
      });
    }, delay);
    delay += 36;
    window.setTimeout(() => {
      emit({
        session_id: sessionId,
        run_id: `${runId}:idea:${index + 1}`,
        type: "text_delta",
        provider: idea.provider,
        role: idea.role,
        delta: idea.content,
      });
    }, delay);
    delay += 60;
    window.setTimeout(() => {
      emit({
        session_id: sessionId,
        run_id: `${runId}:idea:${index + 1}`,
        type: "message_finalized",
        provider: idea.provider,
        role: idea.role,
        content: idea.content,
      });
    }, delay);
    delay += 56;
  }

  window.setTimeout(() => {
    emit({
      session_id: sessionId,
      run_id: `${runId}:moderator`,
      type: "text_delta",
      provider: moderator,
      role: "moderator",
      delta: summaryReply,
    });
  }, delay);
  delay += 72;
  window.setTimeout(() => {
    emit({
      session_id: sessionId,
      run_id: `${runId}:moderator`,
      type: "message_finalized",
      provider: moderator,
      role: "moderator",
      content: summaryReply,
    });
  }, delay);
  delay += 40;
  window.setTimeout(() => {
    emit({
      session_id: sessionId,
      run_id: runId,
      type: "run_completed",
      provider: moderator,
    });
  }, delay);
}

function sendMockDelegateRun(sessionId: string, prompt: string, providers: ProviderId[]) {
  const laneReplies = providers.map((provider, index) => ({
    provider,
    role: "delegate",
    content: [
      `Lane ${index + 1} (${provider}) обработал отдельный срез задачи.`,
      `Результат: ${prompt.slice(0, 80) || "выполнена задача"}; дальше нужен merge и проверка краёв.`,
    ].join("\n"),
  }));

  for (const lane of laneReplies) {
    persistMockMessage({
      id: uid("msg"),
      session_id: sessionId,
      role: "assistant",
      content: lane.content,
      provider: lane.provider,
      agent_role: lane.role,
      timestamp: nowIso(),
    });
  }

  const runId = uid("delegate");
  const streamLane = (lane: (typeof laneReplies)[number], index: number) => {
    const laneRunId = `${runId}:lane:${index + 1}`;
    const words = lane.content.split(/(\s+)/);
    let wordIndex = 0;

    window.setTimeout(() => {
      emit({
        session_id: sessionId,
        run_id: laneRunId,
        type: "system",
        provider: lane.provider,
        content: `Delegate lane ${index + 1} started`,
      });
    }, 32 + index * 42);

    const tick = () => {
      if (wordIndex < words.length) {
        const chunk = words[wordIndex++];
        emit({
          session_id: sessionId,
          run_id: laneRunId,
          type: "text_delta",
          provider: lane.provider,
          role: lane.role,
          delta: chunk,
        });
        window.setTimeout(tick, chunk.trim() ? 18 : 8);
        return;
      }

      emit({
        session_id: sessionId,
        run_id: laneRunId,
        type: "message_finalized",
        provider: lane.provider,
        role: lane.role,
        content: lane.content,
      });
      emit({
        session_id: sessionId,
        run_id: laneRunId,
        type: "system",
        provider: lane.provider,
        content: `Delegate lane ${index + 1} completed`,
      });
    };

    window.setTimeout(tick, 92 + index * 58);
  };

  laneReplies.forEach((lane, index) => {
    streamLane(lane, index);
  });
  window.setTimeout(() => {
    emit({
      session_id: sessionId,
      run_id: runId,
      type: "system",
      provider: laneReplies[0]?.provider ?? "claude",
      content: `Delegate finished: ${laneReplies.length} completed, 0 failed.`,
    });
  }, 280 + laneReplies.length * 42);
  window.setTimeout(() => {
    emit({
      session_id: sessionId,
      run_id: runId,
      type: "run_completed",
      provider: laneReplies[0]?.provider ?? "claude",
    });
  }, 330 + laneReplies.length * 42);
}

function buildMockSearchSnippet(content: string, query: string) {
  const loweredContent = content.toLowerCase();
  const loweredQuery = query.toLowerCase();
  const start = loweredContent.indexOf(loweredQuery);
  if (start < 0) {
    return content.slice(0, 96);
  }
  const prefixStart = Math.max(0, start - 42);
  const suffixEnd = Math.min(content.length, start + query.length + 54);
  const prefix = content.slice(prefixStart, start);
  const match = content.slice(start, start + query.length);
  const suffix = content.slice(start + query.length, suffixEnd);
  const head = prefixStart > 0 ? "..." : "";
  const tail = suffixEnd < content.length ? "..." : "";
  return `${head}${prefix}<mark>${match}</mark>${suffix}${tail}`;
}

function emitMockTerminalPrompt(terminalId: string) {
  emit({
    session_id: "",
    terminal_id: terminalId,
    type: "terminal_output",
    data: btoa("martin@triad % "),
  });
}

function buildMockDiagnostics() {
  const activeSessions = state.sessions
    .filter((session) => session.status === "active" || session.status === "running")
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at));

  return {
    version: "0.1.0",
    python_version: "3.12.2 (mock bridge)",
    triad_home: "/Users/martin/.triad",
    db_path: "/Users/martin/.triad/triad.db",
    providers: {
      claude: [
        {
          name: "acc1",
          available: true,
          requests_made: 24,
          errors: 0,
          cooldown_remaining_sec: 0,
        },
        {
          name: "acc2",
          available: false,
          requests_made: 17,
          errors: 1,
          cooldown_remaining_sec: 142,
        },
      ],
      codex: [
        {
          name: "acc1",
          available: true,
          requests_made: 11,
          errors: 0,
          cooldown_remaining_sec: 0,
        },
      ],
      gemini: [
        {
          name: "acc1",
          available: true,
          requests_made: 8,
          errors: 0,
          cooldown_remaining_sec: 0,
        },
      ],
    },
    active_claude_sessions: activeSessions
      .filter((session) => session.provider === "claude")
      .map((session) => session.id),
    active_sessions: activeSessions.slice(0, 6).map((session) => ({
      id: session.id,
      mode: session.mode,
      provider: session.provider ?? "claude",
      project_path: session.project_path,
      state: session.status,
    })),
    active_terminals: Array.from(mockTerminals),
    hooks_socket: "/tmp/triad-hooks.sock",
  };
}

const mockHandlers: Record<string, (params: RpcParams) => Promise<unknown> | unknown> = {
  ping: async () => ({ status: "ok", version: "0.1.0" }),
  "app.get_state": async () => {
    const sessions = state.sessions
      .map(cloneSession)
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    const lastProject = state.projects[0]?.path ?? null;
    const lastSessionId =
      sessions.find((session) => session.project_path === lastProject)?.id ?? sessions[0]?.id ?? null;
    return {
      projects: state.projects.map(cloneProject),
      sessions,
      last_project: lastProject,
      last_session_id: lastSessionId,
    };
  },
  "project.list": async () => ({ projects: state.projects.map(cloneProject) }),
  "project.open": async (params) => {
    const path = String(params.path ?? "");
    const name = String(params.name ?? path.split("/").filter(Boolean).at(-1) ?? "Project");
    const project: Project = {
      path,
      name,
      git_root: String(params.git_root ?? path),
      last_opened_at: nowIso(),
    };
    const existing = state.projects.findIndex((item) => item.path === project.path);
    if (existing >= 0) {
      state.projects[existing] = project;
    } else {
      state.projects = [project, ...state.projects];
    }
    persistState();
    return project;
  },
  "session.list": async (params) => {
    const projectPath = String(params.project_path ?? "");
    const sessions = state.sessions
      .filter((session) => !projectPath || session.project_path === projectPath)
      .map(cloneSession)
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    return { sessions };
  },
  "session.create": async (params) => {
    const projectPath = String(params.project_path ?? "");
    const mode = (String(params.mode ?? "solo") as ModeId) || "solo";
    const provider = (String(params.provider ?? "claude") as ProviderId) || "claude";
    const session: Session = {
      id: uid("session"),
      project_path: projectPath,
      title: String(params.title ?? "Новая беседа"),
      mode,
      status: "active",
      created_at: nowIso(),
      updated_at: nowIso(),
      message_count: 0,
      provider,
    };
    state.sessions = [session, ...state.sessions];
    state.messagesBySession[session.id] = [];
    persistState();
    return session;
  },
  "session.fork": async (params) => {
    const sessionId = String(params.session_id ?? "");
    if (!sessionId) {
      throw new Error("session_id is required");
    }
    const title = String(params.title ?? "").trim();
    return forkSessionInMock(sessionId, title || undefined);
  },
  "session.export": async (params) => {
    const sessionId = String(params.session_id ?? "");
    if (!sessionId) {
      throw new Error("session_id is required");
    }
    const session = ensureSession(sessionId);
    if (!session) {
      throw new Error(`Unknown session: ${sessionId}`);
    }
    const format = (String(params.format ?? "archive") as "archive" | "markdown") || "archive";
    if (format !== "archive" && format !== "markdown") {
      throw new Error(`Unsupported export format: ${format}`);
    }
    const exportPath = String(params.path ?? buildMockExportPath(session, format));
    state.exportsByPath[exportPath] =
      format === "archive"
        ? JSON.stringify(buildMockArchive(sessionId), null, 2)
        : buildMockMarkdown(sessionId);
    persistState();
    return { status: "ok", session_id: sessionId, format, path: exportPath };
  },
  "session.import": async (params) => {
    const path = String(params.path ?? "");
    if (!path) {
      throw new Error("path is required");
    }
    const raw = state.exportsByPath[path];
    if (!raw) {
      throw new Error(`Import file not found: ${path}`);
    }
    let archive: Record<string, unknown>;
    try {
      archive = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      throw new Error("Mock import supports archive exports only");
    }
    return importSessionInMock(path, archive);
  },
  "session.get": async (params) => {
    const sessionId = String(params.session_id ?? "");
    const session = ensureSession(sessionId);
    if (!session) {
      throw new Error(`Unknown session: ${sessionId}`);
    }
    return {
      session: cloneSession(session),
      messages: cloneMessages(state.messagesBySession[sessionId] ?? []),
    };
  },
  "session.send": handleSessionSend,
  "critic.start": async (params) => {
    const sessionId = String(params.session_id ?? "");
    const prompt = String(params.prompt ?? "");
    const session = ensureSession(sessionId);
    if (!session) {
      throw new Error(`Unknown session: ${sessionId}`);
    }
    const writer = (String(params.writer ?? session.provider ?? "claude") as ProviderId) || "claude";
    const critic = (
      String(params.critic ?? (writer === "claude" ? "codex" : "claude")) as ProviderId
    ) || "codex";
    const userMessage = seededMessage(sessionId, "user", prompt, writer);
    persistMockMessage(userMessage);
    sendMockCriticRun(sessionId, prompt, writer, critic);
    return { status: "started", session_id: sessionId, writer_provider: writer, critic_provider: critic };
  },
  "brainstorm.start": async (params) => {
    const sessionId = String(params.session_id ?? "");
    const prompt = String(params.prompt ?? "");
    const session = ensureSession(sessionId);
    if (!session) {
      throw new Error(`Unknown session: ${sessionId}`);
    }
    const primary = (String(params.provider ?? session.provider ?? "claude") as ProviderId) || "claude";
    const ideators = [primary, "codex", "gemini"].filter(
      (provider, index, list): provider is ProviderId => list.indexOf(provider as ProviderId) === index
    ) as ProviderId[];
    const userMessage = seededMessage(sessionId, "user", prompt, primary);
    persistMockMessage(userMessage);
    sendMockBrainstormRun(sessionId, prompt, ideators.slice(0, 3), primary);
    return { status: "started", session_id: sessionId, ideator_providers: ideators.slice(0, 3), moderator_provider: primary };
  },
  "delegate.start": async (params) => {
    const sessionId = String(params.session_id ?? "");
    const prompt = String(params.prompt ?? "");
    const session = ensureSession(sessionId);
    if (!session) {
      throw new Error(`Unknown session: ${sessionId}`);
    }
    const primary = (String(params.provider ?? session.provider ?? "claude") as ProviderId) || "claude";
    const providers = [primary, "codex", "gemini"].filter(
      (provider, index, list): provider is ProviderId => list.indexOf(provider as ProviderId) === index
    ) as ProviderId[];
    const userMessage = seededMessage(sessionId, "user", prompt, primary);
    persistMockMessage(userMessage);
    sendMockDelegateRun(sessionId, prompt, providers.slice(0, 3));
    return { status: "started", session_id: sessionId, providers: providers.slice(0, 3) };
  },
  search: async (params) => {
    const query = String(params.query ?? "").trim();
    if (!query) {
      return { results: [] };
    }
    const results = state.sessions.flatMap((session) =>
      (state.messagesBySession[session.id] ?? [])
        .filter((message) => message.content.toLowerCase().includes(query.toLowerCase()))
        .map((message, index) => ({
          event_id: Number(`${session.id.replace(/\D/g, "").slice(0, 6) || "0"}${index + 1}`),
          session_id: session.id,
          session_title: session.title,
          project_path: session.project_path,
          snippet: buildMockSearchSnippet(message.content, query),
        }))
    );
    return { results: results.slice(0, Number(params.limit ?? 12)) };
  },
  diagnostics: async () => buildMockDiagnostics(),
  "session.resume": async (params) => {
    const sessionId = String(params.session_id ?? "");
    const session = ensureSession(sessionId);
    if (!session) {
      throw new Error(`Unknown session: ${sessionId}`);
    }
    return {
      session: cloneSession(session),
      messages: cloneMessages(state.messagesBySession[sessionId] ?? []),
    };
  },
  "terminal.create": async () => {
    const terminalId = uid("term");
    mockTerminals.add(terminalId);
    window.setTimeout(() => emitMockTerminalPrompt(terminalId), 24);
    return { terminal_id: terminalId };
  },
  "terminal.input": async (params) => {
    const terminalId = String(params.terminal_id ?? "");
    if (!mockTerminals.has(terminalId)) {
      throw new Error(`Unknown terminal: ${terminalId}`);
    }
    const raw = typeof params.data === "string" ? params.data : "";
    const input = raw ? atob(raw) : "";
    const normalized = input.replace(/\r/g, "");
    emit({
      session_id: "",
      terminal_id: terminalId,
      type: "terminal_output",
      data: btoa(normalized),
    });
    if (normalized.includes("\n")) {
      emit({
        session_id: "",
        terminal_id: terminalId,
        type: "terminal_output",
        data: btoa("Mock terminal: backend sidecar is not attached.\r\nmartin@triad % "),
      });
    }
    return { status: "ok" };
  },
  "terminal.resize": async () => ({ status: "ok" }),
  "terminal.close": async (params) => {
    mockTerminals.delete(String(params.terminal_id ?? ""));
    return { status: "ok" };
  },
};

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

async function tryStartTauriBridge(): Promise<boolean> {
  try {
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
    backendMode = "tauri";
    markBridgeConnected("tauri");
    return true;
  } catch (error) {
    console.warn("Falling back to mock desktop bridge:", error);
    return false;
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
      backendMode = "mock";
      child = null;
      started = true;
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
      backendMode = "mock";
      child = null;
      started = true;
      markBridgeDisconnected(error);
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
  const tauriReady = await tryStartTauriBridge();
  if (!tauriReady) {
    backendMode = "mock";
    hydrateState();
    markBridgeFallback("Tauri bridge unavailable.", "Running on mock backend until Retry succeeds.");
  }
}

export async function stopBridge() {
  if (child) {
    await Promise.resolve(child.kill()).catch(() => undefined);
    child = null;
  }
  backendMode = "mock";
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

  if (backendMode === "tauri") {
    return rpcThroughBridge<T>(method, params);
  }

  const handler = mockHandlers[method];
  if (!handler) {
    throw new Error(`Unknown RPC method: ${method}`);
  }
  return handler(params) as Promise<T> | T;
}

export function getMockState() {
  return {
    projects: state.projects.map(cloneProject),
    sessions: state.sessions.map(cloneSession),
  };
}
