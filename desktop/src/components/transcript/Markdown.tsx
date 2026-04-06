import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

interface Props {
  content: string;
}

export function Markdown({ content }: Props) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight]}
      components={{
        p: ({ children }) => <p className="my-0 whitespace-pre-wrap leading-[1.6] text-[var(--color-text-primary)]">{children}</p>,
        a: ({ children, href }) => (
          <a href={href} className="text-[var(--color-text-accent)] underline decoration-[rgba(255,255,255,0.2)] underline-offset-2">
            {children}
          </a>
        ),
        code: ({ children, className }) => {
          const isBlock = className?.includes("language-");
          if (isBlock) {
            return <code className={className}>{children}</code>;
          }
          return (
            <code className="rounded-[4px] bg-[var(--color-bg-elevated)] px-[5px] py-[2px] font-[var(--font-mono)] text-[12px] text-[var(--color-text-primary)]">
              {children}
            </code>
          );
        },
        pre: ({ children }) => (
          <pre className="my-2 overflow-x-auto rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4 font-[var(--font-mono)] text-[12px] leading-[1.55] text-[var(--color-text-primary)]">
            {children}
          </pre>
        ),
        ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5 text-[var(--color-text-primary)]">{children}</ul>,
        ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5 text-[var(--color-text-primary)]">{children}</ol>,
        li: ({ children }) => <li className="pl-1">{children}</li>,
        blockquote: ({ children }) => (
          <blockquote className="my-3 border-l-2 border-[var(--color-border-heavy)] pl-4 text-[var(--color-text-secondary)]">{children}</blockquote>
        ),
        table: ({ children }) => (
          <div className="my-3 overflow-x-auto">
            <table className="w-full border-collapse text-left text-[12px]">{children}</table>
          </div>
        ),
        th: ({ children }) => <th className="border-b border-[var(--color-border-heavy)] px-3 py-2 font-medium text-[var(--color-text-secondary)]">{children}</th>,
        td: ({ children }) => <td className="border-b border-[var(--color-border)] px-3 py-2 align-top text-[var(--color-text-primary)]">{children}</td>,
        h1: ({ children }) => <h1 className="mb-2 mt-4 text-[18px] font-semibold text-[var(--color-text-primary)]">{children}</h1>,
        h2: ({ children }) => <h2 className="mb-2 mt-3 text-[16px] font-semibold text-[var(--color-text-primary)]">{children}</h2>,
        h3: ({ children }) => <h3 className="mb-1 mt-3 text-[14px] font-semibold text-[var(--color-text-primary)]">{children}</h3>,
        strong: ({ children }) => <strong className="font-semibold text-[var(--color-text-primary)]">{children}</strong>,
        em: ({ children }) => <em className="text-[var(--color-text-secondary)]">{children}</em>,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
