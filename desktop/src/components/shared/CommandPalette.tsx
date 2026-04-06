import { useEffect, useMemo, useRef, useState } from "react";
import {
  surfaceBadge,
  surfaceFooter,
  surfaceHeader,
  surfaceInput,
  surfaceRow,
  surfaceRowActive,
  surfaceRowInactive,
  surfaceShell,
} from "./surfaceStyles";

export interface CommandItem {
  id: string;
  label: string;
  description?: string;
  shortcut?: string;
  keywords?: string[];
  action: () => void;
}

interface Props {
  open: boolean;
  onClose: () => void;
  commands: CommandItem[];
}

function scoreCommand(command: CommandItem, query: string) {
  if (!query) {
    return 1;
  }
  const haystack = [command.label, command.description, ...(command.keywords ?? [])]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  const needle = query.toLowerCase().trim();
  if (!needle) {
    return 1;
  }
  if (haystack === needle) {
    return 100;
  }
  if (haystack.includes(needle)) {
    return 70;
  }
  const compact = needle.split(/\s+/).filter(Boolean);
  let score = 0;
  for (const token of compact) {
    if (haystack.includes(token)) {
      score += 10;
    }
  }
  return score;
}

export function CommandPalette({ open, onClose, commands }: Props) {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    setQuery("");
    setActiveIndex(0);
    const timer = window.setTimeout(() => {
      inputRef.current?.focus();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [open]);

  const filtered = useMemo(() => {
    return [...commands]
      .map((command) => ({ command, score: scoreCommand(command, query) }))
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score || a.command.label.localeCompare(b.command.label))
      .map((item) => item.command);
  }, [commands, query]);

  useEffect(() => {
    setActiveIndex((current) => Math.min(current, Math.max(filtered.length - 1, 0)));
  }, [filtered.length]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveIndex((current) => Math.min(current + 1, Math.max(filtered.length - 1, 0)));
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveIndex((current) => Math.max(current - 1, 0));
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        const command = filtered[activeIndex] ?? filtered[0];
        if (command) {
          command.action();
          onClose();
        }
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeIndex, filtered, onClose, open]);

  if (!open) {
    return null;
  }

  const activeCommand = filtered[activeIndex] ?? filtered[0];

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/45 px-4 pt-[14vh] backdrop-blur-[2px]"
      onMouseDown={onClose}
    >
      <div className={`w-full max-w-[680px] ${surfaceShell}`} onMouseDown={(event) => event.stopPropagation()}>
        <div className={surfaceHeader}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-[12px] uppercase tracking-[0.1em] text-[var(--color-text-tertiary)]">Command palette</div>
              <div className="mt-1 text-[14px] text-[var(--color-text-primary)]">Search commands and workspace actions</div>
            </div>
            <span className={surfaceBadge}>Esc closes</span>
          </div>
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Type a command or search"
            className={`mt-3 ${surfaceInput}`}
          />
        </div>

        <div className="max-h-[52vh] overflow-auto p-2">
          {filtered.length ? (
            filtered.map((command, index) => {
              const active = index === activeIndex;
              return (
                <button
                  key={command.id}
                  type="button"
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => {
                    command.action();
                    onClose();
                  }}
                  className={[
                    surfaceRow,
                    active ? surfaceRowActive : surfaceRowInactive,
                  ].join(" ")}
                >
                  <div className="min-w-0">
                    <div className="truncate text-[13px] font-medium">{command.label}</div>
                    {command.description ? (
                      <div className="mt-1 line-clamp-1 text-[12px] text-[var(--color-text-tertiary)]">
                        {command.description}
                      </div>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {command.shortcut ? (
                      <span className={surfaceBadge}>
                        {command.shortcut}
                      </span>
                    ) : null}
                    <span className="text-[var(--color-text-tertiary)]">↵</span>
                  </div>
                </button>
              );
            })
          ) : (
            <div className="px-4 py-10 text-center text-[13px] text-[var(--color-text-tertiary)]">
              No commands found
            </div>
          )}
        </div>

        <div className={surfaceFooter}>
          <span>Esc close</span>
          <span>{activeCommand ? activeCommand.label : "No selection"}</span>
        </div>
      </div>
    </div>
  );
}
