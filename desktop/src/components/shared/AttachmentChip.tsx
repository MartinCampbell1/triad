import type { Attachment, AttachmentDraft } from "../../lib/types";

interface Props {
  attachment: Attachment | AttachmentDraft;
  onRemove?: () => void;
}

function formatFileSize(size?: number) {
  if (!size || size <= 0) {
    return null;
  }

  if (size >= 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (size >= 1024) {
    return `${Math.round(size / 1024)} KB`;
  }
  return `${size} B`;
}

function getBasename(path: string) {
  return path.split(/[/\\]/).pop() || path;
}

export function AttachmentChip({ attachment, onRemove }: Props) {
  const sizeLabel = formatFileSize(attachment.size_bytes);
  const name = attachment.name || getBasename(attachment.path ?? attachment.name);
  const title = attachment.path ?? attachment.name;
  const iconLabel = attachment.kind === "image" ? "img" : "file";

  return (
    <div className="inline-flex max-w-full items-center gap-2 rounded-full border border-[var(--color-border)] bg-[rgba(255,255,255,0.03)] px-2.5 py-1 text-[11px] text-[var(--color-text-secondary)]">
      <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[rgba(255,255,255,0.06)] text-[10px] text-[var(--color-text-tertiary)]">
        {iconLabel}
      </span>
      <span className="min-w-0 truncate text-[var(--color-text-primary)]" title={title}>
        {name}
      </span>
      {sizeLabel ? <span className="shrink-0 text-[var(--color-text-tertiary)]">{sizeLabel}</span> : null}
      {onRemove ? (
        <button
          type="button"
          onClick={onRemove}
          className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[var(--color-text-tertiary)] transition-colors duration-150 hover:bg-[rgba(255,255,255,0.08)] hover:text-[var(--color-text-secondary)]"
          title={`Remove ${name}`}
          aria-label={`Remove ${name}`}
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M2 2L8 8M8 2L2 8" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
          </svg>
        </button>
      ) : null}
    </div>
  );
}
