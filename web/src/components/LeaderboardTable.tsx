import Link from "next/link";

import { gradeColor } from "@/lib/grades";
import type { LeaderboardEntry } from "@/types";

type Props = {
  entries: LeaderboardEntry[];
};

/**
 * Sortable-looking leaderboard table. (Sort is fixed by grade desc at
 * the server; a future client enhancement can swap the order.)
 *
 * Design choices:
 * - Entire row is clickable (wrapping <Link> inside each <td> would
 *   let us avoid JS, but makes the `<tr>` hover state messy). We make
 *   the name cell the link and use `group-hover` to highlight the row.
 * - EPA / CPOE / Success are shown as **raw** values — the shrunk and
 *   z-scored versions are visible on the player detail page.
 */
export function LeaderboardTable({ entries }: Props) {
  if (entries.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-neutral-500">
        No grades for this season yet.
      </p>
    );
  }

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
            <Th className="text-right">Drops</Th>
            <Th className="text-right">EPA/db</Th>
            <Th className="text-right">CPOE</Th>
            <Th className="text-right">Succ%</Th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e, idx) => (
            <Row key={e.player_id} entry={e} rank={idx + 1} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Row({ entry: e, rank }: { entry: LeaderboardEntry; rank: number }) {
  const rowClass = e.qualified
    ? "border-t border-neutral-900 hover:bg-neutral-900/60"
    : "border-t border-neutral-900 bg-neutral-950/60 text-neutral-500 hover:bg-neutral-900/60";
  return (
    <tr className={rowClass}>
      <Td className="text-center text-xs text-neutral-500">{e.qualified ? rank : ""}</Td>
      <Td>
        <Link
          href={{ pathname: `/players/${e.player_id}` }}
          className="font-medium text-neutral-100 hover:text-white hover:underline"
        >
          {e.full_name}
        </Link>
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
      <Td className="text-right font-mono text-neutral-400">
        {e.n_dropbacks ?? "—"}
      </Td>
      <Td className="text-right font-mono text-neutral-300">
        {formatSigned(e.epa_per_dropback, 3)}
      </Td>
      <Td className="text-right font-mono text-neutral-300">
        {formatSigned(e.cpoe, 2)}
      </Td>
      <Td className="text-right font-mono text-neutral-300">
        {e.success_rate === null ? "—" : (e.success_rate * 100).toFixed(1)}
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
  return <th className={`px-3 py-2 text-left ${className}`}>{children}</th>;
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

function formatSigned(v: number | null, digits: number): string {
  if (v === null || !Number.isFinite(v)) return "—";
  const sign = v > 0 ? "+" : v < 0 ? "-" : "";
  return `${sign}${Math.abs(v).toFixed(digits)}`;
}
