interface Props {
  tool: string;
  input: unknown;
  output?: unknown;
  status: "running" | "completed" | "failed";
}

function statusIcon(status: string) {
  if (status === "running") {
    return (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="animate-spin text-[var(--color-text-secondary)]">
        <path d="M8 2a6 6 0 014.9 9.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }
  if (status === "failed") {
    return <span className="h-2 w-2 rounded-full bg-[var(--color-text-error)]" />;
  }
  return null;
}

function formatInput(input: unknown): { summary: string; filePath: string | null; operation: string | null; diffStats: { additions: number; deletions: number } | null; isNew: boolean } {
  const result = { summary: "", filePath: null as string | null, operation: null as string | null, diffStats: null as { additions: number; deletions: number } | null, isNew: false };

  if (typeof input !== "object" || input === null) {
    if (typeof input === "string") result.summary = input;
    return result;
  }

  const obj = input as Record<string, unknown>;

  if (obj.file_path || obj.path) {
    result.filePath = String(obj.file_path ?? obj.path);
  }

  if (obj.old_string !== undefined || obj.new_string !== undefined) {
    const oldStr = String(obj.old_string ?? "");
    const newStr = String(obj.new_string ?? "");
    const oldLines = oldStr ? oldStr.split("\n").length : 0;
    const newLines = newStr ? newStr.split("\n").length : 0;
    result.operation = oldStr ? "Edited" : "Created";
    result.isNew = !oldStr;
    result.diffStats = { additions: newLines, deletions: oldLines };
  } else if (obj.content !== undefined) {
    const content = String(obj.content);
    result.operation = "Created";
    result.isNew = true;
    result.diffStats = { additions: content.split("\n").length, deletions: 0 };
  }

  if (obj.command) result.summary = String(obj.command).slice(0, 80);
  else if (obj.pattern) result.summary = String(obj.pattern);
  else if (obj.query) result.summary = String(obj.query);
  else if (obj.file_path) result.summary = String(obj.file_path);

  return result;
}

const READ_TOOLS = new Set(["Read", "Grep", "Glob", "Search", "LSP"]);

export function ToolCard({ tool, input, output, status }: Props) {
  const info = formatInput(input);
  const isFileOp = info.filePath && info.operation;

  if (isFileOp && info.diffStats) {
    const fileName = info.filePath!.split("/").pop();
    return (
      <div className="flex items-center gap-2 py-0.5 text-[13px]">
        {statusIcon(status)}
        <span className="text-[var(--color-text-secondary)]">{info.operation}</span>
        <span className="font-semibold text-[var(--color-text-accent)]">{fileName}</span>
        <span className="text-[var(--color-text-success)]">+{info.diffStats.additions}</span>
        <span className="text-[var(--color-text-error)]">-{info.diffStats.deletions}</span>
      </div>
    );
  }

  if (READ_TOOLS.has(tool)) {
    return (
      <div className="flex items-center gap-2 py-0.5 text-[13px] text-[var(--color-text-secondary)]">
        {statusIcon(status)}
        <span>Read</span>
        {info.summary ? (
          <span className="min-w-0 truncate text-[var(--color-text-tertiary)]">{info.summary}</span>
        ) : null}
      </div>
    );
  }

  // Generic tool — flat inline
  return (
    <div className="flex items-center gap-2 py-0.5 text-[13px] text-[var(--color-text-secondary)]">
      {statusIcon(status)}
      <span className="text-[var(--color-text-tertiary)]">{tool}</span>
      {info.summary ? (
        <span className="min-w-0 truncate text-[var(--color-text-tertiary)]">{info.summary}</span>
      ) : null}
    </div>
  );
}
