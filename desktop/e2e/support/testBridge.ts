import type { Page } from "@playwright/test";

export type BridgeScenario = "recovery" | "project-unavailable" | "shell";

export async function injectTestBridge(page: Page, scenario: BridgeScenario) {
  await page.addInitScript(({ scenario }) => {
    window.__TRIAD_E2E__ = true;
    const listeners = new Set<(event: Record<string, unknown>) => void>();
    let startAttempts = 0;
    let stateAttempts = 0;
    let sessionCounter = 2;
    const now = () => new Date().toISOString();
    const defaultProject = {
      path: "/tmp/triad-demo",
      name: "triad-demo",
      git_root: "/tmp/triad-demo",
      last_opened_at: now(),
    };
    const projects = scenario === "project-unavailable" ? [] : [defaultProject];
    const sessions =
      scenario === "project-unavailable"
        ? []
        : [
            {
              id: "sess_shell",
              project_path: defaultProject.path,
              title: "Review the bridge flow",
              mode: "solo",
              status: "active",
              created_at: now(),
              updated_at: now(),
              message_count: 0,
              provider: "claude",
            },
          ];
    const sessionMessages = new Map<string, Array<Record<string, unknown>>>();
    sessionMessages.set("sess_shell", []);

    const emit = (event: Record<string, unknown>) => {
      const payload = { schema_version: 1, ...event };
      for (const listener of listeners) {
        listener(payload);
      }
    };

    const queueTerminalPrompt = (terminalId: string) => {
      setTimeout(() => {
        emit({
          session_id: "__terminal__",
          type: "terminal_output",
          terminal_id: terminalId,
          data: btoa("triad % "),
        });
      }, 20);
    };

    const queueShellRun = (sessionId: string, prompt: string) => {
      const runId = `run_${Date.now()}`;
      setTimeout(() => {
        emit({
          session_id: sessionId,
          run_id: runId,
          type: "system",
          provider: "claude",
          content: "Claude writer is running",
        });
      }, 10);
      setTimeout(() => {
        emit({
          session_id: sessionId,
          run_id: runId,
          type: "tool_use",
          provider: "claude",
          role: "assistant",
          tool: "Read",
          status: "running",
          input: { path: "desktop/src/App.tsx" },
        });
      }, 30);
      setTimeout(() => {
        emit({
          session_id: sessionId,
          run_id: runId,
          type: "diff_snapshot",
          provider: "claude",
          role: "assistant",
          path: "desktop/src/lib/rpc.ts",
          old_text: "legacy mock bridge",
          new_text: "fail-closed bridge",
        });
      }, 50);
      setTimeout(() => {
        emit({
          session_id: sessionId,
          run_id: runId,
          type: "review_finding",
          provider: "codex",
          role: "critic",
          severity: "P1",
          file: "desktop/src/hooks/useStreamEvents.ts",
          title: "Persist system events",
          explanation: "Keep status banners visible in the transcript.",
        });
      }, 70);
      setTimeout(() => {
        emit({
          session_id: sessionId,
          run_id: runId,
          type: "text_delta",
          provider: "claude",
          role: "assistant",
          delta: `Reply for: ${prompt}`,
        });
      }, 90);
      setTimeout(() => {
        emit({
          session_id: sessionId,
          run_id: runId,
          type: "message_finalized",
          provider: "claude",
          role: "assistant",
          content: `Reply for: ${prompt}`,
        });
      }, 120);
      setTimeout(() => {
        emit({
          session_id: sessionId,
          run_id: runId,
          type: "run_completed",
          provider: "claude",
        });
      }, 150);
    };

    window.__TRIAD_TEST_BRIDGE__ = {
      async start() {
        startAttempts += 1;
      },
      async request(method: string, params: Record<string, unknown>) {
        switch (method) {
          case "app.get_state":
            stateAttempts += 1;
            if (scenario === "recovery" && stateAttempts === 1) {
              throw new Error("Bridge app state failed for test");
            }
            return {
              projects,
              sessions,
              last_project: projects[0]?.path ?? null,
              last_session_id: sessions[0]?.id ?? null,
            };
          case "project.list":
            return { projects };
          case "project.open": {
            const path = String(params.path ?? "/tmp/new-project");
            const project = {
              path,
              name: path.split("/").filter(Boolean).at(-1) ?? "project",
              git_root: path,
              last_opened_at: now(),
            };
            if (!projects.some((entry) => entry.path === project.path)) {
              projects.unshift(project);
            }
            return project;
          }
          case "session.list": {
            const projectPath = String(params.project_path ?? "");
            return {
              sessions: projectPath ? sessions.filter((session) => session.project_path === projectPath) : sessions,
            };
          }
          case "session.get": {
            const sessionId = String(params.session_id ?? "sess_shell");
            const session = sessions.find((entry) => entry.id === sessionId) ?? sessions[0];
            return {
              session,
              messages: sessionMessages.get(sessionId) ?? [],
            };
          }
          case "session.create": {
            const session = {
              id: `sess_${sessionCounter++}`,
              project_path: String(params.project_path ?? defaultProject.path),
              title: String(params.title ?? "New session"),
              mode: String(params.mode ?? "solo"),
              status: "active",
              created_at: now(),
              updated_at: now(),
              message_count: 0,
              provider: String(params.provider ?? "claude"),
            };
            sessions.unshift(session);
            sessionMessages.set(session.id, []);
            return session;
          }
          case "session.send": {
            const sessionId = String(params.session_id ?? "sess_shell");
            queueShellRun(sessionId, String(params.content ?? "hello"));
            return { status: "sent", session_id: sessionId };
          }
          case "session.stop":
            return { status: "stopped", session_id: String(params.session_id ?? "sess_shell") };
          case "diagnostics":
            return {
              version: "0.1.0-test",
              python_version: "3.12.0 test-bridge",
              triad_home: "/tmp/triad-home",
              db_path: "/tmp/triad-home/triad.db",
              providers: {
                claude: [{ name: "acc1", available: true, requests_made: 3, errors: 0, cooldown_remaining_sec: 0 }],
                codex: [{ name: "acc1", available: true, requests_made: 1, errors: 0, cooldown_remaining_sec: 0 }],
                gemini: [],
              },
              active_claude_sessions: sessions.filter((session) => session.provider === "claude").map((session) => session.id),
              active_sessions: sessions.map((session) => ({
                id: session.id,
                mode: session.mode,
                provider: session.provider,
                project_path: session.project_path,
                state: session.status,
              })),
              active_terminals: ["term_1"],
              active_file_watches: [
                {
                  session_id: "sess_shell",
                  project_path: defaultProject.path,
                  project_dir: "/tmp/triad-home/.claude/projects/tmp-triad-demo",
                  bound_file: "/tmp/triad-home/.claude/projects/tmp-triad-demo/session.jsonl",
                },
              ],
              hooks_socket: "/tmp/triad-hooks.sock",
            };
          case "terminal.create":
            queueTerminalPrompt("term_1");
            return { terminal_id: "term_1" };
          case "terminal.input":
            emit({
              session_id: "__terminal__",
              type: "terminal_output",
              terminal_id: "term_1",
              data: String(params.data ?? ""),
            });
            return { status: "ok" };
          case "terminal.resize":
          case "terminal.close":
            return { status: "ok" };
          default:
            throw new Error(`Unhandled test bridge method: ${method}`);
        }
      },
      subscribe(listener: (event: Record<string, unknown>) => void) {
        listeners.add(listener);
        return () => listeners.delete(listener);
      },
    };
  }, { scenario });
}
