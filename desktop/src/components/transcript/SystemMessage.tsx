interface Props {
  text: string;
}

export function SystemMessage({ text }: Props) {
  return (
    <div className="flex justify-center py-1.5">
      <span className="rounded-full border border-border-light bg-black/20 px-3 py-1 text-[11px] text-text-tertiary">
        {text}
      </span>
    </div>
  );
}
