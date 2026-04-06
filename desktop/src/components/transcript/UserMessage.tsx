import type { Message } from "../../lib/types";

interface Props {
  message: Message;
}

export function UserMessage({ message }: Props) {
  return (
    <div className="codex-message-enter rounded-[18px] border border-border-light bg-[rgba(255,255,255,0.02)] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)] transition-[transform,box-shadow,border-color,background-color] duration-200 ease-out hover:-translate-y-0.5 hover:border-border-default hover:bg-[rgba(255,255,255,0.028)] hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.03),0_18px_34px_rgba(0,0,0,0.16)]">
      <div className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.12em] text-text-tertiary">
        <span className="h-2 w-2 rounded-full bg-accent shadow-[0_0_0_3px_rgba(51,156,255,0.08)] transition-transform duration-200 ease-out hover:scale-110" />
        <span>Вы</span>
      </div>
      <div className="whitespace-pre-wrap text-[13px] leading-[1.6] text-text-primary">{message.content}</div>
    </div>
  );
}
