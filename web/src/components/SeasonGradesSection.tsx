"use client";

import { useState } from "react";

import { ComponentBreakdownTable } from "@/components/ComponentBreakdownTable";
import { GradeBadge } from "@/components/GradeBadge";
import { TeamContextPanel } from "@/components/TeamContextPanel";
import {
  componentLabel,
  componentWeight,
  DATA_TIER_LABELS,
  teRoleLabel,
  zToPercentile,
} from "@/lib/grades";
import type { DataTier, SeasonGradeDetail, StatComponentDetail } from "@/types";

type Props = {
  grades: SeasonGradeDetail[];
};

export function SeasonGradesSection({ grades }: Props) {
  const [advanced, setAdvanced] = useState(false);

  return (
    <div className="mt-10">
      <div className="mb-4 flex justify-end">
        <button
          type="button"
          onClick={() => setAdvanced((v) => !v)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-neutral-700 px-3 py-1.5 text-xs text-neutral-400 transition-colors hover:border-neutral-500 hover:text-neutral-100"
        >
          {advanced ? "Hide advanced" : "Show advanced"}
        </button>
      </div>
      <div className="space-y-10">
        {grades.map((g) => (
          <SeasonGradeCard
            key={`${g.season}-${g.position}`}
            grade={g}
            advanced={advanced}
          />
        ))}
      </div>
    </div>
  );
}

function SeasonGradeCard({
  grade: g,
  advanced,
}: {
  grade: SeasonGradeDetail;
  advanced: boolean;
}) {
  const roleText = g.position === "TE" ? teRoleLabel(g.role) : null;
  return (
    <section className="rounded-xl border border-neutral-800 bg-neutral-950/60 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">
              {g.season} {g.position}
            </h2>
            {g.team_abbr && (
              <span className="rounded border border-neutral-700 px-2 py-0.5 text-xs text-neutral-300">
                {g.team_abbr}
              </span>
            )}
            {roleText && (
              <span className="rounded border border-neutral-700 px-2 py-0.5 text-xs text-neutral-400">
                {roleText}
              </span>
            )}
            <span className="text-[10px] uppercase tracking-wide text-neutral-500">
              {DATA_TIER_LABELS[g.data_tier as DataTier]}
            </span>
          </div>
          <p className="mt-1 text-xs text-neutral-500">
            {g.qualified
              ? `${g.percentile.toFixed(0)}th percentile among qualified ${g.position}s`
              : "Below volume threshold — grade shown for reference"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <GradeBadge
            grade={g.composite_grade}
            tier={g.data_tier as DataTier}
            qualified={g.qualified}
          />
          {g.qualified && (
            <div className="text-right text-xs text-neutral-500">
              <div className="font-mono text-neutral-300">
                z = {formatSignedZ(g.composite_z)}
              </div>
              {g.confidence !== null && (
                <div>confidence {Math.round(g.confidence * 100)}%</div>
              )}
            </div>
          )}
        </div>
      </div>

      {g.context && <TeamContextPanel context={g.context} />}

      <ComponentPercentileBars
        components={g.components}
        role={g.role ?? undefined}
      />

      <div className="mt-5">
        <ComponentBreakdownTable
          components={g.components}
          position={g.position}
          role={g.role ?? undefined}
          advanced={advanced}
        />
      </div>
    </section>
  );
}

function pctHex(pct: number): string {
  if (pct >= 90) return "#34d399";
  if (pct >= 80) return "#4ade80";
  if (pct >= 70) return "#a3e635";
  if (pct >= 55) return "#facc15";
  if (pct >= 40) return "#fb923c";
  return "#f87171";
}

function ComponentPercentileBars({
  components,
  role,
}: {
  components: StatComponentDetail[];
  role?: string;
}) {
  const rows = components
    .filter((c) => c.z_score !== null && Number.isFinite(c.z_score!))
    .map((c) => {
      const w = componentWeight(c.component_name, role);
      const isNegative = w !== null && w < 0;
      const pct = zToPercentile(c.z_score);
      const displayPct = pct === null ? null : isNegative ? 100 - pct : pct;
      return { c, displayPct };
    });

  if (rows.length === 0) return null;

  return (
    <div className="mt-4 space-y-2">
      {rows.map(({ c, displayPct }) => {
        const color = displayPct !== null ? pctHex(displayPct) : undefined;
        return (
          <div key={c.component_name} className="flex items-center gap-3">
            <span className="w-32 shrink-0 text-right text-[11px] text-neutral-500">
              {componentLabel(c.component_name)}
            </span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-neutral-800">
              {displayPct !== null && (
                <div
                  className="h-full rounded-full"
                  style={{ width: `${displayPct}%`, backgroundColor: color }}
                />
              )}
            </div>
            <span
              className="w-10 text-right font-mono text-[11px]"
              style={{ color: color ?? "#737373" }}
            >
              {displayPct !== null ? `${displayPct}th` : "—"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function formatSignedZ(z: number): string {
  const sign = z > 0 ? "+" : z < 0 ? "-" : "";
  return `${sign}${Math.abs(z).toFixed(2)}`;
}
