import { useState } from "react";
import { rpc } from "../../lib/rpc";
import { useSessionStore } from "../../stores/session-store";
import { useUiStore } from "../../stores/ui-store";

interface Props {
  open: boolean;
  onClose: () => void;
}

export function CommitDialog({ open, onClose }: Props) {
  const activeSession = useSessionStore((state) => state.activeSession);
  const diffFiles = useUiStore((state) => state.diffFiles);
  const [message, setMessage] = useState("");
  const [includeUnstaged, setIncludeUnstaged] = useState(true);
  const [autoMessage, setAutoMessage] = useState(true);

  if (!open) return null;

  const totalAdditions = diffFiles.reduce((sum, f) => sum + f.additions, 0);
  const totalDeletions = diffFiles.reduce((sum, f) => sum + f.deletions, 0);

  const branchName = activeSession?.title
    ? activeSession.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 40)
    : "main";

  const handleCommit = async (pushAfter = false) => {
    await rpc("session.commit", {
      session_id: activeSession?.id,
      message: autoMessage ? undefined : message,
      include_unstaged: includeUnstaged,
      push: pushAfter,
    }).catch(() => {});
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full max-w-[480px] rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#1e1e1e] shadow-[0_24px_64px_rgba(0,0,0,0.5)]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.06)] px-5 py-4">
          <h2 className="text-[16px] font-medium text-text-primary">Commit changes</h2>
          <button onClick={onClose} className="text-text-tertiary hover:text-text-secondary">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path d="M4 4L12 12M12 4L4 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4">
          {/* Branch + stats */}
          <div className="flex items-center justify-between text-[12px]">
            <div className="flex items-center gap-2">
              <span className="text-text-tertiary">Branch</span>
              <span className="rounded-md bg-[rgba(255,255,255,0.06)] px-2 py-0.5 font-mono text-[11px] text-text-secondary">
                {branchName}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-text-tertiary">Files {diffFiles.length}</span>
              <span className="text-green-300">+{totalAdditions}</span>
              <span className="text-red-300">-{totalDeletions}</span>
            </div>
          </div>

          {/* Include unstaged toggle */}
          <label className="mt-3 flex items-center gap-2 text-[13px] text-text-secondary">
            <button
              onClick={() => setIncludeUnstaged(!includeUnstaged)}
              className={`flex h-5 w-5 items-center justify-center rounded-md border transition-colors ${
                includeUnstaged
                  ? "border-[#339cff] bg-[#339cff]"
                  : "border-[rgba(255,255,255,0.15)] bg-transparent"
              }`}
            >
              {includeUnstaged ? (
                <svg width="10" height="10" viewBox="0 0 16 16" fill="white">
                  <path d="M3 8L7 12L13 4" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                </svg>
              ) : null}
            </button>
            <span>Include unstaged changes</span>
          </label>

          {/* Commit message */}
          <div className="mt-4">
            <div className="flex items-center justify-between">
              <span className="text-[13px] text-text-secondary">Commit message</span>
              <label className="flex items-center gap-1.5 text-[11px] text-text-tertiary">
                <input
                  type="checkbox"
                  checked={autoMessage}
                  onChange={(e) => setAutoMessage(e.target.checked)}
                  className="accent-[#339cff]"
                />
                <span>Custom message</span>
              </label>
            </div>
            {!autoMessage ? (
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Leave this blank to generate a commit message automatically"
                rows={3}
                className="mt-2 w-full resize-none rounded-lg border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-3 text-[13px] text-text-primary outline-none placeholder:text-text-muted focus:border-[rgba(51,156,255,0.3)]"
              />
            ) : (
              <p className="mt-2 text-[12px] text-text-tertiary">
                Leave this blank to generate the message automatically
              </p>
            )}
          </div>

          {/* Action steps */}
          <div className="mt-5">
            <span className="text-[12px] text-text-tertiary">Next step</span>
            <div className="mt-2 space-y-1.5">
              <label className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-[13px] text-text-primary transition-colors hover:bg-white/[0.03]">
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-green-300">
                  <path d="M3 8L7 12L13 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Commit
              </label>
              <label className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-[13px] text-text-secondary transition-colors hover:bg-white/[0.03]">
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-text-tertiary">
                  <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.2" />
                </svg>
                Commit and push
              </label>
              <label className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-[13px] text-text-secondary transition-colors hover:bg-white/[0.03]">
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-text-tertiary">
                  <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.2" />
                </svg>
                Commit and open pull request
              </label>
              <label className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-[13px] text-text-secondary transition-colors hover:bg-white/[0.03]">
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-text-tertiary">
                  <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.2" />
                </svg>
                Draft
              </label>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 border-t border-[rgba(255,255,255,0.06)] px-5 py-3">
          <button
            onClick={onClose}
            className="rounded-lg px-3 py-1.5 text-[13px] text-text-tertiary transition-colors hover:text-text-secondary"
          >
            Review
          </button>
          <button
            onClick={() => void handleCommit(false)}
            className="rounded-lg bg-white/90 px-4 py-1.5 text-[13px] font-medium text-[#181818] transition-opacity hover:bg-white"
          >
            Commit
          </button>
        </div>
      </div>
    </div>
  );
}
