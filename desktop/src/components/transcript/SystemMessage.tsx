interface Props {
  text: string;
}

export function SystemMessage({ text }: Props) {
  return (
    <div className="py-1.5 text-center text-[12px] text-text-tertiary">
      {text}
    </div>
  );
}
