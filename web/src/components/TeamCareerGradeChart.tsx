"use client";

import { useEffect, useRef, useState } from "react";

import { gradeHex } from "@/lib/grades";

type Props = {
  /** Team's overall_grade across seasons, ordered season asc. */
  history: { season: number; overall_grade: number }[];
  /** The season the team page is currently focused on — highlighted on the chart. */
  activeSeason: number;
};

// Chart dimensions tuned to feel like a hero element rather than a
// sparkline. Mirrors the player profile's CareerGradeChart so the two
// surfaces read as a coordinated visual system.
const H = 220;
const PAD_X = 28;
const PAD_TOP = 36;
const PAD_BOT = 32;
// Invisible hover-target circles widen each point's hit zone so the
// cursor doesn't have to land on the dot exactly.
const HIT_R = 22;

/**
 * Team-grade history chart. Sibling of the player profile's
 * CareerGradeChart — same dimensions, same area-fill + tier-reference
 * treatment — sourced from `team_grades.overall_grade` instead of
 * `season_grades.composite_grade`.
 *
 * Two interaction layers stack:
 *   - The currently-selected season (driven by `?season=`) always
 *     wears an outline ring so readers can see "you're looking at
 *     this year on the timeline."
 *   - Hovering any dot reveals a popover with season + grade and
 *     gives the dot the same hover treatment as the player chart.
 */
export function TeamCareerGradeChart({ history, activeSeason }: Props) {
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

  const sorted = [...history].sort((a, b) => a.season - b.season);
  if (sorted.length < 2) return null;

  const chartW = W !== null ? W - PAD_X * 2 : 0;
  const chartH = H - PAD_TOP - PAD_BOT;
  const n = sorted.length;
  // Px per data point. Below the threshold we drop the floating grade
  // labels above the dots — they overlap at narrow widths. The colored
  // dots still convey tier, the hover tooltip shows the exact number.
  const slotWidth = n > 0 ? chartW / n : 0;
  const showGradeLabels = slotWidth >= 28;

  const xOf = (i: number) =>
    n === 1 ? PAD_X + chartW / 2 : PAD_X + (i / (n - 1)) * chartW;
  const yOf = (grade: number) => PAD_TOP + chartH * (1 - grade / 100);

  const points =
    W !== null
      ? sorted.map((g, i) => `${xOf(i)},${yOf(g.overall_grade)}`).join(" ")
      : "";
  // Area-fill polygon: same line, plus two anchor points along the
  // chart's bottom edge so the polygon closes into a filled region
  // below the line. Gives the chart real visual weight.
  const areaPoints =
    W !== null && points
      ? `${PAD_X},${PAD_TOP + chartH} ${points} ${W - PAD_X},${PAD_TOP + chartH}`
      : "";

  // Grade-tier reference lines — 50/70/90 mirror the methodology page
  // tier boundaries. Without them the chart's points float on a
  // featureless plane; with them, "this team crossed into elite (90+)
  // in 2023" reads at a glance.
  const tierLines = [
    { grade: 90, y: yOf(90), label: "90" },
    { grade: 70, y: yOf(70), label: "70" },
    { grade: 50, y: yOf(50), label: "50" },
  ];

  const hoveredGrade = hovered !== null ? sorted[hovered] : null;
  const hoveredX = hovered !== null ? xOf(hovered) : 0;
  const hoveredY =
    hoveredGrade !== null ? yOf(hoveredGrade.overall_grade) : 0;

  return (
    <div className="mt-6 rounded-xl border border-neutral-800 bg-neutral-950/60 p-3 sm:p-5 md:p-6">
      <p className="mb-3 px-1 text-[11px] font-semibold uppercase tracking-[0.15em] text-neutral-500 sm:px-0">
        Overall grade trend
      </p>
      <div ref={containerRef} className="relative">
        {W !== null && (
          <svg
            viewBox={`0 0 ${W} ${H}`}
            width="100%"
            height={H}
            aria-label="Team overall-grade trend"
            onMouseLeave={() => setHovered(null)}
          >
            <defs>
              {/* Soft area fill below the line — fades from a low-
                  opacity neutral at the top to fully transparent at
                  the bottom. Anchors the line to a region instead of
                  letting it float on an empty plane. */}
              <linearGradient id="team-career-chart-fill" x1="0" y1="0" x2="0" y2="1">
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
              fill="url(#team-career-chart-fill)"
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
            {sorted.map((g, i) => {
              const cx = xOf(i);
              const cy = yOf(g.overall_grade);
              const color = gradeHex(g.overall_grade);
              const isActive = g.season === activeSeason;
              const isHovered = hovered === i;
              const emphasized = isActive || isHovered;
              return (
                <g key={g.season} className="chart-point">
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
                      {g.overall_grade.toFixed(0)}
                    </text>
                  )}
                  {/* Outline ring on the active-season dot (so the
                      reader can locate "this year" on the timeline at
                      a glance) and on the hovered dot (for the
                      inspect-other-years interaction). */}
                  {emphasized && (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={11}
                      fill="none"
                      stroke={color}
                      strokeWidth={1.75}
                      strokeOpacity={isHovered ? 0.7 : 0.55}
                    />
                  )}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={emphasized ? 7 : 5.5}
                    fill={color}
                  />
                  <text
                    x={cx}
                    y={H - 8}
                    textAnchor="middle"
                    fontSize={13}
                    fill={emphasized ? "#d4d4d4" : "#737373"}
                    fontWeight={emphasized ? "600" : "500"}
                    fontFamily="ui-monospace, monospace"
                  >
                    {chartW / n < 56 ? `'${String(g.season).slice(2)}` : g.season}
                  </text>
                  {/* Transparent hover target widens the hit zone.
                      Per-circle `onMouseLeave` clears the hovered
                      state when the cursor moves into chart whitespace
                      (the SVG's own `onMouseLeave` only fires when
                      leaving the whole chart). */}
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
        {/* Tooltip — same coord-space convention as the player
            CareerGradeChart so the two surfaces feel consistent. */}
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
              {hoveredGrade.season} overall
            </div>
            <div className="text-neutral-400">
              {hoveredGrade.overall_grade.toFixed(1)} grade
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
