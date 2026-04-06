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
    <div className="py-2">
      <div className="whitespace-pre-wrap text-[14px] leading-[1.6] text-text-primary">
        {text}
        <span className="ml-0.5 inline-block h-[14px] w-[2px] animate-pulse rounded-full bg-text-secondary align-text-bottom" />
      </div>
    </div>
  );
}
