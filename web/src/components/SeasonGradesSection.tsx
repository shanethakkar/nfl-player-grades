"use client";

import { useState } from "react";

import { ComponentBreakdownTable } from "@/components/ComponentBreakdownTable";
import { GradeBadge } from "@/components/GradeBadge";
import { TeamContextPanel } from "@/components/TeamContextPanel";
import { TeamLogo } from "@/components/TeamLogo";
import { Tooltip } from "@/components/Tooltip";
import {
  cbRoleLabel,
  componentDescription,
  componentLabel,
  componentWeight,
  DATA_TIER_LABELS,
  gradeHex,
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
  const roleText =
    g.position === "TE" ? teRoleLabel(g.role) :
    g.position === "CB" ? cbRoleLabel(g.role) :
    null;
  return (
    <section className="rounded-xl border border-neutral-800 bg-neutral-950/60 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">
              {g.season} {g.position}
            </h2>
            {g.team_abbr && (
              <span className="flex items-center gap-1 rounded border border-neutral-700 px-2 py-0.5 text-xs text-neutral-300">
                <TeamLogo abbr={g.team_abbr} size={14} />
                {g.team_abbr}
              </span>
            )}
            {roleText && (
              <span className="rounded border border-neutral-700 px-2 py-0.5 text-xs text-neutral-400">
                {roleText}
              </span>
            )}
            <span className="group/tier relative">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
                className="h-3.5 w-3.5 cursor-default text-neutral-600 hover:text-neutral-400"
              >
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-7-4a1 1 0 1 1-2 0 1 1 0 0 1 2 0ZM9 9a.75.75 0 0 0 0 1.5h.253a.25.25 0 0 1 .244.304l-.459 2.066A1.75 1.75 0 0 0 10.747 15H11a.75.75 0 0 0 0-1.5h-.253a.25.25 0 0 1-.244-.304l.459-2.066A1.75 1.75 0 0 0 9.253 9H9Z"
                  clipRule="evenodd"
                />
              </svg>
              <span className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 w-36 -translate-x-1/2 rounded-lg border border-neutral-700 bg-neutral-900 px-3 py-2 text-center text-xs text-neutral-300 opacity-0 shadow-lg transition-opacity duration-150 group-hover/tier:opacity-100">
                {DATA_TIER_LABELS[g.data_tier as DataTier]}
              </span>
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
        const color = displayPct !== null ? gradeHex(displayPct) : undefined;
        return (
          <div key={c.component_name} className="flex items-center gap-3">
            <div className="flex w-32 shrink-0 items-center justify-end">
              {(() => {
                const desc = componentDescription(c.component_name);
                return desc ? (
                  <Tooltip content={desc}>
                    <span className="cursor-help text-right text-[11px] text-neutral-500 decoration-dotted underline-offset-4 hover:underline">
                      {componentLabel(c.component_name)}
                    </span>
                  </Tooltip>
                ) : (
                  <span className="text-right text-[11px] text-neutral-500">
                    {componentLabel(c.component_name)}
                  </span>
                );
              })()}
            </div>
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
