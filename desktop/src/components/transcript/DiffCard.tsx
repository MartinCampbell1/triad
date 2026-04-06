interface Props {
  filePath: string;
  oldText: string;
  newText: string;
}

function rowsFromDiff(oldText: string, newText: string) {
  const oldLines = oldText.split("\n");
  const newLines = newText.split("\n");
  const max = Math.max(oldLines.length, newLines.length);
  const rows: Array<{ kind: "context" | "add" | "remove"; text: string }> = [];

  for (let index = 0; index < max; index += 1) {
    const oldLine = oldLines[index];
    const newLine = newLines[index];
    if (oldLine === newLine) {
      if (oldLine !== undefined) {
        rows.push({ kind: "context", text: oldLine });
      }
      continue;
    }
    if (oldLine !== undefined) {
      rows.push({ kind: "remove", text: oldLine });
    }
    if (newLine !== undefined) {
      rows.push({ kind: "add", text: newLine });
    }
  }

  return rows;
}

export function DiffCard({ filePath, oldText, newText }: Props) {
  const rows = rowsFromDiff(oldText, newText).slice(0, 24);

  return (
    <div className="py-1">
      <div className="flex items-center gap-2 py-1 text-[12px] text-text-tertiary">
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" className="text-green-300">
          <path d="M3 8L7 12L13 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span>Edit</span>
        <span className="text-text-secondary">{filePath}</span>
      </div>
      <div className="mt-1 max-h-[260px] overflow-auto rounded-lg bg-[rgba(0,0,0,0.3)] font-mono text-[12px] leading-[1.5]">
        {rows.map((row, index) => (
          <div
            key={`${filePath}-${index}`}
            className={[
              "whitespace-pre-wrap px-3 py-px",
              row.kind === "add" ? "bg-[rgba(64,201,119,0.1)] text-[#c8f7d5]" : "",
              row.kind === "remove" ? "bg-[rgba(255,103,100,0.1)] text-[#ffd6d4]" : "",
              row.kind === "context" ? "text-text-secondary" : "",
            ].join(" ")}
          >
            {row.kind === "add" ? "+ " : row.kind === "remove" ? "- " : "  "}
            {row.text}
          </div>
        ))}
      </div>
    </div>
  );
}
