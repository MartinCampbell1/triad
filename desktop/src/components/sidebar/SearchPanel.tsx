import { type KeyboardEvent as ReactKeyboardEvent, useEffect, useMemo, useState } from "react";
import { rpc } from "../../lib/rpc";
import { useProjectStore } from "../../stores/project-store";
import { useSessionStore } from "../../stores/session-store";
import {
  surfaceBadge,
  surfaceFooter,
  surfaceHeader,
  surfaceInput,
  surfaceSidebarShell,
  surfaceStackRow,
  surfaceStackRowInactive,
} from "../shared/surfaceStyles";

interface SearchResult {
  result_id: string;
  artifact_type?: string;
  event_id?: number | null;
  session_id?: string | null;
  session_title?: string | null;
  project_path?: string | null;
  event_type?: string | null;
  kind?: string | null;
  title?: string | null;
  path?: string | null;
  line?: number | null;
  severity?: string | null;
  attachment_name?: string | null;
  attachment_count?: number | null;
  diff_stat?: string | null;
  provider?: string | null;
  role?: string | null;
  snippet: string;
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatSnippet(snippet: string) {
  return escapeHtml(snippet)
    .replaceAll("&lt;mark&gt;", '<mark class="rounded bg-accent/20 px-0.5 text-text-primary">')
    .replaceAll("&lt;/mark&gt;", "</mark>");
}

function compactPath(value: string) {
  if (!value) {
    return "n/a";
  }
  return value.length > 42 ? `...${value.slice(-39)}` : value;
}

function titleCase(value: string) {
  return value
    .split(/[_\s.]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function artifactLabel(artifactType: string | null | undefined) {
  switch (artifactType) {
    case "message":
      return "Message";
    case "reply":
      return "Reply";
    case "attachment":
      return "Attachment";
    case "file_change":
      return "File change";
    case "finding":
      return "Finding";
    case "diff_snapshot":
      return "Diff";
    case "terminal":
      return "Terminal";
    case "session":
      return "Session";
    case "project":
      return "Project";
    case "tool":
      return "Tool";
    case "command":
      return "Command";
    case "system":
      return "System";
    default:
      return artifactType ? titleCase(artifactType) : "Result";
  }
}

function kindLabel(kind: string | null | undefined) {
  switch (kind) {
    case "message":
      return "Message";
    case "reply":
      return "Reply";
    case "tool":
      return "Tool";
    case "command":
      return "Command";
    case "file_change":
      return "File change";
    case "finding":
      return "Finding";
    case "terminal":
      return "Terminal";
    case "session":
      return "Session";
    default:
      return kind ? titleCase(kind) : "Result";
  }
}

function eventTypeLabel(eventType: string | null | undefined, artifactType?: string | null) {
  if (!eventType || eventType === artifactType) {
    return "";
  }
  switch (eventType) {
    case "user.message":
      return "user.message";
    case "message_finalized":
      return "message.finalized";
    case "tool_use":
      return "tool.use";
    case "tool_result":
      return "tool.result";
    case "review_finding":
      return "review.finding";
    case "system":
      return "system";
    default:
      return titleCase(eventType);
  }
}

function resultMeta(result: SearchResult) {
  const parts: string[] = [];
  if (result.artifact_type === "project") {
    if (result.project_path) {
      parts.push(compactPath(result.project_path));
    }
  } else {
    if (result.session_title && result.session_title !== result.title) {
      parts.push(result.session_title);
    }
    if (result.project_path) {
      parts.push(compactPath(result.project_path));
    }
    if (result.path && result.path !== result.project_path) {
      parts.push(compactPath(result.path));
    }
    if (typeof result.line === "number") {
      parts.push(`line ${result.line}`);
    }
    if (result.severity) {
      parts.push(result.severity);
    }
    if (typeof result.attachment_count === "number" && result.attachment_count > 0) {
      parts.push(`${result.attachment_count} attachment${result.attachment_count === 1 ? "" : "s"}`);
    }
  }
  return parts.filter(Boolean).join(" · ");
}

export function SearchPanel() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const projects = useProjectStore((state) => state.projects);
  const setActiveProject = useProjectStore((state) => state.setActiveProject);
  const openProject = useProjectStore((state) => state.openProject);
  const hydrateSession = useSessionStore((state) => state.hydrateSession);

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setSearching(false);
      return;
    }

    let cancelled = false;
    setSearching(true);
    const timeoutId = window.setTimeout(() => {
      void rpc<{ results: SearchResult[] }>("search", { query, limit: 12 })
        .then((response) => {
          if (!cancelled) {
            setResults(response.results);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setResults([]);
          }
        })
        .finally(() => {
          if (!cancelled) {
            setSearching(false);
          }
        });
    }, 160);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [query]);

  const visibleResults = useMemo(() => results.slice(0, 8), [results]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query, visibleResults.length]);

  const handleOpenResult = async (result: SearchResult) => {
    let project = result.project_path ? projects.find((item) => item.path === result.project_path) ?? null : null;
    if (!project && result.project_path) {
      try {
        project = await openProject(result.project_path);
      } catch {
        project = null;
      }
    }
    if (project) {
      setActiveProject(project);
    }
    if (result.session_id) {
      await hydrateSession(result.session_id);
    }
    setQuery("");
    setResults([]);
  };

  const handleInputKeyDown = async (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      setQuery("");
      setResults([]);
      return;
    }

    if (!query.trim() || visibleResults.length === 0) {
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => Math.min(current + 1, visibleResults.length - 1));
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => Math.max(current - 1, 0));
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      const target = visibleResults[activeIndex] ?? visibleResults[0];
      if (target) {
        await handleOpenResult(target);
      }
    }
  };

  return (
    <div className="px-3 pb-2">
      <div className={surfaceSidebarShell}>
        <div className={surfaceHeader}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[12px] uppercase tracking-[0.1em] text-[var(--color-text-tertiary)]">Search</div>
              <div className="mt-1 text-[13px] text-[var(--color-text-primary)]">Sessions, messages, findings, files</div>
            </div>
            <span className={surfaceBadge}>Typed results</span>
          </div>
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[rgba(255,255,255,0.03)] px-3 py-[6px]">
            <svg width="13" height="13" viewBox="0 0 16 16" fill="none" className="flex-shrink-0 text-[var(--color-text-tertiary)]">
              <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.3" />
              <path d="M11 11L14.5 14.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
            </svg>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => void handleInputKeyDown(event)}
              placeholder="Search"
              className={surfaceInput.replace("text-[14px]", "text-[13px]")}
            />
          </div>
        </div>

        {query.trim() ? (
          <div className="max-h-[280px] overflow-y-auto p-1">
            {searching ? (
              <div className="px-2 py-3 text-center text-[12px] text-[var(--color-text-tertiary)]">Searching...</div>
            ) : null}
            {!searching && visibleResults.length === 0 ? (
              <div className="px-2 py-3 text-center text-[12px] text-[var(--color-text-tertiary)]">No results</div>
            ) : null}
            {!searching &&
              visibleResults.map((result, index) => (
                <button
                  key={result.result_id}
                  type="button"
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => void handleOpenResult(result)}
                  className={[
                    surfaceStackRow,
                    index === activeIndex ? "bg-[var(--color-bg-elevated)] text-[var(--color-text-primary)]" : surfaceStackRowInactive,
                    "mb-1 flex-col items-stretch gap-2",
                  ].join(" ")}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate text-[12px] text-[var(--color-text-primary)]">
                        {result.title ?? result.session_title ?? "Result"}
                      </div>
                      <div className="mt-0.5 text-[11px] text-[var(--color-text-tertiary)]">{resultMeta(result)}</div>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <span className={surfaceBadge}>{artifactLabel(result.artifact_type ?? result.kind ?? result.event_type)}</span>
                      {kindLabel(result.kind) !== artifactLabel(result.artifact_type ?? result.kind ?? result.event_type) ? (
                        <span className={surfaceBadge}>{kindLabel(result.kind)}</span>
                      ) : null}
                      {eventTypeLabel(result.event_type, result.artifact_type) ? (
                        <span className={surfaceBadge}>{eventTypeLabel(result.event_type, result.artifact_type)}</span>
                      ) : null}
                    </div>
                  </div>
                  <div
                    className="line-clamp-2 text-[11px] leading-[1.5] text-[var(--color-text-secondary)]"
                    dangerouslySetInnerHTML={{ __html: formatSnippet(result.snippet) }}
                  />
                </button>
              ))}
          </div>
        ) : (
          <div className="px-4 py-4">
            <div className="rounded-[14px] border border-[var(--color-border)] bg-[rgba(0,0,0,0.18)] px-3 py-3 text-[12px] text-[var(--color-text-tertiary)]">
              Search across sessions, messages, findings, files, and projects.
            </div>
          </div>
        )}

        <div className={surfaceFooter}>
          <span>{query.trim() ? "Arrows move, Enter opens, Esc clears" : "Enter opens a result"}</span>
          <span>{query.trim() ? `${visibleResults.length} results` : "Idle"}</span>
        </div>
      </div>
    </div>
  );
}
