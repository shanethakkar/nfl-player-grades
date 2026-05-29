"use client";

import { useEffect, useRef, useState } from "react";

import { gradeHex } from "@/lib/grades";
import type { SeasonGradeDetail } from "@/types";

type Props = {
  grades: SeasonGradeDetail[];
};

const H = 90;
const PAD_X = 20;
const PAD_TOP = 24;
const PAD_BOT = 18;
// Invisible hover-target circles widen each point's hit zone so the
// cursor doesn't have to land on the 4px dot exactly.
const HIT_R = 16;

export function CareerGradeChart({ grades }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [W, setW] = useState<number | null>(null);
  const [hovered, setHovered] = useState<number | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const qualified = grades
    .filter((g) => g.qualified)
    .sort((a, b) => a.season - b.season);

  if (qualified.length < 2) return null;

  const chartW = W !== null ? W - PAD_X * 2 : 0;
  const chartH = H - PAD_TOP - PAD_BOT;
  const n = qualified.length;

  const xOf = (i: number) =>
    n === 1 ? PAD_X + chartW / 2 : PAD_X + (i / (n - 1)) * chartW;
  const yOf = (grade: number) => PAD_TOP + chartH * (1 - grade / 100);

  const points =
    W !== null
      ? qualified.map((g, i) => `${xOf(i)},${yOf(g.composite_grade)}`).join(" ")
      : "";

  const y50 = yOf(50);

  const hoveredGrade = hovered !== null ? qualified[hovered] : null;
  const hoveredX = hovered !== null ? xOf(hovered) : 0;
  const hoveredY =
    hoveredGrade !== null ? yOf(hoveredGrade.composite_grade) : 0;

  return (
    <div className="mt-6 rounded-xl border border-neutral-800 bg-neutral-950/60 p-4">
      <p className="mb-1 text-xs uppercase tracking-wide text-neutral-500">
        Career grade trend
      </p>
      <div ref={containerRef} className="relative">
        {W !== null && (
          <svg
            viewBox={`0 0 ${W} ${H}`}
            width="100%"
            height={H}
            aria-label="Career grade trend sparkline"
            onMouseLeave={() => setHovered(null)}
          >
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
              className="chart-line"
              points={points}
              fill="none"
              stroke="#404040"
              strokeWidth={1.5}
              strokeLinejoin="round"
            />
            {qualified.map((g, i) => {
              const cx = xOf(i);
              const cy = yOf(g.composite_grade);
              const color = gradeHex(g.composite_grade);
              const isActive = hovered === i;
              return (
                <g key={`${g.season}-${g.position}`} className="chart-point">
                  <text
                    x={cx}
                    y={cy - 8}
                    textAnchor="middle"
                    fontSize={12}
                    fill={color}
                    fontFamily="ui-monospace, monospace"
                    fontWeight="600"
                  >
                    {g.composite_grade.toFixed(0)}
                  </text>
                  {/* Active dot gets an outer ring + slight size bump
                      to give the hovered state visual weight. */}
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
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isActive ? 5 : 4}
                    fill={color}
                  />
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
                  {/* Transparent hover target widens the hit zone so
                      hover works even when the cursor is near but not
                      on the dot itself. */}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={HIT_R}
                    fill="transparent"
                    style={{ cursor: "default" }}
                    onMouseEnter={() => setHovered(i)}
                  />
                </g>
              );
            })}
          </svg>
        )}
        {/* Tooltip positioned in the chart's container coordinate
            space. We use absolute positioning so the SVG's viewBox
            scaling stays clean and the tooltip text stays crisp. The
            chart's container width is in CSS px, but the SVG viewBox
            is also in W px — so a viewBox x maps 1:1 to a CSS
            percentage of (cx / W). */}
        {hoveredGrade && W !== null && (
          <div
            className="pointer-events-none absolute z-10 -translate-x-1/2 animate-pop-in whitespace-nowrap rounded-lg border border-neutral-700 bg-neutral-900 px-2.5 py-1.5 text-[11px] leading-tight text-neutral-200 shadow-lg"
            style={{
              left: `${(hoveredX / W) * 100}%`,
              top: `${(hoveredY / H) * 100}%`,
              transform: `translate(-50%, calc(-100% - 14px))`,
            }}
          >
            <div className="font-semibold">
              {hoveredGrade.season} {hoveredGrade.position}
              {hoveredGrade.team_abbr ? (
                <span className="ml-1.5 font-normal text-neutral-400">
                  · {hoveredGrade.team_abbr}
                </span>
              ) : null}
            </div>
            <div className="text-neutral-400">
              {hoveredGrade.percentile.toFixed(0)}th percentile
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
