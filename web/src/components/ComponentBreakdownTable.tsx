import {
  componentDescription,
  componentLabel,
  componentWeight,
  formatComponentValue,
  formatPercentile,
  formatSample,
  formatWeight,
  formatZ,
  zBand,
} from "@/lib/grades";
import type { StatComponentDetail } from "@/types";

type Props = {
  components: StatComponentDetail[];
  advanced: boolean;
  /**
   * Player's position. Currently informational only — kept on the prop so
   * future per-position layouts (e.g. grouping TE blocking-related fields)
   * can branch without an API change.
   */
  position?: string;
  /** Player's role for the season — used to select the correct weight set (e.g. blocking_te). */
  role?: string;
};

/**
 * Per-season component breakdown shown on the player page.
 *
 * Controlled by the `advanced` prop — the toggle lives one level up in
 * SeasonGradesSection so a single button switches all seasons at once.
 *
 * Two views:
 *   - **Friendly**: stat name (hover for definition), value, percentile,
 *     weight, sample size. No jargon or variable names.
 *   - **Advanced**: component variable name, raw value, shrunk
 *     (empirical-Bayes-adjusted), z-score, weight, sample size.
 *
 * Components excluded from the composite (blocking-TE earn rate, ADR-0016)
 * get a "tracked, not graded" tag and a muted row colour in both views.
 */
export function ComponentBreakdownTable({ components, advanced, role }: Props) {
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
        {advanced ? (
          <AdvancedView components={components} role={role} />
        ) : (
          <FriendlyView components={components} role={role} />
        )}
      </table>
    </div>
  );
}

function FriendlyView({
  components,
  role,
}: {
  components: StatComponentDetail[];
  role?: string;
}) {
  return (
    <>
      <thead className="bg-neutral-950 text-xs uppercase tracking-wide text-neutral-500">
        <tr>
          <th className="px-3 py-2 text-left">Stat</th>
          <th className="px-3 py-2 text-right">Value</th>
          <th className="px-3 py-2 text-right">Percentile</th>
          <th className="hidden px-3 py-2 text-right text-neutral-600 sm:table-cell">
            Weight
          </th>
          <th className="hidden px-3 py-2 text-right text-neutral-600 sm:table-cell">
            Sample
          </th>
        </tr>
      </thead>
      <tbody>
        {components.map((c) => {
          const tracked = c.used_in_composite === false;
          const description = componentDescription(c.component_name);
          const band = zBand(c.z_score);
          const toneCls =
            band.tone === "good"
              ? "text-emerald-400"
              : band.tone === "bad"
                ? "text-red-400"
                : "text-neutral-400";
          return (
            <tr
              key={c.component_name}
              className={
                tracked
                  ? "border-t border-neutral-900 bg-neutral-950/40 text-neutral-500"
                  : "border-t border-neutral-900"
              }
            >
              <td className="px-3 py-2 text-neutral-200">
                <span
                  className={
                    description
                      ? "cursor-help decoration-dotted underline-offset-4 hover:underline"
                      : ""
                  }
                  title={description ?? undefined}
                >
                  {componentLabel(c.component_name)}
                </span>
                {tracked && (
                  <span className="ml-2 rounded border border-neutral-700 px-1.5 py-0.5 text-[10px] uppercase text-neutral-500">
                    tracked, not graded
                  </span>
                )}
              </td>
              <td className="px-3 py-2 text-right font-mono text-neutral-100">
                {formatComponentValue(c.component_name, c.raw_value)}
              </td>
              <td className={`px-3 py-2 text-right font-mono ${toneCls}`}>
                {formatPercentile(c.z_score)}
              </td>
              <td className="hidden px-3 py-2 text-right font-mono text-neutral-500 sm:table-cell">
                {formatWeight(componentWeight(c.component_name, role))}
              </td>
              <td className="hidden px-3 py-2 text-right font-mono text-neutral-500 sm:table-cell">
                {formatSample(c.component_name, c.sample_size)}
              </td>
            </tr>
          );
        })}
      </tbody>
    </>
  );
}

function AdvancedView({
  components,
  role,
}: {
  components: StatComponentDetail[];
  role?: string;
}) {
  return (
    <>
      <thead className="bg-neutral-950 text-xs uppercase tracking-wide text-neutral-500">
        <tr>
          <th className="px-3 py-2 text-left">Component</th>
          <th className="px-3 py-2 text-right">Raw</th>
          <th className="px-3 py-2 text-right">Shrunk</th>
          <th className="px-3 py-2 text-right">Z</th>
          <th className="px-3 py-2 text-right">Weight</th>
          <th className="px-3 py-2 text-right">Sample</th>
        </tr>
      </thead>
      <tbody>
        {components.map((c) => {
          const tracked = c.used_in_composite === false;
          return (
            <tr
              key={c.component_name}
              className={
                tracked
                  ? "border-t border-neutral-900 bg-neutral-950/40 text-neutral-500"
                  : "border-t border-neutral-900"
              }
            >
              <td className="px-3 py-2 text-neutral-200">
                {componentLabel(c.component_name)}
                <span className="ml-2 text-[10px] uppercase text-neutral-600">
                  {c.component_name}
                </span>
                {tracked && (
                  <span className="ml-2 rounded border border-neutral-700 px-1.5 py-0.5 text-[10px] uppercase text-neutral-500">
                    tracked, not graded
                  </span>
                )}
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
              <td className="px-3 py-2 text-right font-mono text-neutral-500">
                {formatWeight(componentWeight(c.component_name, role))}
              </td>
              <td className="px-3 py-2 text-right font-mono text-neutral-400">
                {c.sample_size ?? "—"}
              </td>
            </tr>
          );
        })}
      </tbody>
    </>
  );
}
