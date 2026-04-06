import { lazy, Suspense, useState } from "react";

interface Props {
  content: string;
}

const Markdown = lazy(async () => {
  const module = await import("./Markdown");
  return { default: module.Markdown };
});

export function AssistantMessage({ content }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    void navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="group py-1.5">
      <div className="text-[13px] leading-[1.6] text-[var(--color-text-primary)]">
        <Suspense fallback={<div className="whitespace-pre-wrap">{content}</div>}>
          <Markdown content={content} />
        </Suspense>
      </div>
      {/* Copy button — hidden by default, shown on hover (like Codex) */}
      <div className="mt-1 flex items-center opacity-0 transition-opacity duration-150 group-hover:opacity-100">
        <button
          onClick={handleCopy}
          className="flex h-6 w-6 items-center justify-center rounded text-[var(--color-text-tertiary)] transition-colors duration-150 hover:text-[var(--color-text-secondary)]"
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
    </div>
  );
}
