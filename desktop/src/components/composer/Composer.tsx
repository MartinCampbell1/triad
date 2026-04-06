import { useEffect, useRef, useState, type ChangeEvent, type ClipboardEvent, type DragEvent } from "react";
import { rpc } from "../../lib/rpc";
import type { Attachment, AttachmentDraft, AttachmentKind } from "../../lib/types";
import { useProviderStore } from "../../stores/provider-store";
import { useProjectStore } from "../../stores/project-store";
import { appendUserMessage, useSessionStore } from "../../stores/session-store";
import { AttachmentChip } from "../shared/AttachmentChip";
import { ModelSelector } from "./ModelSelector";
import { ModeSelector } from "./ModeSelector";

const MAX_ATTACHMENTS = 8;
const MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024;

function makeAttachmentId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `att_${crypto.randomUUID().slice(0, 8)}`;
  }
  return `att_${Math.random().toString(36).slice(2, 10)}`;
}

function getFilePath(file: File) {
  const maybePath = (file as File & { path?: string }).path;
  if (typeof maybePath === "string" && maybePath.trim()) {
    return maybePath;
  }
  return null;
}

function hasDraggedFiles(event: DragEvent<HTMLElement>) {
  return Array.from(event.dataTransfer.types).includes("Files");
}

function guessAttachmentKind(file: File): AttachmentKind {
  return file.type.startsWith("image/") ? "image" : "file";
}

function arrayBufferToBase64(buffer: ArrayBuffer) {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }
  return btoa(binary);
}

async function createAttachmentDraft(file: File, source: AttachmentDraft["source"]): Promise<AttachmentDraft> {
  const path = getFilePath(file);
  const draft: AttachmentDraft = {
    id: makeAttachmentId(),
    name: file.name || path?.split(/[/\\]/).pop() || "attachment",
    kind: guessAttachmentKind(file),
    path: path ?? undefined,
    size_bytes: file.size || undefined,
    source,
    mime_type: file.type || undefined,
  };

  if (!path) {
    const payload = await file.arrayBuffer();
    draft.content_base64 = arrayBufferToBase64(payload);
  }

  return draft;
}

function attachmentKey(attachment: AttachmentDraft) {
  if (attachment.path) {
    return `path:${attachment.path}`;
  }
  return `inline:${attachment.name}:${attachment.size_bytes ?? 0}:${attachment.mime_type ?? ""}`;
}

function toOptimisticAttachment(attachment: AttachmentDraft): Attachment {
  return {
    id: attachment.id,
    name: attachment.name,
    path: attachment.path ?? attachment.name,
    kind: attachment.kind,
    size_bytes: attachment.size_bytes,
    source: attachment.source,
    mime_type: attachment.mime_type,
  };
}

function formatAttachmentFeedback(added: number, duplicates: number, oversized: number, truncated: number) {
  const parts: string[] = [];
  if (added > 0) {
    parts.push(`Added ${added} file${added === 1 ? "" : "s"}.`);
  }
  if (duplicates > 0) {
    parts.push(`Ignored ${duplicates} duplicate${duplicates === 1 ? "" : "s"}.`);
  }
  if (oversized > 0) {
    parts.push(`Skipped ${oversized} file${oversized === 1 ? "" : "s"} over 5 MB.`);
  }
  if (truncated > 0) {
    parts.push(`Only kept the first ${MAX_ATTACHMENTS} attachments.`);
  }
  return parts.join(" ") || null;
}

export function Composer() {
  const [value, setValue] = useState("");
  const [attachments, setAttachments] = useState<AttachmentDraft[]>([]);
  const [attachmentFeedback, setAttachmentFeedback] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const dragDepthRef = useRef(0);
  const { activeProject } = useProjectStore();
  const { activeSession, createSession, clearStreamingText, streamingRuns } = useSessionStore();
  const { mode, activeProvider, activeModel, loadRuntimeOptions } = useProviderStore();

  useEffect(() => {
    const node = textareaRef.current;
    if (!node) {
      return;
    }
    node.style.height = "0px";
    node.style.height = `${Math.min(node.scrollHeight, 144)}px`;
  }, [value]);

  useEffect(() => {
    void loadRuntimeOptions();
  }, [loadRuntimeOptions]);

  useEffect(() => {
    if (!attachmentFeedback) {
      return;
    }
    const timeoutId = window.setTimeout(() => setAttachmentFeedback(null), 3200);
    return () => window.clearTimeout(timeoutId);
  }, [attachmentFeedback]);

  const mergeAttachments = async (files: Iterable<File>, source: AttachmentDraft["source"]) => {
    const entries = Array.from(files);
    if (entries.length === 0) {
      return;
    }

    const drafts: AttachmentDraft[] = [];
    let oversized = 0;
    try {
      for (const file of entries) {
        if (file.size > MAX_ATTACHMENT_BYTES) {
          oversized += 1;
          continue;
        }
        drafts.push(await createAttachmentDraft(file, source));
      }
    } catch {
      setAttachmentFeedback("Failed to read one of the attachments.");
      return;
    }

    let feedback: string | null = null;
    setAttachments((current) => {
      const known = new Set(current.map(attachmentKey));
      const next = [...current];
      let added = 0;
      let duplicates = 0;

      for (const draft of drafts) {
        const key = attachmentKey(draft);
        if (known.has(key)) {
          duplicates += 1;
          continue;
        }
        if (next.length >= MAX_ATTACHMENTS) {
          break;
        }
        known.add(key);
        next.push(draft);
        added += 1;
      }

      const truncated = Math.max(current.length + drafts.length - duplicates - MAX_ATTACHMENTS, 0);
      feedback = formatAttachmentFeedback(added, duplicates, oversized, truncated);
      return next;
    });
    setAttachmentFeedback(feedback);
  };

  const handleFileInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files?.length) {
      void mergeAttachments(Array.from(event.target.files), "picker");
    }
    event.target.value = "";
  };

  const handlePaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = Array.from(event.clipboardData.files);
    if (!files.length) {
      return;
    }
    event.preventDefault();
    void mergeAttachments(files, "paste");
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    if (!hasDraggedFiles(event)) {
      return;
    }

    event.preventDefault();
    dragDepthRef.current = 0;
    setDragActive(false);

    if (event.dataTransfer.files.length) {
      void mergeAttachments(Array.from(event.dataTransfer.files), "drop");
    }
  };

  const handleSend = async () => {
    const content = value.trim();
    const nextAttachments = attachments;
    if (!content && nextAttachments.length === 0) {
      return;
    }

    let session = activeSession;
    if (!session) {
      const project = activeProject ?? (await rpc<{ projects: { path: string }[] }>("project.list")).projects[0];
      if (!project) {
        return;
      }
      session = await createSession(project.path, mode, {
        provider: activeProvider,
        title: content.slice(0, 60) || nextAttachments[0]?.name || "New task",
      });
    }

    clearStreamingText();
    appendUserMessage(session.id, content, activeProvider, nextAttachments.map(toOptimisticAttachment));
    setValue("");
    setAttachments([]);
    setAttachmentFeedback(null);

    const attachmentPayloads = nextAttachments.map((attachment) => ({
      id: attachment.id,
      name: attachment.name,
      kind: attachment.kind,
      path: attachment.path,
      size_bytes: attachment.size_bytes,
      source: attachment.source,
      mime_type: attachment.mime_type,
      content_base64: attachment.content_base64,
    }));

    if (mode === "critic") {
      await rpc("critic.start", {
        session_id: session.id,
        prompt: content,
        project_path: session.project_path,
        writer: activeProvider,
        model: activeModel,
        max_rounds: 3,
        attachments: attachmentPayloads,
      });
      return;
    }

    if (mode === "brainstorm") {
      await rpc("brainstorm.start", {
        session_id: session.id,
        prompt: content,
        project_path: session.project_path,
        provider: activeProvider,
        model: activeModel,
        attachments: attachmentPayloads,
      });
      return;
    }

    if (mode === "delegate") {
      await rpc("delegate.start", {
        session_id: session.id,
        prompt: content,
        project_path: session.project_path,
        provider: activeProvider,
        model: activeModel,
        attachments: attachmentPayloads,
      });
      return;
    }

    await rpc("session.send", {
      session_id: session.id,
      content,
      project_path: session.project_path,
      provider: activeProvider,
      model: activeModel,
      mode,
      attachments: attachmentPayloads,
    });
  };

  const removeAttachment = (attachmentId: string) => {
    setAttachments((current) => current.filter((attachment) => attachment.id !== attachmentId));
  };

  const isRunning = activeSession?.status === "running" || streamingRuns.length > 0;
  const canSend = Boolean(value.trim() || attachments.length);

  return (
    <div className="px-4 pb-3 pt-2">
      <div className="mx-auto w-full max-w-[var(--composer-width)]">
        <div
          onDragEnter={(event) => {
            if (!hasDraggedFiles(event)) {
              return;
            }
            event.preventDefault();
            dragDepthRef.current += 1;
            setDragActive(true);
          }}
          onDragOver={(event) => {
            if (!hasDraggedFiles(event)) {
              return;
            }
            event.preventDefault();
            event.dataTransfer.dropEffect = "copy";
          }}
          onDragLeave={(event) => {
            if (!hasDraggedFiles(event)) {
              return;
            }
            event.preventDefault();
            dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
            if (dragDepthRef.current === 0) {
              setDragActive(false);
            }
          }}
          onDrop={handleDrop}
          className={`relative rounded-[20px] border px-4 pb-3 pt-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)] transition-colors duration-150 ${
            dragActive
              ? "border-[var(--color-text-tertiary)] bg-[rgba(255,255,255,0.045)]"
              : "border-[var(--color-border)] bg-[rgba(255,255,255,0.02)]"
          }`}
        >
          <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileInputChange} />

          {attachments.length > 0 ? (
            <div className="mb-2 flex flex-wrap gap-2">
              {attachments.map((attachment) => (
                <AttachmentChip key={attachment.id} attachment={attachment} onRemove={() => removeAttachment(attachment.id)} />
              ))}
            </div>
          ) : null}

          <textarea
            ref={textareaRef}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onPaste={handlePaste}
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                event.preventDefault();
                void handleSend();
              }
            }}
            placeholder="Ask for changes, drop files, or paste screenshots for context"
            rows={1}
            className="min-h-[22px] w-full resize-none border-0 bg-transparent text-[13px] leading-[1.5] text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-muted)]"
          />

          {attachmentFeedback ? <div className="mt-2 text-[11px] text-[var(--color-text-tertiary)]">{attachmentFeedback}</div> : null}

          <div className="mt-2 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isRunning}
                className="flex h-7 w-7 items-center justify-center rounded-full border border-[var(--color-border)] text-[var(--color-text-tertiary)] transition-colors duration-150 hover:bg-[rgba(255,255,255,0.04)] hover:text-[var(--color-text-secondary)] disabled:opacity-30"
                title="Attach files"
              >
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                  <path
                    d="M6.5 8.5L10 5C10.8284 4.17157 12.1716 4.17157 13 5C13.8284 5.82843 13.8284 7.17157 13 8L8 13C6.61929 14.3807 4.38071 14.3807 3 13C1.61929 11.6193 1.61929 9.38071 3 8L8.5 2.5"
                    stroke="currentColor"
                    strokeWidth="1.4"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
              <ModelSelector />
              <ModeSelector />
            </div>

            <div className="flex items-center gap-2">
              {isRunning ? (
                <button
                  type="button"
                  onClick={() => {
                    if (activeSession) {
                      void rpc("session.stop", { session_id: activeSession.id });
                    }
                  }}
                  className="flex h-[30px] w-[30px] items-center justify-center rounded-full bg-white text-[var(--color-bg-surface)] transition-opacity duration-150"
                  title="Stop"
                >
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
                    <rect x="0" y="0" width="10" height="10" rx="1.5" />
                  </svg>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => void handleSend()}
                  disabled={!canSend}
                  className="flex h-[30px] w-[30px] items-center justify-center rounded-full bg-white text-[var(--color-bg-surface)] transition-opacity duration-150 disabled:opacity-20"
                  title="Send"
                >
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                    <path d="M8 12V4M8 4L4 8M8 4L12 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              )}
            </div>
          </div>

          {dragActive ? (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-[20px] border border-dashed border-[var(--color-border-light)] bg-[rgba(16,18,22,0.58)] text-[12px] text-[var(--color-text-secondary)]">
              Drop files to attach
            </div>
          ) : null}
        </div>

        <div className="mt-1.5 flex items-center justify-between gap-3 px-1 text-[11px] text-[var(--color-text-tertiary)]">
          <div className="min-w-0 truncate">{activeProject?.name ?? "No project selected"}</div>
          <div className="shrink-0">
            <span className="rounded-full border border-[var(--color-border)] px-2 py-0.5">
              {attachments.length > 0
                ? `${attachments.length} file${attachments.length === 1 ? "" : "s"} attached`
                : canSend
                  ? "⌘↩ send"
                  : "Type a message or add files"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
