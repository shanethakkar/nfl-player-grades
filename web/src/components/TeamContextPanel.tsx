import Link from "next/link";

import { gradeColor } from "@/lib/grades";
import type { TeamContext } from "@/types";

type Props = {
  context: TeamContext;
};

/**
 * Team / offense context for a non-QB season grade (ADR-0017 mitigation).
 *
 * Always shows:
 *   - Team offensive EPA/play and league rank
 *   - Lead QB (most dropbacks that season) and their season composite grade
 *
 * Conditionally shows the ADR-0017 inline note when
 *   (player_high_volume) AND (top QB grade is numeric and <= 45).
 *
 * The note does NOT adjust the grade. It tells the reader that v1 treats
 * per-target efficiency as skill, which systematically underrates
 * high-volume receivers whose targets are forced by the QB context
 * (Bowers 2024 / Njoku 2024 / etc.). See ADR-0017.
 *
 * The trigger is deliberately narrow: it fires only for high-volume
 * receivers on teams whose top QB graded notably poorly, not for every
 * bad-offense receiver — Brian Thomas Jr. (JAX 2024) and Jonnu Smith
 * (MIA 2024) show the grader already rewards efficiency within a weak
 * offensive environment.
 */
export function TeamContextPanel({ context: ctx }: Props) {
  const showNote =
    ctx.player_high_volume &&
    ctx.top_qb !== null &&
    ctx.top_qb.composite_grade !== null &&
    ctx.top_qb.composite_grade <= 45;

  return (
    <div className="mt-5 rounded-lg border border-neutral-800 bg-neutral-950/40 px-4 py-3 text-xs text-neutral-400">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <span>
          <span className="uppercase tracking-wide text-neutral-600">
            Team offense
          </span>{" "}
          <span className="font-mono text-neutral-300">
            {formatSignedEpa(ctx.team_epa_per_play)}
          </span>{" "}
          EPA/play · rank{" "}
          <span className="font-mono text-neutral-300">
            #{ctx.team_epa_rank}
          </span>{" "}
          of {ctx.team_epa_total}
        </span>
        {ctx.top_qb && (
          <span>
            <span className="uppercase tracking-wide text-neutral-600">
              Top QB
            </span>{" "}
            <Link
              href={{ pathname: `/players/${ctx.top_qb.player_id}` }}
              className="text-neutral-200 hover:underline"
            >
              {ctx.top_qb.full_name}
            </Link>
            {ctx.top_qb.composite_grade !== null && (
              <>
                {" · grade "}
                <span
                  className={`font-mono ${gradeColor(
                    ctx.top_qb.composite_grade,
                  )}`}
                >
                  {ctx.top_qb.composite_grade.toFixed(1)}
                </span>
              </>
            )}{" "}
            <span className="text-neutral-500">
              ({ctx.top_qb.dropbacks} dropbacks
              {ctx.top_qb.qualified === false ? ", non-qualified" : ""})
            </span>
          </span>
        )}
        {!ctx.top_qb && (
          <span className="text-neutral-500">
            No QB with recorded dropbacks for this team / season.
          </span>
        )}
      </div>
      {showNote && (
        <p className="mt-2 text-neutral-300">
          <span className="mr-1 text-amber-400">⚠</span>
          Grade may be suppressed by QB context — v1&apos;s per-target
          efficiency components don&apos;t adjust for the passer (see{" "}
          <Link
            href="/about/decisions#adr-0017"
            className="underline decoration-dotted hover:text-neutral-100"
          >
            ADR-0017
          </Link>
          ).
        </p>
      )}
    </div>
  );
}

function formatSignedEpa(v: number): string {
  const sign = v > 0 ? "+" : v < 0 ? "-" : "";
  return `${sign}${Math.abs(v).toFixed(3)}`;
}
