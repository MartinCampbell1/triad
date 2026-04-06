import { useMemo, useRef, useState } from "react";
import {
  composeStructuredDiffPatch,
  diffHunkSelectionKey,
  summarizeStructuredDiffSelection,
  type DiffHunk,
  type StructuredDiffFile,
} from "../../lib/diff";
import { rpc } from "../../lib/rpc";
import type { ReviewFindingTimelineItem } from "../../lib/types";
import { useSessionStore } from "../../stores/session-store";
import { useUiStore } from "../../stores/ui-store";

interface Props {
  files: StructuredDiffFile[];
}

const statusLabel: Record<StructuredDiffFile["status"], string> = {
  added: "Added",
  modified: "Modified",
  deleted: "Deleted",
  renamed: "Renamed",
};

type SelectionState = "none" | "partial" | "all";

function statusTone(status: StructuredDiffFile["status"]) {
  switch (status) {
    case "added":
      return "text-[var(--color-text-success)]";
    case "deleted":
      return "text-[var(--color-text-error)]";
    default:
      return "text-[var(--color-text-tertiary)]";
  }
}

function lineKey(filePath: string, line: number) {
  return `${filePath}:${line}`;
}

function downloadPatch(filename: string, patch: string) {
  const blob = new Blob([patch], { type: "text/x-diff;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function selectionLabel(summary: ReturnType<typeof summarizeStructuredDiffSelection>) {
  if (summary.totalHunks === 0 || summary.selectedHunks === 0) {
    return "No hunks selected. Actions use the full patch.";
  }

  if (summary.selectedHunks === summary.totalHunks) {
    return "All hunks selected.";
  }

  const fileCount = summary.selectedFiles + summary.partialFiles;
  return `${summary.selectedHunks} of ${summary.totalHunks} hunks selected across ${fileCount} ${fileCount === 1 ? "file" : "files"}.`;
}

function fileSelectionState(file: StructuredDiffFile, selectedSet: Set<string>): SelectionState {
  if (file.hunks.length === 0) {
    return "none";
  }

  const selectedCount = file.hunks.filter((hunk) => selectedSet.has(diffHunkSelectionKey(file.path, hunk.id))).length;
  if (selectedCount === 0) {
    return "none";
  }
  if (selectedCount === file.hunks.length) {
    return "all";
  }
  return "partial";
}

function selectionTone(state: SelectionState) {
  switch (state) {
    case "all":
      return "border-[rgba(255,255,255,0.10)] bg-[rgba(255,255,255,0.08)] text-text-primary";
    case "partial":
      return "border-[rgba(255,255,255,0.10)] bg-[rgba(255,255,255,0.05)] text-text-primary";
    default:
      return "border-[rgba(255,255,255,0.06)] text-text-tertiary hover:border-[rgba(255,255,255,0.10)] hover:text-text-primary";
  }
}

function selectionGlyph(state: SelectionState) {
  if (state === "all") {
    return "x";
  }
  if (state === "partial") {
    return "-";
  }
  return "";
}

function hunkButtonTone(selected: boolean) {
  return selected
    ? "border-[rgba(255,255,255,0.10)] bg-[rgba(255,255,255,0.07)] text-text-primary"
    : "border-[rgba(255,255,255,0.06)] text-text-tertiary hover:border-[rgba(255,255,255,0.10)] hover:text-text-primary";
}

function fileHeaderTone(selected: SelectionState, active: boolean) {
  const base = active
    ? "border-[rgba(255,255,255,0.10)] bg-[rgba(255,255,255,0.05)]"
    : "border-transparent hover:border-[rgba(255,255,255,0.05)] hover:bg-[rgba(255,255,255,0.02)]";
  if (selected === "all") {
    return `${base} ring-1 ring-inset ring-[rgba(255,255,255,0.06)]`;
  }
  if (selected === "partial") {
    return `${base} ring-1 ring-inset ring-[rgba(255,210,64,0.20)]`;
  }
  return base;
}

export function DiffPanel({ files }: Props) {
  const { diffPanelOpen, toggleDiffPanel, activeDiffPath, setActiveDiffPath, clearDiffFiles } = useUiStore();
  const activeSession = useSessionStore((state) => state.activeSession);
  const timeline = useSessionStore((state) => state.timeline);
  const activeFile = files.find((file) => file.path === activeDiffPath) ?? files[0] ?? null;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [reviewAction, setReviewAction] = useState<"apply" | "abandon" | null>(null);
  const [selectedHunkKeys, setSelectedHunkKeys] = useState<string[]>([]);

  const selectedHunkSet = useMemo(() => new Set(selectedHunkKeys), [selectedHunkKeys]);
  const selectionSummary = useMemo(
    () => summarizeStructuredDiffSelection(files, selectedHunkKeys),
    [files, selectedHunkKeys]
  );
  const selectedPatch = useMemo(
    () => composeStructuredDiffPatch(files, selectedHunkKeys),
    [files, selectedHunkKeys]
  );
  const exportFilename = useMemo(() => {
    const seed = activeSession?.title?.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-") || "triad-review";
    return `${seed.slice(0, 48) || "triad-review"}.patch`;
  }, [activeSession?.title]);

  const findings = useMemo(
    () =>
      timeline.filter(
        (item): item is ReviewFindingTimelineItem =>
          item.kind === "review_finding" && (!activeFile || item.file === activeFile.path)
      ),
    [activeFile, timeline]
  );

  const highlightedLines = useMemo(() => {
    const next = new Set<string>();
    for (const finding of findings) {
      if (finding.line) {
        next.add(lineKey(finding.file, finding.line));
      }
    }
    return next;
  }, [findings]);

  const selectionMessage = selectionLabel(selectionSummary);
  const applyLabel = selectedHunkKeys.length === 0 ? "Apply all changes" : "Apply selected patch";
  const copyLabel = selectedHunkKeys.length === 0 ? "Copy all changes" : "Copy selected patch";
  const exportLabel = selectedHunkKeys.length === 0 ? "Export all changes" : "Export selected patch";

  const jumpToLine = (line?: number) => {
    if (!line || !activeFile) {
      return;
    }
    const target = containerRef.current?.querySelector<HTMLElement>(
      `[data-line-key="${lineKey(activeFile.path, line)}"]`
    );
    target?.scrollIntoView({ block: "center", behavior: "smooth" });
  };

  const scrollToHunk = (hunk: DiffHunk) => {
    const target = containerRef.current?.querySelector<HTMLElement>(`#${hunk.id}`);
    target?.scrollIntoView({ block: "start", behavior: "smooth" });
  };

  const toggleSelection = (keys: string[]) => {
    setSelectedHunkKeys((current) => {
      const next = new Set(current);
      const allSelected = keys.length > 0 && keys.every((key) => next.has(key));
      if (allSelected) {
        for (const key of keys) {
          next.delete(key);
        }
      } else {
        for (const key of keys) {
          next.add(key);
        }
      }
      return [...next];
    });
  };

  const toggleFileSelection = (file: StructuredDiffFile) => {
    if (file.hunks.length === 0) {
      return;
    }
    toggleSelection(file.hunks.map((hunk) => diffHunkSelectionKey(file.path, hunk.id)));
  };

  const toggleHunkSelection = (file: StructuredDiffFile, hunk: DiffHunk) => {
    const key = diffHunkSelectionKey(file.path, hunk.id);
    setSelectedHunkKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return [...next];
    });
    scrollToHunk(hunk);
  };

  const selectAllHunks = () => {
    setSelectedHunkKeys(
      files.flatMap((file) => file.hunks.map((hunk) => diffHunkSelectionKey(file.path, hunk.id)))
    );
  };

  const clearSelection = () => setSelectedHunkKeys([]);

  const handleApplyPatch = async () => {
    if (!activeSession || !selectedPatch.trim()) {
      return;
    }
    setReviewError(null);
    setReviewAction("apply");
    try {
      await rpc("review.apply_patch", {
        session_id: activeSession.id,
        patch: selectedPatch,
      });
      clearDiffFiles();
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "Failed to apply review patch.");
    } finally {
      setReviewAction(null);
    }
  };

  const handleCopyPatch = async () => {
    if (!selectedPatch.trim()) {
      return;
    }
    await navigator.clipboard.writeText(selectedPatch);
  };

  const handleExportPatch = () => {
    if (!selectedPatch.trim()) {
      return;
    }
    downloadPatch(exportFilename, selectedPatch);
  };

  const handleAbandonReview = async () => {
    setReviewError(null);
    setReviewAction("abandon");
    try {
      if (activeSession) {
        await rpc("review.abandon", { session_id: activeSession.id });
      }
    } catch {
      // Clearing the local review surface is still the primary outcome.
    } finally {
      clearDiffFiles();
      setSelectedHunkKeys([]);
      setReviewAction(null);
    }
  };

  if (!diffPanelOpen) {
    return null;
  }

  return (
    <aside className="flex w-[46%] min-w-[420px] border-l border-[rgba(255,255,255,0.06)] bg-[var(--color-bg-editor)]">
      <div className="flex w-[240px] shrink-0 flex-col border-r border-[rgba(255,255,255,0.06)]">
        <div className="border-b border-[rgba(255,255,255,0.06)] px-3 py-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="text-[11px] uppercase tracking-[0.1em] text-text-tertiary">Review</div>
              <div className="mt-1 text-[13px] text-text-primary">
                {files.length > 0 ? `${files.length} changed ${files.length === 1 ? "file" : "files"}` : "No changes"}
              </div>
            </div>
            <span className="rounded-full border border-[rgba(255,255,255,0.06)] px-2 py-0.5 text-[10px] uppercase tracking-[0.08em] text-text-tertiary">
              {selectionSummary.selectedHunks === 0 ? "Full patch" : "Selected"}
            </span>
          </div>
          <div className="mt-2 text-[11px] text-text-tertiary">{selectionMessage}</div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={selectAllHunks}
              disabled={files.length === 0}
              className="rounded-md border border-[rgba(255,255,255,0.06)] px-2 py-1 text-[11px] text-text-secondary transition-colors hover:bg-white/[0.03] hover:text-text-primary disabled:opacity-40"
            >
              Select all
            </button>
            <button
              type="button"
              onClick={clearSelection}
              disabled={selectedHunkKeys.length === 0}
              className="rounded-md border border-[rgba(255,255,255,0.06)] px-2 py-1 text-[11px] text-text-secondary transition-colors hover:bg-white/[0.03] hover:text-text-primary disabled:opacity-40"
            >
              Clear selection
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-2">
          {files.map((file) => {
            const selectionState = fileSelectionState(file, selectedHunkSet);
            const active = file.path === activeFile?.path;
            return (
              <div key={file.path} className="mb-1 flex items-stretch gap-2">
                <button
                  type="button"
                  onClick={() => setActiveDiffPath(file.path)}
                  className={[
                    "min-w-0 flex-1 rounded-lg border px-3 py-2 text-left transition-colors",
                    fileHeaderTone(selectionState, active),
                  ].join(" ")}
                >
                  <div className="truncate text-[12px] text-text-primary">{file.path.split("/").pop() ?? file.path}</div>
                  <div className="mt-1 flex items-center gap-2 text-[11px]">
                    <span className={statusTone(file.status)}>{statusLabel[file.status]}</span>
                    <span className="text-[var(--color-text-success)]">+{file.additions}</span>
                    <span className="text-[var(--color-text-error)]">-{file.deletions}</span>
                    <span className="text-text-tertiary">{file.hunks.length} hunks</span>
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => toggleFileSelection(file)}
                  disabled={file.hunks.length === 0}
                  aria-label={`Toggle selection for ${file.path}`}
                  className={[
                    "flex h-[48px] w-[28px] shrink-0 items-center justify-center rounded-lg border text-[10px] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-40",
                    selectionTone(selectionState),
                  ].join(" ")}
                  title={selectionState === "all" ? "Clear file selection" : "Select all hunks in file"}
                >
                  <span aria-hidden="true">{selectionGlyph(selectionState)}</span>
                </button>
              </div>
            );
          })}
        </div>
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-start justify-between gap-3 border-b border-[rgba(255,255,255,0.06)] px-4 py-3">
          <div className="min-w-0">
            {activeFile ? (
              <>
                <div className="truncate text-[13px] text-text-primary">{activeFile.path}</div>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-text-tertiary">
                  <span className={statusTone(activeFile.status)}>{statusLabel[activeFile.status]}</span>
                  <span>{activeFile.hunks.length} hunks</span>
                  {findings.length > 0 ? <span>{findings.length} findings</span> : null}
                  <span className="rounded-full border border-[rgba(255,255,255,0.06)] px-2 py-0.5 text-[10px] uppercase tracking-[0.08em] text-text-tertiary">
                    {selectionSummary.selectedHunks === 0 ? "Fallback: full patch" : "Selected patch"}
                  </span>
                </div>
              </>
            ) : (
              <div className="text-[13px] text-text-tertiary">No files to diff</div>
            )}
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => void handleApplyPatch()}
              disabled={!activeSession || !selectedPatch.trim() || reviewAction !== null}
              className="rounded-md border border-[rgba(255,255,255,0.06)] px-2.5 py-1 text-[11px] text-text-secondary transition-colors hover:bg-white/[0.03] hover:text-text-primary disabled:opacity-40"
            >
              {reviewAction === "apply" ? "Applying..." : applyLabel}
            </button>
            <button
              type="button"
              onClick={() => void handleCopyPatch()}
              disabled={!selectedPatch.trim()}
              className="rounded-md border border-[rgba(255,255,255,0.06)] px-2.5 py-1 text-[11px] text-text-secondary transition-colors hover:bg-white/[0.03] hover:text-text-primary disabled:opacity-40"
            >
              {copyLabel}
            </button>
            <button
              type="button"
              onClick={() => handleExportPatch()}
              disabled={!selectedPatch.trim()}
              className="rounded-md border border-[rgba(255,255,255,0.06)] px-2.5 py-1 text-[11px] text-text-secondary transition-colors hover:bg-white/[0.03] hover:text-text-primary disabled:opacity-40"
            >
              {exportLabel}
            </button>
            <button
              type="button"
              onClick={() => void handleAbandonReview()}
              disabled={reviewAction !== null}
              className="rounded-md border border-[rgba(255,255,255,0.06)] px-2.5 py-1 text-[11px] text-text-secondary transition-colors hover:bg-white/[0.03] hover:text-text-primary"
            >
              {reviewAction === "abandon" ? "Abandoning..." : "Abandon review"}
            </button>
            <button
              type="button"
              onClick={toggleDiffPanel}
              className="flex h-6 w-6 items-center justify-center rounded text-text-tertiary hover:text-text-secondary"
            >
              <svg width="10" height="10" viewBox="0 0 16 16" fill="none">
                <path d="M4 4L12 12M12 4L4 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        </div>

        {activeFile ? (
          <>
            <div className="border-b border-[rgba(255,255,255,0.06)] px-4 py-2">
              {reviewError ? (
                <div className="mb-2 rounded-md border border-[rgba(255,103,100,0.16)] bg-[rgba(255,103,100,0.08)] px-2.5 py-1.5 text-[11px] text-[var(--color-text-error)]">
                  {reviewError}
                </div>
              ) : null}
              <div className="flex flex-wrap gap-1.5">
                {activeFile.hunks.map((hunk) => {
                  const key = diffHunkSelectionKey(activeFile.path, hunk.id);
                  const selected = selectedHunkSet.has(key);
                  return (
                    <button
                      key={hunk.id}
                      type="button"
                      onClick={() => toggleHunkSelection(activeFile, hunk)}
                      className={[
                        "rounded-md border px-2 py-0.5 text-[11px] transition-colors",
                        hunkButtonTone(selected),
                      ].join(" ")}
                      title={selected ? "Remove hunk from selected patch" : "Add hunk to selected patch"}
                    >
                      <span className="mr-1.5">{selected ? "✓" : "+"}</span>
                      {hunk.header}
                    </button>
                  );
                })}
              </div>
              {findings.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {findings.map((finding) => (
                    <button
                      key={finding.id}
                      type="button"
                      onClick={() => jumpToLine(finding.line)}
                      className="rounded-md bg-[rgba(255,255,255,0.03)] px-2 py-0.5 text-[11px] text-text-secondary transition-colors hover:bg-[rgba(255,255,255,0.05)] hover:text-text-primary"
                    >
                      {finding.severity} {finding.line ? `L${finding.line}` : ""} {finding.title}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            <div ref={containerRef} className="flex-1 overflow-y-auto font-mono text-[12px] leading-[1.5]">
              {activeFile.hunks.length === 0 ? (
                <div className="flex h-full items-center justify-center text-[13px] text-text-tertiary">
                  No hunks available
                </div>
              ) : (
                activeFile.hunks.map((hunk) => {
                  const selected = selectedHunkSet.has(diffHunkSelectionKey(activeFile.path, hunk.id));
                  return (
                    <section
                      key={hunk.id}
                      id={hunk.id}
                      className={[
                        "border-b border-[rgba(255,255,255,0.04)]",
                        selected ? "bg-[rgba(255,255,255,0.025)]" : "",
                      ].join(" ")}
                    >
                      <div className="sticky top-0 z-[1] flex items-center justify-between gap-2 bg-[rgba(255,255,255,0.03)] px-4 py-1 text-[11px] text-text-tertiary">
                        <span>{hunk.header}</span>
                        <span className="rounded-full border border-[rgba(255,255,255,0.06)] px-1.5 py-0.5 text-[10px] uppercase tracking-[0.08em]">
                          {selected ? "selected" : "idle"}
                        </span>
                      </div>
                      {hunk.lines.map((line, index) => {
                        const highlight =
                          (line.oldLineNumber && highlightedLines.has(lineKey(activeFile.path, line.oldLineNumber))) ||
                          (line.newLineNumber && highlightedLines.has(lineKey(activeFile.path, line.newLineNumber)));
                        return (
                          <div
                            key={`${hunk.id}-${index}`}
                            data-line-key={
                              line.newLineNumber
                                ? lineKey(activeFile.path, line.newLineNumber)
                                : line.oldLineNumber
                                  ? lineKey(activeFile.path, line.oldLineNumber)
                                  : undefined
                            }
                            className={[
                              "grid grid-cols-[64px_64px_20px_minmax(0,1fr)] px-2",
                              line.kind === "add" ? "bg-[rgba(64,201,119,0.08)]" : "",
                              line.kind === "remove" ? "bg-[rgba(255,103,100,0.08)]" : "",
                              highlight ? "ring-1 ring-inset ring-[rgba(255,210,64,0.35)]" : "",
                            ].join(" ")}
                          >
                            <span className="select-none px-2 py-px text-right text-[11px] text-text-tertiary">
                              {line.oldLineNumber ?? ""}
                            </span>
                            <span className="select-none px-2 py-px text-right text-[11px] text-text-tertiary">
                              {line.newLineNumber ?? ""}
                            </span>
                            <span className="select-none px-1 py-px text-center text-text-tertiary">
                              {line.kind === "add" ? "+" : line.kind === "remove" ? "-" : " "}
                            </span>
                            <span
                              className={[
                                "whitespace-pre-wrap break-words px-2 py-px",
                                line.kind === "add" ? "text-[#c8f7d5]" : "",
                                line.kind === "remove" ? "text-[#ffd6d4]" : "",
                                line.kind === "context" ? "text-text-secondary" : "",
                              ].join(" ")}
                            >
                              {line.text}
                            </span>
                          </div>
                        );
                      })}
                    </section>
                  );
                })
              )}
            </div>
          </>
        ) : (
          <div className="flex h-full items-center justify-center text-[13px] text-text-tertiary">
            No files to diff
          </div>
        )}
      </div>
    </aside>
  );
}
