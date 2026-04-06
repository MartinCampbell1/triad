interface Props {
  tool: string;
  input: unknown;
  output?: unknown;
  status: "running" | "completed" | "failed";
}

export function ToolCard({ tool, input, output, status }: Props) {
  return (
    <details className="group rounded-[18px] border border-border-default bg-[rgba(255,255,255,0.025)] px-4 py-3">
      <summary className="cursor-pointer list-none text-[13px] text-text-primary">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="rounded-full border border-border-light px-2 py-0.5 text-[11px] text-text-secondary">
              {tool}
            </span>
            <span className="text-[11px] uppercase tracking-[0.12em] text-text-tertiary">{status}</span>
          </div>
          <span className="text-text-tertiary transition-transform group-open:rotate-180">▾</span>
        </div>
      </summary>
      <div className="mt-3 space-y-3 text-[12px] leading-[1.6] text-text-secondary">
        <div>
          <div className="mb-1 text-[11px] uppercase tracking-[0.12em] text-text-tertiary">Input</div>
          <pre className="overflow-x-auto rounded-xl border border-border-light bg-black/25 p-3 font-mono text-[12px] text-text-primary">
            {typeof input === "string" ? input : JSON.stringify(input, null, 2)}
          </pre>
        </div>
        {output ? (
          <div>
            <div className="mb-1 text-[11px] uppercase tracking-[0.12em] text-text-tertiary">Output</div>
            <pre className="overflow-x-auto rounded-xl border border-border-light bg-black/25 p-3 font-mono text-[12px] text-text-primary">
              {typeof output === "string" ? output : JSON.stringify(output, null, 2)}
            </pre>
          </div>
        ) : null}
      </div>
    </details>
  );
}
