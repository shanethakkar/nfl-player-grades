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

export function CareerGradeChart({ grades }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [W, setW] = useState<number | null>(null);

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

  return (
    <div className="mt-6 rounded-xl border border-neutral-800 bg-neutral-950/60 p-4">
      <p className="mb-1 text-xs uppercase tracking-wide text-neutral-500">
        Career grade trend
      </p>
      {/* ref div measures the available SVG width after p-4 padding */}
      <div ref={containerRef}>
        {W !== null && (
          <svg
            viewBox={`0 0 ${W} ${H}`}
            width="100%"
            height={H}
            aria-label="Career grade trend sparkline"
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
              return (
                <g key={`${g.season}-${g.position}`}>
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
                  <circle cx={cx} cy={cy} r={4} fill={color} />
                  <text
                    x={cx}
                    y={H - 3}
                    textAnchor="middle"
                    fontSize={11}
                    fill="#525252"
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
