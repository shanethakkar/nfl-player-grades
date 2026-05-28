"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { ScrollableTableWrapper } from "@/components/ScrollableTableWrapper";
import { SparklinePopover } from "@/components/SparklinePopover";
import { TeamLogo } from "@/components/TeamLogo";
import { Tooltip } from "@/components/Tooltip";
import { gradeColor } from "@/lib/grades";
import type { TeamLeaderboardEntry } from "@/types";

type Props = {
  entries: TeamLeaderboardEntry[];
  season: number;
};

type SortDir = "asc" | "desc";
type SortState = { key: string; dir: SortDir };

type SortableCol = {
  key: string;
  header: string;
  hover?: string;
  defaultDir: SortDir;
  sortValue: (e: TeamLeaderboardEntry) => number | string | null;
};

/**
 * Sortable team-grades leaderboard for /teams.
 *
 * Pattern intentionally mirrors {@link LeaderboardTable} so users
 * carry their muscle memory from the position leaderboards: rank +
 * sticky entity column + sortable numeric columns + click row to drill
 * down. Differences:
 *  - Entity is a team (logo + name), and the whole row is a single
 *    <Link> to /teams/[abbr]?season=N
 *  - No "FORMULA / CONTEXT" group banner — every column is treated
 *    equally; the per-position composite already lives on the team page
 *  - No sparklines for v1 (career-grade trend across years is a v2
 *    candidate)
 */
export function TeamLeaderboardTable({ entries, season }: Props) {
  const [sort, setSort] = useState<SortState>({ key: "overall", dir: "desc" });

  const sorted = useMemo(() => {
    const col = COLS.find((c) => c.key === sort.key);
    if (!col) return entries;
    const sign = sort.dir === "asc" ? 1 : -1;
    return [...entries].sort((a, b) => {
      const va = col.sortValue(a);
      const vb = col.sortValue(b);
      const aMissing = va === null || va === undefined;
      const bMissing = vb === null || vb === undefined;
      if (aMissing && bMissing) return 0;
      if (aMissing) return 1;
      if (bMissing) return -1;
      if (typeof va === "string" && typeof vb === "string") {
        return va.localeCompare(vb) * sign;
      }
      return ((va as number) - (vb as number)) * sign;
    });
  }, [entries, sort]);

  if (entries.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-neutral-500">
        No team grades for this season yet.
      </p>
    );
  }

  function onSort(col: SortableCol) {
    setSort((cur) =>
      cur.key === col.key
        ? { key: col.key, dir: cur.dir === "asc" ? "desc" : "asc" }
        : { key: col.key, dir: col.defaultDir },
    );
  }

  // Wrapping in the shared ScrollableTableWrapper gives us the same
  // right-edge fade gradient + click-and-drag-to-pan behavior as the
  // player leaderboard, plus the `w-max max-w-full` shrink-to-content
  // styling that keeps the bordered wrapper from stretching wide.
  return (
    <ScrollableTableWrapper>
      <table className="w-max text-sm [font-variant-numeric:tabular-nums]">
        <thead className="sticky top-0 z-10 bg-neutral-950 text-xs uppercase text-neutral-400">
          <tr>
            <Th className="w-14 text-center">Rank</Th>
            <SortHeader
              col={COL_TEAM}
              sort={sort}
              onSort={onSort}
              align="left"
              className="sticky left-0 z-30 bg-neutral-950 border-r border-neutral-800"
            />
            <SortHeader col={COL_OVERALL} sort={sort} onSort={onSort} align="right" />
            <SortHeader col={COL_OFF}     sort={sort} onSort={onSort} align="right" />
            <SortHeader col={COL_DEF}     sort={sort} onSort={onSort} align="right" />
            <SortHeader col={COL_ST}      sort={sort} onSort={onSort} align="right" />
            <SortHeader col={COL_RECORD}  sort={sort} onSort={onSort} align="right" />
            <SortHeader col={COL_PD}      sort={sort} onSort={onSort} align="right" />
            <SortHeader col={COL_TOP_QB}  sort={sort} onSort={onSort} align="left" />
          </tr>
        </thead>
        <tbody>
          {sorted.map((e, idx) => (
            <Row key={e.team_id} entry={e} rank={idx + 1} season={season} />
          ))}
        </tbody>
      </table>
    </ScrollableTableWrapper>
  );
}

// ---------------------------------------------------------------------------
// Column specs
// ---------------------------------------------------------------------------

const COL_TEAM: SortableCol = {
  key: "team",
  header: "Team",
  defaultDir: "asc",
  sortValue: (e) => e.name,
};
const COL_OVERALL: SortableCol = {
  key: "overall",
  header: "Overall",
  hover: "Composite team grade — 0.55×Offense + 0.40×Defense + 0.05×ST (ADR-0026)",
  defaultDir: "desc",
  sortValue: (e) => e.overall_grade,
};
const COL_OFF: SortableCol = {
  key: "offense",
  header: "Off",
  hover: "Offense phase grade — snap-weighted aggregate of QB / RB / WR / TE / OL",
  defaultDir: "desc",
  sortValue: (e) => e.offense_grade,
};
const COL_DEF: SortableCol = {
  key: "defense",
  header: "Def",
  hover: "Defense phase grade — snap-weighted aggregate of EDGE / iDL / LB / CB / S",
  defaultDir: "desc",
  sortValue: (e) => e.defense_grade,
};
const COL_ST: SortableCol = {
  key: "st",
  header: "ST",
  hover: "Special teams phase grade — K / P composite",
  defaultDir: "desc",
  sortValue: (e) => e.st_grade,
};
const COL_RECORD: SortableCol = {
  key: "record",
  header: "Record",
  hover: "Regular-season W-L (ties shown as W-L-T when nonzero)",
  defaultDir: "desc",
  sortValue: (e) => e.wins - e.losses, // sort by win differential
};
const COL_PD: SortableCol = {
  key: "pd",
  header: "PD",
  hover: "Regular-season point differential — points for minus points against",
  defaultDir: "desc",
  sortValue: (e) => e.point_diff,
};
const COL_TOP_QB: SortableCol = {
  key: "top_qb",
  header: "Top QB",
  hover: "Snap-leader at QB this season + their composite QB grade",
  defaultDir: "desc",
  sortValue: (e) => e.top_qb_grade,
};

const COLS: SortableCol[] = [
  COL_TEAM, COL_OVERALL, COL_OFF, COL_DEF, COL_ST, COL_RECORD, COL_PD, COL_TOP_QB,
];

// ---------------------------------------------------------------------------
// Row + cell components
// ---------------------------------------------------------------------------

function Row({
  entry: e,
  rank,
  season,
}: {
  entry: TeamLeaderboardEntry;
  rank: number;
  season: number;
}) {
  const isEven = rank % 2 === 0;
  const rowClass = isEven
    ? "group border-t border-neutral-800/50 bg-[#111111] hover:bg-[#181818]"
    : "group border-t border-neutral-800/50 hover:bg-[#111111]";
  const stickyBg = isEven
    ? "bg-[#111111] group-hover:bg-[#181818]"
    : "bg-neutral-950 group-hover:bg-[#111111]";

  const recordText =
    e.ties > 0 ? `${e.wins}-${e.losses}-${e.ties}` : `${e.wins}-${e.losses}`;
  const pdSign = e.point_diff > 0 ? "+" : "";

  return (
    <tr className={rowClass}>
      <Td className="text-center text-xs text-neutral-500">{rank}</Td>
      <Td className={`sticky left-0 z-20 border-r border-neutral-800 ${stickyBg}`}>
        <div className="flex items-center gap-4">
          {/* Chevron after the team name mirrors the player-row
              treatment — signals "click for the team profile." */}
          <Link
            href={{ pathname: `/teams/${e.abbr}`, query: { season } }}
            className="group inline-flex items-center gap-2 hover:text-white"
          >
            <TeamLogo abbr={e.abbr} size={20} />
            <span className="font-medium text-neutral-100">{e.name}</span>
            <span
              aria-hidden
              className="text-xs leading-none text-neutral-600 transition-all duration-150 group-hover:translate-x-0.5 group-hover:text-neutral-300"
            >
              ›
            </span>
          </Link>
          {/* Inline overall-grade trend across the last 5 seasons.
              Same SparklinePopover used on the player leaderboard.
              Mirrors the player leaderboard: hidden below sm: so phone
              widths don't waste horizontal space on it. */}
          {e.gradeTrend.length > 0 && (
            <div className="hidden sm:block">
              <SparklinePopover
                points={e.gradeTrend}
                header={`${e.name} — overall grade`}
              />
            </div>
          )}
        </div>
      </Td>
      <Td className={`text-right font-mono text-base font-semibold ${gradeColor(e.overall_grade)}`}>
        {e.overall_grade.toFixed(1)}
      </Td>
      <Td className={`text-right font-mono ${gradeColor(e.offense_grade)}`}>
        {e.offense_grade.toFixed(1)}
      </Td>
      <Td className={`text-right font-mono ${gradeColor(e.defense_grade)}`}>
        {e.defense_grade.toFixed(1)}
      </Td>
      <Td className={`text-right font-mono ${gradeColor(e.st_grade)}`}>
        {e.st_grade.toFixed(1)}
      </Td>
      <Td className="text-right font-mono text-neutral-300">{recordText}</Td>
      <Td className={`text-right font-mono ${e.point_diff >= 0 ? "text-neutral-200" : "text-neutral-500"}`}>
        {pdSign}
        {e.point_diff}
      </Td>
      <Td className="text-neutral-300">
        {e.top_qb_name ? (
          <div className="flex items-baseline gap-2">
            <span className="text-sm">{e.top_qb_name}</span>
            {e.top_qb_grade != null && (
              <span className={`font-mono text-xs ${gradeColor(e.top_qb_grade)}`}>
                {e.top_qb_grade.toFixed(0)}
              </span>
            )}
          </div>
        ) : (
          <span className="text-neutral-600">—</span>
        )}
      </Td>
    </tr>
  );
}

function SortHeader({
  col,
  sort,
  onSort,
  align,
  className = "",
}: {
  col: SortableCol;
  sort: SortState;
  onSort: (c: SortableCol) => void;
  align: "left" | "right";
  className?: string;
}) {
  const active = sort.key === col.key;
  const arrow = active ? (sort.dir === "asc" ? "▲" : "▼") : "";
  const alignCls = align === "right" ? "text-right" : "text-left";
  const sortIndicator = (
    <span
      aria-hidden
      className={`text-[10px] ${active ? "" : "opacity-0 group-hover:opacity-50"}`}
    >
      {arrow || "▾"}
    </span>
  );
  const labelNode = col.hover ? (
    <Tooltip content={col.hover}><span>{col.header}</span></Tooltip>
  ) : (
    <span>{col.header}</span>
  );
  return (
    <th className={`px-2 py-2 sm:px-3 ${alignCls} ${className}`}>
      <button
        type="button"
        onClick={() => onSort(col)}
        className={`inline-flex items-center gap-1 ${
          active ? "text-neutral-200" : "text-neutral-500 hover:text-neutral-300"
        }`}
      >
        {align === "right" ? <>{sortIndicator}{labelNode}</> : <>{labelNode}{sortIndicator}</>}
      </button>
    </th>
  );
}

function Th({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <th className={`px-2 py-2 text-left sm:px-3 ${className}`}>{children}</th>
  );
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
