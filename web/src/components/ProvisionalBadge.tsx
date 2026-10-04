import { provisionalLabel } from "@/lib/grades";

/**
 * Marks grades from a season still in progress. Rendered wherever a
 * Provisional season's grades appear so a 3-game sample is never read as
 * a full season.
 */
export function ProvisionalBadge({ throughWeek }: { throughWeek: number }) {
  return (
    <span className="inline-flex items-center rounded border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-300">
      {provisionalLabel(throughWeek)}
    </span>
  );
}
