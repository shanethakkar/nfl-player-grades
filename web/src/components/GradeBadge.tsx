import { formatGrade, gradeColor } from "@/lib/grades";
import type { DataTier } from "@/types";

type Props = {
  grade: number;
  tier?: DataTier;
  qualified?: boolean;
};

/**
 * Pill displaying a player-season composite grade with the color
 * palette used elsewhere.
 *
 * Elite grades (≥ 90) get a subtle emerald ring + glow so the badge
 * visually rewards a top-tier season — the brain spots them at a glance
 * when skimming season-by-season cards on a player page. Below-90 grades
 * stay flat to avoid noise; below-volume (unqualified) grades fade to
 * 70% so they read as "reference only" without being hidden.
 */
export function GradeBadge({ grade, tier, qualified = true }: Props) {
  const elite = qualified && grade >= 90;
  return (
    <span
      className={
        "inline-flex items-center gap-1 rounded border px-2 py-0.5 font-mono text-sm transition-shadow " +
        (qualified ? "" : "opacity-70 ") +
        (elite
          ? "border-emerald-500/40 shadow-[0_0_0_1px_rgba(16,185,129,0.25),0_0_18px_-4px_rgba(16,185,129,0.4)]"
          : "border-neutral-700")
      }
    >
      <span className={gradeColor(grade)}>{formatGrade(grade)}</span>
      {tier && tier > 1 && (
        <span className="text-[10px] uppercase opacity-60">tier {tier}</span>
      )}
    </span>
  );
}
