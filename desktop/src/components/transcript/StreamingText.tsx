interface Props {
  text: string;
  provider?: string | null;
  role?: string | null;
}

export function StreamingText({ text }: Props) {
  if (!text.trim()) {
    return null;
  }

  return (
    <div className="py-1.5">
      <div className="whitespace-pre-wrap text-[13px] leading-[1.6] text-[var(--color-text-primary)]">
        {text}
        <span className="ml-0.5 inline-block h-[13px] w-[2px] animate-pulse rounded-full bg-[var(--color-text-secondary)] align-text-bottom" />
      </div>
    </div>
  );
}
