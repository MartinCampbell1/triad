import { useState } from "react";

interface Props {
  command: string;
  output?: string;
  status?: "running" | "completed" | "failed";
}

export function BashCard({ command, output, status = "completed" }: Props) {
  const isRunning = status === "running";
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    const text = output ? `$ ${command}\n${output}` : `$ ${command}`;
    void navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="py-1">
      {/* Inline status line */}
      <div className="flex items-center gap-2 py-0.5 text-[13px] text-[var(--color-text-secondary)]">
        {isRunning ? (
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="shrink-0 animate-spin text-[var(--color-text-secondary)]">
            <path d="M8 2a6 6 0 014.9 9.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        ) : (
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" className="shrink-0 text-[var(--color-text-success)]">
            <path d="M3 8L7 12L13 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
        <span>Command</span>
        <span className="min-w-0 truncate font-[var(--font-mono)] text-[12px] text-[var(--color-text-tertiary)]">{command.slice(0, 120)}</span>
      </div>

      {isRunning ? (
        <div className="mt-1 text-[13px] text-[var(--color-text-tertiary)]">Running command...</div>
      ) : null}

      {output ? (
        <div className="group/shell relative mt-2 overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)]">
          <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-2">
            <span className="text-[12px] text-[var(--color-text-secondary)]">Shell</span>
            <button
              onClick={handleCopy}
              className="flex h-6 w-6 items-center justify-center rounded text-[var(--color-text-tertiary)] opacity-0 transition-all duration-150 hover:text-[var(--color-text-secondary)] group-hover/shell:opacity-100"
              title="Copy"
            >
              {copied ? (
                <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
                  <path d="M3 8L7 12L13 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : (
                <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
                  <rect x="5" y="5" width="9" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
                  <path d="M11 5V3.5A1.5 1.5 0 009.5 2h-6A1.5 1.5 0 002 3.5v6A1.5 1.5 0 003.5 11H5" stroke="currentColor" strokeWidth="1.2" />
                </svg>
              )}
            </button>
          </div>
          <pre className="max-h-[400px] overflow-auto p-4 font-[var(--font-mono)] text-[12px] leading-[1.6] text-[var(--color-text-secondary)]">
<span className="text-[var(--color-text-tertiary)]">$ </span><span className="text-[var(--color-text-primary)]">{command}</span>
{"\n"}{output}</pre>
        </div>
      ) : null}
    </div>
  );
}
