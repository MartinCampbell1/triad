interface Props {
  command: string;
  output?: string;
  status?: "running" | "completed" | "failed";
}

export function BashCard({ command, output, status = "completed" }: Props) {
  return (
    <details className="group py-1">
      <summary className="flex cursor-pointer list-none items-center gap-2 py-1 text-[13px] text-text-secondary">
        {status === "running" ? (
          <span className="h-2 w-2 animate-pulse rounded-full bg-[#339cff]" />
        ) : (
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" className="text-green-300">
            <path d="M3 8L7 12L13 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
        <span className="text-text-secondary">Запущен</span>
        <span className="min-w-0 truncate font-mono text-[12px] text-text-tertiary">{command.slice(0, 80)}</span>
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none" className="ml-auto flex-shrink-0 text-text-tertiary transition-transform group-open:rotate-180">
          <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </summary>
      <div className="mt-2 space-y-2">
        <pre className="overflow-x-auto rounded-lg bg-[rgba(0,0,0,0.3)] p-3 font-mono text-[12px] leading-[1.5] text-text-primary">
          {command}
        </pre>
        {output ? (
          <pre className="max-h-[300px] overflow-auto rounded-lg bg-[rgba(0,0,0,0.3)] p-3 font-mono text-[12px] leading-[1.5] text-text-secondary">
            {output}
          </pre>
        ) : null}
      </div>
    </details>
  );
}
