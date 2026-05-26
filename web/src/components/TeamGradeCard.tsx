import Link from "next/link";

import { TeamCareerGradeChart } from "@/components/TeamCareerGradeChart";
import { gradeColor } from "@/lib/grades";
import type { TeamGradeComponent, TeamGradeSummary } from "@/types";

type Props = {
  summary: TeamGradeSummary;
  components: TeamGradeComponent[];
  /** Full overall_grade history (every graded season) for the trend chart. */
  history: { season: number; overall_grade: number }[];
  season: number;
};

const PHASE_LABEL: Record<TeamGradeComponent["phase"], string> = {
  offense: "Offense",
  defense: "Defense",
  st: "Special teams",
};

/**
 * Header card on /teams/[abbr] showing the team's Overall + Offense /
 * Defense / Special-teams grades for the active season, plus the
 * per-position breakdown that fed them.
 *
 * Layout:
 *  - Top row: big Overall on the left, three phase chips on the right
 *    (Overall is text-5xl on desktop and text-4xl on mobile, color-coded
 *    by the same grade scale as player grades).
 *  - Bottom: a grouped position breakdown — one row per phase, each row
 *    listing position chips sorted by weight (so the biggest formula
 *    contributors lead the eye).
 *
 * Methodology lives at /methodology — a small "see methodology" link
 * sits at the bottom of the card so the curious reader can verify the
 * weights without crowding the headline UI.
 */
export function TeamGradeCard({ summary, components, history, season }: Props) {
  // Group components by phase, preserving the SQL ordering
  // (weight desc within each phase).
  const byPhase: Record<TeamGradeComponent["phase"], TeamGradeComponent[]> = {
    offense: [],
    defense: [],
    st: [],
  };
  for (const c of components) byPhase[c.phase].push(c);

  return (
    <section className="rounded-xl border border-neutral-800 bg-neutral-950/70 p-6 sm:p-8">
      <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-neutral-500">
        Team grade · {season}
      </div>

      {/* Top row: big Overall + 3 phase chips */}
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <div
            className={`font-mono text-5xl font-bold leading-none tracking-tight sm:text-6xl ${gradeColor(summary.overall_grade)}`}
          >
            {summary.overall_grade.toFixed(1)}
          </div>
          <div className="mt-2 text-xs uppercase tracking-wider text-neutral-500">
            Overall
            {summary.overall_percentile != null && (
              <span className="ml-2 text-neutral-600">
                {summary.overall_percentile.toFixed(0)} pct
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-3 sm:gap-4">
          <PhaseChip
            label="Offense"
            grade={summary.offense_grade}
            percentile={summary.offense_percentile}
          />
          <PhaseChip
            label="Defense"
            grade={summary.defense_grade}
            percentile={summary.defense_percentile}
          />
          <PhaseChip
            label="S. Teams"
            grade={summary.st_grade}
            percentile={summary.st_percentile}
          />
        </div>
      </div>

      {/* Position breakdown */}
      <div className="mt-8 border-t border-neutral-800/70 pt-6">
        <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-neutral-500">
          Position breakdown
        </div>
        <div className="space-y-3">
          {(Object.keys(byPhase) as Array<keyof typeof byPhase>).map((phase) => {
            const rows = byPhase[phase];
            if (rows.length === 0) return null;
            return (
              <div
                key={phase}
                className="flex flex-wrap items-center gap-x-3 gap-y-2"
              >
                <span className="w-28 shrink-0 text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
                  {PHASE_LABEL[phase]}
                </span>
                {rows.map((r) => (
                  <PositionChip key={r.position} row={r} />
                ))}
              </div>
            );
          })}
        </div>
      </div>

      {/* Trend chart — full overall-grade history. Active season is
          highlighted so the reader can locate "this card's season" on
          the timeline. Renders nothing if the team has only one graded
          season (the chart needs ≥2 points to be informative). */}
      {history.length >= 2 && (
        <TeamCareerGradeChart history={history} activeSeason={season} />
      )}

      <div className="mt-6 text-xs text-neutral-500">
        Snap-weighted aggregate of the player grades on this team, by
        position, weighted into Offense / Defense / Special-teams (see{" "}
        <Link href="/methodology" className="underline hover:text-neutral-300">
          methodology
        </Link>
        ).
      </div>
    </section>
  );
}

function PhaseChip({
  label,
  grade,
  percentile,
}: {
  label: string;
  grade: number;
  percentile: number | null;
}) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-950 px-4 py-3 text-right sm:min-w-[120px]">
      <div
        className={`font-mono text-2xl font-bold leading-none tracking-tight sm:text-3xl ${gradeColor(grade)}`}
      >
        {grade.toFixed(1)}
      </div>
      <div className="mt-1.5 text-[10px] uppercase tracking-wider text-neutral-500">
        {label}
        {percentile != null && (
          <span className="ml-1.5 text-neutral-600">
            {percentile.toFixed(0)}
          </span>
        )}
      </div>
    </div>
  );
}

function PositionChip({ row }: { row: TeamGradeComponent }) {
  // Chip = a small pill with the position label + its team grade.
  // No weight on the chip itself (the weights are already locked in
  // methodology; the chip is for ranking strengths/weaknesses at a glance).
  return (
    <span className="inline-flex items-baseline gap-1.5 rounded-md border border-neutral-800/80 bg-neutral-900/50 px-2.5 py-1">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-neutral-400">
        {row.position}
      </span>
      <span
        className={`font-mono text-sm font-semibold leading-none ${gradeColor(row.position_grade)}`}
      >
        {row.position_grade.toFixed(0)}
      </span>
    </span>
  );
}
