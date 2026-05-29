"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { ScrollableTableWrapper } from "@/components/ScrollableTableWrapper";
import { gradeColor } from "@/lib/grades";
import { fmtInt } from "@/lib/format";
import type { TeamRosterEntry } from "@/types";

type Props = {
  entries: TeamRosterEntry[];
};

type Bucket = "all" | "offense" | "defense" | "special";

// Position-side bucketing for the top-level filter. nflverse uses a mix of
// labels (e.g. SAF + FS + S + DB for safeties) so we group permissively.
const OFFENSE: ReadonlySet<string> = new Set([
  "QB", "RB", "HB", "FB",
  "WR", "TE",
  "C", "G", "T", "OG", "OT", "OL", "LT", "LG", "RG", "RT",
]);
const DEFENSE: ReadonlySet<string> = new Set([
  "CB", "DB",
  "S", "FS", "SS", "SAF",
  "LB", "ILB", "MLB", "OLB",
  "DE", "DT", "NT", "DL", "EDGE",
]);
const SPECIAL: ReadonlySet<string> = new Set(["K", "P", "LS"]);

function bucketOf(positionPlayed: string): Bucket {
  if (OFFENSE.has(positionPlayed)) return "offense";
  if (DEFENSE.has(positionPlayed)) return "defense";
  if (SPECIAL.has(positionPlayed)) return "special";
  return "all";
}

type SortKey = "grade" | "snaps" | "name" | "pos" | "games";
type SortDir = "asc" | "desc";

/**
 * Team roster table on /teams/[abbr]. Polished to match the main
 * leaderboards: shared ScrollableTableWrapper (right-fade + drag-pan +
 * sticky-column shadow), sticky entity column, rotating sort arrow,
 * chevron after player name. Plus a leading bucket filter for
 * offense / defense / special teams.
 */
export function RosterTable({ entries }: Props) {
  const [bucket, setBucket] = useState<Bucket>("all");
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({
    key: "grade",
    dir: "desc",
  });

  const filtered = useMemo(() => {
    if (bucket === "all") return entries;
    return entries.filter((e) => bucketOf(e.position_played) === bucket);
  }, [entries, bucket]);

  const sorted = useMemo(() => {
    const sign = sort.dir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      const aVal = sortKey(a, sort.key);
      const bVal = sortKey(b, sort.key);
      const aMissing = aVal === null || aVal === undefined;
      const bMissing = bVal === null || bVal === undefined;
      if (aMissing && bMissing) return 0;
      if (aMissing) return 1;
      if (bMissing) return -1;
      if (typeof aVal === "string" && typeof bVal === "string") {
        return aVal.localeCompare(bVal) * sign;
      }
      return ((aVal as number) - (bVal as number)) * sign;
    });
  }, [filtered, sort]);

  function onSort(key: SortKey, defaultDir: SortDir) {
    setSort((cur) =>
      cur.key === key
        ? { key, dir: cur.dir === "asc" ? "desc" : "asc" }
        : { key, dir: defaultDir },
    );
  }

  return (
    <div>
      <div className="mb-3 inline-flex items-center gap-1 rounded-lg border border-neutral-800 bg-neutral-950 p-1">
        {(["all", "offense", "defense", "special"] as const).map((b) => (
          <button
            key={b}
            type="button"
            onClick={() => setBucket(b)}
            className={
              bucket === b
                ? "rounded-md bg-neutral-100 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-neutral-900"
                : "rounded-md px-3 py-1 text-xs uppercase tracking-wider text-neutral-400 hover:text-neutral-100"
            }
          >
            {b === "special" ? "Special teams" : b}
          </button>
        ))}
      </div>

      <ScrollableTableWrapper>
        <table className="w-max text-sm [font-variant-numeric:tabular-nums]">
          <thead className="sticky top-0 z-10 bg-neutral-950 text-xs uppercase text-neutral-400">
            <tr>
              <Th className="w-14 text-center">#</Th>
              <ThSort
                label="Player"
                onClick={() => onSort("name", "asc")}
                active={sort.key === "name"}
                dir={sort.dir}
                align="left"
                className="sticky left-0 z-30 bg-neutral-950 border-r border-neutral-800 transition-shadow duration-150 group-data-[scrolled-x=true]/tbl:shadow-[8px_0_12px_-6px_rgba(0,0,0,0.55)]"
              />
              <ThSort
                label="Pos"
                onClick={() => onSort("pos", "asc")}
                active={sort.key === "pos"}
                dir={sort.dir}
                align="left"
              />
              <ThSort
                label="GP / GS"
                onClick={() => onSort("games", "desc")}
                active={sort.key === "games"}
                dir={sort.dir}
                align="right"
              />
              <ThSort
                label="Snaps"
                onClick={() => onSort("snaps", "desc")}
                active={sort.key === "snaps"}
                dir={sort.dir}
                align="right"
              />
              <ThSort
                label="Grade"
                onClick={() => onSort("grade", "desc")}
                active={sort.key === "grade"}
                dir={sort.dir}
                align="right"
              />
              <Th className="text-right">Pct</Th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((e, idx) => (
              <Row key={`${e.player_id}-${e.position_played}`} entry={e} rank={idx + 1} />
            ))}
            {sorted.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="px-3 py-8 text-center text-sm text-neutral-500"
                >
                  No players in this group.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </ScrollableTableWrapper>
    </div>
  );
}

function sortKey(
  e: TeamRosterEntry,
  key: SortKey,
): number | string | null {
  switch (key) {
    case "grade":
      return e.composite_grade;
    case "snaps":
      return e.total_snaps;
    case "name":
      return e.full_name;
    case "pos":
      return e.position_played;
    case "games":
      return e.games;
  }
}

function Row({ entry, rank }: { entry: TeamRosterEntry; rank: number }) {
  const isEven = rank % 2 === 0;
  const rowCls = isEven
    ? "group border-t border-neutral-800/50 bg-[#111111] hover:bg-[#181818]"
    : "group border-t border-neutral-800/50 hover:bg-[#111111]";
  const stickyBg = isEven
    ? "bg-[#111111] group-hover:bg-[#181818]"
    : "bg-neutral-950 group-hover:bg-[#111111]";
  return (
    <tr className={rowCls}>
      <Td className="text-center text-xs text-neutral-500">{rank}</Td>
      <Td className={`sticky left-0 z-20 border-r border-neutral-800 transition-shadow duration-150 group-data-[scrolled-x=true]/tbl:shadow-[8px_0_12px_-6px_rgba(0,0,0,0.55)] ${stickyBg}`}>
        <Link
          href={{ pathname: `/players/${entry.slug}` }}
          className="group/lnk inline-flex items-center gap-1 font-medium text-neutral-100 hover:text-white hover:underline"
        >
          <span>{entry.full_name}</span>
          <span
            aria-hidden
            className="text-xs leading-none text-neutral-600 transition-all duration-150 group-hover/lnk:translate-x-0.5 group-hover/lnk:text-neutral-300"
          >
            ›
          </span>
        </Link>
        {entry.traded_in_season && (
          <span className="ml-2 rounded border border-neutral-700 px-1.5 py-0.5 text-[10px] uppercase text-neutral-500">
            traded
          </span>
        )}
        {entry.composite_grade !== null && entry.qualified === false && (
          <span className="ml-2 rounded border border-neutral-700 px-1.5 py-0.5 text-[10px] uppercase text-neutral-500">
            low volume
          </span>
        )}
      </Td>
      <Td className="text-neutral-300">{entry.position_played}</Td>
      <Td className="text-right text-neutral-300">
        {entry.games}
        <span className="text-neutral-600"> / {entry.games_started}</span>
      </Td>
      <Td className="text-right text-neutral-300">{entry.total_snaps ? fmtInt(entry.total_snaps) : "—"}</Td>
      <Td className="text-right font-mono text-base font-semibold">
        {entry.composite_grade === null ? (
          <span className="text-neutral-600">—</span>
        ) : (
          <span
            className={`${gradeColor(entry.composite_grade)} ${
              entry.qualified === false ? "opacity-60" : ""
            }`}
          >
            {entry.composite_grade.toFixed(1)}
          </span>
        )}
      </Td>
      <Td className="text-right font-mono text-neutral-400">
        {entry.percentile === null ? "—" : entry.percentile.toFixed(0)}
      </Td>
    </tr>
  );
}

function Th({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <th className={`px-2 py-2 text-left sm:px-3 ${className}`}>{children}</th>;
}

function Td({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <td className={`px-2 py-2 sm:px-3 ${className}`}>{children}</td>;
}

function ThSort({
  label,
  onClick,
  active,
  dir,
  align,
  className = "",
}: {
  label: string;
  onClick: () => void;
  active: boolean;
  dir: SortDir;
  align: "left" | "right";
  className?: string;
}) {
  const alignCls = align === "right" ? "text-right" : "text-left";
  // Single ▼ rotated 180° when ascending; matches the leaderboard
  // sort-header pattern (animated direction flip, muted-but-visible on
  // inactive headers so every column reads as sortable).
  const sortIndicator = (
    <span
      aria-hidden
      className={
        "inline-block text-[10px] transition-transform duration-150 " +
        (active && dir === "asc" ? "rotate-180 " : "") +
        (active ? "" : "opacity-30 group-hover:opacity-60")
      }
    >
      ▼
    </span>
  );
  return (
    <th className={`px-2 py-2 sm:px-3 ${alignCls} ${className}`}>
      <button
        type="button"
        onClick={onClick}
        className={`group inline-flex items-center gap-1 ${
          active ? "text-neutral-200" : "text-neutral-500 hover:text-neutral-300"
        }`}
      >
        {align === "right" ? (
          <>{sortIndicator}<span>{label}</span></>
        ) : (
          <><span>{label}</span>{sortIndicator}</>
        )}
      </button>
    </th>
  );
}
