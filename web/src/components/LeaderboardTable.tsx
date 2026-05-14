"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { TeamLogo } from "@/components/TeamLogo";
import { Tooltip } from "@/components/Tooltip";
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
    <div>
      {columns.length > 0 && (
        <>
          <p className="mb-2 text-right text-xs text-neutral-600 sm:hidden">
            Hold column headers for stat definitions
          </p>
          <p className="mb-2 hidden text-right text-xs text-neutral-600 sm:block">
            Hover column headers for stat definitions
          </p>
        </>
      )}
      <div className="overflow-x-auto rounded-l-lg border-y border-l border-neutral-800 sm:rounded-lg sm:border-r">
      <table className="w-max min-w-full text-sm [font-variant-numeric:tabular-nums]">
        <thead className="sticky top-0 z-10 bg-neutral-950 text-xs uppercase text-neutral-400">
          {columns.some((c) => c.group) && (
            <tr className="border-b border-neutral-800/60">
              {/* Empty cells over Rank, Player, Team, Grade, Pct */}
              <th colSpan={5} />
              {computeHeaderGroups(columns).map((g, i) => (
                <th
                  key={i}
                  colSpan={g.count}
                  className={
                    g.label
                      ? g.label === "FORMULA"
                        ? "px-3 py-1 text-center text-[10px] font-semibold uppercase tracking-wider text-emerald-300/80 border-l border-r border-neutral-800/60"
                        : "px-3 py-1 text-center text-[10px] font-semibold uppercase tracking-wider text-neutral-500 border-l border-r border-neutral-800/60"
                      : ""
                  }
                >
                  {g.label}
                </th>
              ))}
            </tr>
          )}
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
              className="w-24"
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
              hover={FIXED_COLUMNS_BY_KEY.percentile.hoverLabel}
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

type ColumnGroup = "formula" | "context";

type SortableColumn = {
  key: string;
  header: string;
  hoverLabel?: string;
  defaultDir: SortDir;
  /** Returns the value used by the sort comparator (number or string). */
  sortValue: (e: LeaderboardEntry) => number | string | null;
  /** Cell renderer. Stat columns provide one; fixed columns render in JSX. */
  render?: (e: LeaderboardEntry) => string;
  /**
   * Optional grouping for a two-tier header (e.g. "FORMULA" / "CONTEXT").
   * Only K uses this currently — see K_COLUMNS. When absent (other positions),
   * the table renders a flat single-row header.
   */
  group?: ColumnGroup;
};

const FIXED_COLUMNS: SortableColumn[] = [
  { key: "player", header: "Player", defaultDir: "asc", sortValue: (e) => e.full_name },
  { key: "team",   header: "Team",   defaultDir: "asc", sortValue: (e) => e.team_abbr ?? "" },
  { key: "grade",  header: "Grade",  defaultDir: "desc", sortValue: (e) => e.composite_grade },
  { key: "percentile", header: "Pct", hoverLabel: "Percentile Rank — composite grade percentile among qualified players at this position", defaultDir: "desc", sortValue: (e) => e.percentile },
];

/**
 * Compute contiguous column-group spans for the two-tier header.
 * Returns one entry per group span (label + count of columns it covers).
 * Used when any column in the position's spec declares a `group` field
 * (currently K only — Formula / Context). Columns without a `group` produce
 * a `label: null` span (empty top-row cell).
 */
function computeHeaderGroups(columns: SortableColumn[]): Array<{ label: string | null; count: number }> {
  const result: Array<{ label: string | null; count: number }> = [];
  let current: { label: string | null; count: number } | null = null;
  for (const c of columns) {
    const label =
      c.group === "formula" ? "FORMULA"
      : c.group === "context" ? "CONTEXT"
      : null;
    if (current && current.label === label) {
      current.count++;
    } else {
      current = { label, count: 1 };
      result.push(current);
    }
  }
  return result;
}
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
    header: "Dropbacks",
    hoverLabel: "Qualifying Dropbacks — pass plays including sacks and scrambles counted in the grade",
    defaultDir: "desc",
    sortValue: (e) => e.n_dropbacks,
    render: (e) => fmtInt(e.n_dropbacks),
  },
  {
    key: "epa_per_dropback",
    header: "EPA/db",
    hoverLabel: "Expected Points Added / Dropback — passing value generated per play above league average",
    defaultDir: "desc",
    sortValue: (e) => e.epa_per_dropback,
    render: (e) => fmtSigned(e.epa_per_dropback, 3),
  },
  {
    key: "cpoe",
    header: "CPOE",
    hoverLabel: "Completion % Over Expected — actual completion rate minus model prediction accounting for throw location and difficulty",
    defaultDir: "desc",
    sortValue: (e) => e.cpoe,
    render: (e) => fmtSigned(e.cpoe, 2),
  },
  {
    key: "success_rate",
    header: "Succ%",
    hoverLabel: "Dropback Success Rate — share of dropbacks that gained positive expected points",
    defaultDir: "desc",
    sortValue: (e) => e.success_rate,
    render: (e) => fmtPct(e.success_rate, 1),
  },
];

const RB_COLUMNS: SortableColumn[] = [
  {
    key: "n_touches",
    header: "Touches",
    hoverLabel: "Qualifying Touches — carries and receptions counted in the grade",
    defaultDir: "desc",
    sortValue: (e) => e.n_touches,
    render: (e) => fmtInt(e.n_touches),
  },
  {
    key: "ryoe",
    header: "RYOE/att",
    hoverLabel: "Rush Yards Over Expected / Attempt — rushing yards gained above model prediction per carry",
    defaultDir: "desc",
    sortValue: (e) => e.rb_ryoe_per_attempt,
    render: (e) => fmtSigned(e.rb_ryoe_per_attempt, 2),
  },
  {
    key: "rush_epa",
    header: "Rush EPA/att",
    hoverLabel: "Rush Expected Points Added / Attempt — rushing value generated per carry above league average",
    defaultDir: "desc",
    sortValue: (e) => e.rb_rush_epa_per_attempt,
    render: (e) => fmtSigned(e.rb_rush_epa_per_attempt, 3),
  },
  {
    key: "rush_succ",
    header: "Rush Succ%",
    hoverLabel: "Rush Success Rate — share of carries that gained positive expected points",
    defaultDir: "desc",
    sortValue: (e) => e.rb_rush_success_rate,
    render: (e) => fmtPct(e.rb_rush_success_rate, 1),
  },
  {
    key: "rec_epa",
    header: "Rec EPA/tgt",
    hoverLabel: "Receiving Expected Points Added / Target — receiving value generated per target above league average",
    defaultDir: "desc",
    sortValue: (e) => e.rec_epa_per_target,
    render: (e) => fmtSigned(e.rec_epa_per_target, 3),
  },
  {
    key: "rb_yac_oe",
    header: "YAC-OE/rec",
    hoverLabel: "Yards After Catch Over Expected / Reception — yards after catch above model prediction per reception",
    defaultDir: "desc",
    sortValue: (e) => e.rb_yac_over_expected_per_rec,
    render: (e) => fmtSigned(e.rb_yac_over_expected_per_rec, 2),
  },
  {
    key: "rb_yac_carry",
    header: "YAC/carry",
    hoverLabel: "Yards After Contact / Carry — post-contact rushing yards per carry (PFR charting). Pure RB skill: tackle-breaking, fall-forward, second-effort yardage. Data 2018+.",
    defaultDir: "desc",
    sortValue: (e) => e.rb_yards_after_contact_per_carry,
    render: (e) => (e.rb_yards_after_contact_per_carry == null
      ? "—"
      : e.rb_yards_after_contact_per_carry.toFixed(2)),
  },
  {
    key: "rb_fumble",
    header: "Fum%",
    hoverLabel: "Fumble Rate — fumbles per touch. Lower is better.",
    defaultDir: "asc",
    sortValue: (e) => e.rb_fumble_rate,
    render: (e) => fmtPct(e.rb_fumble_rate, 2),
  },
];

const WR_COLUMNS: SortableColumn[] = [
  {
    key: "n_targets",
    header: "Tgts",
    hoverLabel: "Qualifying Targets — targets counted in the grade",
    defaultDir: "desc",
    sortValue: (e) => e.n_targets,
    render: (e) => fmtInt(e.n_targets),
  },
  {
    key: "rec_epa",
    header: "EPA/tgt",
    hoverLabel: "Expected Points Added / Target — receiving value generated per target above league average",
    defaultDir: "desc",
    sortValue: (e) => e.rec_epa_per_target,
    render: (e) => fmtSigned(e.rec_epa_per_target, 3),
  },
  {
    key: "yac_oe",
    header: "YAC-OE/rec",
    hoverLabel: "Yards After Catch Over Expected / Reception — yards after catch above model prediction per reception",
    defaultDir: "desc",
    sortValue: (e) => e.yac_over_expected_per_rec,
    render: (e) => fmtSigned(e.yac_over_expected_per_rec, 2),
  },
  {
    key: "separation",
    header: "Sep",
    hoverLabel: "Average Separation — yards of open space at the moment of the target",
    defaultDir: "desc",
    sortValue: (e) => e.separation,
    render: (e) => e.separation === null || !Number.isFinite(e.separation) ? "—" : e.separation.toFixed(1),
  },
  {
    key: "succ_rate",
    header: "Succ%",
    hoverLabel: "Success Rate / Target — share of targets that gained positive expected points",
    defaultDir: "desc",
    sortValue: (e) => e.success_rate_per_target,
    render: (e) => fmtPct(e.success_rate_per_target, 1),
  },
  {
    key: "earn",
    header: "Earn%",
    hoverLabel: "Target Earn Rate — targets earned as a share of team pass attempts while the receiver was active",
    defaultDir: "desc",
    sortValue: (e) => e.target_earn_rate,
    render: (e) => fmtPct(e.target_earn_rate, 1),
  },
  {
    key: "drop_rate",
    header: "Drop%",
    hoverLabel: "Drop Rate — drops as a share of catchable balls (FTN charting). Lower is better. Data 2022+.",
    defaultDir: "asc",
    sortValue: (e) => e.drop_rate,
    render: (e) => fmtPct(e.drop_rate, 1),
  },
];

// TEs share the same columns as WRs: drop_rate (FTN charting) is the
// hands slot for both positions as of TE v1.1 / WR v1.2 (2026-05-14).
const TE_COLUMNS: SortableColumn[] = WR_COLUMNS;

const CB_COLUMNS: SortableColumn[] = [
  {
    key: "n_targets",
    header: "Tgts",
    hoverLabel: "Qualifying Targets Against — targets thrown at this corner counted in the grade",
    defaultDir: "desc",
    sortValue: (e) => e.n_targets,
    render: (e) => fmtInt(e.n_targets),
  },
  {
    key: "cb_passer_rating_allowed",
    header: "PR Allowed",
    hoverLabel: "NFL Passer Rating Allowed — comp%, yards, TDs, and INTs combined into one coverage damage metric. Lower is better.",
    defaultDir: "asc",
    sortValue: (e) => e.cb_passer_rating_allowed,
    render: (e) => e.cb_passer_rating_allowed === null || !Number.isFinite(e.cb_passer_rating_allowed) ? "—" : e.cb_passer_rating_allowed.toFixed(1),
  },
  {
    key: "cb_yac_per_rec",
    header: "YAC/Rec Alwd",
    hoverLabel: "Yards After Catch / Reception Allowed — YAC allowed per reception against. Lower is better.",
    defaultDir: "asc",
    sortValue: (e) => e.cb_yac_per_rec_allowed,
    render: (e) => e.cb_yac_per_rec_allowed === null || !Number.isFinite(e.cb_yac_per_rec_allowed) ? "—" : e.cb_yac_per_rec_allowed.toFixed(1),
  },
  {
    key: "cb_target_rate",
    header: "Tgt%",
    hoverLabel: "Target Rate — targets faced per defensive snap. Lower is better.",
    defaultDir: "asc",
    sortValue: (e) => e.cb_target_rate,
    render: (e) => fmtPct(e.cb_target_rate, 1),
  },
  {
    key: "cb_pbu_rate",
    header: "PBU%",
    hoverLabel: "Pass Breakup Rate — passes broken up as a share of targets faced (INTs are captured inside passer rating allowed)",
    defaultDir: "desc",
    sortValue: (e) => e.cb_pbu_rate,
    render: (e) => fmtPct(e.cb_pbu_rate, 2),
  },
];

const S_COLUMNS: SortableColumn[] = [
  {
    key: "n_snaps",
    header: "Snaps",
    hoverLabel: "Qualifying Defensive Snaps — snaps counted in the grade",
    defaultDir: "desc",
    sortValue: (e) => e.n_snaps,
    render: (e) => fmtInt(e.n_snaps),
  },
  {
    key: "s_passer_rating_allowed",
    header: "PR Allowed",
    hoverLabel: "NFL Passer Rating Allowed — comp%, yards, TDs, and INTs combined into one coverage damage metric. Lower is better.",
    defaultDir: "asc",
    sortValue: (e) => e.s_passer_rating_allowed,
    render: (e) => e.s_passer_rating_allowed === null || !Number.isFinite(e.s_passer_rating_allowed) ? "—" : e.s_passer_rating_allowed.toFixed(1),
  },
  {
    key: "s_target_rate",
    header: "Tgt%",
    hoverLabel: "Target Rate — targets faced per defensive snap. Lower is better.",
    defaultDir: "asc",
    sortValue: (e) => e.s_target_rate,
    render: (e) => fmtPct(e.s_target_rate, 1),
  },
  {
    key: "s_pbu_rate",
    header: "PBU%",
    hoverLabel: "Pass Breakup Rate — passes broken up as a share of targets faced (INTs are captured inside passer rating allowed)",
    defaultDir: "desc",
    sortValue: (e) => e.s_pbu_rate,
    render: (e) => fmtPct(e.s_pbu_rate, 2),
  },
  {
    key: "s_tackles_per_snap",
    header: "Tkl/Snap",
    hoverLabel: "Combined Tackles / Snap — total tackles and assists per defensive snap",
    defaultDir: "desc",
    sortValue: (e) => e.s_tackles_per_snap,
    render: (e) => e.s_tackles_per_snap === null || !Number.isFinite(e.s_tackles_per_snap) ? "—" : e.s_tackles_per_snap.toFixed(3),
  },
  {
    key: "s_missed_tkl",
    header: "MTkl%",
    hoverLabel: "Missed Tackle Rate — missed tackles as a share of tackle attempts. Lower is better.",
    defaultDir: "asc",
    sortValue: (e) => e.s_missed_tackle_rate,
    render: (e) => fmtPct(e.s_missed_tackle_rate, 1),
  },
  {
    key: "s_disruption",
    header: "Disrpt/100",
    hoverLabel: "Backfield Disruption / 100 Snaps — tackles for loss and sacks per 100 defensive snaps",
    defaultDir: "desc",
    sortValue: (e) => e.s_backfield_disruption_per_snap,
    render: (e) => e.s_backfield_disruption_per_snap === null || !Number.isFinite(e.s_backfield_disruption_per_snap) ? "—" : (e.s_backfield_disruption_per_snap * 100).toFixed(2),
  },
];

const EDGE_COLUMNS: SortableColumn[] = [
  {
    key: "n_snaps",
    header: "Snaps",
    hoverLabel: "Qualifying Defensive Snaps — snaps counted in the grade",
    defaultDir: "desc",
    sortValue: (e) => e.n_snaps,
    render: (e) => fmtInt(e.n_snaps),
  },
  {
    key: "edge_pressure_rate",
    header: "Press%",
    hoverLabel: "Pressure Rate — sacks + QB hits + hurries per defensive snap",
    defaultDir: "desc",
    sortValue: (e) => e.edge_pressure_rate,
    render: (e) => fmtPct(e.edge_pressure_rate, 1),
  },
  {
    key: "edge_sack_rate",
    header: "Sack%",
    hoverLabel: "Sack Rate — sacks per defensive snap. Premium pass-rush outcome.",
    defaultDir: "desc",
    sortValue: (e) => e.edge_sack_rate,
    render: (e) => fmtPct(e.edge_sack_rate, 2),
  },
  {
    key: "edge_tfl_rate",
    header: "TFL%",
    hoverLabel: "Run-Stop TFL Rate — tackles for loss (sacks excluded) per defensive snap",
    defaultDir: "desc",
    sortValue: (e) => e.edge_tfl_rate,
    render: (e) => fmtPct(e.edge_tfl_rate, 2),
  },
  {
    key: "edge_tackles_per_snap",
    header: "Tkl/Snap",
    hoverLabel: "Tackles per defensive snap — chase-tackles and box-score activity beyond pressure/sack/TFL (added v1.2 per exhaustive audit)",
    defaultDir: "desc",
    sortValue: (e) => e.edge_tackles_per_snap,
    render: (e) => fmtPct(e.edge_tackles_per_snap, 1),
  },
  {
    key: "edge_missed_tkl",
    header: "MTkl%",
    hoverLabel: "Missed Tackle Rate — missed tackles as a share of tackle attempts. Lower is better.",
    defaultDir: "asc",
    sortValue: (e) => e.edge_missed_tackle_rate,
    render: (e) => fmtPct(e.edge_missed_tackle_rate, 1),
  },
];

const IDL_COLUMNS: SortableColumn[] = [
  {
    key: "n_snaps",
    header: "Snaps",
    hoverLabel: "Qualifying Defensive Snaps — snaps counted in the grade",
    defaultDir: "desc",
    sortValue: (e) => e.n_snaps,
    render: (e) => fmtInt(e.n_snaps),
  },
  {
    key: "idl_tfl_rate",
    header: "TFL%",
    hoverLabel: "Run-Stop TFL Rate — tackles for loss (sacks excluded) per defensive snap. Primary iDL differentiator.",
    defaultDir: "desc",
    sortValue: (e) => e.idl_tfl_rate,
    render: (e) => fmtPct(e.idl_tfl_rate, 2),
  },
  {
    key: "idl_pressure_rate",
    header: "Press%",
    hoverLabel: "Pressure Rate — sacks + QB hits + hurries per defensive snap",
    defaultDir: "desc",
    sortValue: (e) => e.idl_pressure_rate,
    render: (e) => fmtPct(e.idl_pressure_rate, 1),
  },
  {
    key: "idl_sack_rate",
    header: "Sack%",
    hoverLabel: "Sack Rate — sacks per defensive snap. Interior sacks are rarer but equally impactful.",
    defaultDir: "desc",
    sortValue: (e) => e.idl_sack_rate,
    render: (e) => fmtPct(e.idl_sack_rate, 2),
  },
  {
    key: "idl_tackles_per_snap",
    header: "Tkl/Snap",
    hoverLabel: "Tackles per defensive snap — chase-tackles and box-score activity beyond pressure/sack/TFL (added v1.2 per exhaustive audit)",
    defaultDir: "desc",
    sortValue: (e) => e.idl_tackles_per_snap,
    render: (e) => fmtPct(e.idl_tackles_per_snap, 1),
  },
  {
    key: "idl_missed_tkl",
    header: "MTkl%",
    hoverLabel: "Missed Tackle Rate — missed tackles as a share of tackle attempts. Lower is better.",
    defaultDir: "asc",
    sortValue: (e) => e.idl_missed_tackle_rate,
    render: (e) => fmtPct(e.idl_missed_tackle_rate, 1),
  },
];

const LB_COLUMNS: SortableColumn[] = [
  {
    key: "n_snaps",
    header: "Snaps",
    hoverLabel: "Qualifying Defensive Snaps — snaps counted in the grade",
    defaultDir: "desc",
    sortValue: (e) => e.n_snaps,
    render: (e) => fmtInt(e.n_snaps),
  },
  {
    key: "lb_tfl_rate",
    header: "TFL%",
    hoverLabel: "Run-Stop TFL Rate — tackles for loss (sacks excluded) per defensive snap",
    defaultDir: "desc",
    sortValue: (e) => e.lb_tfl_rate,
    render: (e) => fmtPct(e.lb_tfl_rate, 2),
  },
  {
    key: "lb_passer_rating_allowed",
    header: "PR Allowed",
    hoverLabel: "NFL Passer Rating Allowed — comp%, yards, TDs, and INTs combined into one coverage damage metric. Lower is better.",
    defaultDir: "asc",
    sortValue: (e) => e.lb_passer_rating_allowed,
    render: (e) => (e.lb_passer_rating_allowed == null ? "—" : e.lb_passer_rating_allowed.toFixed(1)),
  },
  {
    key: "lb_missed_tkl",
    header: "MTkl%",
    hoverLabel: "Missed Tackle Rate — missed tackles as a share of tackle attempts. Lower is better.",
    defaultDir: "asc",
    sortValue: (e) => e.lb_missed_tackle_rate,
    render: (e) => fmtPct(e.lb_missed_tackle_rate, 1),
  },
  {
    key: "lb_pbu_rate",
    header: "PBU%",
    hoverLabel: "PBU Rate — pass breakups per coverage target (INTs counted in passer rating allowed)",
    defaultDir: "desc",
    sortValue: (e) => e.lb_pbu_rate,
    render: (e) => fmtPct(e.lb_pbu_rate, 1),
  },
  {
    key: "lb_tackle_rate",
    header: "Tkl/Snap",
    hoverLabel: "Tackles per defensive snap — volume signal for run-defense work",
    defaultDir: "desc",
    sortValue: (e) => e.lb_tackle_rate,
    render: (e) => (e.lb_tackle_rate == null ? "—" : e.lb_tackle_rate.toFixed(3)),
  },
  {
    key: "lb_pressure_rate",
    header: "Press%",
    hoverLabel: "Pressure Rate — pressures per defensive snap (small weight in LB grading)",
    defaultDir: "desc",
    sortValue: (e) => e.lb_pressure_rate,
    render: (e) => fmtPct(e.lb_pressure_rate, 1),
  },
];

const K_COLUMNS: SortableColumn[] = [
  {
    key: "n_fg_att",
    header: "FG/XP Att",
    hoverLabel: "Total FG + XP attempts — sample size (kickers have no snap count)",
    defaultDir: "desc",
    sortValue: (e) => e.n_fg_att,
    render: (e) => fmtInt(e.n_fg_att),
  },
  {
    key: "k_fg_over_expected_per_att",
    header: "FGOE / att",
    hoverLabel: "Field Goal Over Expected per attempt. League baseline per distance bucket is subtracted from each attempt — 60-yard make worth +0.60, XP miss worth -0.94. Risk-asymmetric: making hard kicks rewarded, missing easy kicks heavily penalized. Sole formula component (v1.1).",
    defaultDir: "desc",
    sortValue: (e) => e.k_fg_over_expected_per_att,
    render: (e) => fmtSigned(e.k_fg_over_expected_per_att, 3),
    group: "formula",
  },
  {
    key: "k_fg_pct",
    header: "FG%",
    hoverLabel: "Overall field goal percentage (all distances). CONTEXT ONLY — not part of the K v1.1 formula.",
    defaultDir: "desc",
    sortValue: (e) => e.k_fg_pct,
    render: (e) => fmtPct(e.k_fg_pct, 1),
    group: "context",
  },
  {
    key: "k_fg_pct_40_plus",
    header: "FG% 40+",
    hoverLabel: "Field goal percentage on 40+ yard attempts. CONTEXT ONLY — not part of the K v1.1 formula.",
    defaultDir: "desc",
    sortValue: (e) => e.k_fg_pct_40_plus,
    render: (e) => fmtPct(e.k_fg_pct_40_plus, 1),
    group: "context",
  },
  {
    key: "k_pat_pct",
    header: "XP%",
    hoverLabel: "Extra-point conversion rate. CONTEXT ONLY — XPs are folded into FGOE / att in the formula.",
    defaultDir: "desc",
    sortValue: (e) => e.k_pat_pct,
    render: (e) => fmtPct(e.k_pat_pct, 1),
    group: "context",
  },
  {
    key: "k_fg_long",
    header: "FG long",
    hoverLabel: "Longest field goal made this season. CONTEXT ONLY — not part of the K v1.1 formula.",
    defaultDir: "desc",
    sortValue: (e) => e.k_fg_long,
    render: (e) => (e.k_fg_long == null ? "—" : e.k_fg_long.toFixed(0)),
    group: "context",
  },
];

const COLUMN_SPECS: Record<string, SortableColumn[]> = {
  QB:   QB_COLUMNS,
  RB:   RB_COLUMNS,
  WR:   WR_COLUMNS,
  TE:   TE_COLUMNS,
  CB:   CB_COLUMNS,
  S:    S_COLUMNS,
  EDGE: EDGE_COLUMNS,
  iDL:  IDL_COLUMNS,
  LB:   LB_COLUMNS,
  K:    K_COLUMNS,
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
  const isEven = rank % 2 === 0;
  const rowClass = e.qualified
    ? isEven
      ? "group border-t border-neutral-800/50 bg-[#111111] hover:bg-[#181818]"
      : "group border-t border-neutral-800/50 hover:bg-[#111111]"
    : isEven
      ? "group border-t border-neutral-800/50 bg-[#0e0e0e] text-neutral-500 hover:bg-[#151515]"
      : "group border-t border-neutral-800/50 text-neutral-500 hover:bg-[#0d0d0d]";
  const stickyBg = isEven
    ? "bg-[#111111] group-hover:bg-[#181818]"
    : "bg-neutral-950 group-hover:bg-[#111111]";
  const roleText =
    position === "TE" ? teRoleLabel(e.role) :
    position === "CB" ? cbRoleLabel(e.role) :
    null;
  return (
    <tr className={rowClass}>
      <Td className="text-center text-xs text-neutral-500">{rank}</Td>
      <Td className={`sticky left-0 z-20 border-r border-neutral-800 ${stickyBg}`}>
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
      <Td className="text-right font-mono">
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
  const sortIndicator = (
    <span
      aria-hidden
      className={`text-[10px] ${active ? "" : "opacity-0 group-hover:opacity-50"}`}
    >
      {arrow || "▾"}
    </span>
  );
  const labelNode = hover ? (
    <Tooltip content={hover}><span>{label}</span></Tooltip>
  ) : (
    <span>{label}</span>
  );
  return (
    <th className={`px-3 py-2 ${alignCls} ${className}`}>
      <button
        type="button"
        onClick={() => onSort(col)}
        className={`flex items-center gap-1 ${buttonAlignCls} ${
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
