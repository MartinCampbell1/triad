import { buildStructuredDiffFile } from "../../lib/diff";

interface Props {
  filePath: string;
  oldText: string;
  newText: string;
}

export function DiffCard({ filePath, oldText, newText }: Props) {
  const diff = buildStructuredDiffFile({
    path: filePath,
    oldContent: oldText,
    newContent: newText,
  });
  const previewLines = diff.hunks.flatMap((hunk) => hunk.lines).slice(0, 24);

  return (
    <div className="py-1">
      <div className="flex items-center gap-2 py-1 text-[12px] text-text-tertiary">
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" className="text-green-300">
          <path d="M3 8L7 12L13 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span>{diff.status === "added" ? "Create" : diff.status === "deleted" ? "Delete" : "Edit"}</span>
        <span className="text-text-secondary">{filePath}</span>
        <span className="text-[var(--color-text-success)]">+{diff.additions}</span>
        <span className="text-[var(--color-text-error)]">-{diff.deletions}</span>
      </div>
      <div className="mt-1 max-h-[260px] overflow-auto rounded-lg bg-[rgba(0,0,0,0.3)] font-mono text-[12px] leading-[1.5]">
        {previewLines.map((line, index) => (
          <div
            key={`${filePath}-${index}`}
            className={[
              "grid grid-cols-[48px_48px_20px_minmax(0,1fr)] px-2",
              line.kind === "add" ? "bg-[rgba(64,201,119,0.1)]" : "",
              line.kind === "remove" ? "bg-[rgba(255,103,100,0.1)]" : "",
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
        ))}
      </div>
    </div>
  );
}
