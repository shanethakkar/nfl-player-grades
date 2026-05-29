import { gradeColor } from "@/lib/grades";
import type { SeasonGradeDetail } from "@/types";

type Props = {
  grades: SeasonGradeDetail[];
};

/**
 * Three-up summary at the top of the player page: how many seasons are
 * graded, the average composite across those seasons, and the
 * best/worst single season.
 *
 * Only qualified seasons count. Below-volume grades are stored for
 * reference but they're noisy and including them in the average would
 * mislead — a 12-target receiver who happened to catch a long TD is
 * not a top WR.
 *
 * Renders nothing when the player has zero qualified seasons (the
 * caller already shows a friendlier "no grades yet" message in that
 * case).
 */
export function CareerSummary({ grades }: Props) {
  const qualified = grades.filter((g) => g.qualified);
  if (qualified.length === 0) return null;

  const avg =
    qualified.reduce((acc, g) => acc + g.composite_grade, 0) / qualified.length;

  // grades come back ordered season DESC from the query, but we re-sort
  // here so the component is independent of upstream ordering.
  const byGrade = [...qualified].sort(
    (a, b) => b.composite_grade - a.composite_grade,
  );
  const best = byGrade[0];
  const worst = byGrade[byGrade.length - 1];
  const showWorst = qualified.length > 1; // only one season → best == worst, redundant

  return (
    <section className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
      <Stat
        label="Graded seasons"
        value={String(qualified.length)}
        sub={
          qualified.length === grades.length
            ? null
            : `${grades.length - qualified.length} below volume`
        }
      />
      <Stat
        label="Average grade"
        value={
          <span className={gradeColor(avg)}>{avg.toFixed(1)}</span>
        }
        sub={`across ${qualified.length} qualified ${
          qualified.length === 1 ? "season" : "seasons"
        }`}
      />
      <Stat
        label={showWorst ? "Best / worst season" : "Best season"}
        value={
          <span className="flex items-baseline gap-2">
            <span className={gradeColor(best.composite_grade)}>
              {best.composite_grade.toFixed(1)}
            </span>
            <span className="text-xs text-neutral-500">{best.season}</span>
            {showWorst && (
              <>
                <span className="text-neutral-700">/</span>
                <span className={gradeColor(worst.composite_grade)}>
                  {worst.composite_grade.toFixed(1)}
                </span>
                <span className="text-xs text-neutral-500">{worst.season}</span>
              </>
            )}
          </span>
        }
      />
    </section>
  );
}

function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string | null;
}) {
  return (
    // Hover brightens the border + bumps the bg slightly, matching the
    // PositionChip / PhaseChip treatment on /teams/[abbr]. Even though
    // these cards aren't clickable, the hover feedback makes the page
    // feel tactile and signals "you can read this card."
    <div className="rounded-lg border border-neutral-800 bg-neutral-950/60 px-4 py-3 transition-colors hover:border-neutral-700 hover:bg-neutral-900/60">
      <div className="text-[11px] uppercase tracking-wide text-neutral-500">
        {label}
      </div>
      <div className="mt-1 font-mono text-xl font-semibold">{value}</div>
      {sub && <div className="mt-1 text-xs text-neutral-500">{sub}</div>}
    </div>
  );
}
