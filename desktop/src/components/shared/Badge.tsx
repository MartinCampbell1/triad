import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  tone?: "neutral" | "subtle" | "accent";
  className?: string;
  title?: string;
  leading?: ReactNode;
}

const TONE_STYLES: Record<NonNullable<Props["tone"]>, string> = {
  neutral: "border-border-light bg-black/20 text-text-secondary",
  subtle: "border-border-light bg-white/5 text-text-tertiary",
  accent: "border-[rgba(51,156,255,0.28)] bg-accent-bg text-[#8cc7ff]",
};

export function Badge({ children, tone = "neutral", className = "", title, leading }: Props) {
  return (
    <span
      title={title}
      className={[
        "inline-flex max-w-full items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium leading-none",
        TONE_STYLES[tone],
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {leading ? <span className="shrink-0 text-[9px] leading-none">{leading}</span> : null}
      <span className="truncate">{children}</span>
    </span>
  );
}
