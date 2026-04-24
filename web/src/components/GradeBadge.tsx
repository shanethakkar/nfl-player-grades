import { formatGrade, gradeColor } from "@/lib/grades";
import type { DataTier } from "@/types";

type Props = {
  grade: number;
  tier?: DataTier;
  qualified?: boolean;
};

export function GradeBadge({ grade, tier, qualified = true }: Props) {
  if (!qualified) {
    return (
      <span className="inline-flex items-center rounded border border-neutral-700 px-2 py-0.5 text-xs opacity-60">
        insufficient sample
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded border border-neutral-700 px-2 py-0.5 font-mono text-sm">
      <span className={gradeColor(grade)}>{formatGrade(grade)}</span>
      {tier && tier > 1 && (
        <span className="text-[10px] uppercase opacity-60">tier {tier}</span>
      )}
    </span>
  );
}
