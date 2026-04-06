import type { Message } from "../../lib/types";

interface Props {
  message: Message;
}

export function UserMessage({ message }: Props) {
  return (
    <div className="py-2">
      <div className="whitespace-pre-wrap text-[14px] leading-[1.6] text-text-primary">
        {message.content}
      </div>
    </div>
  );
}
