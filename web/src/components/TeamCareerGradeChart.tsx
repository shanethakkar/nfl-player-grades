"use client";

import { useEffect, useRef, useState } from "react";

import { gradeHex } from "@/lib/grades";

type Props = {
  /** Team's overall_grade across seasons, ordered season asc. */
  history: { season: number; overall_grade: number }[];
  /** The season the team page is currently focused on — highlighted on the chart. */
  activeSeason: number;
};

const H = 110;
const PAD_X = 24;
const PAD_TOP = 26;
const PAD_BOT = 20;

/**
 * Team-grade history sparkline. Direct sibling of CareerGradeChart on
 * the player page — same layout, same styling, just sourced from
 * `team_grades.overall_grade` instead of `season_grades.composite_grade`.
 *
 * The currently-selected season (driven by the team page's `?season=`
 * query) is highlighted with a larger dot + outline so the reader sees
 * "here's this team's trajectory across years, and you're looking at
 * THIS year."
 */
export function TeamCareerGradeChart({ history, activeSeason }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [W, setW] = useState<number | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const sorted = [...history].sort((a, b) => a.season - b.season);
  if (sorted.length < 2) return null;

  const chartW = W !== null ? W - PAD_X * 2 : 0;
  const chartH = H - PAD_TOP - PAD_BOT;
  const n = sorted.length;

  const xOf = (i: number) =>
    n === 1 ? PAD_X + chartW / 2 : PAD_X + (i / (n - 1)) * chartW;
  const yOf = (grade: number) => PAD_TOP + chartH * (1 - grade / 100);

  const points =
    W !== null
      ? sorted.map((g, i) => `${xOf(i)},${yOf(g.overall_grade)}`).join(" ")
      : "";
  const y50 = yOf(50);

  return (
    <div className="mt-6 rounded-xl border border-neutral-800 bg-neutral-950/60 p-4">
      <p className="mb-1 text-xs uppercase tracking-wide text-neutral-500">
        Overall grade trend
      </p>
      <div ref={containerRef}>
        {W !== null && (
          <svg
            viewBox={`0 0 ${W} ${H}`}
            width="100%"
            height={H}
            aria-label="Team overall-grade trend"
          >
            {/* 50-line reference */}
            <line
              x1={PAD_X}
              y1={y50}
              x2={W - PAD_X}
              y2={y50}
              stroke="#262626"
              strokeWidth={1}
              strokeDasharray="4 3"
            />
            <polyline
              points={points}
              fill="none"
              stroke="#404040"
              strokeWidth={1.5}
              strokeLinejoin="round"
            />
            {sorted.map((g, i) => {
              const cx = xOf(i);
              const cy = yOf(g.overall_grade);
              const color = gradeHex(g.overall_grade);
              const isActive = g.season === activeSeason;
              return (
                <g key={g.season}>
                  <text
                    x={cx}
                    y={cy - 8}
                    textAnchor="middle"
                    fontSize={12}
                    fill={color}
                    fontFamily="ui-monospace, monospace"
                    fontWeight="600"
                  >
                    {g.overall_grade.toFixed(0)}
                  </text>
                  {/* Outline ring on the active-season dot so the reader
                      can see at a glance which row in the chart corresponds
                      to the team-grade card above. */}
                  {isActive && (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={7}
                      fill="none"
                      stroke={color}
                      strokeWidth={1.5}
                      strokeOpacity={0.55}
                    />
                  )}
                  <circle cx={cx} cy={cy} r={4} fill={color} />
                  <text
                    x={cx}
                    y={H - 3}
                    textAnchor="middle"
                    fontSize={11}
                    fill={isActive ? "#a3a3a3" : "#525252"}
                    fontWeight={isActive ? "600" : undefined}
                  >
                    {g.season}
                  </text>
                </g>
              );
            })}
          </svg>
        )}
      </div>
    </div>
  );
}
