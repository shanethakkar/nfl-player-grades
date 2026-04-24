import {
  componentLabel,
  formatComponentValue,
  formatZ,
} from "@/lib/grades";
import type { StatComponentDetail } from "@/types";

type Props = {
  components: StatComponentDetail[];
};

/**
 * Shows each stat_components row for a season grade: raw value, the
 * empirical-Bayes-shrunk ("adjusted") value, z-score within position,
 * and sample size.
 *
 * Component names come from the pipeline (e.g. `qb_epa_per_dropback`)
 * and are translated via `componentLabel`.
 */
export function ComponentBreakdownTable({ components }: Props) {
  if (components.length === 0) {
    return (
      <p className="text-sm text-neutral-500">
        No components recorded for this season.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-neutral-800">
      <table className="min-w-full text-sm">
        <thead className="bg-neutral-950 text-xs uppercase tracking-wide text-neutral-500">
          <tr>
            <th className="px-3 py-2 text-left">Component</th>
            <th className="px-3 py-2 text-right">Raw</th>
            <th className="px-3 py-2 text-right">Shrunk</th>
            <th className="px-3 py-2 text-right">Z</th>
            <th className="px-3 py-2 text-right">Sample</th>
          </tr>
        </thead>
        <tbody>
          {components.map((c) => (
            <tr key={c.component_name} className="border-t border-neutral-900">
              <td className="px-3 py-2 text-neutral-200">
                {componentLabel(c.component_name)}
                <span className="ml-2 text-[10px] uppercase text-neutral-600">
                  {c.component_name}
                </span>
              </td>
              <td className="px-3 py-2 text-right font-mono text-neutral-200">
                {formatComponentValue(c.component_name, c.raw_value)}
              </td>
              <td className="px-3 py-2 text-right font-mono text-neutral-400">
                {formatComponentValue(c.component_name, c.adjusted_value)}
              </td>
              <td className="px-3 py-2 text-right font-mono text-neutral-300">
                {formatZ(c.z_score)}
              </td>
              <td className="px-3 py-2 text-right font-mono text-neutral-400">
                {c.sample_size ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
