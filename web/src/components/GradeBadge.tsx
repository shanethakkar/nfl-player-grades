import { formatGrade, gradeColor } from "@/lib/grades";
import type { DataTier } from "@/types";

type Props = {
  grade: number;
  tier?: DataTier;
  qualified?: boolean;
};

export function GradeBadge({ grade, tier, qualified = true }: Props) {
  // Unqualified grades are still computed on the same 0-100 scale, just
  // noisier due to small sample. The accompanying section copy says
  // "grade shown for reference" — so show it (muted) rather than hiding.
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border border-neutral-700 px-2 py-0.5 font-mono text-sm ${
        qualified ? "" : "opacity-70"
      }`}
    >
      <span className={gradeColor(grade)}>{formatGrade(grade)}</span>
      {tier && tier > 1 && (
        <span className="text-[10px] uppercase opacity-60">tier {tier}</span>
      )}
    </span>
  );
}
