"use client";

import { useEffect, useRef, useState } from "react";

import { gradeHex } from "@/lib/grades";

import { MiniSparkline } from "./MiniSparkline";

type Point = { season: number; grade: number };

type Props = {
  points: Point[];
};

// Approximate height of the popover content (chart + padding + label).
// Used to decide if there's room to render above the trigger or below.
const POPOVER_HEIGHT = 130;
const POPOVER_WIDTH = 240;
const GAP = 8;

type Pos = {
  top: number;
  left: number;
  placeBelow: boolean;
};

/**
 * Hover/focus-triggered popover that wraps the inline MiniSparkline with a
 * larger labeled chart. Renders nothing if there's no trend data.
 *
 * The popover uses **fixed positioning** so it can escape the leaderboard's
 * `overflow-x:auto` container (which would otherwise clip the popover
 * vertically because the CSS spec coerces overflow-y to auto when overflow-x
 * isn't visible).
 *
 * Interaction notes:
 *  - 150ms open delay so quick mouse-overs don't flash the popover
 *  - Closes immediately on leave / blur / scroll / resize
 *  - Pointer-events: none on the popover so the mouse stays "on" the trigger
 *    (popover is purely informational)
 *  - Flips above ↔ below based on viewport space at open time
 */
export function SparklinePopover({ points }: Props) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<Pos>({ top: 0, left: 0, placeBelow: false });
  const wrapperRef = useRef<HTMLDivElement>(null);
  const openTimer = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (openTimer.current !== null) window.clearTimeout(openTimer.current);
    };
  }, []);

  // Close on scroll / resize so the popover doesn't get stranded at stale
  // viewport coordinates while the user navigates.
  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [open]);

  if (!points.length) return null;

  const computePos = (): Pos => {
    const el = wrapperRef.current;
    if (!el) return { top: 0, left: 0, placeBelow: false };
    const rect = el.getBoundingClientRect();
    const placeBelow = rect.top < POPOVER_HEIGHT + GAP + 4;
    return {
      top: placeBelow ? rect.bottom + GAP : rect.top - GAP,
      left: rect.left + rect.width / 2,
      placeBelow,
    };
  };

  const handleEnter = () => {
    if (openTimer.current !== null) window.clearTimeout(openTimer.current);
    openTimer.current = window.setTimeout(() => {
      setPos(computePos());
      setOpen(true);
    }, 150);
  };
  const handleLeave = () => {
    if (openTimer.current !== null) {
      window.clearTimeout(openTimer.current);
      openTimer.current = null;
    }
    setOpen(false);
  };

  return (
    <div
      ref={wrapperRef}
      className="relative inline-flex"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      onFocus={handleEnter}
      onBlur={handleLeave}
    >
      <button
        type="button"
        onClick={() => {
          setPos(computePos());
          setOpen((o) => !o);
        }}
        className="inline-flex cursor-default items-center border-0 bg-transparent p-0"
        tabIndex={0}
        aria-label="Show grade trend detail"
      >
        <MiniSparkline points={points} />
      </button>
      {open && (
        <div
          role="tooltip"
          className="pointer-events-none fixed z-50"
          style={{
            top: pos.top,
            left: pos.left,
            width: POPOVER_WIDTH,
            transform: pos.placeBelow
              ? "translateX(-50%)"
              : "translate(-50%, -100%)",
          }}
        >
          <div className="rounded-lg border border-neutral-700 bg-neutral-950/95 p-3 shadow-xl shadow-black/60 backdrop-blur">
            <SparklineDetail points={points} />
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SparklineDetail — the popover content
// Bigger SVG with year labels under each point and grade values above each
// point. Auto-scaled Y range (with padding) so the visualization uses the
// available height regardless of how clustered the values are.
// ---------------------------------------------------------------------------

function SparklineDetail({ points }: { points: Point[] }) {
  const W = 216;
  const H = 96;
  const PAD_X = 16;
  const PAD_TOP = 22;
  const PAD_BOT = 18;

  const innerW = W - PAD_X * 2;
  const innerH = H - PAD_TOP - PAD_BOT;

  const grades = points.map((p) => p.grade);
  const dataMax = Math.max(...grades);
  const dataMin = Math.min(...grades);
  // Clamp axis to [0, 100] but pad inside that for visual breathing room.
  const yMax = Math.min(100, dataMax + 5);
  const yMin = Math.max(0, dataMin - 5);
  const yRange = Math.max(1, yMax - yMin);

  const xOf = (i: number) =>
    points.length === 1
      ? PAD_X + innerW / 2
      : PAD_X + (i / (points.length - 1)) * innerW;
  const yOf = (g: number) => PAD_TOP + innerH * (1 - (g - yMin) / yRange);

  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${xOf(i)} ${yOf(p.grade)}`)
    .join(" ");

  return (
    <div>
      <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-neutral-500">
        Career grade
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        className="block"
        aria-hidden
      >
        {/* Trend line */}
        <path
          d={path}
          fill="none"
          stroke="#525252"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Per-point dots + labels */}
        {points.map((p, i) => {
          const x = xOf(i);
          const y = yOf(p.grade);
          const color = gradeHex(p.grade);
          return (
            <g key={p.season}>
              <circle cx={x} cy={y} r={2.5} fill={color} />
              <text
                x={x}
                y={y - 7}
                fill="#e5e5e5"
                fontSize="10"
                textAnchor="middle"
                fontFamily="ui-monospace, monospace"
                fontWeight="500"
              >
                {p.grade.toFixed(0)}
              </text>
              <text
                x={x}
                y={H - 4}
                fill="#737373"
                fontSize="9"
                textAnchor="middle"
                fontFamily="ui-monospace, monospace"
              >
                &apos;{String(p.season).slice(2)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
