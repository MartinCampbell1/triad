interface Props {
  title?: string;
  text: string;
  tone?: "info" | "warning" | "error";
}

const toneClass = {
  info: "text-text-tertiary",
  warning: "text-[var(--color-text-warning)]",
  error: "text-[var(--color-text-error)]",
};

export function SystemMessage({ title, text, tone = "info" }: Props) {
  return (
    <div className={`py-1.5 text-center text-[12px] ${toneClass[tone]}`}>
      {title ? <div className="mb-0.5 text-[11px] uppercase tracking-[0.08em] opacity-80">{title}</div> : null}
      <div>{text}</div>
    </div>
  );
}
