import { useVirtualizer } from "@tanstack/react-virtual";
import { type ReactNode, useEffect, useMemo, useRef } from "react";
import type { TimelineItem } from "../../lib/types";
import { useProjectStore } from "../../stores/project-store";
import { useSessionStore } from "../../stores/session-store";
import { TriadLogo } from "../shared/TriadLogo";
import { AssistantMessage } from "./AssistantMessage";
import { BashCard } from "./BashCard";
import { DiffCard } from "./DiffCard";
import { DiffSnapshotCard } from "./DiffSnapshotCard";
import { FindingCard } from "./FindingCard";
import { StreamingText } from "./StreamingText";
import { SystemMessage } from "./SystemMessage";
import { ToolCard } from "./ToolCard";
import { UserMessage } from "./UserMessage";

function estimateTimelineItemSize(item: TimelineItem) {
  switch (item.kind) {
    case "user_message":
      return 80 + Math.ceil((item.attachments?.length ?? 0) / 2) * 34;
    case "review_finding":
      return 96;
    case "diff_snapshot":
      return 132;
    case "tool_call":
      return item.tool === "Bash" ? 160 : 56;
    case "system_notice":
      return 44;
    case "assistant_message":
      if (item.text.length > 2400) return 400;
      if (item.text.length > 1200) return 280;
      if (item.text.length > 600) return 180;
      return 100;
    default:
      return 88;
  }
}

function renderTimelineNode(item: TimelineItem): ReactNode {
  switch (item.kind) {
    case "user_message":
      return <UserMessage content={item.text} attachments={item.attachments} />;
    case "assistant_message":
      return <AssistantMessage content={item.text} />;
    case "system_notice":
      return <SystemMessage title={item.title} text={item.body} tone={item.level} />;
    case "review_finding":
      return (
        <FindingCard
          finding={{
            severity: item.severity,
            file: item.file,
            title: item.title,
            explanation: item.explanation,
            line_range: item.line_range ?? (item.line ? `Line ${item.line}` : undefined),
          }}
        />
      );
    case "diff_snapshot":
      return <DiffSnapshotCard patch={item.patch} />;
    case "tool_call": {
      const input =
        item.input && typeof item.input === "object" ? (item.input as Record<string, unknown>) : {};

      if (item.tool === "Bash") {
        return (
          <BashCard
            command={String(input.command ?? input.cmd ?? "")}
            output={typeof item.output === "string" ? item.output : undefined}
            status={item.status}
          />
        );
      }

      if ((item.tool === "Edit" || item.tool === "Write") && (input.old_string || input.new_string || input.content)) {
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
          tool={item.tool}
          input={item.input ?? {}}
          output={item.output}
          status={item.status}
        />
      );
    }
    default:
      return null;
  }
}

function EmptyState({ projectName, hasProject }: { projectName: string; hasProject: boolean }) {
  return (
    <div className="flex min-h-full flex-1 items-center justify-center">
      <div className="text-center">
        <TriadLogo size={48} className="mx-auto mb-5 text-text-tertiary" />
        <h1 className="text-[26px] font-medium tracking-[-0.02em] text-text-primary">
          {hasProject ? "Start a session" : "Open a project"}
        </h1>
        <p className="mt-1.5 text-[14px] text-text-tertiary">
          {hasProject ? projectName : "Choose a project to load a live session."}
        </p>
      </div>
    </div>
  );
}

export function Transcript() {
  const { activeProject } = useProjectStore();
  const { activeSession, timeline, streamingRuns } = useSessionStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const orderedStreamingRuns = useMemo(
    () => [...streamingRuns].sort((left, right) => left.updated_at.localeCompare(right.updated_at)),
    [streamingRuns]
  );
  const streamingSignature = useMemo(
    () => orderedStreamingRuns.map((stream) => `${stream.run_id}:${stream.text.length}`).join("|"),
    [orderedStreamingRuns]
  );
  const rowVirtualizer = useVirtualizer({
    count: timeline.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: (index) => estimateTimelineItemSize(timeline[index]),
    getItemKey: (index) => timeline[index]?.id ?? index,
    overscan: 8,
    useFlushSync: false,
  });
  const virtualRows = rowVirtualizer.getVirtualItems();

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [timeline.length, streamingSignature, activeSession?.id]);

  if (!activeSession) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState
          projectName={activeProject?.name ?? "Triad Desktop"}
          hasProject={Boolean(activeProject)}
        />
      </div>
    );
  }

  if (!timeline.length && !orderedStreamingRuns.length) {
    return (
      <div className="relative flex h-full min-h-0 flex-1 flex-col">
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 pb-6 pt-4">
          <div className="mx-auto flex min-h-full w-full max-w-[840px] flex-col">
            <EmptyState
              projectName={activeProject?.name ?? "Triad Desktop"}
              hasProject={Boolean(activeProject)}
            />
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
          <div className="relative" style={{ height: rowVirtualizer.getTotalSize() }}>
            {virtualRows.map((virtualRow) => {
              const item = timeline[virtualRow.index];
              if (!item) {
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
                  {renderTimelineNode(item)}
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
