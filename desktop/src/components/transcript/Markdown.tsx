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
        p: ({ children }) => <p className="my-0 whitespace-pre-wrap leading-[1.6] text-text-primary">{children}</p>,
        a: ({ children, href }) => (
          <a href={href} className="text-text-accent underline decoration-white/20 underline-offset-2">
            {children}
          </a>
        ),
        code: ({ children, className }) => (
          <code
            className={[
              "rounded-md border border-border-light bg-black/30 px-1.5 py-0.5 font-mono text-[12px] text-text-primary",
              className ?? "",
            ].join(" ")}
          >
            {children}
          </code>
        ),
        pre: ({ children }) => (
          <pre className="overflow-x-auto rounded-xl border border-border-default bg-black/30 p-4 font-mono text-[12px] leading-[1.55] text-text-primary shadow-glow">
            {children}
          </pre>
        ),
        ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5 text-text-primary">{children}</ul>,
        ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5 text-text-primary">{children}</ol>,
        li: ({ children }) => <li className="pl-1">{children}</li>,
        blockquote: ({ children }) => (
          <blockquote className="my-3 border-l-2 border-border-default pl-4 text-text-secondary">{children}</blockquote>
        ),
        table: ({ children }) => (
          <div className="my-3 overflow-x-auto">
            <table className="w-full border-collapse text-left text-[12px]">{children}</table>
          </div>
        ),
        th: ({ children }) => <th className="border-b border-border-default px-3 py-2 font-medium text-text-secondary">{children}</th>,
        td: ({ children }) => <td className="border-b border-border-light px-3 py-2 align-top text-text-primary">{children}</td>,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
