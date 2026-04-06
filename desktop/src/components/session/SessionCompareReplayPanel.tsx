import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { SessionCompareRow, SessionReplayFrame, TimelineItem } from "../../lib/types";
import { useSessionStore } from "../../stores/session-store";
import { useUiStore } from "../../stores/ui-store";
import { AssistantMessage } from "../transcript/AssistantMessage";
import { BashCard } from "../transcript/BashCard";
import { DiffCard } from "../transcript/DiffCard";
import { DiffSnapshotCard } from "../transcript/DiffSnapshotCard";
import { FindingCard } from "../transcript/FindingCard";
import { SystemMessage } from "../transcript/SystemMessage";
import { ToolCard } from "../transcript/ToolCard";
import { UserMessage } from "../transcript/UserMessage";

function renderReplayItem(item: TimelineItem): ReactNode {
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
      return <ToolCard tool={item.tool} input={item.input ?? {}} output={item.output} status={item.status} />;
    }
    default:
      return null;
  }
}

function CompareCell({
  title,
  row,
}: {
  title: string;
  row: SessionCompareRow;
}) {
  const summary = title === "left" ? row.left_summary : row.right_summary;
  const item = title === "left" ? row.left : row.right;

  if (!summary || !item) {
    return (
      <div className="rounded-[14px] border border-dashed border-[var(--color-border)] bg-[rgba(255,255,255,0.015)] px-3 py-3 text-[12px] text-[var(--color-text-tertiary)]">
        No item
      </div>
    );
  }

  return (
    <div className="rounded-[14px] border border-[var(--color-border)] bg-[rgba(255,255,255,0.02)] px-3 py-3">
      <div className="text-[11px] uppercase tracking-[0.08em] text-[var(--color-text-tertiary)]">
        {summary.label}
      </div>
      {summary.excerpt ? (
        <div className="mt-1 text-[12px] leading-[1.5] text-[var(--color-text-secondary)]">{summary.excerpt}</div>
      ) : null}
      <div className="mt-2 text-[11px] text-[var(--color-text-tertiary)]">
        {new Date(item.ts).toLocaleString()}
      </div>
    </div>
  );
}

function statusTone(status: SessionCompareRow["status"]) {
  switch (status) {
    case "same":
      return "text-[var(--color-text-success)]";
    case "different":
      return "text-[var(--color-text-warning)]";
    default:
      return "text-[var(--color-text-tertiary)]";
  }
}

function frameCountLabel(frame: SessionReplayFrame) {
  return Object.entries(frame.counts)
    .filter(([, count]) => typeof count === "number" && count > 0)
    .map(([kind, count]) => `${kind.replace("_", " ")} ${count}`)
    .join(" · ");
}

export function SessionCompareReplayPanel() {
  const activeSession = useSessionStore((state) => state.activeSession);
  const sessions = useSessionStore((state) => state.sessions);
  const compareResult = useSessionStore((state) => state.compareResult);
  const replay = useSessionStore((state) => state.replay);
  const loadCompare = useSessionStore((state) => state.loadCompare);
  const loadReplay = useSessionStore((state) => state.loadReplay);
  const clearCompareReplay = useSessionStore((state) => state.clearCompareReplay);
  const compareReplayPanelOpen = useUiStore((state) => state.compareReplayPanelOpen);
  const compareReplayPanelTab = useUiStore((state) => state.compareReplayPanelTab);
  const setCompareReplayPanel = useUiStore((state) => state.setCompareReplayPanel);
  const [compareTargetId, setCompareTargetId] = useState<string>("");
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [replayLoading, setReplayLoading] = useState(false);
  const [replayError, setReplayError] = useState<string | null>(null);
  const [frameIndex, setFrameIndex] = useState(0);

  const compareCandidates = useMemo(
    () =>
      sessions.filter(
        (session) =>
          session.id !== activeSession?.id && (!activeSession || session.project_path === activeSession.project_path)
      ),
    [activeSession, sessions]
  );

  useEffect(() => {
    if (!compareReplayPanelOpen) {
      return;
    }
    if (compareReplayPanelTab !== "compare") {
      return;
    }
    if (compareCandidates.length === 0) {
      setCompareTargetId("");
      return;
    }
    setCompareTargetId((current) =>
      current && compareCandidates.some((session) => session.id === current) ? current : compareCandidates[0].id
    );
  }, [compareCandidates, compareReplayPanelOpen, compareReplayPanelTab]);

  useEffect(() => {
    if (!compareReplayPanelOpen || compareReplayPanelTab !== "replay" || !activeSession) {
      return;
    }
    setReplayLoading(true);
    setReplayError(null);
    void loadReplay(activeSession.id)
      .then((result) => {
        setFrameIndex((current) => Math.min(current, Math.max(result.total_frames - 1, 0)));
      })
      .catch((error) => {
        setReplayError(error instanceof Error ? error.message : "Failed to load replay.");
      })
      .finally(() => {
        setReplayLoading(false);
      });
  }, [activeSession?.id, compareReplayPanelOpen, compareReplayPanelTab, loadReplay]);

  useEffect(() => {
    setFrameIndex(0);
  }, [replay?.session.id]);

  if (!compareReplayPanelOpen) {
    return null;
  }

  const currentFrame = replay?.frames[frameIndex] ?? null;

  return (
    <aside className="flex w-[46%] min-w-[420px] border-l border-[rgba(255,255,255,0.06)] bg-[var(--color-bg-editor)]">
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="border-b border-[rgba(255,255,255,0.06)] px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[11px] uppercase tracking-[0.1em] text-[var(--color-text-tertiary)]">
                Session tools
              </div>
              <div className="mt-1 text-[13px] text-[var(--color-text-primary)]">
                Compare branches of work or replay a session timeline
              </div>
            </div>
            <button
              type="button"
              onClick={() => {
                clearCompareReplay();
                setCompareReplayPanel(false);
              }}
              className="flex h-6 w-6 items-center justify-center rounded text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]"
            >
              <svg width="10" height="10" viewBox="0 0 16 16" fill="none">
                <path d="M4 4L12 12M12 4L4 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
          </div>
          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setCompareReplayPanel(true, { tab: "compare" })}
              className={[
                "rounded-md border px-2.5 py-1 text-[11px] transition-colors",
                compareReplayPanelTab === "compare"
                  ? "border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.05)] text-[var(--color-text-primary)]"
                  : "border-[rgba(255,255,255,0.06)] text-[var(--color-text-secondary)] hover:bg-white/[0.03] hover:text-[var(--color-text-primary)]",
              ].join(" ")}
            >
              Compare
            </button>
            <button
              type="button"
              onClick={() => setCompareReplayPanel(true, { tab: "replay" })}
              className={[
                "rounded-md border px-2.5 py-1 text-[11px] transition-colors",
                compareReplayPanelTab === "replay"
                  ? "border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.05)] text-[var(--color-text-primary)]"
                  : "border-[rgba(255,255,255,0.06)] text-[var(--color-text-secondary)] hover:bg-white/[0.03] hover:text-[var(--color-text-primary)]",
              ].join(" ")}
            >
              Replay
            </button>
          </div>
        </div>

        {compareReplayPanelTab === "compare" ? (
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="border-b border-[rgba(255,255,255,0.06)] px-4 py-3">
              <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
                <select
                  value={compareTargetId}
                  onChange={(event) => setCompareTargetId(event.target.value)}
                  className="rounded-md border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)] px-3 py-2 text-[12px] text-[var(--color-text-primary)] outline-none"
                >
                  {compareCandidates.length === 0 ? (
                    <option value="">No compatible sessions</option>
                  ) : null}
                  {compareCandidates.map((session) => (
                    <option key={session.id} value={session.id}>
                      {session.title}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={!activeSession || !compareTargetId || compareLoading}
                  onClick={() => {
                    if (!activeSession || !compareTargetId) {
                      return;
                    }
                    setCompareLoading(true);
                    setCompareError(null);
                    void loadCompare(activeSession.id, compareTargetId)
                      .catch((error) => {
                        setCompareError(error instanceof Error ? error.message : "Failed to compare sessions.");
                      })
                      .finally(() => {
                        setCompareLoading(false);
                      });
                  }}
                  className="rounded-md border border-[rgba(255,255,255,0.06)] px-3 py-2 text-[11px] text-[var(--color-text-secondary)] transition-colors hover:bg-white/[0.03] hover:text-[var(--color-text-primary)] disabled:opacity-40"
                >
                  {compareLoading ? "Comparing..." : "Compare"}
                </button>
              </div>
              {compareError ? (
                <div className="mt-2 rounded-md border border-[rgba(255,103,100,0.16)] bg-[rgba(255,103,100,0.08)] px-2.5 py-1.5 text-[11px] text-[var(--color-text-error)]">
                  {compareError}
                </div>
              ) : null}
              {compareResult ? (
                <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-[var(--color-text-tertiary)]">
                  <span className="rounded-full border border-[rgba(255,255,255,0.06)] px-2 py-1">
                    Shared prefix {compareResult.overview.shared_prefix_count}
                  </span>
                  <span className="rounded-full border border-[rgba(255,255,255,0.06)] px-2 py-1">
                    Left {compareResult.overview.left_total}
                  </span>
                  <span className="rounded-full border border-[rgba(255,255,255,0.06)] px-2 py-1">
                    Right {compareResult.overview.right_total}
                  </span>
                </div>
              ) : null}
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-3">
              {compareResult ? (
                <div className="flex flex-col gap-3">
                  {compareResult.rows.map((row) => (
                    <section key={row.index} className="rounded-[16px] border border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.015)] p-3">
                      <div className={`mb-2 text-[11px] uppercase tracking-[0.08em] ${statusTone(row.status)}`}>
                        Step {row.index + 1} · {row.status.replace("_", " ")}
                      </div>
                      <div className="grid gap-3 lg:grid-cols-2">
                        <CompareCell title="left" row={row} />
                        <CompareCell title="right" row={row} />
                      </div>
                    </section>
                  ))}
                </div>
              ) : (
                <div className="flex h-full items-center justify-center text-center text-[13px] text-[var(--color-text-tertiary)]">
                  Choose a sibling session to compare against the active one.
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="border-b border-[rgba(255,255,255,0.06)] px-4 py-3">
              {replayError ? (
                <div className="rounded-md border border-[rgba(255,103,100,0.16)] bg-[rgba(255,103,100,0.08)] px-2.5 py-1.5 text-[11px] text-[var(--color-text-error)]">
                  {replayError}
                </div>
              ) : null}
              {replayLoading ? (
                <div className="text-[12px] text-[var(--color-text-tertiary)]">Loading replay…</div>
              ) : replay && replay.total_frames > 0 ? (
                <>
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-[12px] text-[var(--color-text-secondary)]">
                      Frame {frameIndex + 1} of {replay.total_frames}
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        disabled={frameIndex <= 0}
                        onClick={() => setFrameIndex((current) => Math.max(current - 1, 0))}
                        className="rounded-md border border-[rgba(255,255,255,0.06)] px-2 py-1 text-[11px] text-[var(--color-text-secondary)] disabled:opacity-40"
                      >
                        Prev
                      </button>
                      <button
                        type="button"
                        disabled={frameIndex >= replay.total_frames - 1}
                        onClick={() => setFrameIndex((current) => Math.min(current + 1, replay.total_frames - 1))}
                        className="rounded-md border border-[rgba(255,255,255,0.06)] px-2 py-1 text-[11px] text-[var(--color-text-secondary)] disabled:opacity-40"
                      >
                        Next
                      </button>
                    </div>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={Math.max(replay.total_frames - 1, 0)}
                    value={frameIndex}
                    onChange={(event) => setFrameIndex(Number(event.target.value))}
                    className="mt-3 w-full"
                  />
                  <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                    {replay.markers.map((marker) => (
                      <button
                        key={`${marker.index}-${marker.kind}`}
                        type="button"
                        onClick={() => setFrameIndex(marker.index)}
                        className={[
                          "shrink-0 rounded-full border px-2 py-1 text-[11px] transition-colors",
                          marker.index === frameIndex
                            ? "border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.05)] text-[var(--color-text-primary)]"
                            : "border-[rgba(255,255,255,0.06)] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]",
                        ].join(" ")}
                      >
                        {marker.index + 1}. {marker.label}
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <div className="text-[12px] text-[var(--color-text-tertiary)]">
                  The active session has no replayable timeline items yet.
                </div>
              )}
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-4">
              {currentFrame ? (
                <div className="rounded-[16px] border border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.015)] p-4">
                  <div className="mb-3">
                    <div className="text-[11px] uppercase tracking-[0.08em] text-[var(--color-text-tertiary)]">
                      {currentFrame.summary.label}
                    </div>
                    {currentFrame.summary.excerpt ? (
                      <div className="mt-1 text-[12px] leading-[1.5] text-[var(--color-text-secondary)]">
                        {currentFrame.summary.excerpt}
                      </div>
                    ) : null}
                    <div className="mt-2 text-[11px] text-[var(--color-text-tertiary)]">
                      {new Date(currentFrame.ts).toLocaleString()}
                    </div>
                    <div className="mt-1 text-[11px] text-[var(--color-text-tertiary)]">
                      {frameCountLabel(currentFrame)}
                    </div>
                  </div>
                  {renderReplayItem(currentFrame.item)}
                </div>
              ) : (
                <div className="flex h-full items-center justify-center text-center text-[13px] text-[var(--color-text-tertiary)]">
                  Open replay on a session with recorded activity.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
