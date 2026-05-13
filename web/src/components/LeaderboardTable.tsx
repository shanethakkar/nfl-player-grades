"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { TeamLogo } from "@/components/TeamLogo";
import { cbRoleLabel, gradeColor, teRoleLabel } from "@/lib/grades";
import type { LeaderboardEntry } from "@/types";

type Props = {
  entries: LeaderboardEntry[];
  /**
   * Position determines which trailing stat columns render. Each
   * position has its own headline set (ADR-0013/0014/0015/0016) —
   * the SQL in getLeaderboard wires the right components, and this
   * component picks the right column spec per row.
   */
  position: string;
};

type SortDir = "asc" | "desc";
type SortState = { key: string; dir: SortDir };

/**
 * Sortable, mobile-responsive leaderboard table.
 *
 * - Server passes rows ordered by grade desc, so first paint is
 *   correct without JS. Client-side `useMemo` re-sorts on header
 *   click — instant for the ~50-row leaderboards we render.
 * - Click cycles: numeric columns default to desc on first click
 *   (best at top), alpha columns default to asc; clicking the
 *   already-active column flips direction.
 * - All stat columns are always visible; the table itself scrolls
 *   horizontally inside its `overflow-x-auto` container so the page
 *   never scrolls horizontally. The Player column is sticky-pinned
 *   to the left so context is never lost while scrolling right.
 * - `<thead>` is `sticky top-0` so column names stay visible on long
 *   lists (RB/WR with 70+ rows).
 */
export function LeaderboardTable({ entries, position }: Props) {
  // `COLUMN_SPECS[position]` is a module-level constant array per position;
  // wrapping it in useMemo gives a stable reference for the deps array of
  // the `allColumns` memo below.
  const columns = useMemo<SortableColumn[]>(
    () => COLUMN_SPECS[position] ?? [],
    [position],
  );
  const allColumns = useMemo<SortableColumn[]>(
    () => [...FIXED_COLUMNS, ...columns],
    [columns],
  );

  const [sort, setSort] = useState<SortState>({
    key: "grade",
    dir: "desc",
  });

  const sortedEntries = useMemo(() => {
    const col = allColumns.find((c) => c.key === sort.key);
    if (!col) return entries;
    const sortValue = col.sortValue;
    const sign = sort.dir === "asc" ? 1 : -1;
    // Stable sort: copy first; nulls sink to the bottom regardless of dir
    // so "no value" never wins a sort.
    return [...entries].sort((a, b) => {
      const va = sortValue(a);
      const vb = sortValue(b);
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
  }, [entries, sort, allColumns]);

  if (entries.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-neutral-500">
        No grades for this season yet.
      </p>
    );
  }

  function onSort(col: SortableColumn) {
    setSort((cur) => {
      if (cur.key === col.key) {
        return { key: col.key, dir: cur.dir === "asc" ? "desc" : "asc" };
      }
      return { key: col.key, dir: col.defaultDir };
    });
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-neutral-800">
      <table className="w-max min-w-full text-sm [font-variant-numeric:tabular-nums]">
        <thead className="sticky top-0 z-10 bg-neutral-950 text-xs uppercase text-neutral-500">
          <tr>
            <Th className="w-14 text-center">Rank</Th>
            <SortHeader
              label="Player"
              align="left"
              sort={sort}
              col={FIXED_COLUMNS_BY_KEY.player}
              onSort={onSort}
              className="sticky left-0 z-30 bg-neutral-950 border-r border-neutral-800"
            />
            <SortHeader
              label="Team"
              align="left"
              sort={sort}
              col={FIXED_COLUMNS_BY_KEY.team}
              onSort={onSort}
            />
            <SortHeader
              label="Grade"
              align="right"
              sort={sort}
              col={FIXED_COLUMNS_BY_KEY.grade}
              onSort={onSort}
            />
            <SortHeader
              label="Pct"
              align="right"
              sort={sort}
              col={FIXED_COLUMNS_BY_KEY.percentile}
              onSort={onSort}
            />
            {columns.map((c) => (
              <SortHeader
                key={c.key}
                label={c.header}
                hover={c.hoverLabel}
                align="right"
                sort={sort}
                col={c}
                onSort={onSort}
              />
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedEntries.map((e, idx) => (
            <Row
              key={e.player_id}
              entry={e}
              rank={idx + 1}
              columns={columns}
              position={position}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Column specs.
//
// FIXED_COLUMNS = the always-visible fixed columns (player/team/grade/pct).
// COLUMN_SPECS  = per-position headline stat columns; each carries its own
//                 `render` for the cell and `sortValue` accessor for the sort
//                 comparator. Adding a new sortable column is one entry, no
//                 conditional JSX.
// ---------------------------------------------------------------------------

type SortableColumn = {
  key: string;
  header: string;
  hoverLabel?: string;
  defaultDir: SortDir;
  /** Returns the value used by the sort comparator (number or string). */
  sortValue: (e: LeaderboardEntry) => number | string | null;
  /** Cell renderer. Stat columns provide one; fixed columns render in JSX. */
  render?: (e: LeaderboardEntry) => string;
};

const FIXED_COLUMNS: SortableColumn[] = [
  { key: "player", header: "Player", defaultDir: "asc", sortValue: (e) => e.full_name },
  { key: "team",   header: "Team",   defaultDir: "asc", sortValue: (e) => e.team_abbr ?? "" },
  { key: "grade",  header: "Grade",  defaultDir: "desc", sortValue: (e) => e.composite_grade },
  { key: "percentile", header: "Pct", defaultDir: "desc", sortValue: (e) => e.percentile },
];
const FIXED_COLUMNS_BY_KEY = Object.fromEntries(
  FIXED_COLUMNS.map((c) => [c.key, c]),
) as Record<string, SortableColumn>;

function fmtSigned(v: number | null, digits: number): string {
  if (v === null || !Number.isFinite(v)) return "—";
  const sign = v > 0 ? "+" : v < 0 ? "-" : "";
  return `${sign}${Math.abs(v).toFixed(digits)}`;
}

function fmtPct(v: number | null, digits: number): string {
  if (v === null || !Number.isFinite(v)) return "—";
  return `${(v * 100).toFixed(digits)}`;
}

function fmtInt(v: number | null): string {
  return v === null || !Number.isFinite(v) ? "—" : String(v);
}

const QB_COLUMNS: SortableColumn[] = [
  {
    key: "n_dropbacks",
    header: "Drops",
    hoverLabel: "Qualifying dropbacks",
    defaultDir: "desc",
    sortValue: (e) => e.n_dropbacks,
    render: (e) => fmtInt(e.n_dropbacks),
  },
  {
    key: "epa_per_dropback",
    header: "EPA/db",
    hoverLabel: "EPA per dropback",
    defaultDir: "desc",
    sortValue: (e) => e.epa_per_dropback,
    render: (e) => fmtSigned(e.epa_per_dropback, 3),
  },
  {
    key: "cpoe",
    header: "CPOE",
    hoverLabel: "Completion % over expected",
    defaultDir: "desc",
    sortValue: (e) => e.cpoe,
    render: (e) => fmtSigned(e.cpoe, 2),
  },
  {
    key: "success_rate",
    header: "Succ%",
    hoverLabel: "Dropback success rate",
    defaultDir: "desc",
    sortValue: (e) => e.success_rate,
    render: (e) => fmtPct(e.success_rate, 1),
  },
];

const RB_COLUMNS: SortableColumn[] = [
  {
    key: "n_touches",
    header: "Touches",
    hoverLabel: "Qualifying touches (carries + receptions)",
    defaultDir: "desc",
    sortValue: (e) => e.n_touches,
    render: (e) => fmtInt(e.n_touches),
  },
  {
    key: "ryoe",
    header: "RYOE/att",
    hoverLabel: "Rush yards over expected per attempt (NGS)",
    defaultDir: "desc",
    sortValue: (e) => e.rb_ryoe_per_attempt,
    render: (e) => fmtSigned(e.rb_ryoe_per_attempt, 2),
  },
  {
    key: "rush_epa",
    header: "Rush EPA/att",
    hoverLabel: "Rush EPA per attempt",
    defaultDir: "desc",
    sortValue: (e) => e.rb_rush_epa_per_attempt,
    render: (e) => fmtSigned(e.rb_rush_epa_per_attempt, 3),
  },
  {
    key: "rush_succ",
    header: "Rush Succ%",
    hoverLabel: "Rushing success rate",
    defaultDir: "desc",
    sortValue: (e) => e.rb_rush_success_rate,
    render: (e) => fmtPct(e.rb_rush_success_rate, 1),
  },
  {
    key: "rec_epa",
    header: "Rec EPA/tgt",
    hoverLabel: "Receiving EPA per target",
    defaultDir: "desc",
    sortValue: (e) => e.rec_epa_per_target,
    render: (e) => fmtSigned(e.rec_epa_per_target, 3),
  },
  {
    key: "rb_yac_oe",
    header: "YAC-OE/rec",
    hoverLabel: "YAC over expected per reception (NGS)",
    defaultDir: "desc",
    sortValue: (e) => e.rb_yac_over_expected_per_rec,
    render: (e) => fmtSigned(e.rb_yac_over_expected_per_rec, 2),
  },
  {
    key: "catch_pct",
    header: "Catch%",
    hoverLabel: "Reception rate (receptions / targets)",
    defaultDir: "desc",
    sortValue: (e) => e.rb_catch_pct,
    render: (e) => fmtPct(e.rb_catch_pct, 1),
  },
  {
    key: "rb_fumble",
    header: "Fum%",
    hoverLabel: "Fumble rate per touch (lower is better)",
    defaultDir: "asc",
    sortValue: (e) => e.rb_fumble_rate,
    render: (e) => fmtPct(e.rb_fumble_rate, 2),
  },
];

const WR_COLUMNS: SortableColumn[] = [
  {
    key: "n_targets",
    header: "Tgts",
    hoverLabel: "Qualifying targets",
    defaultDir: "desc",
    sortValue: (e) => e.n_targets,
    render: (e) => fmtInt(e.n_targets),
  },
  {
    key: "rec_epa",
    header: "EPA/tgt",
    hoverLabel: "Receiving EPA per target",
    defaultDir: "desc",
    sortValue: (e) => e.rec_epa_per_target,
    render: (e) => fmtSigned(e.rec_epa_per_target, 3),
  },
  {
    key: "yac_oe",
    header: "YAC-OE/rec",
    hoverLabel: "YAC over expected per reception (NGS)",
    defaultDir: "desc",
    sortValue: (e) => e.yac_over_expected_per_rec,
    render: (e) => fmtSigned(e.yac_over_expected_per_rec, 2),
  },
  {
    key: "separation",
    header: "Sep",
    hoverLabel: "Average separation at target (yards, NGS)",
    defaultDir: "desc",
    sortValue: (e) => e.separation,
    render: (e) => e.separation === null || !Number.isFinite(e.separation) ? "—" : e.separation.toFixed(1),
  },
  {
    key: "succ_rate",
    header: "Succ%",
    hoverLabel: "Success rate per target",
    defaultDir: "desc",
    sortValue: (e) => e.success_rate_per_target,
    render: (e) => fmtPct(e.success_rate_per_target, 1),
  },
  {
    key: "earn",
    header: "Earn%",
    hoverLabel: "Target earn rate (targets / team pass attempts while active)",
    defaultDir: "desc",
    sortValue: (e) => e.target_earn_rate,
    render: (e) => fmtPct(e.target_earn_rate, 1),
  },
  {
    key: "fumble_rate",
    header: "Fum%",
    hoverLabel: "Fumble rate per reception (lower is better)",
    defaultDir: "asc",
    sortValue: (e) => e.fumble_rate,
    render: (e) => fmtPct(e.fumble_rate, 2),
  },
];

// TEs share WR's columns. Role is shown inline next to the name, not as
// its own column, to keep table density under control.
const TE_COLUMNS: SortableColumn[] = WR_COLUMNS;

const CB_COLUMNS: SortableColumn[] = [
  {
    key: "n_targets",
    header: "Tgts",
    hoverLabel: "Qualifying targets against",
    defaultDir: "desc",
    sortValue: (e) => e.n_targets,
    render: (e) => fmtInt(e.n_targets),
  },
  {
    key: "cb_comp_pct_allowed",
    header: "Comp% Alwd",
    hoverLabel: "Completion % allowed (lower is better)",
    defaultDir: "asc",
    sortValue: (e) => e.cb_comp_pct_allowed,
    render: (e) => fmtPct(e.cb_comp_pct_allowed, 1),
  },
  {
    key: "cb_yac_per_rec",
    header: "YAC/Rec Alwd",
    hoverLabel: "YAC per reception allowed (lower is better)",
    defaultDir: "asc",
    sortValue: (e) => e.cb_yac_per_rec_allowed,
    render: (e) => e.cb_yac_per_rec_allowed === null || !Number.isFinite(e.cb_yac_per_rec_allowed) ? "—" : e.cb_yac_per_rec_allowed.toFixed(1),
  },
  {
    key: "cb_target_rate",
    header: "Tgt%",
    hoverLabel: "Target rate per defensive snap (lower is better)",
    defaultDir: "asc",
    sortValue: (e) => e.cb_target_rate,
    render: (e) => fmtPct(e.cb_target_rate, 1),
  },
  {
    key: "cb_pbu_rate",
    header: "PBU%",
    hoverLabel: "Pass breakup rate per target",
    defaultDir: "desc",
    sortValue: (e) => e.cb_pbu_rate,
    render: (e) => fmtPct(e.cb_pbu_rate, 2),
  },
  {
    key: "cb_int_rate",
    header: "INT%",
    hoverLabel: "Interception rate per target",
    defaultDir: "desc",
    sortValue: (e) => e.cb_int_rate,
    render: (e) => fmtPct(e.cb_int_rate, 2),
  },
];

const S_COLUMNS: SortableColumn[] = [
  {
    key: "n_snaps",
    header: "Snaps",
    hoverLabel: "Qualifying defensive snaps",
    defaultDir: "desc",
    sortValue: (e) => e.n_snaps,
    render: (e) => fmtInt(e.n_snaps),
  },
  {
    key: "s_comp_pct_allowed",
    header: "Comp% Alwd",
    hoverLabel: "Completion % allowed (lower is better)",
    defaultDir: "asc",
    sortValue: (e) => e.s_comp_pct_allowed,
    render: (e) => fmtPct(e.s_comp_pct_allowed, 1),
  },
  {
    key: "s_yds_per_tgt",
    header: "Yds/Tgt",
    hoverLabel: "Yards per target allowed (lower is better)",
    defaultDir: "asc",
    sortValue: (e) => e.s_yards_per_target_allowed,
    render: (e) => e.s_yards_per_target_allowed === null || !Number.isFinite(e.s_yards_per_target_allowed) ? "—" : e.s_yards_per_target_allowed.toFixed(1),
  },
  {
    key: "s_target_rate",
    header: "Tgt%",
    hoverLabel: "Target rate per defensive snap (lower is better)",
    defaultDir: "asc",
    sortValue: (e) => e.s_target_rate,
    render: (e) => fmtPct(e.s_target_rate, 1),
  },
  {
    key: "s_pbu_rate",
    header: "PBU%",
    hoverLabel: "Pass breakup rate per target",
    defaultDir: "desc",
    sortValue: (e) => e.s_pbu_rate,
    render: (e) => fmtPct(e.s_pbu_rate, 2),
  },
  {
    key: "s_int_rate",
    header: "INT%",
    hoverLabel: "Interception rate per target",
    defaultDir: "desc",
    sortValue: (e) => e.s_int_rate,
    render: (e) => fmtPct(e.s_int_rate, 2),
  },
  {
    key: "s_tackles_per_snap",
    header: "Tkl/Snap",
    hoverLabel: "Combined tackles per defensive snap",
    defaultDir: "desc",
    sortValue: (e) => e.s_tackles_per_snap,
    render: (e) => e.s_tackles_per_snap === null || !Number.isFinite(e.s_tackles_per_snap) ? "—" : e.s_tackles_per_snap.toFixed(3),
  },
  {
    key: "s_missed_tkl",
    header: "MTkl%",
    hoverLabel: "Missed tackle rate (missed / tackle attempts, lower is better)",
    defaultDir: "asc",
    sortValue: (e) => e.s_missed_tackle_rate,
    render: (e) => fmtPct(e.s_missed_tackle_rate, 1),
  },
  {
    key: "s_disruption",
    header: "Disrpt/100",
    hoverLabel: "Backfield disruption per 100 snaps (TFL + sacks)",
    defaultDir: "desc",
    sortValue: (e) => e.s_backfield_disruption_per_snap,
    render: (e) => e.s_backfield_disruption_per_snap === null || !Number.isFinite(e.s_backfield_disruption_per_snap) ? "—" : (e.s_backfield_disruption_per_snap * 100).toFixed(2),
  },
];

const COLUMN_SPECS: Record<string, SortableColumn[]> = {
  QB: QB_COLUMNS,
  RB: RB_COLUMNS,
  WR: WR_COLUMNS,
  TE: TE_COLUMNS,
  CB: CB_COLUMNS,
  S:  S_COLUMNS,
};

function Row({
  entry: e,
  rank,
  columns,
  position,
}: {
  entry: LeaderboardEntry;
  rank: number;
  columns: SortableColumn[];
  position: string;
}) {
  const rowClass = e.qualified
    ? "group border-t border-neutral-800/50 hover:bg-neutral-900/60"
    : "group border-t border-neutral-800/50 bg-neutral-950/60 text-neutral-500 hover:bg-neutral-900/60";
  const roleText =
    position === "TE" ? teRoleLabel(e.role) :
    position === "CB" ? cbRoleLabel(e.role) :
    null;
  return (
    <tr className={rowClass}>
      <Td className="text-center text-xs text-neutral-500">{rank}</Td>
      <Td className="sticky left-0 z-20 bg-neutral-950 group-hover:bg-neutral-900/60 border-r border-neutral-800">
        <Link
          href={{ pathname: `/players/${e.player_id}` }}
          className="font-medium text-neutral-100 hover:text-white hover:underline"
        >
          {e.full_name}
        </Link>
        {roleText && (
          <span className="ml-2 rounded border border-neutral-700 px-1.5 py-0.5 text-[10px] uppercase text-neutral-400">
            {roleText}
          </span>
        )}
        {!e.qualified && (
          <span className="ml-2 rounded border border-neutral-700 px-1.5 py-0.5 text-[10px] uppercase text-neutral-500">
            low volume
          </span>
        )}
      </Td>
      <Td>
        {e.team_abbr ? (
          <div className="flex items-center gap-1.5">
            <TeamLogo abbr={e.team_abbr} size={20} />
            <span className="text-xs text-neutral-400">{e.team_abbr}</span>
          </div>
        ) : (
          <span className="text-neutral-500">—</span>
        )}
      </Td>
      <Td className="text-right font-mono font-semibold">
        <span className={gradeColor(e.composite_grade)}>
          {e.composite_grade.toFixed(1)}
        </span>
      </Td>
      <Td className="text-right font-mono text-neutral-400">
        {e.percentile.toFixed(0)}
      </Td>
      {columns.map((c) => (
        <Td key={c.key} className="text-right font-mono text-neutral-300">
          {c.render ? c.render(e) : "—"}
        </Td>
      ))}
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Header cells
// ---------------------------------------------------------------------------

function SortHeader({
  label,
  hover,
  align,
  sort,
  col,
  onSort,
  className = "",
}: {
  label: string;
  hover?: string;
  align: "left" | "center" | "right";
  sort: SortState;
  col: SortableColumn;
  onSort: (c: SortableColumn) => void;
  className?: string;
}) {
  const active = sort.key === col.key;
  const arrow = active ? (sort.dir === "asc" ? "▲" : "▼") : "";
  const alignCls =
    align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left";
  const buttonAlignCls =
    align === "right"
      ? "ml-auto"
      : align === "center"
        ? "mx-auto"
        : "";
  return (
    <th className={`px-3 py-2 ${alignCls} ${className}`} title={hover}>
      <button
        type="button"
        onClick={() => onSort(col)}
        className={`flex items-center gap-1 ${buttonAlignCls} ${
          active ? "text-neutral-200" : "text-neutral-500 hover:text-neutral-300"
        }`}
      >
        <span>{label}</span>
        <span
          aria-hidden
          className={`text-[10px] ${active ? "" : "opacity-0 group-hover:opacity-50"}`}
        >
          {arrow || "▾"}
        </span>
      </button>
    </th>
  );
}

function Th({
  children,
  className = "",
  title,
}: {
  children: React.ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <th className={`px-3 py-2 text-left ${className}`} title={title}>
      {children}
    </th>
  );
}

function Td({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <td className={`px-3 py-2 ${className}`}>{children}</td>;
}
