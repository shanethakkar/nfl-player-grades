"use client";

import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { gradeColor } from "@/lib/grades";

type Hit = {
  player_id: number;
  full_name: string;
  position: string;
  team_abbr: string | null;
  best_grade: number;
  latest_season: number;
};

type SearchState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; hits: Hit[] }
  | { kind: "error"; message: string };

const MIN_QUERY_LEN = 2;
const DEBOUNCE_MS = 150;

/**
 * Header autocomplete for player names.
 *
 * UX contract:
 *   - Typing fewer than 2 chars never fires a request.
 *   - Subsequent keystrokes are debounced 150ms; the in-flight request
 *     is aborted when a new one starts so we always show the latest.
 *   - Arrow keys move highlight, Enter navigates to the highlighted
 *     hit (or the first hit if none is highlighted), Escape closes.
 *   - Clicking outside the component closes the dropdown.
 *   - Selecting a hit calls `router.push` so navigation is client-side
 *     (no full reload).
 *
 * Ranked by `best_grade DESC` server-side, so "tom brady" surfaces TB
 * over Brady Quinn even though Brady Quinn comes first alphabetically.
 */
export function PlayerSearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [state, setState] = useState<SearchState>({ kind: "idle" });
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // --- Fetch with debounce + abort
  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < MIN_QUERY_LEN) {
      setState({ kind: "idle" });
      abortRef.current?.abort();
      return;
    }
    setState({ kind: "loading" });
    const handle = setTimeout(async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const res = await fetch(
          `/api/players/search?q=${encodeURIComponent(trimmed)}`,
          { signal: controller.signal },
        );
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data: { results: Hit[] } = await res.json();
        setState({ kind: "ready", hits: data.results });
        setHighlight(0);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setState({ kind: "error", message: "Search failed" });
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [query]);

  // --- Close on outside click
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const hits = useMemo(
    () => (state.kind === "ready" ? state.hits : []),
    [state],
  );

  const select = useCallback(
    (hit: Hit) => {
      setOpen(false);
      setQuery("");
      router.push(`/players/${hit.player_id}`);
    },
    [router],
  );

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (hits.length > 0) {
        setHighlight((h) => Math.min(h + 1, hits.length - 1));
        setOpen(true);
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      const hit = hits[highlight];
      if (hit) {
        e.preventDefault();
        select(hit);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  const showDropdown =
    open &&
    query.trim().length >= MIN_QUERY_LEN &&
    state.kind !== "idle";

  return (
    <div ref={containerRef} className="relative w-44 sm:w-64">
      <input
        type="search"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        placeholder="Search players..."
        aria-label="Search players"
        autoComplete="off"
        className="w-full rounded-md border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-100 placeholder-neutral-500 focus:border-neutral-600 focus:outline-none"
      />
      {showDropdown && (
        <div className="absolute right-0 z-20 mt-1 w-72 max-w-[calc(100vw-2rem)] overflow-hidden rounded-md border border-neutral-800 bg-neutral-950 shadow-lg sm:w-80">
          {state.kind === "loading" && (
            <p className="px-3 py-2 text-xs text-neutral-500">Searching...</p>
          )}
          {state.kind === "error" && (
            <p className="px-3 py-2 text-xs text-red-400">{state.message}</p>
          )}
          {state.kind === "ready" && hits.length === 0 && (
            <p className="px-3 py-2 text-xs text-neutral-500">
              No graded players match &ldquo;{query.trim()}&rdquo;.
            </p>
          )}
          {state.kind === "ready" && hits.length > 0 && (
            <ul role="listbox" className="max-h-80 overflow-y-auto">
              {hits.map((hit, i) => {
                const active = i === highlight;
                return (
                  <li key={hit.player_id} role="option" aria-selected={active}>
                    <button
                      type="button"
                      onMouseEnter={() => setHighlight(i)}
                      onClick={() => select(hit)}
                      className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm ${
                        active
                          ? "bg-neutral-900 text-neutral-100"
                          : "text-neutral-300"
                      }`}
                    >
                      <span className="truncate">
                        <span className="font-medium">{hit.full_name}</span>
                        <span className="ml-2 text-xs text-neutral-500">
                          {hit.position}
                          {hit.team_abbr ? ` \u00B7 ${hit.team_abbr}` : ""}
                        </span>
                      </span>
                      <span
                        className={`font-mono text-xs ${gradeColor(hit.best_grade)}`}
                        title={`Best grade (${hit.latest_season} or earlier)`}
                      >
                        {hit.best_grade.toFixed(0)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
