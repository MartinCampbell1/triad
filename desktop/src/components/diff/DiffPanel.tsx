import { useMemo } from "react";
import { useUiStore } from "../../stores/ui-store";
import type { DiffFile } from "../../lib/types";

interface Props {
  files: DiffFile[];
}

function lineDiff(oldValue: string, newValue: string) {
  const oldLines = oldValue.split("\n");
  const newLines = newValue.split("\n");
  const max = Math.max(oldLines.length, newLines.length);
  const rows: Array<{ kind: "context" | "add" | "remove"; oldLine?: string; newLine?: string; lineNo: number }> = [];

  for (let index = 0; index < max; index += 1) {
    const oldLine = oldLines[index];
    const newLine = newLines[index];
    if (oldLine === newLine) {
      rows.push({ kind: "context", oldLine, newLine, lineNo: index + 1 });
      continue;
    }
    if (oldLine !== undefined) {
      rows.push({ kind: "remove", oldLine, lineNo: index + 1 });
    }
    if (newLine !== undefined) {
      rows.push({ kind: "add", newLine, lineNo: index + 1 });
    }
  }

  return rows;
}

function DiffFallback({ file }: { file: DiffFile }) {
  const rows = useMemo(() => lineDiff(file.oldContent, file.newContent), [file]);
  return (
    <div className="h-full overflow-auto font-mono text-[12px] leading-[1.5]">
      {rows.map((row, index) => (
        <div
          key={`${file.path}-${index}`}
          className={[
            "flex",
            row.kind === "add" ? "bg-[rgba(64,201,119,0.1)]" : "",
            row.kind === "remove" ? "bg-[rgba(255,103,100,0.1)]" : "",
          ].join(" ")}
        >
          <span className="w-[50px] flex-shrink-0 select-none px-2 py-px text-right text-[11px] text-text-tertiary">
            {row.lineNo}
          </span>
          <span className="w-[20px] flex-shrink-0 select-none px-1 py-px text-center text-text-tertiary">
            {row.kind === "remove" ? "-" : row.kind === "add" ? "+" : " "}
          </span>
          <span className={[
            "flex-1 whitespace-pre-wrap break-words px-2 py-px",
            row.kind === "add" ? "text-[#c8f7d5]" : "",
            row.kind === "remove" ? "text-[#ffd6d4]" : "",
            row.kind === "context" ? "text-text-secondary" : "",
          ].join(" ")}>
            {row.oldLine ?? row.newLine ?? ""}
          </span>
        </div>
      ))}
    </div>
  );
}

export function DiffPanel({ files }: Props) {
  const { diffPanelOpen, toggleDiffPanel, activeDiffPath, setActiveDiffPath } = useUiStore();
  const activeFile = files.find((file) => file.path === activeDiffPath) ?? files[0] ?? null;

  if (!diffPanelOpen) {
    return null;
  }

  return (
    <aside className="flex w-[44%] min-w-[360px] flex-col border-l border-[rgba(255,255,255,0.06)] bg-[var(--color-bg-editor)]">
      {/* Header */}
      <div className="flex h-9 items-center justify-between border-b border-[rgba(255,255,255,0.06)] px-3">
        <div className="flex items-center gap-2">
          {activeFile ? (
            <span className="truncate text-[12px] text-text-primary">
              {activeFile.path.split("/").pop() ?? activeFile.path}
            </span>
          ) : (
            <span className="text-[12px] text-text-tertiary">No changes</span>
          )}
          <span className="text-[11px] text-text-tertiary">Непоставленный</span>
        </div>
        <button
          type="button"
          onClick={toggleDiffPanel}
          className="flex h-5 w-5 items-center justify-center rounded text-text-tertiary hover:text-text-secondary"
        >
          <svg width="10" height="10" viewBox="0 0 16 16" fill="none">
            <path d="M4 4L12 12M12 4L4 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {/* File tabs */}
      {files.length > 1 ? (
        <div className="flex gap-px overflow-x-auto border-b border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)]">
          {files.map((file) => (
            <button
              key={file.path}
              type="button"
              onClick={() => setActiveDiffPath(file.path)}
              className={[
                "px-3 py-1.5 text-[12px] transition-colors",
                file.path === activeFile?.path
                  ? "bg-[var(--color-bg-editor)] text-text-primary"
                  : "text-text-tertiary hover:text-text-secondary",
              ].join(" ")}
            >
              {file.path.split("/").pop() ?? file.path}
            </button>
          ))}
        </div>
      ) : null}

      {/* Diff content */}
      <div className="flex-1 overflow-hidden">
        {activeFile ? (
          <DiffFallback file={activeFile} />
        ) : (
          <div className="flex h-full items-center justify-center text-[13px] text-text-tertiary">
            No files to diff
          </div>
        )}
      </div>
    </aside>
  );
}
