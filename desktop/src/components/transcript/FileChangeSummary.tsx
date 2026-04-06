import { useUiStore } from "../../stores/ui-store";

interface FileChange {
  path: string;
  additions: number;
  deletions: number;
}

interface Props {
  files: FileChange[];
}

export function FileChangeSummary({ files }: Props) {
  const setDiffPanelOpen = useUiStore((state) => state.setDiffPanelOpen);
  const clearDiffFiles = useUiStore((state) => state.clearDiffFiles);

  if (files.length === 0) return null;

  const totalAdditions = files.reduce((sum, f) => sum + f.additions, 0);
  const totalDeletions = files.reduce((sum, f) => sum + f.deletions, 0);

  return (
    <div className="my-2 rounded-lg border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)]">
      <div className="flex items-center justify-between px-4 py-2.5">
        <span className="text-[14px] text-text-secondary">
          Changed {files.length} {files.length === 1 ? "file" : "files"}{" "}
          <span className="text-green-300">+{totalAdditions}</span>{" "}
          <span className="text-red-300">-{totalDeletions}</span>
        </span>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={clearDiffFiles}
            className="flex items-center gap-1 text-[13px] text-text-tertiary transition-colors hover:text-text-secondary"
          >
            Clear
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
              <path d="M4 4L12 12M12 4L4 12" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      {files.map((file) => (
        <div key={file.path} className="flex items-center justify-between border-t border-[rgba(255,255,255,0.04)] px-4 py-2">
          <span className="min-w-0 truncate font-mono text-[13px] text-text-tertiary">{file.path}</span>
          <span className="ml-2 flex-shrink-0 text-[12px]">
            <span className="text-green-300">+{file.additions}</span>{" "}
            <span className="text-red-300">-{file.deletions}</span>
          </span>
        </div>
      ))}

      <div className="flex items-center justify-end border-t border-[rgba(255,255,255,0.04)] px-4 py-2">
        <button
          type="button"
          onClick={() => setDiffPanelOpen(true)}
          className="flex items-center gap-1 text-[13px] text-text-tertiary transition-colors hover:text-text-secondary"
        >
          Open diff
          <svg width="10" height="10" viewBox="0 0 16 16" fill="none">
            <path d="M4 4L12 12M12 12H6M12 12V6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}
