interface Props {
  tool: string;
  input: unknown;
  output?: unknown;
  status: "running" | "completed" | "failed";
}

function statusIcon(status: string) {
  if (status === "running") {
    return (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="animate-spin text-text-secondary">
        <path d="M8 2a6 6 0 014.9 9.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }
  if (status === "failed") {
    return <span className="h-2 w-2 rounded-full bg-red-300" />;
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

  // File operations
  if (obj.file_path || obj.path) {
    result.filePath = String(obj.file_path ?? obj.path);
  }

  // Detect operation type and compute diff stats
  if (obj.old_string !== undefined || obj.new_string !== undefined) {
    const oldStr = String(obj.old_string ?? "");
    const newStr = String(obj.new_string ?? "");
    const oldLines = oldStr ? oldStr.split("\n").length : 0;
    const newLines = newStr ? newStr.split("\n").length : 0;
    result.operation = oldStr ? "Редактирование" : "Создано";
    result.isNew = !oldStr;
    result.diffStats = {
      additions: newLines,
      deletions: oldLines,
    };
  } else if (obj.content !== undefined) {
    const content = String(obj.content);
    result.operation = "Создано";
    result.isNew = true;
    result.diffStats = {
      additions: content.split("\n").length,
      deletions: 0,
    };
  }

  // Fallback summary
  if (obj.command) result.summary = String(obj.command).slice(0, 80);
  else if (obj.pattern) result.summary = String(obj.pattern);
  else if (obj.query) result.summary = String(obj.query);
  else if (obj.file_path) result.summary = String(obj.file_path);

  return result;
}

const READ_TOOLS = new Set(["Read", "Grep", "Glob", "Search", "LSP"]);

function toolDisplayLabel(tool: string): { label: string; isRead: boolean } {
  if (READ_TOOLS.has(tool)) {
    return { label: "Изучение", isRead: true };
  }
  return { label: tool, isRead: false };
}

export function ToolCard({ tool, input, output, status }: Props) {
  const info = formatInput(input);
  const isFileOp = info.filePath && info.operation;

  // Codex-style file change badge
  if (isFileOp && info.diffStats) {
    return (
      <details className="group py-0.5">
        <summary className="flex cursor-pointer list-none items-center gap-2 py-1 text-[13px]">
          {statusIcon(status)}
          <span className="text-text-secondary">{info.operation}</span>
          <span className="font-mono text-[12px] text-text-accent">{info.filePath!.split("/").pop()}</span>
          <span className="text-[12px]">
            <span className="text-green-300">+{info.diffStats.additions}</span>
            {" "}
            <span className="text-red-300">-{info.diffStats.deletions}</span>
          </span>
          {info.isNew ? (
            <span className="h-[6px] w-[6px] rounded-full bg-[#339cff]" />
          ) : null}
          <svg width="10" height="10" viewBox="0 0 16 16" fill="none" className="ml-auto flex-shrink-0 text-text-tertiary transition-transform group-open:rotate-180">
            <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </summary>
        <div className="mt-1.5">
          {input ? (
            <pre className="overflow-x-auto rounded-lg bg-[rgba(0,0,0,0.3)] p-3 font-mono text-[12px] leading-[1.5] text-text-secondary">
              {typeof input === "string" ? input : JSON.stringify(input, null, 2)}
            </pre>
          ) : null}
          {output ? (
            <pre className="mt-1.5 overflow-x-auto rounded-lg bg-[rgba(0,0,0,0.3)] p-3 font-mono text-[12px] leading-[1.5] text-text-secondary">
              {typeof output === "string" ? output : JSON.stringify(output, null, 2)}
            </pre>
          ) : null}
        </div>
      </details>
    );
  }

  // Generic tool card
  const display = toolDisplayLabel(tool);
  return (
    <details className="group py-0.5">
      <summary className="flex cursor-pointer list-none items-center gap-2 py-1 text-[13px] text-text-secondary">
        {statusIcon(status)}
        <span className={display.isRead ? "text-text-secondary" : "text-text-tertiary"}>{display.label}</span>
        {info.summary ? (
          <span className="min-w-0 truncate text-text-tertiary">{info.summary}</span>
        ) : null}
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none" className="ml-auto flex-shrink-0 text-text-tertiary transition-transform group-open:rotate-180">
          <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </summary>
      <div className="mt-1.5 space-y-1.5">
        {input ? (
          <pre className="overflow-x-auto rounded-lg bg-[rgba(0,0,0,0.3)] p-3 font-mono text-[12px] leading-[1.5] text-text-secondary">
            {typeof input === "string" ? input : JSON.stringify(input, null, 2)}
          </pre>
        ) : null}
        {output ? (
          <pre className="overflow-x-auto rounded-lg bg-[rgba(0,0,0,0.3)] p-3 font-mono text-[12px] leading-[1.5] text-text-secondary">
            {typeof output === "string" ? output : JSON.stringify(output, null, 2)}
          </pre>
        ) : null}
      </div>
    </details>
  );
}
