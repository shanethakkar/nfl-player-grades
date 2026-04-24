import Link from "next/link";

import { gradeColor, teRoleLabel } from "@/lib/grades";
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

/**
 * Sortable-looking leaderboard table. (Sort is fixed by grade desc at
 * the server; a future client enhancement can swap the order.)
 *
 * Design choices:
 * - Entire row is clickable via the name cell (wrapping <Link> inside
 *   every <td> would work but makes the `<tr>` hover state messy).
 * - Component columns are shown as **raw** values. The shrunk,
 *   z-scored, and sample-size breakdown lives on the player detail page.
 * - The column spec is data-driven (see COLUMN_SPECS below) so adding
 *   a new position later is one array entry, not a new conditional
 *   branch through JSX.
 */
export function LeaderboardTable({ entries, position }: Props) {
  if (entries.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-neutral-500">
        No grades for this season yet.
      </p>
    );
  }

  const columns = COLUMN_SPECS[position] ?? [];

  return (
    <div className="overflow-x-auto rounded-lg border border-neutral-800">
      <table className="min-w-full text-sm">
        <thead className="bg-neutral-950 text-xs uppercase tracking-wide text-neutral-500">
          <tr>
            <Th className="w-10 text-center">#</Th>
            <Th>Player</Th>
            <Th className="text-center">Team</Th>
            <Th className="text-right">Grade</Th>
            <Th className="text-right">Pct</Th>
            {columns.map((c) => (
              <Th key={c.key} className="text-right" title={c.hoverLabel}>
                {c.header}
              </Th>
            ))}
          </tr>
        </thead>
        <tbody>
          {entries.map((e, idx) => (
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
// Column specs — one per position. Each spec is a thin renderer that pulls
// its value off the LeaderboardEntry and formats it. Labels are short
// because the leaderboard is dense; `hoverLabel` gives the fuller name on
// cell hover (via native `title`).
// ---------------------------------------------------------------------------

type ColumnSpec = {
  key: string;
  header: string;
  hoverLabel: string;
  render: (e: LeaderboardEntry) => string;
};

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

const QB_COLUMNS: ColumnSpec[] = [
  {
    key: "n_dropbacks",
    header: "Drops",
    hoverLabel: "Qualifying dropbacks",
    render: (e) => fmtInt(e.n_dropbacks),
  },
  {
    key: "epa_per_dropback",
    header: "EPA/db",
    hoverLabel: "EPA per dropback",
    render: (e) => fmtSigned(e.epa_per_dropback, 3),
  },
  {
    key: "cpoe",
    header: "CPOE",
    hoverLabel: "Completion % over expected",
    render: (e) => fmtSigned(e.cpoe, 2),
  },
  {
    key: "success_rate",
    header: "Succ%",
    hoverLabel: "Dropback success rate",
    render: (e) => fmtPct(e.success_rate, 1),
  },
];

const RB_COLUMNS: ColumnSpec[] = [
  {
    key: "n_touches",
    header: "Touches",
    hoverLabel: "Carries + receptions after filters",
    render: (e) => fmtInt(e.n_touches),
  },
  {
    key: "ryoe",
    header: "RYOE/att",
    hoverLabel: "Rush yards over expected per attempt (NGS)",
    render: (e) => fmtSigned(e.rb_ryoe_per_attempt, 2),
  },
  {
    key: "rush_epa",
    header: "EPA/att",
    hoverLabel: "Rush EPA per attempt",
    render: (e) => fmtSigned(e.rb_rush_epa_per_attempt, 3),
  },
  {
    key: "rush_succ",
    header: "Rush Succ%",
    hoverLabel: "Rushing success rate",
    render: (e) => fmtPct(e.rb_rush_success_rate, 1),
  },
];

const WR_COLUMNS: ColumnSpec[] = [
  {
    key: "n_targets",
    header: "Tgts",
    hoverLabel: "Qualifying targets",
    render: (e) => fmtInt(e.n_targets),
  },
  {
    key: "rec_epa",
    header: "EPA/tgt",
    hoverLabel: "Receiving EPA per target",
    render: (e) => fmtSigned(e.rec_epa_per_target, 3),
  },
  {
    key: "yac_oe",
    header: "YAC/rec",
    hoverLabel: "YAC over expected per reception",
    render: (e) => fmtSigned(e.yac_over_expected_per_rec, 2),
  },
  {
    key: "earn",
    header: "Earn%",
    hoverLabel: "Target earn rate (targets / team pass attempts while active)",
    render: (e) => fmtPct(e.target_earn_rate, 1),
  },
];

// TEs share WR's columns. Role is shown inline next to the name, not as
// its own column, to keep table density under control.
const TE_COLUMNS: ColumnSpec[] = WR_COLUMNS;

const COLUMN_SPECS: Record<string, ColumnSpec[]> = {
  QB: QB_COLUMNS,
  RB: RB_COLUMNS,
  WR: WR_COLUMNS,
  TE: TE_COLUMNS,
};

function Row({
  entry: e,
  rank,
  columns,
  position,
}: {
  entry: LeaderboardEntry;
  rank: number;
  columns: ColumnSpec[];
  position: string;
}) {
  const rowClass = e.qualified
    ? "border-t border-neutral-900 hover:bg-neutral-900/60"
    : "border-t border-neutral-900 bg-neutral-950/60 text-neutral-500 hover:bg-neutral-900/60";
  const roleText = position === "TE" ? teRoleLabel(e.role) : null;
  return (
    <tr className={rowClass}>
      <Td className="text-center text-xs text-neutral-500">
        {e.qualified ? rank : ""}
      </Td>
      <Td>
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
      <Td className="text-center text-neutral-400">{e.team_abbr ?? "—"}</Td>
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
          {c.render(e)}
        </Td>
      ))}
    </tr>
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
