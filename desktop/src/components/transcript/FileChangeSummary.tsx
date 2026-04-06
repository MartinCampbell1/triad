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
  const toggleDiffPanel = useUiStore((state) => state.toggleDiffPanel);

  if (files.length === 0) return null;

  const totalAdditions = files.reduce((sum, f) => sum + f.additions, 0);
  const totalDeletions = files.reduce((sum, f) => sum + f.deletions, 0);

  return (
    <div className="my-2 rounded-lg border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)]">
      {/* Summary header */}
      <div className="flex items-center justify-between px-4 py-2.5">
        <span className="text-[14px] text-text-secondary">
          Изменено {files.length} {files.length === 1 ? "файл" : "файлов"}{" "}
          <span className="text-green-300">+{totalAdditions}</span>{" "}
          <span className="text-red-300">-{totalDeletions}</span>
        </span>
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-1 text-[13px] text-text-tertiary transition-colors hover:text-text-secondary">
            Отменить
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
              <path d="M2 8a6 6 0 1011.5-2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
              <path d="M14 2v4h-4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>

      {/* Individual file rows */}
      {files.map((file) => (
        <div key={file.path} className="flex items-center justify-between border-t border-[rgba(255,255,255,0.04)] px-4 py-2">
          <span className="min-w-0 truncate font-mono text-[13px] text-text-tertiary">{file.path}</span>
          <span className="ml-2 flex-shrink-0 text-[12px]">
            <span className="text-green-300">+{file.additions}</span>{" "}
            <span className="text-red-300">-{file.deletions}</span>
          </span>
        </div>
      ))}

      {/* Review button */}
      <div className="flex items-center justify-end border-t border-[rgba(255,255,255,0.04)] px-4 py-2">
        <button
          onClick={toggleDiffPanel}
          className="flex items-center gap-1 text-[13px] text-text-tertiary transition-colors hover:text-text-secondary"
        >
          Проверить изменения
          <svg width="10" height="10" viewBox="0 0 16 16" fill="none">
            <path d="M4 4L12 12M12 12H6M12 12V6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}
