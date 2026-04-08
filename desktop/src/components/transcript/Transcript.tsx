import { useVirtualizer } from "@tanstack/react-virtual";
import { type ReactNode, useEffect, useMemo, useRef } from "react";
import type { Message } from "../../lib/types";
import { useProjectStore } from "../../stores/project-store";
import { useSessionStore } from "../../stores/session-store";
import { AssistantMessage } from "./AssistantMessage";
import { BashCard } from "./BashCard";
import { DiffCard } from "./DiffCard";
import { FindingCard } from "./FindingCard";
import { StreamingText } from "./StreamingText";
import { SystemMessage } from "./SystemMessage";
import { buildTranscriptOverview, TranscriptOverview } from "./TranscriptOverview";
import { ToolCard } from "./ToolCard";
import { UserMessage } from "./UserMessage";

function estimateMessageSize(message: Message) {
  if (message.role === "user") {
    return 144;
  }
  if (message.review_finding) {
    return 196;
  }
  if (message.tool_event) {
    return 188;
  }
  if (message.diff_snapshot) {
    return 184;
  }
  if (message.role === "system") {
    return 96;
  }
  if (message.tool_calls?.length) {
    return 260;
  }
  if (message.content.length > 2400) {
    return 520;
  }
  if (message.content.length > 1200) {
    return 360;
  }
  if (message.content.length > 600) {
    return 260;
  }
  return 176;
}

function renderTranscriptNode(message: Message): ReactNode {
  if (message.role === "user") {
    return <UserMessage message={message} />;
  }

  if (message.review_finding) {
    return <FindingCard finding={message.review_finding} />;
  }

  if (message.diff_snapshot) {
    return (
      <DiffCard
        filePath={message.diff_snapshot.path}
        oldText={message.diff_snapshot.old_text}
        newText={message.diff_snapshot.new_text}
      />
    );
  }

  if (message.tool_event) {
    const input =
      message.tool_event.input && typeof message.tool_event.input === "object"
        ? (message.tool_event.input as Record<string, unknown>)
        : {};
    const tool = String(message.tool_event.tool ?? "tool");

    if (tool === "Bash") {
      return (
        <BashCard
          command={String(input.command ?? input.cmd ?? "")}
          output={typeof message.tool_event.output === "string" ? message.tool_event.output : undefined}
          status={message.tool_event.status ?? "completed"}
        />
      );
    }

    return (
      <ToolCard
        tool={tool}
        input={message.tool_event.input ?? {}}
        output={message.tool_event.output}
        status={message.tool_event.status ?? "completed"}
      />
    );
  }

  if (message.role === "system") {
    return <SystemMessage text={message.content} />;
  }

  if (message.tool_calls?.length) {
    return (
      <div className="space-y-3">
        <AssistantMessage message={message} />
        {message.tool_calls.map((tool) => (
          <ToolCard
            key={tool.id}
            tool={tool.tool}
            input={tool.input}
            output={tool.output}
            status={tool.status}
          />
        ))}
      </div>
    );
  }

  return <AssistantMessage message={message} />;
}

function EmptyTranscriptState({ projectName }: { projectName: string }) {
  return (
    <div className="flex min-h-full flex-1 items-center justify-center px-6 py-10">
      <div className="w-full max-w-[760px]">
        <div className="text-center">
          <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-full border border-border-light bg-elevated/60 text-[22px] text-text-primary shadow-glow">
            ☁
          </div>
          <h1 className="text-[30px] font-medium tracking-[-0.03em] text-text-primary">Давайте построим</h1>
          <p className="mt-2 text-[15px] text-text-secondary">{projectName}</p>
        </div>

        <div className="mt-6 grid gap-3">
          <div className="rounded-[18px] border border-[rgba(96,135,184,0.34)] bg-[linear-gradient(180deg,rgba(18,31,47,0.92),rgba(14,22,34,0.82))] px-4 py-3 text-[13px] text-[rgba(202,222,245,0.92)] shadow-[0_16px_40px_rgba(3,8,16,0.3)]">
            <div className="flex items-center gap-2">
              <span className="rounded-full border border-[rgba(118,170,236,0.3)] bg-[rgba(59,130,246,0.12)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.12em] text-[rgba(156,202,255,0.95)]">
                Tip
              </span>
              <span className="text-text-primary">Toggle `/Fast` when you want a lighter, quicker pass.</span>
            </div>
          </div>

          <div className="rounded-[22px] border border-[rgba(76,140,255,0.28)] bg-[linear-gradient(135deg,rgba(30,64,175,0.28),rgba(16,28,53,0.96)_62%,rgba(10,16,28,0.98))] px-5 py-4 shadow-[0_22px_50px_rgba(8,16,30,0.38)]">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-[rgba(122,184,255,0.26)] bg-[rgba(94,151,255,0.14)] px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.12em] text-[rgba(184,219,255,0.96)]">
                  <span className="rounded-full bg-[rgba(124,196,255,0.94)] px-1.5 py-[1px] text-[9px] font-semibold tracking-[0.12em] text-[rgba(7,20,40,0.92)]">
                    New
                  </span>
                  Skills and Plugins
                </div>
                <h2 className="mt-3 text-[20px] font-medium tracking-[-0.02em] text-white">
                  Make Triad work your way
                </h2>
                <p className="mt-2 max-w-[520px] text-[13px] leading-[1.7] text-[rgba(212,228,255,0.78)]">
                  Connect Figma, GitHub, Notion, search tooling and local workflows before you start the next run.
                </p>
              </div>
              <div className="hidden rounded-full border border-[rgba(148,191,255,0.3)] bg-[rgba(255,255,255,0.07)] px-3 py-1 text-[11px] text-[rgba(220,234,255,0.9)] sm:inline-flex">
                Quick setup
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {["Figma", "GitHub", "Notion", "Search", "Chrome DevTools"].map((label) => (
                <span
                  key={label}
                  className="rounded-full border border-[rgba(141,180,236,0.22)] bg-[rgba(255,255,255,0.05)] px-3 py-1 text-[12px] text-[rgba(225,234,247,0.88)]"
                >
                  {label}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function Transcript() {
  const { activeProject } = useProjectStore();
  const { activeSession, messages, streamingRuns } = useSessionStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const emptyState = useMemo(() => {
    return activeProject
      ? { title: "Давайте построим", subtitle: activeProject.name }
      : { title: "Давайте построим", subtitle: "Triad Desktop" };
  }, [activeProject]);

  const orderedStreamingRuns = useMemo(
    () => [...streamingRuns].sort((left, right) => left.updated_at.localeCompare(right.updated_at)),
    [streamingRuns]
  );
  const overview = useMemo(
    () => buildTranscriptOverview(messages, orderedStreamingRuns),
    [messages, orderedStreamingRuns]
  );
  const streamingSignature = useMemo(
    () => orderedStreamingRuns.map((stream) => `${stream.run_id}:${stream.text.length}`).join("|"),
    [orderedStreamingRuns]
  );
  const messageIndexById = useMemo(
    () => new Map(messages.map((message, index) => [message.id, index])),
    [messages]
  );
  const rowVirtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: (index) => estimateMessageSize(messages[index]),
    getItemKey: (index) => messages[index]?.id ?? index,
    overscan: 8,
    scrollPaddingStart: overview ? 112 : 0,
    useFlushSync: false,
  });
  const virtualRows = rowVirtualizer.getVirtualItems();

  const jumpToMessage = (messageId: string) => {
    const index = messageIndexById.get(messageId);
    if (index === undefined) {
      return;
    }
    rowVirtualizer.scrollToIndex(index, {
      align: "start",
      behavior: "smooth",
    });
  };

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages.length, streamingSignature, activeSession?.id]);

  if (!activeSession) {
    return (
      <div className="flex h-full items-center justify-center px-6">
        <div className="max-w-[420px] text-center">
          <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-full border border-border-light bg-elevated/60 text-[22px] text-text-primary shadow-glow">
            ☁
          </div>
          <h1 className="text-[28px] font-medium tracking-[-0.02em] text-text-primary">{emptyState.title}</h1>
          <p className="mt-1 text-[16px] text-text-secondary">{emptyState.subtitle}</p>
          <div className="mx-auto mt-6 max-w-[360px] rounded-2xl border border-border-default bg-[rgba(255,255,255,0.025)] px-4 py-3 text-left text-[13px] leading-[1.6] text-text-secondary">
            Это стартовый экран в стиле Codex. Выберите проект слева или создайте новую беседу, чтобы начать.
          </div>
        </div>
      </div>
    );
  }

  if (!messages.length && !orderedStreamingRuns.length) {
    return (
      <div className="relative flex h-full min-h-0 flex-1 flex-col">
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto bg-[radial-gradient(circle_at_top,rgba(37,72,118,0.14),transparent_34%)] px-6 pb-6 pt-4"
        >
          <div className="mx-auto flex min-h-full w-full max-w-[900px] flex-col">
            <EmptyTranscriptState projectName={activeProject?.name ?? "Triad Desktop"} />
            <div ref={endRef} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex h-full min-h-0 flex-1 flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 pb-6 pt-4">
        <div className="mx-auto flex w-full max-w-[840px] flex-col">
          {overview ? (
            <div className="sticky top-0 z-10 pb-1 pt-0.5 backdrop-blur-[3px]">
              <TranscriptOverview overview={overview} onJump={jumpToMessage} />
            </div>
          ) : null}
          <div
            className={`relative ${overview ? "mt-3" : ""}`}
            style={{ height: rowVirtualizer.getTotalSize() }}
          >
            {virtualRows.map((virtualRow) => {
              const message = messages[virtualRow.index];
              if (!message) {
                return null;
              }

              return (
                <div
                  key={virtualRow.key}
                  data-index={virtualRow.index}
                  ref={rowVirtualizer.measureElement}
                  className="absolute left-0 top-0 w-full"
                  style={{
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                >
                  <div className="pb-3">{renderTranscriptNode(message)}</div>
                </div>
              );
            })}
          </div>

          {orderedStreamingRuns.length > 0 ? (
            <div className="flex flex-col gap-3">
              {orderedStreamingRuns.map((stream) => (
                <StreamingText
                  key={stream.run_id}
                  text={stream.text}
                  provider={stream.provider}
                  role={stream.role}
                />
              ))}
            </div>
          ) : null}
          <div ref={endRef} />
        </div>
      </div>
    </div>
  );
}
