"use client";

import { useEffect, useRef, useState } from "react";

import { gradeHex } from "@/lib/grades";
import type { SeasonGradeDetail } from "@/types";

type Props = {
  grades: SeasonGradeDetail[];
};

// Chart dimensions tuned to feel like a hero element rather than a
// sparkline. Type sizes + dot radii are scaled to match — small fonts
// on a tall chart read as "data dashboard from 2014," not premium.
const H = 220;
const PAD_X = 28;
const PAD_TOP = 36;
const PAD_BOT = 32;
// Invisible hover-target circles widen each point's hit zone so the
// cursor doesn't have to land on the dot exactly.
const HIT_R = 22;

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
  // Px per data point. At narrow widths (mobile + 8-10 seasons), the
  // grade-number labels above the dots overlap each other. Below the
  // threshold we drop those labels — the colored dots still convey
  // tier visually and the hover/tap tooltip shows the exact number.
  // 28 ≈ width of a 2-digit grade at fontSize 18 + a few px of
  // breathing room.
  const slotWidth = n > 0 ? chartW / n : 0;
  const showGradeLabels = slotWidth >= 28;

  const xOf = (i: number) =>
    n === 1 ? PAD_X + chartW / 2 : PAD_X + (i / (n - 1)) * chartW;
  const yOf = (grade: number) => PAD_TOP + chartH * (1 - grade / 100);

  const points =
    W !== null
      ? qualified.map((g, i) => `${xOf(i)},${yOf(g.composite_grade)}`).join(" ")
      : "";
  // Area-fill polygon: same line, plus two anchor points along the
  // chart's bottom edge so the polygon closes into a filled region
  // below the line. Gives the chart real visual weight without
  // changing what it conveys.
  const areaPoints =
    W !== null && points
      ? `${PAD_X},${PAD_TOP + chartH} ${points} ${W - PAD_X},${PAD_TOP + chartH}`
      : "";

  // Grade-tier reference lines. 50/70/90 mirror the tiers documented
  // on the methodology page ("average", "above-average starter",
  // "MVP-caliber"). Without these the chart's points float on a
  // featureless plane; with them, "this player crossed into elite in
  // 2023" reads at a glance.
  const tierLines = [
    { grade: 90, y: yOf(90), label: "90" },
    { grade: 70, y: yOf(70), label: "70" },
    { grade: 50, y: yOf(50), label: "50" },
  ];

  const hoveredGrade = hovered !== null ? qualified[hovered] : null;
  const hoveredX = hovered !== null ? xOf(hovered) : 0;
  const hoveredY =
    hoveredGrade !== null ? yOf(hoveredGrade.composite_grade) : 0;

  return (
    <div className="mt-6 rounded-xl border border-neutral-800 bg-neutral-950/60 p-3 sm:p-5 md:p-6">
      <p className="mb-3 px-1 text-[11px] font-semibold uppercase tracking-[0.15em] text-neutral-500 sm:px-0">
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
            <defs>
              {/* Soft area fill below the line — fades from a low-
                  opacity neutral at the top of the chart to fully
                  transparent at the bottom. Gives the line visual
                  weight (it feels anchored to a region, not floating
                  on a plane) without color-coding the area, which
                  would compete with the per-point colored dots. */}
              <linearGradient id="career-chart-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#737373" stopOpacity="0.18" />
                <stop offset="100%" stopColor="#737373" stopOpacity="0" />
              </linearGradient>
            </defs>
            {tierLines.map((t) => (
              <g key={t.grade}>
                <line
                  x1={PAD_X}
                  y1={t.y}
                  x2={W - PAD_X}
                  y2={t.y}
                  stroke="#262626"
                  strokeWidth={1}
                  strokeDasharray="4 4"
                />
                <text
                  x={W - PAD_X + 6}
                  y={t.y + 4}
                  fontSize={11}
                  fill="#525252"
                  fontFamily="ui-monospace, monospace"
                  fontWeight="500"
                >
                  {t.label}
                </text>
              </g>
            ))}
            <polyline
              className="chart-point"
              points={areaPoints}
              fill="url(#career-chart-fill)"
              stroke="none"
            />
            <polyline
              className="chart-line"
              points={points}
              fill="none"
              stroke="#737373"
              strokeWidth={2.5}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            {qualified.map((g, i) => {
              const cx = xOf(i);
              const cy = yOf(g.composite_grade);
              const color = gradeHex(g.composite_grade);
              const isActive = hovered === i;
              return (
                <g key={`${g.season}-${g.position}`} className="chart-point">
                  {showGradeLabels && (
                    <text
                      x={cx}
                      y={cy - 14}
                      textAnchor="middle"
                      fontSize={18}
                      fill={color}
                      fontFamily="ui-monospace, monospace"
                      fontWeight="700"
                    >
                      {g.composite_grade.toFixed(0)}
                    </text>
                  )}
                  {/* Hovered point gets a larger outer ring and a
                      bigger dot so the active state has real
                      visual weight against the scaled-up baseline. */}
                  {isActive && (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={11}
                      fill="none"
                      stroke={color}
                      strokeWidth={1.75}
                      strokeOpacity={0.7}
                    />
                  )}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isActive ? 7 : 5.5}
                    fill={color}
                  />
                  <text
                    x={cx}
                    y={H - 8}
                    textAnchor="middle"
                    fontSize={13}
                    fill={isActive ? "#d4d4d4" : "#737373"}
                    fontWeight={isActive ? "600" : "500"}
                    fontFamily="ui-monospace, monospace"
                  >
                    {chartW / n < 56 ? `'${String(g.season).slice(2)}` : g.season}
                  </text>
                  {/* Transparent hover target widens the hit zone so
                      hover works even when the cursor is near but not
                      on the dot itself. The per-circle `onMouseLeave`
                      clears the hovered state when the cursor moves
                      off this dot into chart whitespace — the SVG's
                      own `onMouseLeave` only fires when leaving the
                      whole chart, so without this the tooltip would
                      stick after the cursor left the dot. The
                      `(h === i ? null : h)` guard makes sure leave
                      events from a stale index don't blow away a
                      hover that's already moved to a new dot. */}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={HIT_R}
                    fill="transparent"
                    style={{ cursor: "default" }}
                    onMouseEnter={() => setHovered(i)}
                    onMouseLeave={() =>
                      setHovered((h) => (h === i ? null : h))
                    }
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
