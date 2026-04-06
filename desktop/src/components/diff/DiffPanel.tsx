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
  const rows: Array<{ kind: "context" | "add" | "remove"; oldLine?: string; newLine?: string }> = [];

  for (let index = 0; index < max; index += 1) {
    const oldLine = oldLines[index];
    const newLine = newLines[index];
    if (oldLine === newLine) {
      rows.push({ kind: "context", oldLine, newLine });
      continue;
    }
    if (oldLine !== undefined) {
      rows.push({ kind: "remove", oldLine });
    }
    if (newLine !== undefined) {
      rows.push({ kind: "add", newLine });
    }
  }

  return rows;
}

function DiffFallback({ file }: { file: DiffFile }) {
  const rows = useMemo(() => lineDiff(file.oldContent, file.newContent), [file]);
  return (
    <div className="overflow-hidden rounded-[18px] border border-border-default bg-[rgba(255,255,255,0.02)]">
      <div className="flex items-center justify-between border-b border-border-light px-4 py-2">
        <div className="min-w-0">
          <div className="truncate text-[12px] font-medium text-text-primary">{file.path}</div>
          <div className="text-[11px] text-text-tertiary">Unified diff preview</div>
        </div>
        <span className="rounded-full border border-border-light px-2 py-1 text-[11px] text-text-tertiary">
          staged preview
        </span>
      </div>
      <div className="max-h-[60vh] overflow-auto">
        {rows.map((row, index) => (
          <div
            key={`${file.path}-${index}`}
            className={[
              "grid grid-cols-[56px_minmax(0,1fr)] gap-3 border-b border-border-light px-4 py-1.5 font-mono text-[12px] leading-[1.45]",
              row.kind === "add" ? "bg-[rgba(64,201,119,0.08)] text-[#d5ffe5]" : "",
              row.kind === "remove" ? "bg-[rgba(255,103,100,0.08)] text-[#ffd6d4]" : "",
              row.kind === "context" ? "text-[#d8d8d8]" : "",
            ].join(" ")}
          >
            <span className="select-none text-right text-[11px] text-text-tertiary">
              {row.kind === "remove" ? "-" : row.kind === "add" ? "+" : " "}
            </span>
            <span className="whitespace-pre-wrap break-words">
              {row.oldLine ?? row.newLine ?? ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function DiffPanel({ files }: Props) {
  const { diffPanelOpen, toggleDiffPanel, activeDiffPath, setActiveDiffPath } = useUiStore();
  const activeFile =
    files.find((file) => file.path === activeDiffPath) ??
    files[0] ??
    null;

  if (!diffPanelOpen) {
    return null;
  }

  return (
    <aside className="flex w-[44%] min-w-[360px] flex-col border-l border-border-light bg-[linear-gradient(180deg,rgba(255,255,255,0.015),transparent_25%),var(--color-bg-editor)]">
      <div className="flex h-10 items-center justify-between border-b border-border-light px-4">
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-medium text-text-primary">
            {files.length ? `${files.length} file${files.length === 1 ? "" : "s"}` : "No changes"}
          </span>
          <span className="rounded-full border border-border-light px-2 py-1 text-[11px] text-text-tertiary">
            Непоставленный
          </span>
        </div>
        <button
          type="button"
          onClick={toggleDiffPanel}
          className="rounded-md border border-border-light px-2 py-1 text-[11px] text-text-tertiary transition-colors hover:border-border-default hover:text-text-primary"
        >
          Close
        </button>
      </div>

      {files.length > 1 ? (
        <div className="flex gap-2 overflow-x-auto border-b border-border-light px-3 py-2">
          {files.map((file) => (
            <button
              key={file.path}
              type="button"
              onClick={() => setActiveDiffPath(file.path)}
              className={[
                "shrink-0 rounded-full px-3 py-1 text-[11px] transition-colors",
                file.path === activeFile?.path
                  ? "bg-elevated text-text-primary shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]"
                  : "text-text-tertiary hover:bg-elevated-secondary hover:text-text-primary",
              ].join(" ")}
            >
              {file.path.split("/").pop() ?? file.path}
            </button>
          ))}
        </div>
      ) : null}

      <div className="flex-1 overflow-auto p-3">
        {activeFile ? (
          <DiffFallback file={activeFile} />
        ) : (
          <div className="grid h-full place-items-center rounded-[18px] border border-dashed border-border-light bg-[rgba(255,255,255,0.015)] px-6 py-12 text-center">
            <div>
              <div className="text-[18px] text-text-primary">Diff panel</div>
              <p className="mt-2 max-w-[320px] text-[13px] leading-[1.6] text-text-tertiary">
                Open this panel when a file is staged or a patch is available. It is ready for react-diff-viewer-continued,
                but renders a high-quality fallback until the dependency is wired in.
              </p>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
