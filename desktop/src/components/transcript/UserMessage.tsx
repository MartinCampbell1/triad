import type { Attachment } from "../../lib/types";
import { AttachmentChip } from "../shared/AttachmentChip";

interface Props {
  content: string;
  attachments?: Attachment[];
}

export function UserMessage({ content, attachments }: Props) {
  const hasText = Boolean(content.trim());
  const hasAttachments = Boolean(attachments?.length);

  return (
    <div className="py-1.5">
      {hasText ? (
        <div className="whitespace-pre-wrap text-[13px] leading-[1.6] text-[var(--color-text-primary)]">
          {content}
        </div>
      ) : null}
      {hasAttachments ? (
        <div className={`${hasText ? "mt-2" : ""} flex flex-wrap gap-2`}>
          {attachments?.map((attachment) => (
            <AttachmentChip key={attachment.id} attachment={attachment} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
