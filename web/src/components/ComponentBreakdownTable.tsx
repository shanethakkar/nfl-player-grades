"use client";

import { useState } from "react";

import {
  componentDescription,
  componentLabel,
  formatComponentValue,
  formatSample,
  formatZ,
  zBand,
} from "@/lib/grades";
import type { StatComponentDetail } from "@/types";

type Props = {
  components: StatComponentDetail[];
  /**
   * Player's position. Currently informational only — kept on the prop so
   * future per-position layouts (e.g. grouping TE blocking-related fields)
   * can branch without an API change.
   */
  position?: string;
};

/**
 * Per-season component breakdown shown on the player page.
 *
 * Two views, toggle on the right:
 *   - **Friendly** (default): the stat name with a hover description, the
 *     headline value (raw, in the metric's natural units), and a plain
 *     "above/below average" label coloured green/red. No jargon, no
 *     variable names, no z-scores.
 *   - **Advanced**: the original four-column dump — Raw, Shrunk
 *     (empirical-Bayes-adjusted), Z, Sample — with the underlying
 *     variable name (e.g. `qb_cpoe`) shown beside the label so analysts
 *     and developers can map back to the pipeline.
 *
 * Components stored for audit but excluded from the composite (currently
 * only `te_target_earn_rate` for blocking TEs, see ADR-0016) get a small
 * "tracked, not graded" tag and a muted row colour in both views.
 */
export function ComponentBreakdownTable({ components }: Props) {
  const [advanced, setAdvanced] = useState(false);

  if (components.length === 0) {
    return (
      <p className="text-sm text-neutral-500">
        No components recorded for this season.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={() => setAdvanced((v) => !v)}
          className="text-xs text-neutral-500 underline-offset-2 hover:text-neutral-300 hover:underline"
        >
          {advanced ? "Hide advanced" : "Show advanced"}
        </button>
      </div>
      <div className="overflow-x-auto rounded-lg border border-neutral-800">
        <table className="min-w-full text-sm">
          {advanced ? (
            <AdvancedView components={components} />
          ) : (
            <FriendlyView components={components} />
          )}
        </table>
      </div>
      {!advanced && (
        <p className="text-[11px] text-neutral-600">
          Hover a stat name for a quick definition. {" "}
          <button
            type="button"
            className="underline-offset-2 hover:text-neutral-400 hover:underline"
            onClick={() => setAdvanced(true)}
          >
            Show advanced
          </button>{" "}
          for raw, shrunk, and z-score columns.
        </p>
      )}
    </div>
  );
}

function FriendlyView({ components }: { components: StatComponentDetail[] }) {
  return (
    <>
      <thead className="bg-neutral-950 text-xs uppercase tracking-wide text-neutral-500">
        <tr>
          <th className="px-3 py-2 text-left">Stat</th>
          <th className="px-3 py-2 text-right">Value</th>
          <th className="px-3 py-2 text-left">vs. position average</th>
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
                    description ? "decoration-dotted underline-offset-4 hover:underline cursor-help" : ""
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
              <td className={`px-3 py-2 ${toneCls}`}>{band.label}</td>
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

function AdvancedView({ components }: { components: StatComponentDetail[] }) {
  return (
    <>
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
              <td className="px-3 py-2 text-right font-mono text-neutral-400">
                {c.sample_size ?? "\u2014"}
              </td>
            </tr>
          );
        })}
      </tbody>
    </>
  );
}
