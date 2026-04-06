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
import { TriadLogo } from "../shared/TriadLogo";

function parseToolMessage(content: string) {
  if (!content.startsWith("!tool:")) {
    return null;
  }
  try {
    const payload = JSON.parse(content.slice("!tool:".length)) as {
      tool?: string;
      input?: Record<string, unknown> | string;
      output?: unknown;
      status?: "running" | "completed" | "failed";
    };
    return payload;
  } catch {
    return null;
  }
}

function estimateMessageSize(message: Message) {
  if (message.role === "user") return 80;
  if (message.content.startsWith("!finding:")) return 100;
  if (message.content.startsWith("!tool:")) return 48;
  if (message.content.startsWith("!bash:")) return 48;
  if (message.role === "system") return 40;
  if (message.tool_calls?.length) return 200;
  if (message.content.length > 2400) return 400;
  if (message.content.length > 1200) return 280;
  if (message.content.length > 600) return 180;
  return 100;
}

function renderTranscriptNode(message: Message): ReactNode {
  if (message.role === "user") {
    return <UserMessage message={message} />;
  }

  const toolPayload = parseToolMessage(message.content);
  if (toolPayload) {
    const input =
      toolPayload.input && typeof toolPayload.input === "object"
        ? (toolPayload.input as Record<string, unknown>)
        : {};
    const tool = String(toolPayload.tool ?? "tool");

    if (tool === "Bash") {
      return (
        <BashCard
          command={String(input.command ?? input.cmd ?? "")}
          output={typeof toolPayload.output === "string" ? toolPayload.output : undefined}
          status={toolPayload.status ?? "completed"}
        />
      );
    }

    if ((tool === "Edit" || tool === "Write") && (input.old_string || input.new_string || input.content)) {
      return (
        <DiffCard
          filePath={String(input.file_path ?? input.path ?? "untitled")}
          oldText={String(input.old_string ?? "")}
          newText={String(input.new_string ?? input.content ?? "")}
        />
      );
    }

    return (
      <ToolCard
        tool={tool}
        input={toolPayload.input ?? {}}
        output={toolPayload.output}
        status={toolPayload.status ?? "completed"}
      />
    );
  }

  if (message.content.startsWith("!bash:")) {
    return <BashCard command={message.content.replace(/^!bash:/, "").trim()} status="completed" />;
  }

  if (message.content.startsWith("!finding:")) {
    const finding = message.content.replace(/^!finding:/, "").trim().split("|");
    return (
      <FindingCard
        finding={{
          severity: (finding[0] as "P0" | "P1" | "P2" | "P3") || "P2",
          file: finding[1] || "src/App.tsx",
          title: finding[2] || "Finding",
          explanation: finding[3] || "Potential issue detected.",
        }}
      />
    );
  }

  if (message.role === "system") {
    return <SystemMessage text={message.content} />;
  }

  if (message.tool_calls?.length) {
    return (
      <div>
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

function EmptyState({ projectName }: { projectName: string }) {
  return (
    <div className="flex min-h-full flex-1 items-center justify-center">
      <div className="text-center">
        <TriadLogo size={48} className="mx-auto mb-5 text-text-tertiary" />
        <h1 className="text-[28px] font-medium tracking-[-0.02em] text-text-primary">Давайте построим</h1>
        <p className="mt-1.5 text-[14px] text-text-tertiary">{projectName} &#x25BE;</p>
      </div>
    </div>
  );
}

export function Transcript() {
  const { activeProject } = useProjectStore();
  const { activeSession, messages, streamingRuns } = useSessionStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

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
    scrollPaddingStart: overview ? 80 : 0,
    useFlushSync: false,
  });
  const virtualRows = rowVirtualizer.getVirtualItems();

  const jumpToMessage = (messageId: string) => {
    const index = messageIndexById.get(messageId);
    if (index === undefined) {
      return;
    }
    rowVirtualizer.scrollToIndex(index, { align: "start", behavior: "smooth" });
  };

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages.length, streamingSignature, activeSession?.id]);

  // No session
  if (!activeSession) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState projectName={activeProject?.name ?? "Triad Desktop"} />
      </div>
    );
  }

  // Session with no messages yet
  if (!messages.length && !orderedStreamingRuns.length) {
    return (
      <div className="relative flex h-full min-h-0 flex-1 flex-col">
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 pb-6 pt-4">
          <div className="mx-auto flex min-h-full w-full max-w-[840px] flex-col">
            <EmptyState projectName={activeProject?.name ?? "Triad Desktop"} />
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
            <div className="sticky top-0 z-10 pb-1 pt-0.5">
              <TranscriptOverview overview={overview} onJump={jumpToMessage} />
            </div>
          ) : null}
          <div
            className={`relative ${overview ? "mt-2" : ""}`}
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
                  style={{ transform: `translateY(${virtualRow.start}px)` }}
                >
                  {renderTranscriptNode(message)}
                </div>
              );
            })}
          </div>

          {orderedStreamingRuns.length > 0 ? (
            <div className="flex flex-col">
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
