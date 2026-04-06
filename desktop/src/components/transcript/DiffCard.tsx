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
    <div className="rounded-[18px] border border-border-default bg-[rgba(255,255,255,0.025)]">
      <div className="flex items-center gap-2 border-b border-border-light px-4 py-3">
        <span className="rounded-full border border-border-light px-2 py-0.5 text-[11px] text-text-secondary">
          Edit
        </span>
        <span className="truncate text-[12px] text-text-tertiary">{filePath}</span>
      </div>
      <div className="max-h-[260px] overflow-auto px-4 py-3 font-mono text-[12px]">
        {rows.map((row, index) => (
          <div
            key={`${filePath}-${index}`}
            className={[
              "whitespace-pre-wrap rounded px-2 py-1 leading-[1.45]",
              row.kind === "add" ? "bg-[rgba(64,201,119,0.12)] text-[#d7ffe6]" : "",
              row.kind === "remove" ? "bg-[rgba(255,103,100,0.12)] text-[#ffd6d4]" : "",
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
