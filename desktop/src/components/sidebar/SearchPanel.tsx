import { useEffect, useMemo, useState } from "react";
import { rpc } from "../../lib/rpc";
import { useProjectStore } from "../../stores/project-store";
import { useSessionStore } from "../../stores/session-store";

interface SearchResult {
  event_id: number;
  session_id: string;
  session_title: string;
  project_path: string;
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

export function SearchPanel() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
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

  const handleOpenResult = async (result: SearchResult) => {
    const project =
      projects.find((item) => item.path === result.project_path) ??
      (result.project_path ? await openProject(result.project_path) : null);
    if (project) {
      setActiveProject(project);
    }
    await hydrateSession(result.session_id);
    setQuery("");
    setResults([]);
  };

  return (
    <div className="px-4 pb-3">
      <div className="rounded-[16px] border border-border-default bg-[rgba(255,255,255,0.03)] px-3 py-2 shadow-[0_8px_30px_rgba(0,0,0,0.18)]">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Поиск по сессиям"
          className="w-full border-0 bg-transparent text-[13px] text-text-primary outline-none placeholder:text-text-muted"
        />
      </div>

      {query.trim() ? (
        <div className="mt-2 rounded-[16px] border border-border-light bg-[rgba(0,0,0,0.18)] p-1.5">
          {searching ? (
            <div className="px-2 py-4 text-center text-[12px] text-text-tertiary">Поиск…</div>
          ) : null}
          {!searching && visibleResults.length === 0 ? (
            <div className="px-2 py-4 text-center text-[12px] text-text-tertiary">Ничего не найдено</div>
          ) : null}
          {!searching &&
            visibleResults.map((result) => (
              <button
                key={result.event_id}
                type="button"
                onClick={() => void handleOpenResult(result)}
                className="mb-1 block w-full rounded-[12px] px-2.5 py-2 text-left transition-colors hover:bg-white/5 last:mb-0"
              >
                <div className="truncate text-[12px] font-medium text-text-primary">{result.session_title}</div>
                <div
                  className="mt-1 line-clamp-2 text-[11px] leading-[1.5] text-text-secondary"
                  dangerouslySetInnerHTML={{ __html: formatSnippet(result.snippet) }}
                />
              </button>
            ))}
        </div>
      ) : null}
    </div>
  );
}
